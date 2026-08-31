#!/usr/bin/env python3
"""Freeze and verify the one-time, unborn-repository review snapshot.

The ordinary review protocol binds a Git base/head pair.  Stage one has no base
commit, so this tool creates the only permitted substitute: a content-addressed
snapshot plus a narrow list of terminal evidence files that may change after a
read-only review.  ``seal`` records those terminal files before the first
commit while proving that the reviewed core is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable


SCHEMA_VERSION = 1
TOOL_VERSION = "bootstrap-freeze-v1"
MANIFEST_REL = Path("workflow/reviews/bootstrap-stage-01.manifest.json")

# These files contain only the outcome of the frozen review or lifecycle fields
# that cannot be known until that review returns.  Their final bytes are bound
# by ``seal``; all other files are immutable as soon as ``freeze`` succeeds.
TERMINAL_EVIDENCE_PATHS = (
    "research/metrics/sessions.jsonl",
    "research/report.md",
    "workflow/events.jsonl",
    "workflow/reviews/stage-01-bootstrap-final.md",
    "workflow/state/issues.json",
    "workflow/state/sessions.json",
    "workflow/state/stages.json",
)

ROOT_EXCLUDED_DIR_NAMES = {
    ".git",
    ".agents",
    ".codex",
    ".workflow-runtime",
}
ANY_EXCLUDED_DIR_NAMES = {"__pycache__"}
EXCLUDED_PREFIXES = (
    "references/2001.04383v3/source/",
    "references/2001.04383v3/sections/",
)
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".swp", "~")

CANONICAL_CHECKS: tuple[tuple[str, ...], ...] = (
    ("python3", "scripts/check_workflow.py"),
    ("python3", "-m", "compileall", "-q", "scripts", "tests"),
    ("git", "diff", "--check"),
)


class ManifestError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _is_excluded(relative: str) -> bool:
    parts = Path(relative).parts
    if (parts and parts[0] in ROOT_EXCLUDED_DIR_NAMES) or any(
        part in ANY_EXCLUDED_DIR_NAMES for part in parts
    ):
        return True
    if relative == MANIFEST_REL.as_posix():
        return True
    if relative in TERMINAL_EVIDENCE_PATHS:
        return True
    if any(relative.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return True
    return relative.endswith(EXCLUDED_SUFFIXES)


def _iter_core_files(root: Path) -> Iterable[Path]:
    collected: list[Path] = []
    for directory, dir_names, file_names in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        relative_directory = directory_path.relative_to(root)
        kept_directories: list[str] = []
        for name in dir_names:
            candidate = directory_path / name
            relative = candidate.relative_to(root).as_posix() + "/"
            parts = candidate.relative_to(root).parts
            if (
                (len(parts) == 1 and name in ROOT_EXCLUDED_DIR_NAMES)
                or name in ANY_EXCLUDED_DIR_NAMES
                or any(
                relative.startswith(prefix) for prefix in EXCLUDED_PREFIXES
                )
            ):
                continue
            if candidate.is_symlink():
                raise ManifestError(f"symlink is forbidden in reviewed core: {relative}")
            kept_directories.append(name)
        dir_names[:] = kept_directories
        for name in file_names:
            path = directory_path / name
            relative = path.relative_to(root).as_posix()
            if _is_excluded(relative):
                continue
            if path.is_symlink():
                raise ManifestError(f"symlink is forbidden in reviewed core: {relative}")
            if path.is_file():
                collected.append(path)
    yield from sorted(collected, key=lambda path: path.relative_to(root).as_posix())


def _entry(root: Path, path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "size": len(data),
        "sha256": _sha256_bytes(data),
    }


def _core_entries(root: Path) -> list[dict[str, Any]]:
    return [_entry(root, path) for path in _iter_core_files(root)]


def _run_checks(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for argv in CANONICAL_CHECKS:
        started = time.monotonic()
        process = subprocess.run(
            argv,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        elapsed = round(time.monotonic() - started, 6)
        output = process.stdout or ""
        result = {
            "argv": list(argv),
            "display": " ".join(argv),
            "exit_code": process.returncode,
            "elapsed_seconds": elapsed,
            "output_sha256": _sha256_bytes(output.encode("utf-8")),
            "output_tail": output[-4000:],
        }
        results.append(result)
        if process.returncode != 0:
            raise ManifestError(
                f"canonical check failed ({process.returncode}): {' '.join(argv)}\n"
                f"{output[-4000:]}"
            )
    return results


def _text_hygiene(root: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    trailing: list[str] = []
    blank_line_at_eof: list[str] = []
    non_ascii: list[str] = []
    for item in entries:
        relative = item["path"]
        data = (root / relative).read_bytes()
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            non_ascii.append(relative)
            continue
        if any(line.endswith((" ", "\t")) for line in text.splitlines()):
            trailing.append(relative)
        logical_lines = text.splitlines()
        if logical_lines and logical_lines[-1] == "":
            blank_line_at_eof.append(relative)
        if any(ord(character) > 127 for character in text):
            non_ascii.append(relative)
    if trailing or blank_line_at_eof or non_ascii:
        raise ManifestError(
            "text hygiene failed; "
            f"trailing={trailing}, blank_line_at_eof={blank_line_at_eof}, "
            f"non_ascii={non_ascii}"
        )
    return {
        "name": "core text hygiene",
        "trailing_whitespace_paths": trailing,
        "blank_line_at_eof_paths": blank_line_at_eof,
        "non_ascii_paths": non_ascii,
        "status": "passed",
    }


def _review_packet(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": document["schema_version"],
        "tool_version": document["tool_version"],
        "stage_id": document["stage_id"],
        "created_at": document["created_at"],
        "repository_state": document["repository_state"],
        "reviewed_files": document["reviewed_files"],
        "terminal_evidence_contract": document["terminal_evidence_contract"],
        "checks": document["checks"],
        "internal_checks": document["internal_checks"],
    }


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_REL
    if not path.is_file():
        raise ManifestError(f"manifest does not exist: {path}")
    try:
        value = json.loads(path.read_text(encoding="ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"invalid manifest: {error}") from error
    if not isinstance(value, dict):
        raise ManifestError("manifest root must be an object")
    return value


def _git_state(root: Path) -> str:
    process = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return "unborn-main" if process.returncode else "committed-head-exists"


def freeze(root: Path, *, replace: bool) -> dict[str, Any]:
    path = root / MANIFEST_REL
    if path.exists() and not replace:
        raise ManifestError("manifest already exists; pass --replace to invalidate it")
    state = _git_state(root)
    if state != "unborn-main":
        raise ManifestError("bootstrap freeze is forbidden after the first commit")

    check_results = _run_checks(root)
    entries = _core_entries(root)
    if not entries:
        raise ManifestError("refusing to freeze an empty review target")
    hygiene = _text_hygiene(root, entries)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "stage_id": "STAGE-01",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository_state": state,
        "reviewed_files": entries,
        "terminal_evidence_contract": {
            "paths": list(TERMINAL_EVIDENCE_PATHS),
            "rule": (
                "Only review outcome and lifecycle evidence may change after freeze; "
                "seal binds their final bytes before commit"
            ),
        },
        "checks": check_results,
        "internal_checks": [hygiene],
        "seal": None,
    }
    document["reviewed_snapshot_digest"] = _sha256_bytes(
        _canonical_bytes(_review_packet(document))
    )
    _atomic_json(path, document)
    return document


def _verify_document(root: Path, document: dict[str, Any]) -> None:
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("unsupported manifest schema")
    if document.get("tool_version") != TOOL_VERSION:
        raise ManifestError("unexpected manifest tool version")
    expected_digest = _sha256_bytes(_canonical_bytes(_review_packet(document)))
    if document.get("reviewed_snapshot_digest") != expected_digest:
        raise ManifestError("reviewed snapshot digest does not match manifest content")
    recorded = document.get("reviewed_files")
    if not isinstance(recorded, list):
        raise ManifestError("reviewed_files must be a list")
    current = _core_entries(root)
    if current != recorded:
        recorded_by_path = {item.get("path"): item for item in recorded if isinstance(item, dict)}
        current_by_path = {item["path"]: item for item in current}
        changed = sorted(
            path
            for path in set(recorded_by_path) | set(current_by_path)
            if recorded_by_path.get(path) != current_by_path.get(path)
        )
        raise ManifestError(f"reviewed core changed: {changed}")
    _text_hygiene(root, current)


def _terminal_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative in TERMINAL_EVIDENCE_PATHS:
        path = root / relative
        if path.is_file() and not path.is_symlink():
            entries.append(_entry(root, path))
        else:
            entries.append({"path": relative, "missing": True})
    return entries


def _seal_digest(seal: dict[str, Any]) -> str:
    value = {key: item for key, item in seal.items() if key != "seal_digest"}
    return _sha256_bytes(_canonical_bytes(value))


def verify(root: Path, *, require_sealed: bool) -> dict[str, Any]:
    document = _load_manifest(root)
    _verify_document(root, document)
    seal = document.get("seal")
    if seal is None:
        if require_sealed:
            raise ManifestError("manifest has not been sealed")
        return document
    if not isinstance(seal, dict):
        raise ManifestError("seal must be null or an object")
    if seal.get("reviewed_snapshot_digest") != document["reviewed_snapshot_digest"]:
        raise ManifestError("seal is bound to a different reviewed snapshot")
    if seal.get("terminal_files") != _terminal_entries(root):
        raise ManifestError("terminal evidence changed after seal")
    if seal.get("seal_digest") != _seal_digest(seal):
        raise ManifestError("seal digest does not match seal content")
    return document


def seal(
    root: Path,
    *,
    reviewer_session_id: str,
    review_report: str,
    reviewed_snapshot_digest: str,
) -> dict[str, Any]:
    document = verify(root, require_sealed=False)
    if reviewed_snapshot_digest != document["reviewed_snapshot_digest"]:
        raise ManifestError("reviewer named a different reviewed snapshot digest")
    report_path = Path(review_report)
    if report_path.as_posix() not in TERMINAL_EVIDENCE_PATHS:
        raise ManifestError("review report must be an allowed terminal evidence path")
    if not (root / report_path).is_file():
        raise ManifestError(f"review report does not exist: {review_report}")
    report_text = (root / report_path).read_text(encoding="utf-8")
    if reviewed_snapshot_digest not in report_text:
        raise ManifestError("review report does not name the reviewed snapshot digest")
    if reviewer_session_id not in report_text:
        raise ManifestError("review report does not name the reviewer session")
    verdict_lines = {
        line.strip().lower().replace("`", "") for line in report_text.splitlines()
    }
    if "- verdict: approve" not in verdict_lines and "verdict: approve" not in verdict_lines:
        raise ManifestError("only an explicit approve verdict can seal the bootstrap snapshot")
    seal_value: dict[str, Any] = {
        "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reviewer_session_id": reviewer_session_id,
        "review_report": review_report,
        "reviewed_snapshot_digest": document["reviewed_snapshot_digest"],
        "terminal_files": _terminal_entries(root),
    }
    seal_value["seal_digest"] = _seal_digest(seal_value)
    document["seal"] = seal_value
    _atomic_json(root / MANIFEST_REL, document)
    return verify(root, require_sealed=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: parent of scripts/)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--replace", action="store_true")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--sealed", action="store_true")
    seal_parser = subparsers.add_parser("seal")
    seal_parser.add_argument("--reviewer-session-id", required=True)
    seal_parser.add_argument("--review-report", required=True)
    seal_parser.add_argument("--reviewed-snapshot-digest", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = arguments.root.resolve()
    try:
        if arguments.command == "freeze":
            document = freeze(root, replace=arguments.replace)
        elif arguments.command == "verify":
            document = verify(root, require_sealed=arguments.sealed)
        else:
            document = seal(
                root,
                reviewer_session_id=arguments.reviewer_session_id,
                review_report=arguments.review_report,
                reviewed_snapshot_digest=arguments.reviewed_snapshot_digest,
            )
    except ManifestError as error:
        print(f"bootstrap manifest error: {error}", file=sys.stderr)
        return 2
    print(document["reviewed_snapshot_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
