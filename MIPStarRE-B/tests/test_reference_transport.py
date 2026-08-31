from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import _thread
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import reference_transport as transport  # noqa: E402


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def outcome(
    returncode: int | None,
    *,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
) -> transport.CommandOutcome:
    return transport.CommandOutcome(
        ("git", "ls-remote"),
        returncode,
        stdout,
        stderr,
        0.01,
        timed_out=timed_out,
        termination_signal="SIGTERM" if timed_out else None,
        termination_cleanup_complete=True,
    )


class FakeDownloader:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.calls: list[tuple[str, float, int, tuple[str, ...]]] = []

    def __call__(
        self,
        url: str,
        output: Path,
        timeout_seconds: float,
        max_bytes: int,
        allowed_hosts: tuple[str, ...],
    ) -> dict[str, object]:
        self.calls.append((url, timeout_seconds, max_bytes, allowed_hosts))
        output.write_bytes(self.payload)
        return {
            "method": "https",
            "status": "ok",
            "bytes": len(self.payload),
            "timed_out": False,
        }


class FakeResponse:
    def __init__(self, payload: bytes, *, content_length: str | None = None):
        self.payload = io.BytesIO(payload)
        self.headers = {} if content_length is None else {"Content-Length": content_length}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_arguments: object) -> None:
        return None

    def getcode(self) -> int:
        return 200

    def geturl(self) -> str:
        return "https://arxiv.org/src/2001.04383v3"

    def read(self, size: int) -> bytes:
        return self.payload.read(size)


class FakeOpener:
    def __init__(self, response: FakeResponse):
        self.response = response

    def open(self, *_arguments: object, **_keywords: object) -> FakeResponse:
        return self.response


class ReferenceTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.payload = b"pinned reference bytes\n"
        self.direct = transport.DirectDownloadPin(
            "paper-source",
            "https://arxiv.org/src/2001.04383v3",
            digest(self.payload),
            1024,
            ("arxiv.org",),
        )
        self.github = transport.GitHubArchivePin(
            "workflow-source",
            "LionSR/MIPStarRE",
            "main",
            "5" * 40,
            digest(self.payload),
            1024,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_direct_download_verifies_and_atomically_publishes(self) -> None:
        downloader = FakeDownloader(self.payload)
        destination = self.root / "paper.tar"
        result = transport.acquire(self.direct, destination, _downloader=downloader)
        self.assertEqual("published", result["status"])
        self.assertEqual(digest(self.payload), result["actual_sha256"])
        self.assertEqual(self.payload, destination.read_bytes())
        self.assertEqual([], list(self.root.glob(".*.partial")))
        self.assertEqual(("arxiv.org",), downloader.calls[0][3])

    def test_existing_matching_destination_is_a_cache_hit_without_transport(self) -> None:
        destination = self.root / "paper.tar"
        destination.write_bytes(self.payload)
        downloader = mock.Mock()
        result = transport.acquire(self.direct, destination, _downloader=downloader)
        self.assertEqual("cached", result["status"])
        downloader.assert_not_called()

    def test_existing_mismatched_destination_is_preserved(self) -> None:
        destination = self.root / "paper.tar"
        destination.write_bytes(b"user data")
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(self.direct, destination, _downloader=mock.Mock())
        self.assertEqual("ExistingChecksumMismatch", raised.exception.evidence["error"]["class"])
        self.assertEqual(b"user data", destination.read_bytes())

    def test_oversized_existing_destination_failure_is_structured_and_preserved(self) -> None:
        destination = self.root / "oversized-existing"
        payload = b"12345"
        destination.write_bytes(payload)
        pin = transport.DirectDownloadPin(
            "small-cache", self.direct.url, digest(payload), 4, self.direct.allowed_hosts
        )
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(pin, destination, _downloader=mock.Mock())
        self.assertEqual(
            "ExistingDestinationReadFailure", raised.exception.evidence["error"]["class"]
        )
        self.assertEqual(payload, destination.read_bytes())

    def test_checksum_mismatch_never_publishes_partial_bytes(self) -> None:
        destination = self.root / "paper.tar"
        downloader = FakeDownloader(b"wrong")
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(self.direct, destination, _downloader=downloader)
        evidence = raised.exception.evidence
        self.assertEqual("ChecksumMismatch", evidence["error"]["class"])
        self.assertEqual(digest(b"wrong"), evidence["actual_sha256"])
        self.assertFalse(destination.exists())
        self.assertEqual([], list(self.root.glob(".*.partial")))

    def test_byte_bound_is_enforced_even_when_downloader_claims_success(self) -> None:
        pin = transport.DirectDownloadPin(
            "tiny", self.direct.url, digest(b"12345"), 4, self.direct.allowed_hosts
        )
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(pin, self.root / "tiny", _downloader=FakeDownloader(b"12345"))
        self.assertEqual("ByteLimitExceeded", raised.exception.evidence["error"]["class"])
        self.assertFalse((self.root / "tiny").exists())

    def test_download_failure_records_attempt_and_never_publishes(self) -> None:
        def fail(*_arguments: object) -> dict[str, object]:
            raise transport.ReferenceTransportError(
                "timeout",
                {
                    "method": "https",
                    "status": "timed_out",
                    "timed_out": True,
                    "termination_cleanup_complete": True,
                },
            )

        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(self.direct, self.root / "paper", _downloader=fail)
        self.assertEqual("DownloadFailure", raised.exception.evidence["error"]["class"])
        self.assertTrue(raised.exception.evidence["attempts"][0]["timed_out"])
        self.assertFalse((self.root / "paper").exists())

    def test_unsafe_destination_symlink_is_rejected_before_transport(self) -> None:
        target = self.root / "target"
        target.write_bytes(self.payload)
        destination = self.root / "paper"
        destination.symlink_to(target)
        downloader = mock.Mock()
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(self.direct, destination, _downloader=downloader)
        self.assertEqual("UnsafeDestination", raised.exception.evidence["error"]["class"])
        downloader.assert_not_called()

    def test_url_validation_rejects_credentials_and_unsafe_forms_before_io(self) -> None:
        invalid_urls = (
            "http://arxiv.org/src/2001.04383v3",
            "https://user@arxiv.org/src/2001.04383v3",
            "https://user:secret@arxiv.org/src/2001.04383v3",
            "https://arxiv.org/src/2001.04383v3?token=secret",
            "https://arxiv.org/src/2001.04383v3?",
            "https://arxiv.org/src/2001.04383v3#fragment",
            "https://arxiv.org/src/2001.04383v3#",
            "https://arxiv.org:444/src/2001.04383v3",
            "https:\\arxiv.org\\src",
            "git@github.com:LionSR/MIPStarRE.git",
        )
        for index, url in enumerate(invalid_urls):
            with self.subTest(url=url):
                pin = transport.DirectDownloadPin(
                    f"bad-{index}", url, "0" * 64, 1, ("arxiv.org",)
                )
                with self.assertRaises(ValueError):
                    transport.acquire(pin, self.root / f"bad-{index}", _downloader=mock.Mock())

    def test_redirect_handler_rejects_cross_host_and_credentials(self) -> None:
        handler = transport._AllowlistedRedirectHandler(("arxiv.org",))
        request = transport.Request("https://arxiv.org/src/2001.04383v3")
        for url in ("https://example.com/file", "https://user@arxiv.org/file"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, "Found", {}, url)

    def test_http_worker_rejects_declared_size_before_writing(self) -> None:
        output = self.root / "declared-overflow"
        opener = FakeOpener(FakeResponse(b"12345", content_length="5"))
        with mock.patch("reference_transport.build_opener", return_value=opener), self.assertRaisesRegex(
            OSError, "Content-Length exceeds"
        ):
            transport._http_download_worker(
                self.direct.url, output, 4, 1, self.direct.allowed_hosts
            )
        self.assertFalse(output.exists())

    def test_http_worker_rejects_streamed_overflow(self) -> None:
        output = self.root / "stream-overflow"
        opener = FakeOpener(FakeResponse(b"12345"))
        with mock.patch("reference_transport.build_opener", return_value=opener), self.assertRaisesRegex(
            OSError, "response exceeds"
        ):
            transport._http_download_worker(
                self.direct.url, output, 4, 1, self.direct.allowed_hosts
            )
        self.assertEqual(b"", output.read_bytes())

    def test_http_worker_accepts_exact_bound_and_fsyncs(self) -> None:
        output = self.root / "exact-bound"
        opener = FakeOpener(FakeResponse(b"1234", content_length="4"))
        with mock.patch("reference_transport.build_opener", return_value=opener):
            evidence = transport._http_download_worker(
                self.direct.url, output, 4, 1, self.direct.allowed_hosts
            )
        self.assertEqual(b"1234", output.read_bytes())
        self.assertEqual(4, evidence["bytes"])
        self.assertEqual([], evidence["redirects"])

    def test_http_worker_does_not_record_response_headers(self) -> None:
        output = self.root / "header-redaction"
        response = FakeResponse(b"1234", content_length="4")
        response.headers["Authorization"] = "Bearer header-secret"
        response.headers["X-Secret"] = "header-secret"
        with mock.patch(
            "reference_transport.build_opener", return_value=FakeOpener(response)
        ):
            evidence = transport._http_download_worker(
                self.direct.url, output, 4, 1, self.direct.allowed_hosts
            )
        self.assertNotIn("header-secret", json.dumps(evidence))

    def test_http_worker_rejects_swapped_temporary_symlink_without_touching_target(self) -> None:
        target = self.root / "sentinel"
        target.write_bytes(b"sentinel")
        descriptor, name = tempfile.mkstemp(dir=self.root)
        metadata = os.fstat(descriptor)
        os.close(descriptor)
        output = Path(name)
        output.unlink()
        output.symlink_to(target)
        with mock.patch(
            "reference_transport.build_opener", return_value=FakeOpener(FakeResponse(b"attack"))
        ), self.assertRaises(OSError):
            transport._http_download_worker(
                self.direct.url,
                output,
                10,
                1,
                self.direct.allowed_hosts,
                (metadata.st_dev, metadata.st_ino),
            )
        self.assertEqual(b"sentinel", target.read_bytes())

    def test_http_worker_rejects_swapped_hard_link_before_truncation(self) -> None:
        target = self.root / "hard-link-sentinel"
        target.write_bytes(b"sentinel")
        descriptor, name = tempfile.mkstemp(dir=self.root)
        metadata = os.fstat(descriptor)
        os.close(descriptor)
        output = Path(name)
        output.unlink()
        os.link(target, output)
        with mock.patch(
            "reference_transport.build_opener", return_value=FakeOpener(FakeResponse(b"attack"))
        ), self.assertRaisesRegex(OSError, "identity or link count changed"):
            transport._http_download_worker(
                self.direct.url,
                output,
                10,
                1,
                self.direct.allowed_hosts,
                (metadata.st_dev, metadata.st_ino),
            )
        self.assertEqual(b"sentinel", target.read_bytes())

    def test_http_worker_rejects_a_new_link_to_the_original_inode_before_write(self) -> None:
        descriptor, name = tempfile.mkstemp(dir=self.root)
        metadata = os.fstat(descriptor)
        os.close(descriptor)
        output = Path(name)
        alias = self.root / "external-alias"

        class LinkingOpener(FakeOpener):
            def open(self, *_arguments: object, **_keywords: object) -> FakeResponse:
                os.link(output, alias)
                return self.response

        with mock.patch(
            "reference_transport.build_opener",
            return_value=LinkingOpener(FakeResponse(b"attack")),
        ), self.assertRaisesRegex(OSError, "link count changed before download"):
            transport._http_download_worker(
                self.direct.url,
                output,
                10,
                1,
                self.direct.allowed_hosts,
                (metadata.st_dev, metadata.st_ino),
            )
        self.assertEqual(b"", output.read_bytes())
        self.assertEqual(b"", alias.read_bytes())

    def test_parent_rejects_a_new_link_to_the_original_inode_after_download(self) -> None:
        alias = self.root / "post-download-alias"

        def linking_downloader(
            _url: str,
            output: Path,
            _timeout: float,
            _max_bytes: int,
            _hosts: tuple[str, ...],
        ) -> dict[str, object]:
            output.write_bytes(self.payload)
            os.link(output, alias)
            return {"method": "local", "status": "ok"}

        destination = self.root / "hardlink-publication"
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(self.direct, destination, _downloader=linking_downloader)
        self.assertEqual("UnsafeTemporary", raised.exception.evidence["error"]["class"])
        self.assertFalse(destination.exists())
        self.assertEqual(self.payload, alias.read_bytes())

    def test_parent_rechecks_single_link_invariant_after_fsync(self) -> None:
        alias = self.root / "fsync-race-alias"
        real_fsync = transport._fsync_descriptor

        def fsync_then_link(descriptor: int) -> None:
            real_fsync(descriptor)
            partial = next(self.root.glob(".fsync-race.*.partial"))
            os.link(partial, alias)

        destination = self.root / "fsync-race"
        with mock.patch(
            "reference_transport._fsync_descriptor", side_effect=fsync_then_link
        ), self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.direct, destination, _downloader=FakeDownloader(self.payload)
            )
        self.assertEqual("UnsafeTemporary", raised.exception.evidence["error"]["class"])
        self.assertFalse(destination.exists())
        self.assertEqual(self.payload, alias.read_bytes())

    def test_post_replace_link_race_removes_destination_and_fails_closed(self) -> None:
        alias = self.root / "replace-link-alias"
        destination = self.root / "replace-link-race"
        real_replace = os.replace

        def replace_then_link(source: Path, target: Path) -> None:
            real_replace(source, target)
            os.link(target, alias)

        with mock.patch(
            "reference_transport.os.replace", side_effect=replace_then_link
        ), self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.direct, destination, _downloader=FakeDownloader(self.payload)
            )
        self.assertEqual("UnsafeTemporary", raised.exception.evidence["error"]["class"])
        self.assertFalse(destination.exists())
        self.assertEqual(self.payload, alias.read_bytes())

    def test_replace_time_symlink_substitution_is_removed_without_touching_target(self) -> None:
        sentinel = self.root / "replace-sentinel"
        sentinel.write_bytes(b"sentinel")
        held_inode = self.root / "held-original-inode"
        destination = self.root / "replace-symlink-race"
        real_replace = os.replace

        def substitute_before_replace(source: Path, target: Path) -> None:
            real_replace(source, held_inode)
            source.symlink_to(sentinel)
            real_replace(source, target)

        with mock.patch(
            "reference_transport.os.replace", side_effect=substitute_before_replace
        ), self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.direct, destination, _downloader=FakeDownloader(self.payload)
            )
        self.assertEqual("UnsafeTemporary", raised.exception.evidence["error"]["class"])
        self.assertFalse(destination.exists())
        self.assertEqual(b"sentinel", sentinel.read_bytes())
        self.assertEqual(self.payload, held_inode.read_bytes())

    def test_pin_validation_rejects_bad_digests_bounds_and_timeouts(self) -> None:
        for checksum in ("A" * 64, "0" * 63, "not-a-digest"):
            with self.subTest(checksum=checksum), self.assertRaises(ValueError):
                transport.acquire(
                    transport.DirectDownloadPin("pin", self.direct.url, checksum, 1),
                    self.root / "output",
                    _downloader=mock.Mock(),
                )
        for invalid in (0, -1, True):
            with self.subTest(max_bytes=invalid), self.assertRaises(ValueError):
                transport.acquire(
                    transport.DirectDownloadPin("pin", self.direct.url, "0" * 64, invalid),
                    self.root / "output",
                    _downloader=mock.Mock(),
                )
        for invalid in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(timeout=invalid), self.assertRaises(ValueError):
                transport.acquire(self.direct, self.root / "output", timeout_seconds=invalid)

    def test_repository_and_revision_are_explicit_non_url_inputs(self) -> None:
        invalid_repositories = (
            "https://github.com/LionSR/MIPStarRE",
            "user@github.com:LionSR/MIPStarRE",
            "LionSR/MIPStarRE/extra",
            "../repo",
        )
        for repository in invalid_repositories:
            with self.subTest(repository=repository), self.assertRaises(ValueError):
                transport.acquire(
                    transport.GitHubArchivePin(
                        "pin", repository, "main", "0" * 40, "0" * 64, 1
                    ),
                    self.root / "output",
                )
        for revision in ("../main", "main?token=x", "main#x", "main@{1}", "a//b"):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                transport.acquire(
                    transport.GitHubArchivePin(
                        "pin", "LionSR/MIPStarRE", revision, "0" * 40, "0" * 64, 1
                    ),
                    self.root / "output",
                )

    def test_symlinked_destination_parent_is_rejected_before_transport(self) -> None:
        real_parent = self.root / "real"
        real_parent.mkdir()
        linked_parent = self.root / "linked"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        downloader = mock.Mock()
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.direct, linked_parent / "paper.tar", _downloader=downloader
            )
        self.assertEqual("UnsafeDestination", raised.exception.evidence["error"]["class"])
        downloader.assert_not_called()

    def test_git_success_uses_exact_commit_and_skips_rest(self) -> None:
        downloader = FakeDownloader(self.payload)
        runner = mock.Mock(
            return_value=outcome(0, stdout=f"{self.github.expected_commit}\trefs/heads/main\n")
        )
        rest = mock.Mock()
        result = transport.acquire(
            self.github,
            self.root / "archive.tar.gz",
            _runner=runner,
            _json_fetcher=rest,
            _downloader=downloader,
        )
        rest.assert_not_called()
        self.assertEqual(self.github.expected_commit, result["resolved_commit"])
        self.assertEqual(
            f"https://codeload.github.com/LionSR/MIPStarRE/tar.gz/{self.github.expected_commit}",
            downloader.calls[0][0],
        )
        git_argv = runner.call_args.args[0]
        self.assertEqual("https://github.com/LionSR/MIPStarRE.git", git_argv[-2])
        self.assertEqual("main", git_argv[-1])

    def test_git_timeout_falls_back_to_rest_then_exact_codeload(self) -> None:
        runner = mock.Mock(return_value=outcome(None, timed_out=True))
        rest = mock.Mock(
            return_value=(
                {"sha": self.github.expected_commit},
                {"method": "https", "status": "ok", "timed_out": False},
            )
        )
        downloader = FakeDownloader(self.payload)
        result = transport.acquire(
            self.github,
            self.root / "archive.tar.gz",
            _runner=runner,
            _json_fetcher=rest,
            _downloader=downloader,
        )
        self.assertEqual(["git_ls_remote", "github_rest", "https"], [x["method"] for x in result["attempts"]])
        rest_url = rest.call_args.args[0]
        self.assertEqual(
            "https://api.github.com/repos/LionSR/MIPStarRE/commits/main",
            rest_url,
        )
        self.assertTrue(result["attempts"][0]["termination_cleanup_complete"])

    def test_rest_fallback_resolves_the_declared_revision_not_the_expected_commit(self) -> None:
        pin = transport.GitHubArchivePin(
            "workflow-source",
            "LionSR/MIPStarRE",
            "release/candidate",
            self.github.expected_commit,
            digest(self.payload),
            1024,
        )
        rest = mock.Mock(
            return_value=({"sha": pin.expected_commit}, {"method": "https", "status": "ok"})
        )
        transport.acquire(
            pin,
            self.root / "archive.tar.gz",
            _runner=lambda _argv, _timeout: outcome(2),
            _json_fetcher=rest,
            _downloader=FakeDownloader(self.payload),
        )
        self.assertEqual(
            "https://api.github.com/repos/LionSR/MIPStarRE/commits/release%2Fcandidate",
            rest.call_args.args[0],
        )

    def test_rest_fallback_cannot_accept_a_stale_or_nonexistent_revision(self) -> None:
        for rest_result in (
            ({"sha": "6" * 40}, {"status": "ok"}),
            transport.ReferenceTransportError("missing ref", {"status": "failed"}),
        ):
            with self.subTest(rest_result=type(rest_result).__name__):
                rest = mock.Mock()
                if isinstance(rest_result, Exception):
                    rest.side_effect = rest_result
                else:
                    rest.return_value = rest_result
                downloader = mock.Mock()
                with self.assertRaises(transport.ReferenceTransportError):
                    transport.acquire(
                        self.github,
                        self.root / f"missing-{len(rest.mock_calls)}",
                        _runner=lambda _argv, _timeout: outcome(2),
                        _json_fetcher=rest,
                        _downloader=downloader,
                    )
                self.assertTrue(rest.call_args.args[0].endswith("/commits/main"))
                downloader.assert_not_called()

    def test_git_and_http_timeouts_are_independently_bounded(self) -> None:
        runner = mock.Mock(return_value=outcome(2))
        rest = mock.Mock(
            return_value=({"sha": self.github.expected_commit}, {"status": "ok"})
        )
        downloader = FakeDownloader(self.payload)
        result = transport.acquire(
            self.github,
            self.root / "separate-timeouts",
            timeout_seconds=90,
            git_timeout_seconds=7,
            _runner=runner,
            _json_fetcher=rest,
            _downloader=downloader,
        )
        self.assertEqual(7, runner.call_args.args[1])
        self.assertEqual(90, rest.call_args.args[1])
        self.assertEqual(90, downloader.calls[0][1])
        self.assertEqual(7, result["git_timeout_seconds"])

    def test_incomplete_git_timeout_cleanup_fails_closed_without_rest(self) -> None:
        incomplete = transport.CommandOutcome(
            ("git", "ls-remote"),
            None,
            "",
            "",
            1.0,
            timed_out=True,
            termination_signal="SIGTERM",
            termination_escalated=True,
            termination_cleanup_complete=False,
        )
        rest = mock.Mock()
        downloader = mock.Mock()
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.github,
                self.root / "archive",
                _runner=lambda _argv, _timeout: incomplete,
                _json_fetcher=rest,
                _downloader=downloader,
            )
        self.assertEqual("IncompleteProcessCleanup", raised.exception.evidence["error"]["class"])
        rest.assert_not_called()
        downloader.assert_not_called()

    @mock.patch("reference_transport.run_bounded_argv")
    def test_default_git_probe_is_config_isolated_and_noninteractive(
        self, bounded: mock.Mock
    ) -> None:
        bounded.return_value = outcome(
            0, stdout=f"{self.github.expected_commit}\trefs/heads/main\n"
        )
        transport.acquire(
            self.github,
            self.root / "archive",
            _json_fetcher=mock.Mock(),
            _downloader=FakeDownloader(self.payload),
        )
        environment = bounded.call_args.kwargs["environment"]
        self.assertEqual("1", environment["GIT_CONFIG_NOSYSTEM"])
        self.assertEqual(transport.os.devnull, environment["GIT_CONFIG_GLOBAL"])
        self.assertEqual("0", environment["GIT_TERMINAL_PROMPT"])
        self.assertEqual(tempfile.gettempdir(), environment["GIT_CEILING_DIRECTORIES"])
        self.assertNotIn("GIT_ASKPASS", environment)
        self.assertFalse(any(name.startswith("GIT_CONFIG_KEY_") for name in environment))
        self.assertEqual(Path(tempfile.gettempdir()), bounded.call_args.kwargs["cwd"])

    def test_git_nonzero_falls_back_to_rest(self) -> None:
        runner = mock.Mock(return_value=outcome(2, stderr="transport unavailable"))
        rest = mock.Mock(
            return_value=(
                {"sha": self.github.expected_commit},
                {"method": "https", "status": "ok"},
            )
        )
        transport.acquire(
            self.github,
            self.root / "archive.tar.gz",
            _runner=runner,
            _json_fetcher=rest,
            _downloader=FakeDownloader(self.payload),
        )
        rest.assert_called_once()

    def test_successful_malformed_git_output_is_a_hard_failure_without_rest(self) -> None:
        runner = mock.Mock(return_value=outcome(0, stdout="not-a-commit\trefs/heads/main\n"))
        rest = mock.Mock()
        downloader = mock.Mock()
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.github,
                self.root / "archive",
                _runner=runner,
                _json_fetcher=rest,
                _downloader=downloader,
            )
        self.assertEqual("MalformedGitResolution", raised.exception.evidence["error"]["class"])
        rest.assert_not_called()
        downloader.assert_not_called()

    def test_git_commit_mismatch_is_a_hard_failure_without_rest(self) -> None:
        runner = mock.Mock(return_value=outcome(0, stdout=f"{'6' * 40}\trefs/heads/main\n"))
        rest = mock.Mock()
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.github, self.root / "archive", _runner=runner, _json_fetcher=rest
            )
        self.assertEqual("CommitMismatch", raised.exception.evidence["error"]["class"])
        rest.assert_not_called()

    def test_rest_invalid_or_mismatched_commit_never_downloads(self) -> None:
        for value, error_class in (("bad", "MalformedRestResolution"), ("6" * 40, "CommitMismatch")):
            with self.subTest(value=value):
                rest = mock.Mock(return_value=({"sha": value}, {"status": "ok"}))
                downloader = mock.Mock()
                with self.assertRaises(transport.ReferenceTransportError) as raised:
                    transport.acquire(
                        self.github,
                        self.root / f"archive-{value[:3]}",
                        _runner=lambda _argv, _timeout: outcome(2),
                        _json_fetcher=rest,
                        _downloader=downloader,
                    )
                self.assertEqual(error_class, raised.exception.evidence["error"]["class"])
                downloader.assert_not_called()

    def test_rest_transport_failure_is_structured(self) -> None:
        def rest_failure(_url: str, _timeout: float) -> tuple[dict[str, object], dict[str, object]]:
            raise transport.ReferenceTransportError(
                "REST timeout", {"status": "timed_out", "timed_out": True}
            )

        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.github,
                self.root / "archive",
                _runner=lambda _argv, _timeout: outcome(None, timed_out=True),
                _json_fetcher=rest_failure,
            )
        evidence = raised.exception.evidence
        self.assertEqual("GitHubRestFailure", evidence["error"]["class"])
        self.assertEqual("github_rest", evidence["attempts"][-1]["method"])
        self.assertFalse(evidence["published"])

    def test_subprocess_evidence_records_digests_not_raw_diagnostics(self) -> None:
        sentinel = "diagnostic-secret"
        evidence = outcome(1, stdout=sentinel, stderr=sentinel).evidence("git_ls_remote")
        encoded = json.dumps(evidence)
        self.assertNotIn(sentinel, encoded)
        self.assertEqual(len(sentinel), evidence["stdout_bytes"])
        self.assertEqual(digest(sentinel.encode()), evidence["stderr_sha256"])

    def test_bounded_runner_limits_stdout_and_stderr_without_losing_raw_digests(self) -> None:
        for stream_name in ("stdout", "stderr"):
            with self.subTest(stream_name=stream_name):
                payload = b"x" * (transport.SUBPROCESS_OUTPUT_LIMIT + 257)
                descriptor = 1 if stream_name == "stdout" else 2
                code = textwrap.dedent(
                    f"""
                    import os
                    payload = {payload!r}
                    while payload:
                        payload = payload[os.write({descriptor}, payload):]
                    """
                )
                result = transport.run_bounded_argv([sys.executable, "-c", code], 5)
                evidence = result.evidence("test")
                self.assertTrue(result.output_limit_exceeded)
                self.assertEqual("output_limited", evidence["status"])
                self.assertEqual(len(payload), evidence[f"{stream_name}_bytes"])
                self.assertEqual(digest(payload), evidence[f"{stream_name}_sha256"])
                self.assertEqual(
                    transport.SUBPROCESS_OUTPUT_LIMIT,
                    len(getattr(result, stream_name).encode()),
                )
                self.assertTrue(result.termination_cleanup_complete)

    def test_subprocess_digest_counts_raw_bytes_before_utf8_replacement(self) -> None:
        payload = b"\xff\xfe\x80raw"
        code = f"import os; os.write(1, {payload!r})"
        result = transport.run_bounded_argv([sys.executable, "-c", code], 5)
        evidence = result.evidence("test")
        self.assertEqual(len(payload), evidence["stdout_bytes"])
        self.assertEqual(digest(payload), evidence["stdout_sha256"])
        self.assertIn("\ufffd", result.stdout)

    def test_git_output_limit_is_a_hard_failure_without_rest_fallback(self) -> None:
        limited = transport.CommandOutcome(
            ("git", "ls-remote"),
            0,
            "5" * 40,
            "",
            0.1,
            output_limit_exceeded=True,
            stdout_byte_count=transport.SUBPROCESS_OUTPUT_LIMIT + 1,
            stdout_digest=digest(b"x" * (transport.SUBPROCESS_OUTPUT_LIMIT + 1)),
        )
        rest = mock.Mock()
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport.acquire(
                self.github,
                self.root / "limited-git",
                _runner=lambda _argv, _timeout: limited,
                _json_fetcher=rest,
            )
        self.assertEqual("OutputLimitExceeded", raised.exception.evidence["error"]["class"])
        rest.assert_not_called()

    @mock.patch("reference_transport.run_bounded_argv")
    def test_worker_output_limit_is_a_structured_failure(self, bounded: mock.Mock) -> None:
        bounded.return_value = transport.CommandOutcome(
            ("worker",),
            0,
            "{}",
            "",
            0.1,
            output_limit_exceeded=True,
            stdout_byte_count=transport.SUBPROCESS_OUTPUT_LIMIT + 1,
            stdout_digest="0" * 64,
        )
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport._download_via_worker(
                self.direct.url,
                self.root / "worker-output-limit",
                1,
                4,
                self.direct.allowed_hosts,
            )
        self.assertEqual("OutputLimitExceeded", raised.exception.evidence["error"]["class"])

    @mock.patch("reference_transport.run_bounded_argv")
    def test_worker_failure_parses_safe_fields_without_raw_diagnostics(
        self, bounded: mock.Mock
    ) -> None:
        bounded.return_value = transport.CommandOutcome(
            ("worker",),
            1,
            json.dumps(
                {
                    "status": "failed",
                    "error": {"class": "ByteLimitExceeded", "message": "response too large"},
                }
            ),
            "proxy diagnostic secret",
            0.1,
        )
        with self.assertRaises(transport.ReferenceTransportError) as raised:
            transport._download_via_worker(
                self.direct.url,
                self.root / "worker-output",
                1,
                4,
                self.direct.allowed_hosts,
            )
        encoded = json.dumps(raised.exception.evidence)
        self.assertNotIn("proxy diagnostic secret", encoded)
        self.assertEqual("ByteLimitExceeded", raised.exception.evidence["error"]["class"])

    def test_real_timeout_terminates_descendant_process_group(self) -> None:
        marker = self.root / "child-terminated"
        child_code = textwrap.dedent(
            f"""
            import pathlib
            import signal
            import sys
            import time
            marker = pathlib.Path({str(marker)!r})
            def terminate(_signal, _frame):
                marker.write_text("terminated", encoding="utf-8")
                sys.exit(0)
            signal.signal(signal.SIGTERM, terminate)
            print("child-ready", flush=True)
            time.sleep(60)
            """
        )
        parent_code = textwrap.dedent(
            f"""
            import subprocess
            import sys
            import time
            subprocess.Popen([sys.executable, "-c", {child_code!r}])
            print("parent-ready", flush=True)
            time.sleep(60)
            """
        )
        result = transport.run_bounded_argv(
            [sys.executable, "-c", parent_code], 0.5, cwd=self.root
        )
        self.assertTrue(result.timed_out)
        self.assertEqual("SIGTERM", result.termination_signal)
        self.assertTrue(result.termination_cleanup_complete)
        self.assertIn("parent-ready", result.stdout)
        self.assertEqual("terminated", marker.read_text(encoding="utf-8"))

    def test_timeout_escalates_to_sigkill_when_process_ignores_sigterm(self) -> None:
        code = textwrap.dedent(
            """
            import signal
            import time
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            print("ready", flush=True)
            time.sleep(60)
            """
        )
        result = transport.run_bounded_argv([sys.executable, "-c", code], 0.2, cwd=self.root)
        self.assertTrue(result.timed_out)
        self.assertTrue(result.termination_escalated)
        self.assertTrue(result.termination_cleanup_complete)
        self.assertLess(result.elapsed_seconds, 3.0)

    @mock.patch("reference_transport._signal_process_group")
    @mock.patch("reference_transport._terminate_process_group", side_effect=KeyboardInterrupt)
    @mock.patch("reference_transport.subprocess.Popen")
    def test_second_interrupt_forces_sigkill_and_bounded_wait(
        self,
        popen: mock.Mock,
        _terminate: mock.Mock,
        send_signal: mock.Mock,
    ) -> None:
        process = popen.return_value
        process.stdout = io.BytesIO()
        process.stderr = io.BytesIO()
        process.poll.side_effect = KeyboardInterrupt
        process.wait.return_value = 0
        with self.assertRaises(KeyboardInterrupt):
            transport.run_bounded_argv(["git", "--version"], 1)
        send_signal.assert_called_once_with(process, signal.SIGKILL)
        process.wait.assert_called_once_with(timeout=transport.PROCESS_TERMINATION_GRACE_SECONDS)

    def test_keyboard_interrupt_terminates_parent_and_descendant(self) -> None:
        parent_marker = self.root / "parent-interrupted"
        child_marker = self.root / "child-interrupted"
        child_code = textwrap.dedent(
            f"""
            import pathlib
            import signal
            import sys
            import time
            marker = pathlib.Path({str(child_marker)!r})
            def terminate(_signal, _frame):
                marker.write_text("terminated", encoding="utf-8")
                sys.exit(0)
            signal.signal(signal.SIGTERM, terminate)
            print("child-ready", flush=True)
            time.sleep(60)
            """
        )
        parent_code = textwrap.dedent(
            f"""
            import pathlib
            import signal
            import subprocess
            import sys
            import time
            marker = pathlib.Path({str(parent_marker)!r})
            def terminate(_signal, _frame):
                marker.write_text("terminated", encoding="utf-8")
                sys.exit(0)
            signal.signal(signal.SIGTERM, terminate)
            subprocess.Popen([sys.executable, "-c", {child_code!r}])
            print("parent-ready", flush=True)
            time.sleep(60)
            """
        )
        timer = threading.Timer(0.5, _thread.interrupt_main)
        timer.start()
        try:
            with self.assertRaises(KeyboardInterrupt):
                transport.run_bounded_argv(
                    [sys.executable, "-c", parent_code], 10, cwd=self.root
                )
        finally:
            timer.cancel()
        self.assertEqual("terminated", parent_marker.read_text(encoding="utf-8"))
        self.assertEqual("terminated", child_marker.read_text(encoding="utf-8"))

    def test_publication_failures_report_the_exact_phase(self) -> None:
        cases = (
            ("_fsync_descriptor", "FileSyncFailure", False),
            ("os.replace", "AtomicReplaceFailure", False),
            ("_fsync_directory", "DirectorySyncFailure", True),
        )
        for index, (target, error_class, published) in enumerate(cases):
            destination = self.root / f"phase-{index}"
            patch_target = (
                f"reference_transport.{target}" if not target.startswith("os.") else "reference_transport.os.replace"
            )
            with self.subTest(target=target), mock.patch(
                patch_target, side_effect=OSError("injected phase failure")
            ), self.assertRaises(transport.ReferenceTransportError) as raised:
                transport.acquire(
                    self.direct,
                    destination,
                    _downloader=FakeDownloader(self.payload),
                )
            evidence = raised.exception.evidence
            self.assertEqual(error_class, evidence["error"]["class"])
            self.assertEqual(published, evidence["published"])
            self.assertEqual(published, destination.exists())
            self.assertEqual([], list(self.root.glob(f".{destination.name}.*.partial")))
            if published:
                self.assertTrue(evidence["durability_uncertain"])

    @mock.patch("reference_transport.subprocess.Popen")
    def test_bounded_runner_uses_argv_without_shell(self, popen: mock.Mock) -> None:
        process = popen.return_value
        process.stdout = io.BytesIO()
        process.stderr = io.BytesIO()
        process.poll.return_value = 0
        process.returncode = 0
        transport.run_bounded_argv(["git", "--version"], 1)
        self.assertEqual(("git", "--version"), popen.call_args.args[0])
        self.assertFalse(popen.call_args.kwargs["shell"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertIsNone(popen.call_args.kwargs["env"])

    def test_cli_failure_does_not_echo_credential_bearing_url(self) -> None:
        stream = io.StringIO()
        with mock.patch("sys.stdout", stream):
            returncode = transport.main(
                [
                    "direct",
                    "--id",
                    "secret",
                    "--url",
                    "https://user:secret@arxiv.org/file",
                    "--sha256",
                    "0" * 64,
                    "--max-bytes",
                    "1",
                    "--output",
                    str(self.root / "output"),
                ]
            )
        self.assertEqual(1, returncode)
        self.assertNotIn("user", stream.getvalue())
        self.assertNotIn("secret@", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
