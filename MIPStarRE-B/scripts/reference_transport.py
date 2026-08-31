#!/usr/bin/env python3
"""Acquire checksum-pinned references with bounded, auditable transports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA_VERSION = 1
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 64 * 1024 * 1024
REST_MAX_BYTES = 1024 * 1024
PROCESS_TERMINATION_GRACE_SECONDS = 1.0
OUTPUT_EVIDENCE_LIMIT = 4096
SUBPROCESS_OUTPUT_LIMIT = 64 * 1024
PROCESS_POLL_SECONDS = 0.01
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
REVISION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


class ReferenceTransportError(RuntimeError):
    """A reference acquisition failure with machine-readable evidence."""

    def __init__(self, message: str, evidence: Mapping[str, Any]):
        super().__init__(message)
        self.evidence = dict(evidence)


@dataclass(frozen=True)
class DirectDownloadPin:
    """An exact HTTPS object pin."""

    identifier: str
    url: str
    sha256: str
    max_bytes: int
    allowed_hosts: tuple[str, ...] = ()

    def validate(self) -> None:
        _validate_identifier(self.identifier)
        _validate_sha256(self.sha256)
        _validate_max_bytes(self.max_bytes)
        hosts = self.allowed_hosts or (_validated_https_url(self.url)[0],)
        _validate_allowed_hosts(hosts)
        _validated_https_url(self.url, hosts)


@dataclass(frozen=True)
class GitHubArchivePin:
    """A GitHub repository archive pinned to one full commit and checksum."""

    identifier: str
    repository: str
    revision: str
    expected_commit: str
    sha256: str
    max_bytes: int

    def validate(self) -> None:
        _validate_identifier(self.identifier)
        _parse_repository(self.repository)
        _validate_revision(self.revision)
        if not GIT_COMMIT_RE.fullmatch(self.expected_commit):
            raise ValueError("expected_commit must be a lowercase 40-character Git commit")
        _validate_sha256(self.sha256)
        _validate_max_bytes(self.max_bytes)


@dataclass(frozen=True)
class CommandOutcome:
    """Bounded subprocess result, including process-group cleanup evidence."""

    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool = False
    termination_signal: str | None = None
    termination_escalated: bool = False
    termination_cleanup_complete: bool = True
    output_limit_exceeded: bool = False
    stdout_byte_count: int | None = None
    stdout_digest: str | None = None
    stderr_byte_count: int | None = None
    stderr_digest: str | None = None

    def evidence(self, method: str) -> dict[str, Any]:
        stdout_bytes = self.stdout.encode("utf-8", errors="replace")
        stderr_bytes = self.stderr.encode("utf-8", errors="replace")
        return {
            "method": method,
            "status": (
                "output_limited"
                if self.output_limit_exceeded
                else "timed_out"
                if self.timed_out
                else ("ok" if self.returncode == 0 else "failed")
            ),
            "argv": list(self.argv),
            "returncode": self.returncode,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "timed_out": self.timed_out,
            "termination_signal": self.termination_signal,
            "termination_escalated": self.termination_escalated,
            "termination_cleanup_complete": self.termination_cleanup_complete,
            "output_limit_exceeded": self.output_limit_exceeded,
            "output_limit_bytes": SUBPROCESS_OUTPUT_LIMIT,
            "stdout_bytes": (
                self.stdout_byte_count if self.stdout_byte_count is not None else len(stdout_bytes)
            ),
            "stdout_sha256": self.stdout_digest or hashlib.sha256(stdout_bytes).hexdigest(),
            "stderr_bytes": (
                self.stderr_byte_count if self.stderr_byte_count is not None else len(stderr_bytes)
            ),
            "stderr_sha256": self.stderr_digest or hashlib.sha256(stderr_bytes).hexdigest(),
        }


ProcessRunner = Callable[[Sequence[str], float], CommandOutcome]
Downloader = Callable[[str, Path, float, int, tuple[str, ...]], dict[str, Any]]
JsonFetcher = Callable[[str, float], tuple[Mapping[str, Any], dict[str, Any]]]


def _validate_identifier(value: str) -> None:
    if not IDENTIFIER_RE.fullmatch(value):
        raise ValueError("identifier contains unsupported characters")


def _validate_sha256(value: str) -> None:
    if not SHA256_RE.fullmatch(value):
        raise ValueError("sha256 must be a lowercase 64-character digest")


def _validate_max_bytes(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("max_bytes must be a positive integer")


def _validated_timeout(value: float | int) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("timeout_seconds must be a positive finite number")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be a positive finite number")
    return timeout


def _validate_allowed_hosts(hosts: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for host in hosts:
        candidate = host.lower()
        if not candidate or candidate != host or any(character in host for character in "/:@\\"):
            raise ValueError("allowed hosts must be lowercase DNS names")
        normalized.append(candidate)
    if not normalized:
        raise ValueError("at least one allowed host is required")
    return tuple(dict.fromkeys(normalized))


def _validated_https_url(url: str, allowed_hosts: Sequence[str] | None = None) -> tuple[str, str]:
    if not isinstance(url, str) or not url or "\\" in url or any(ord(c) < 32 for c in url):
        raise ValueError("URL is not a valid HTTPS URL")
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("URL has an invalid port") from error
    if parsed.scheme != "https" or not parsed.hostname or port not in (None, 443):
        raise ValueError("URL must use HTTPS on the default port")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credential-bearing URLs are forbidden")
    if "?" in url or "#" in url:
        raise ValueError("URL queries and fragments are forbidden")
    host = parsed.hostname.lower()
    if parsed.netloc.lower() not in (host, f"{host}:443"):
        raise ValueError("URL authority is not canonical")
    if allowed_hosts is not None and host not in _validate_allowed_hosts(allowed_hosts):
        raise ValueError("URL host is outside the explicit allowlist")
    return host, parsed.path


def _parse_repository(repository: str) -> tuple[str, str]:
    if not isinstance(repository, str) or repository.count("/") != 1:
        raise ValueError("repository must be an explicit owner/name slug")
    owner, name = repository.split("/", 1)
    if not IDENTIFIER_RE.fullmatch(owner) or not IDENTIFIER_RE.fullmatch(name):
        raise ValueError("repository must be an explicit owner/name slug")
    if owner in (".", "..") or name in (".", ".."):
        raise ValueError("repository contains a traversal component")
    return owner, name.removesuffix(".git")


def _validate_revision(revision: str) -> None:
    if (
        not isinstance(revision, str)
        or not REVISION_RE.fullmatch(revision)
        or revision.endswith("/")
        or ".." in revision
        or "//" in revision
        or "@{" in revision
    ):
        raise ValueError("revision contains unsupported characters")


class _BoundedCapture:
    def __init__(self, limit: int, exceeded: threading.Event):
        self.limit = limit
        self.exceeded = exceeded
        self.total = 0
        self.digest = hashlib.sha256()
        self.retained = bytearray()

    def add(self, chunk: bytes) -> None:
        self.total += len(chunk)
        self.digest.update(chunk)
        remaining = self.limit - len(self.retained)
        if remaining > 0:
            self.retained.extend(chunk[:remaining])
        if self.total > self.limit:
            self.exceeded.set()


def _drain_stream(stream: Any, capture: _BoundedCapture, done: threading.Event) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            capture.add(chunk)
    except (OSError, TypeError, ValueError):
        return
    finally:
        done.set()


def _signal_process_group(process: subprocess.Popen[bytes], signal_number: int) -> None:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal_number)
        except ProcessLookupError:
            pass
    elif signal_number == signal.SIGTERM:
        process.terminate()
    else:
        process.kill()


def _terminate_process_group(
    process: subprocess.Popen[bytes],
    stream_done: Sequence[threading.Event],
) -> tuple[bool, bool]:
    def await_cleanup() -> bool:
        deadline = time.monotonic() + PROCESS_TERMINATION_GRACE_SECONDS
        while time.monotonic() < deadline:
            if process.poll() is not None and all(done.is_set() for done in stream_done):
                return True
            time.sleep(PROCESS_POLL_SECONDS)
        return process.poll() is not None and all(done.is_set() for done in stream_done)

    _signal_process_group(process, signal.SIGTERM)
    escalated = False
    cleanup_complete = await_cleanup()
    if not cleanup_complete:
        escalated = True
        _signal_process_group(process, signal.SIGKILL)
        cleanup_complete = await_cleanup()
    if not cleanup_complete:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
    return escalated, cleanup_complete


def run_bounded_argv(
    argv: Sequence[str],
    timeout_seconds: float | int,
    *,
    cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> CommandOutcome:
    """Run an argv without a shell and terminate its complete process group on timeout."""

    timeout = _validated_timeout(timeout_seconds)
    command = tuple(argv)
    if not command or any(not isinstance(item, str) or not item or "\0" in item for item in command):
        raise ValueError("argv must contain nonempty strings")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
            env=environment,
        )
    except OSError as error:
        return CommandOutcome(
            command,
            None,
            "",
            str(error),
            time.monotonic() - started,
            termination_cleanup_complete=True,
        )
    exceeded = threading.Event()
    stdout_capture = _BoundedCapture(SUBPROCESS_OUTPUT_LIMIT, exceeded)
    stderr_capture = _BoundedCapture(SUBPROCESS_OUTPUT_LIMIT, exceeded)
    stdout_done = threading.Event()
    stderr_done = threading.Event()
    assert process.stdout is not None and process.stderr is not None
    threads = (
        threading.Thread(
            target=_drain_stream,
            args=(process.stdout, stdout_capture, stdout_done),
            name="reference-stdout-reader",
            daemon=True,
        ),
        threading.Thread(
            target=_drain_stream,
            args=(process.stderr, stderr_capture, stderr_done),
            name="reference-stderr-reader",
            daemon=True,
        ),
    )
    for thread in threads:
        thread.start()
    timed_out = False
    output_limited = False
    escalated = False
    cleanup_complete = True
    termination_attempted = False
    try:
        deadline = started + timeout
        while True:
            if exceeded.is_set():
                output_limited = True
                if process.poll() is None or not (stdout_done.is_set() and stderr_done.is_set()):
                    termination_attempted = True
                    escalated, cleanup_complete = _terminate_process_group(
                        process, (stdout_done, stderr_done)
                    )
                break
            if process.poll() is not None and stdout_done.is_set() and stderr_done.is_set():
                break
            if time.monotonic() >= deadline:
                timed_out = True
                termination_attempted = True
                escalated, cleanup_complete = _terminate_process_group(
                    process, (stdout_done, stderr_done)
                )
                break
            time.sleep(PROCESS_POLL_SECONDS)
    except KeyboardInterrupt:
        try:
            _terminate_process_group(process, (stdout_done, stderr_done))
        except KeyboardInterrupt:
            _signal_process_group(process, signal.SIGKILL)
            try:
                process.wait(timeout=PROCESS_TERMINATION_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                pass
        raise
    finally:
        for thread in threads:
            thread.join(PROCESS_TERMINATION_GRACE_SECONDS)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except (OSError, ValueError):
                    pass
    stdout_bytes = bytes(stdout_capture.retained)
    stderr_bytes = bytes(stderr_capture.retained)
    return CommandOutcome(
        command,
        process.returncode,
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
        time.monotonic() - started,
        timed_out=timed_out,
        termination_signal="SIGTERM" if termination_attempted else None,
        termination_escalated=escalated,
        termination_cleanup_complete=cleanup_complete,
        output_limit_exceeded=output_limited,
        stdout_byte_count=stdout_capture.total,
        stdout_digest=stdout_capture.digest.hexdigest(),
        stderr_byte_count=stderr_capture.total,
        stderr_digest=stderr_capture.digest.hexdigest(),
    )


class _AllowlistedRedirectHandler(HTTPRedirectHandler):
    max_redirections = 3

    def __init__(self, allowed_hosts: Sequence[str]):
        self.allowed_hosts = _validate_allowed_hosts(allowed_hosts)
        self.redirects: list[str] = []
        super().__init__()

    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> Request | None:
        _validated_https_url(new_url, self.allowed_hosts)
        self.redirects.append(new_url)
        return super().redirect_request(request, file_pointer, code, message, headers, new_url)


def _http_download_worker(
    url: str,
    output: Path,
    max_bytes: int,
    timeout_seconds: float,
    allowed_hosts: Sequence[str],
    expected_identity: tuple[int, int] | None = None,
) -> dict[str, Any]:
    hosts = _validate_allowed_hosts(allowed_hosts)
    _validated_https_url(url, hosts)
    _validate_max_bytes(max_bytes)
    timeout = _validated_timeout(timeout_seconds)
    redirect_handler = _AllowlistedRedirectHandler(hosts)
    opener = build_opener(redirect_handler)
    request = Request(url, headers={"User-Agent": "MIPStarRE-reference-transport/1"}, method="GET")
    started = time.monotonic()
    byte_count = 0
    with opener.open(request, timeout=timeout) as response:
        status_code = response.getcode()
        if status_code != 200:
            raise OSError(f"HTTP response status was {status_code}, expected 200")
        _validated_https_url(response.geturl(), hosts)
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                declared_bytes = int(content_length)
            except ValueError as error:
                raise OSError("HTTP Content-Length is invalid") from error
            if declared_bytes < 0 or declared_bytes > max_bytes:
                raise OSError("HTTP Content-Length exceeds max_bytes")
        flags = os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if expected_identity is None:
            flags |= os.O_CREAT | os.O_EXCL
        descriptor = os.open(output, flags, 0o600)
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or expected_identity is not None
            and (opened.st_dev, opened.st_ino) != expected_identity
        ):
            os.close(descriptor)
            raise OSError("temporary file identity or link count changed before download")
        os.ftruncate(descriptor, 0)
        with os.fdopen(descriptor, "wb") as stream:
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes - byte_count + 1))
                if not chunk:
                    break
                byte_count += len(chunk)
                if byte_count > max_bytes:
                    raise OSError("HTTP response exceeds max_bytes")
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
            completed = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(completed.st_mode)
                or completed.st_nlink != 1
                or expected_identity is not None
                and (completed.st_dev, completed.st_ino) != expected_identity
            ):
                raise OSError("temporary file identity or link count changed during download")
    return {
        "method": "https",
        "status": "ok",
        "http_status": 200,
        "bytes": byte_count,
        "redirects": redirect_handler.redirects,
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "timed_out": False,
    }


def _download_via_worker(
    url: str,
    output: Path,
    timeout_seconds: float,
    max_bytes: int,
    allowed_hosts: tuple[str, ...],
    *,
    expected_identity: tuple[int, int] | None = None,
) -> dict[str, Any]:
    _validated_https_url(url, allowed_hosts)
    timeout = _validated_timeout(timeout_seconds)
    argv = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_download-worker",
        "--url",
        url,
        "--output",
        str(output),
        "--timeout-seconds",
        str(timeout),
        "--max-bytes",
        str(max_bytes),
    ]
    for host in allowed_hosts:
        argv.extend(("--allowed-host", host))
    if expected_identity is not None:
        argv.extend(("--expected-device", str(expected_identity[0])))
        argv.extend(("--expected-inode", str(expected_identity[1])))
    outcome = run_bounded_argv(argv, timeout)
    evidence = outcome.evidence("https")
    if outcome.output_limit_exceeded or outcome.timed_out or outcome.returncode != 0:
        if outcome.output_limit_exceeded:
            error_class = "OutputLimitExceeded"
            error_message = "HTTPS worker diagnostics exceeded the subprocess output bound"
        elif outcome.timed_out:
            error_class = "ProcessTimeout"
            error_message = "bounded HTTPS worker timed out"
        else:
            error_class = "WorkerFailure"
            error_message = "HTTPS worker failed"
        if not outcome.output_limit_exceeded and not outcome.timed_out:
            try:
                failure_document = json.loads(outcome.stdout)
            except json.JSONDecodeError:
                failure_document = None
            if isinstance(failure_document, dict) and isinstance(failure_document.get("error"), dict):
                worker_error = failure_document["error"]
                if isinstance(worker_error.get("class"), str):
                    error_class = worker_error["class"][:128]
                if isinstance(worker_error.get("message"), str):
                    error_message = worker_error["message"][:OUTPUT_EVIDENCE_LIMIT]
        evidence["error"] = {"class": error_class, "message": error_message}
        raise ReferenceTransportError("bounded HTTPS download failed", evidence)
    try:
        worker_evidence = json.loads(outcome.stdout)
    except json.JSONDecodeError as error:
        raise ReferenceTransportError("HTTPS worker returned malformed evidence", evidence) from error
    if not isinstance(worker_evidence, dict) or worker_evidence.get("status") != "ok":
        raise ReferenceTransportError("HTTPS worker did not report success", evidence)
    evidence.update(
        {
            "http_status": worker_evidence.get("http_status"),
            "bytes": worker_evidence.get("bytes"),
            "redirects": worker_evidence.get("redirects", []),
            "worker_elapsed_seconds": worker_evidence.get("elapsed_seconds"),
        }
    )
    return evidence


def _sha256_descriptor(descriptor: int, max_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    offset = 0
    while chunk := os.pread(descriptor, 1024 * 1024, offset):
        byte_count += len(chunk)
        if byte_count > max_bytes:
            raise OSError("downloaded file exceeds max_bytes")
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest(), byte_count


def _sha256_file(path: Path, max_bytes: int) -> tuple[str, int]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        return _sha256_descriptor(descriptor, max_bytes)
    finally:
        os.close(descriptor)


def _base_evidence(
    pin: DirectDownloadPin | GitHubArchivePin,
    destination: Path,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_id": pin.identifier,
        "kind": "github_archive" if isinstance(pin, GitHubArchivePin) else "direct_https",
        "status": "running",
        "destination": str(destination),
        "expected_sha256": pin.sha256,
        "max_bytes": pin.max_bytes,
        "attempts": [],
        "published": False,
    }
    if isinstance(pin, GitHubArchivePin):
        evidence.update(
            {
                "repository": pin.repository,
                "revision": pin.revision,
                "expected_commit": pin.expected_commit,
            }
        )
    else:
        evidence["url"] = pin.url
    return evidence


def _fail(evidence: dict[str, Any], message: str, error_class: str) -> ReferenceTransportError:
    evidence.update(
        {
            "status": "failed",
            "error": {"class": error_class, "message": message},
        }
    )
    return ReferenceTransportError(message, evidence)


def _validate_destination_path(destination: Path) -> None:
    if ".." in destination.parts or destination.name in ("", ".", ".."):
        raise ValueError("destination must not contain traversal components")
    absolute = destination.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:-1]:
        current /= component
        if not current.exists() and not current.is_symlink():
            continue
        metadata = current.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("destination parent must contain only real directories")


def _fsync_descriptor(descriptor: int) -> None:
    os.fsync(descriptor)


def _require_bound_temporary(
    descriptor: int,
    temporary: Path,
    expected_identity: tuple[int, int],
) -> None:
    opened = os.fstat(descriptor)
    named = temporary.stat(follow_symlinks=False)
    if (
        not stat.S_ISREG(opened.st_mode)
        or not stat.S_ISREG(named.st_mode)
        or opened.st_nlink != 1
        or named.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != expected_identity
        or (named.st_dev, named.st_ino) != expected_identity
    ):
        raise OSError("temporary file identity or single-link invariant changed")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _existing_destination(evidence: dict[str, Any], destination: Path, pin: Any) -> dict[str, Any] | None:
    if not destination.exists() and not destination.is_symlink():
        return None
    if destination.is_symlink() or not destination.is_file():
        raise _fail(evidence, "destination exists but is not a regular file", "UnsafeDestination")
    try:
        actual_sha256, byte_count = _sha256_file(destination, pin.max_bytes)
    except OSError as error:
        raise _fail(
            evidence,
            str(error),
            "ExistingDestinationReadFailure",
        ) from error
    if actual_sha256 != pin.sha256:
        evidence.update({"actual_sha256": actual_sha256, "bytes": byte_count})
        raise _fail(evidence, "existing destination checksum does not match pin", "ExistingChecksumMismatch")
    evidence.update(
        {
            "status": "cached",
            "actual_sha256": actual_sha256,
            "bytes": byte_count,
            "published": True,
        }
    )
    return evidence


def _download_verify_publish(
    *,
    url: str,
    allowed_hosts: tuple[str, ...],
    pin: DirectDownloadPin | GitHubArchivePin,
    destination: Path,
    timeout_seconds: float,
    evidence: dict[str, Any],
    downloader: Downloader,
) -> dict[str, Any]:
    try:
        _validate_destination_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _validate_destination_path(destination)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".partial", dir=destination.parent
        )
    except (OSError, ValueError) as error:
        raise _fail(evidence, str(error), "UnsafeDestination") from error
    temporary = Path(temporary_name)
    temporary_metadata = os.fstat(descriptor)
    temporary_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
    try:
        try:
            _require_bound_temporary(descriptor, temporary, temporary_identity)
        except OSError as error:
            raise _fail(evidence, str(error), "UnsafeTemporary") from error
        try:
            if downloader is _download_via_worker:
                attempt = _download_via_worker(
                    url,
                    temporary,
                    timeout_seconds,
                    pin.max_bytes,
                    allowed_hosts,
                    expected_identity=temporary_identity,
                )
            else:
                attempt = downloader(url, temporary, timeout_seconds, pin.max_bytes, allowed_hosts)
            evidence["attempts"].append(attempt)
        except ReferenceTransportError as error:
            evidence["attempts"].append(error.evidence)
            raise _fail(evidence, str(error), "DownloadFailure") from error
        except (OSError, ValueError) as error:
            raise _fail(evidence, str(error), "DownloadFailure") from error
        try:
            _require_bound_temporary(descriptor, temporary, temporary_identity)
            actual_sha256, byte_count = _sha256_descriptor(descriptor, pin.max_bytes)
            _require_bound_temporary(descriptor, temporary, temporary_identity)
        except OSError as error:
            error_class = (
                "ByteLimitExceeded" if "exceeds max_bytes" in str(error) else "UnsafeTemporary"
            )
            raise _fail(evidence, str(error), error_class) from error
        evidence.update({"actual_sha256": actual_sha256, "bytes": byte_count})
        if actual_sha256 != pin.sha256:
            raise _fail(evidence, "download checksum does not match pin", "ChecksumMismatch")
        try:
            _require_bound_temporary(descriptor, temporary, temporary_identity)
        except OSError as error:
            raise _fail(evidence, str(error), "UnsafeTemporary") from error
        try:
            _fsync_descriptor(descriptor)
        except OSError as error:
            raise _fail(evidence, str(error), "FileSyncFailure") from error
        try:
            _require_bound_temporary(descriptor, temporary, temporary_identity)
        except OSError as error:
            raise _fail(evidence, str(error), "UnsafeTemporary") from error
        try:
            os.replace(temporary, destination)
        except OSError as error:
            raise _fail(evidence, str(error), "AtomicReplaceFailure") from error
        try:
            _require_bound_temporary(descriptor, destination, temporary_identity)
        except OSError as error:
            try:
                destination.unlink(missing_ok=True)
                _fsync_directory(destination.parent)
            except OSError as cleanup_error:
                evidence["publication_cleanup_error"] = type(cleanup_error).__name__
            raise _fail(evidence, str(error), "UnsafeTemporary") from error
        evidence.update({"status": "published", "published": True})
        try:
            _fsync_directory(destination.parent)
        except OSError as error:
            evidence["durability_uncertain"] = True
            raise _fail(evidence, str(error), "DirectorySyncFailure") from error
        return evidence
    finally:
        os.close(descriptor)
        temporary.unlink(missing_ok=True)


def _parse_ls_remote(stdout: str) -> str:
    commits: set[str] = set()
    for line in stdout.splitlines():
        fields = line.split("\t", 1)
        if len(fields) != 2 or not GIT_COMMIT_RE.fullmatch(fields[0]):
            raise ValueError("git ls-remote returned malformed successful output")
        commits.add(fields[0])
    if len(commits) != 1:
        raise ValueError("git ls-remote did not resolve exactly one commit")
    return commits.pop()


def _isolated_git_environment() -> dict[str, str]:
    """Retain network routing while excluding Git config and credential injection."""

    inherited_names = (
        "PATH",
        "LANG",
        "LC_ALL",
        "HTTPS_PROXY",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    )
    environment = {name: os.environ[name] for name in inherited_names if name in os.environ}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _run_isolated_git(argv: Sequence[str], timeout_seconds: float) -> CommandOutcome:
    isolated_cwd = Path(tempfile.gettempdir())
    environment = _isolated_git_environment()
    environment["GIT_CEILING_DIRECTORIES"] = str(isolated_cwd)
    return run_bounded_argv(
        argv,
        timeout_seconds,
        cwd=isolated_cwd,
        environment=environment,
    )


def _default_json_fetcher(url: str, timeout_seconds: float) -> tuple[Mapping[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="reference-rest-") as temporary_directory:
        output = Path(temporary_directory) / "response.json"
        attempt = _download_via_worker(
            url, output, timeout_seconds, REST_MAX_BYTES, ("api.github.com",)
        )
        try:
            document = json.loads(output.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReferenceTransportError("GitHub REST returned malformed JSON", attempt) from error
    if not isinstance(document, dict):
        raise ReferenceTransportError("GitHub REST response is not an object", attempt)
    return document, attempt


def _resolve_github_commit(
    pin: GitHubArchivePin,
    git_timeout_seconds: float,
    rest_timeout_seconds: float,
    evidence: dict[str, Any],
    runner: ProcessRunner,
    json_fetcher: JsonFetcher,
) -> str:
    owner, name = _parse_repository(pin.repository)
    git_url = f"https://github.com/{owner}/{name}.git"
    git_outcome = runner(
        [
            "git",
            "-c",
            "credential.helper=",
            "-c",
            "core.askPass=",
            "-c",
            "http.extraHeader=",
            "ls-remote",
            "--exit-code",
            "--refs",
            git_url,
            pin.revision,
        ],
        git_timeout_seconds,
    )
    git_evidence = git_outcome.evidence("git_ls_remote")
    git_evidence["environment_policy"] = "isolated_noninteractive_git"
    evidence["attempts"].append(git_evidence)
    if git_outcome.output_limit_exceeded:
        raise _fail(
            evidence,
            "git diagnostics exceeded the subprocess output bound",
            "OutputLimitExceeded",
        )
    if git_outcome.timed_out and not git_outcome.termination_cleanup_complete:
        raise _fail(
            evidence,
            "git process-group cleanup did not complete; refusing fallback",
            "IncompleteProcessCleanup",
        )
    if not git_outcome.timed_out and git_outcome.returncode == 0:
        try:
            resolved = _parse_ls_remote(git_outcome.stdout)
        except ValueError as error:
            raise _fail(evidence, str(error), "MalformedGitResolution") from error
        if resolved != pin.expected_commit:
            evidence["resolved_commit"] = resolved
            raise _fail(evidence, "git resolution does not match expected commit", "CommitMismatch")
        git_evidence["resolved_commit"] = resolved
        return resolved

    rest_url = (
        f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}/commits/"
        f"{quote(pin.revision, safe='')}"
    )
    try:
        document, rest_evidence = json_fetcher(rest_url, rest_timeout_seconds)
        rest_evidence = dict(rest_evidence)
        rest_evidence["method"] = "github_rest"
        evidence["attempts"].append(rest_evidence)
    except ReferenceTransportError as error:
        rest_evidence = dict(error.evidence)
        rest_evidence["method"] = "github_rest"
        evidence["attempts"].append(rest_evidence)
        raise _fail(evidence, str(error), "GitHubRestFailure") from error
    resolved = document.get("sha")
    if not isinstance(resolved, str) or not GIT_COMMIT_RE.fullmatch(resolved):
        raise _fail(evidence, "GitHub REST returned an invalid commit", "MalformedRestResolution")
    rest_evidence["resolved_commit"] = resolved
    if resolved != pin.expected_commit:
        evidence["resolved_commit"] = resolved
        raise _fail(evidence, "GitHub REST resolution does not match expected commit", "CommitMismatch")
    return resolved


def acquire(
    pin: DirectDownloadPin | GitHubArchivePin,
    destination: Path,
    *,
    timeout_seconds: float | int = DEFAULT_TIMEOUT_SECONDS,
    git_timeout_seconds: float | int | None = None,
    _runner: ProcessRunner | None = None,
    _downloader: Downloader | None = None,
    _json_fetcher: JsonFetcher | None = None,
) -> dict[str, Any]:
    """Acquire one pin, verifying bytes before a same-directory atomic publication."""

    pin.validate()
    timeout = _validated_timeout(timeout_seconds)
    git_timeout = timeout if git_timeout_seconds is None else _validated_timeout(git_timeout_seconds)
    destination = Path(destination)
    evidence = _base_evidence(pin, destination)
    evidence["timeout_seconds"] = timeout
    if isinstance(pin, GitHubArchivePin):
        evidence["git_timeout_seconds"] = git_timeout
    try:
        _validate_destination_path(destination)
    except (OSError, ValueError) as error:
        raise _fail(evidence, str(error), "UnsafeDestination") from error
    cached = _existing_destination(evidence, destination, pin)
    if cached is not None:
        return cached
    downloader = _downloader or _download_via_worker
    if isinstance(pin, DirectDownloadPin):
        hosts = pin.allowed_hosts or (_validated_https_url(pin.url)[0],)
        return _download_verify_publish(
            url=pin.url,
            allowed_hosts=hosts,
            pin=pin,
            destination=destination,
            timeout_seconds=timeout,
            evidence=evidence,
            downloader=downloader,
        )

    resolved_commit = _resolve_github_commit(
        pin,
        git_timeout,
        timeout,
        evidence,
        _runner or _run_isolated_git,
        _json_fetcher or _default_json_fetcher,
    )
    evidence["resolved_commit"] = resolved_commit
    owner, name = _parse_repository(pin.repository)
    codeload_url = (
        f"https://codeload.github.com/{quote(owner, safe='')}/{quote(name, safe='')}/tar.gz/"
        f"{resolved_commit}"
    )
    return _download_verify_publish(
        url=codeload_url,
        allowed_hosts=("codeload.github.com",),
        pin=pin,
        destination=destination,
        timeout_seconds=timeout,
        evidence=evidence,
        downloader=downloader,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    direct = commands.add_parser("direct", help="acquire one checksum-pinned HTTPS object")
    direct.add_argument("--id", required=True)
    direct.add_argument("--url", required=True)
    direct.add_argument("--sha256", required=True)
    direct.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    direct.add_argument("--allowed-host", action="append", default=[])
    direct.add_argument("--output", type=Path, required=True)
    direct.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    github = commands.add_parser("github", help="acquire one pinned GitHub codeload archive")
    github.add_argument("--id", required=True)
    github.add_argument("--repository", required=True)
    github.add_argument("--revision", required=True)
    github.add_argument("--commit", required=True)
    github.add_argument("--sha256", required=True)
    github.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    github.add_argument("--output", type=Path, required=True)
    github.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    github.add_argument("--git-timeout-seconds", type=float, default=20.0)

    worker = commands.add_parser("_download-worker", help=argparse.SUPPRESS)
    worker.add_argument("--url", required=True)
    worker.add_argument("--output", type=Path, required=True)
    worker.add_argument("--timeout-seconds", type=float, required=True)
    worker.add_argument("--max-bytes", type=int, required=True)
    worker.add_argument("--allowed-host", action="append", required=True)
    worker.add_argument("--expected-device", type=int)
    worker.add_argument("--expected-inode", type=int)
    return parser


def run_cli(arguments: argparse.Namespace) -> dict[str, Any]:
    if arguments.command == "_download-worker":
        identity = None
        if arguments.expected_device is not None or arguments.expected_inode is not None:
            if arguments.expected_device is None or arguments.expected_inode is None:
                raise ValueError("both expected temporary-file identity fields are required")
            identity = (arguments.expected_device, arguments.expected_inode)
        return _http_download_worker(
            arguments.url,
            arguments.output,
            arguments.max_bytes,
            arguments.timeout_seconds,
            tuple(arguments.allowed_host),
            identity,
        )
    if arguments.command == "direct":
        pin: DirectDownloadPin | GitHubArchivePin = DirectDownloadPin(
            arguments.id,
            arguments.url,
            arguments.sha256,
            arguments.max_bytes,
            tuple(arguments.allowed_host),
        )
    else:
        pin = GitHubArchivePin(
            arguments.id,
            arguments.repository,
            arguments.revision,
            arguments.commit,
            arguments.sha256,
            arguments.max_bytes,
        )
    return acquire(
        pin,
        arguments.output,
        timeout_seconds=arguments.timeout_seconds,
        git_timeout_seconds=(
            arguments.git_timeout_seconds if arguments.command == "github" else None
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run_cli(build_parser().parse_args(argv))
    except ReferenceTransportError as error:
        print(json.dumps(error.evidence, indent=2, ensure_ascii=True))
        return 1
    except (HTTPError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "failed",
                    "error": {"class": type(error).__name__, "message": str(error)},
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
