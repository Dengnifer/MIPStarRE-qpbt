#!/usr/bin/env python3
"""Verify and atomically materialize exact Lake packages from GitHub archives."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Iterator, Mapping, Sequence
import zlib


SCHEMA_VERSION = 2
LAKE_SCHEMA_VERSION = "1.2.0"
PIN_RELATIVE_PATH = Path("references/lake-packages.json")
ROOT_MANIFEST = Path("lake-manifest.json")
MATHLIB_MANIFEST_SNAPSHOT = Path("references/mathlib-lake-manifest.json")
PACKAGES_DIRECTORY = Path(".lake/packages")
OVERRIDE_PATH = Path(".lake/package-overrides.json")
RUNTIME_DIRECTORY = Path(".lake/lake-package-materialization")
BLOCK = 512
HARD_MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
HARD_MAX_TAR_BYTES = 128 * 1024 * 1024
HARD_MAX_MEMBERS = 20_000
HARD_MAX_MEMBER_BYTES = 16 * 1024 * 1024
HARD_MAX_REGULAR_BYTES = 128 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 300.0
CANONICAL_ARCHIVE_DIRECTORY_MODE = 0o775
CANONICAL_ARCHIVE_REGULAR_MODES = {0o664: 0o644, 0o775: 0o755}

ARCHIVE_KEYS = {
    "sha256", "bytes", "tar_sha256", "tar_bytes", "exact_prefix", "members",
    "directories", "regular_files", "symlinks", "regular_bytes", "max_member_bytes",
}
OUTPUT_KEYS = {
    "directories", "files", "regular_files", "symlinks", "bytes", "max_file_bytes",
    "inventory_sha256", "archive_tree_sha", "tree_sha", "gitlinks",
}
GITLINK_KEYS = {"path", "mode", "type", "sha"}
PACKAGE_KEYS = {
    "name", "scope", "repository", "repository_url", "revision", "input_revision",
    "config_file", "manifest_file", "root_inherited", "mathlib_inherited", "archive_url",
    "archive", "output", "pending_reason",
}
MANIFEST_ENTRY_KEYS = {
    "url", "type", "subDir", "scope", "rev", "name", "manifestFile", "inputRev",
    "inherited", "configFile",
}


class MaterializationError(Exception):
    """An exact package acquisition or publication invariant failed."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 16 * 1024 * 1024:
                raise MaterializationError(f"{label} is not one bounded regular file")
            payload = bytearray()
            while len(payload) <= before.st_size:
                chunk = os.read(descriptor, min(1024 * 1024, before.st_size + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
            after = os.fstat(descriptor)
            identity = lambda item: (
                item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_nlink
            )
            if identity(before) != identity(after) or len(payload) != before.st_size:
                raise MaterializationError(f"{label} changed while read")
        finally:
            os.close(descriptor)
        value = json.loads(
            bytes(payload).decode("utf-8"), object_pairs_hook=_object_without_duplicates
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MaterializationError(f"could not load {label}: {error}") from error
    if not isinstance(value, dict):
        raise MaterializationError(f"{label} must be a JSON object")
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise MaterializationError(
            f"{label} keys differ: expected {sorted(expected)}, got {sorted(value)}"
        )


def _full_sha1(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise MaterializationError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise MaterializationError(f"{label} must be a lowercase SHA-256")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise MaterializationError(f"{label} must be a non-empty trimmed string")
    return value


def _safe_component(value: Any, label: str) -> str:
    text = _nonempty(value, label)
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if (
        len(text) > 128
        or not text[0].isalnum()
        or any(character not in allowed for character in text)
    ):
        raise MaterializationError(f"{label} must be one safe ASCII path component")
    return text


def _count(value: Any, label: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise MaterializationError(f"{label} must be an integer >= {minimum}")
    return value


def _repository(value: Any, label: str) -> str:
    text = _nonempty(value, label)
    parts = text.split("/")
    if len(parts) != 2 or any(part in {"", ".", ".."} for part in parts):
        raise MaterializationError(f"{label} must have owner/repository form")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    if any(character not in allowed for part in parts for character in part):
        raise MaterializationError(f"{label} contains unsupported characters")
    return text


def _relative_file(value: Any, label: str) -> str:
    return _safe_component(value, label)


def _facts_pending(package: Mapping[str, Any]) -> bool:
    return any(value is None for section in (package["archive"], package["output"]) for value in section.values())


def _gitlinks(value: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise MaterializationError(f"{label} must be an array")
    result: list[dict[str, str]] = []
    paths: set[str] = set()
    for index, raw in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(raw, dict):
            raise MaterializationError(f"{item_label} must be an object")
        _exact_keys(raw, GITLINK_KEYS, item_label)
        path = _nonempty(raw["path"], f"{item_label}.path")
        parts = path.split("/")
        if (
            path.startswith("/")
            or "\\" in path
            or "\0" in path
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise MaterializationError(f"{item_label}.path must be a safe canonical relative path")
        if path in paths or any(
            path.startswith(existing + "/") or existing.startswith(path + "/")
            for existing in paths
        ):
            raise MaterializationError(f"{label} paths overlap or repeat")
        if raw["mode"] != "160000" or raw["type"] != "commit":
            raise MaterializationError(f"{item_label} must describe a Git commit entry")
        _full_sha1(raw["sha"], f"{item_label}.sha")
        paths.add(path)
        result.append(dict(raw))
    if [item["path"] for item in result] != sorted(paths):
        raise MaterializationError(f"{label} must be sorted by path")
    return result


def _validate_facts(package: Mapping[str, Any], index: int, *, allow_pending: bool) -> None:
    archive = package["archive"]
    output = package["output"]
    if not isinstance(archive, dict) or not isinstance(output, dict):
        raise MaterializationError(f"packages[{index}] archive/output must be objects")
    _exact_keys(archive, ARCHIVE_KEYS, f"packages[{index}].archive")
    _exact_keys(output, OUTPUT_KEYS, f"packages[{index}].output")
    pending = _facts_pending(package)
    if pending:
        if not allow_pending:
            raise MaterializationError(f"package {package['name']} has pending acquisition facts")
        if any(value is not None for key, value in archive.items() if key != "exact_prefix") or any(
            value is not None for value in output.values()
        ):
            raise MaterializationError(f"package {package['name']} has partially populated facts")
        _nonempty(package["pending_reason"], f"packages[{index}].pending_reason")
        return
    if package["pending_reason"] is not None:
        raise MaterializationError(f"package {package['name']} has complete facts and a pending reason")
    _sha256(archive["sha256"], f"packages[{index}].archive.sha256")
    _sha256(archive["tar_sha256"], f"packages[{index}].archive.tar_sha256")
    _sha256(output["inventory_sha256"], f"packages[{index}].output.inventory_sha256")
    _full_sha1(output["archive_tree_sha"], f"packages[{index}].output.archive_tree_sha")
    _full_sha1(output["tree_sha"], f"packages[{index}].output.tree_sha")
    _gitlinks(output["gitlinks"], f"packages[{index}].output.gitlinks")
    for key in (
        "bytes", "tar_bytes", "members", "directories", "regular_files", "symlinks",
        "regular_bytes", "max_member_bytes",
    ):
        _count(archive[key], f"packages[{index}].archive.{key}", positive=key in {"bytes", "tar_bytes", "members"})
    for key in ("directories", "files", "regular_files", "symlinks", "bytes", "max_file_bytes"):
        _count(output[key], f"packages[{index}].output.{key}", positive=key == "files")
    if archive["bytes"] > HARD_MAX_ARCHIVE_BYTES or archive["tar_bytes"] > HARD_MAX_TAR_BYTES:
        raise MaterializationError(f"package {package['name']} exceeds hard archive bounds")
    if archive["members"] > HARD_MAX_MEMBERS or archive["max_member_bytes"] > HARD_MAX_MEMBER_BYTES:
        raise MaterializationError(f"package {package['name']} exceeds hard member bounds")
    if archive["regular_bytes"] > HARD_MAX_REGULAR_BYTES:
        raise MaterializationError(f"package {package['name']} exceeds hard regular-byte bound")
    if output["files"] != output["regular_files"] + output["symlinks"]:
        raise MaterializationError(f"package {package['name']} output file counts do not add up")


def load_pin(path: Path, *, allow_pending: bool = False) -> dict[str, Any]:
    value = _load_json(path, "Lake package pin")
    _exact_keys(
        value,
        {
            "schema_version", "lake_manifest_version", "packages_directory", "override_path",
            "root_manifest_sha256", "mathlib_manifest_sha256", "packages",
        },
        "Lake package pin",
    )
    if value["schema_version"] != SCHEMA_VERSION or value["lake_manifest_version"] != LAKE_SCHEMA_VERSION:
        raise MaterializationError("unsupported Lake package pin schema")
    if (
        value["packages_directory"] != PACKAGES_DIRECTORY.as_posix()
        or value["override_path"] != OVERRIDE_PATH.as_posix()
    ):
        raise MaterializationError("Lake package output paths differ from the canonical paths")
    _sha256(value["root_manifest_sha256"], "root_manifest_sha256")
    _sha256(value["mathlib_manifest_sha256"], "mathlib_manifest_sha256")
    packages = value["packages"]
    if not isinstance(packages, list) or len(packages) != 8:
        raise MaterializationError("Lake package pin must contain exactly eight packages")
    names: set[str] = set()
    repositories: set[str] = set()
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise MaterializationError(f"packages[{index}] must be an object")
        _exact_keys(package, PACKAGE_KEYS, f"packages[{index}]")
        name = _safe_component(package["name"], f"packages[{index}].name")
        scope = _nonempty(package["scope"], f"packages[{index}].scope")
        repository = _repository(package["repository"], f"packages[{index}].repository")
        revision = _full_sha1(package["revision"], f"packages[{index}].revision")
        _nonempty(package["input_revision"], f"packages[{index}].input_revision")
        _relative_file(package["config_file"], f"packages[{index}].config_file")
        _relative_file(package["manifest_file"], f"packages[{index}].manifest_file")
        if not isinstance(package["root_inherited"], bool) or not isinstance(package["mathlib_inherited"], bool):
            raise MaterializationError(f"packages[{index}] inherited flags must be booleans")
        expected_url = f"https://github.com/{repository}"
        expected_archive = f"https://codeload.github.com/{repository}/tar.gz/{revision}"
        expected_prefix = f"{repository.split('/')[1]}-{revision}/"
        if package["repository_url"] != expected_url or package["archive_url"] != expected_archive:
            raise MaterializationError(f"package {name} URLs do not derive from repository and revision")
        if package["archive"].get("exact_prefix") != expected_prefix:
            raise MaterializationError(f"package {name} archive prefix is not exact")
        if repository.split("/")[0] != scope:
            raise MaterializationError(f"package {name} scope differs from repository owner")
        if name in names or repository in repositories:
            raise MaterializationError("duplicate package name or repository")
        names.add(name)
        repositories.add(repository)
        _validate_facts(package, index, allow_pending=allow_pending)
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise MaterializationError(f"hash input is not one regular file: {path}")
            while chunk := os.read(descriptor, 1024 * 1024):
                digest.update(chunk)
            after = os.fstat(descriptor)
            identity = lambda item: (
                item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_nlink
            )
            if identity(before) != identity(after):
                raise MaterializationError(f"hash input changed while read: {path}")
        finally:
            os.close(descriptor)
    except OSError as error:
        raise MaterializationError(f"could not hash {path}: {error}") from error
    return digest.hexdigest()


def _assert_real_directory(path: Path) -> None:
    try:
        mode = path.stat(follow_symlinks=False).st_mode
    except OSError as error:
        raise MaterializationError(f"required directory is unavailable: {path}") from error
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise MaterializationError(f"required path is not a real directory: {path}")


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            mode = current.stat(follow_symlinks=False).st_mode
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MaterializationError(f"could not inspect path component {current}") from error
        if stat.S_ISLNK(mode):
            raise MaterializationError(f"path contains a symlink component: {current}")


def _directory_identity(value: os.stat_result) -> tuple[int, int]:
    if not stat.S_ISDIR(value.st_mode):
        raise MaterializationError("bound path is no longer a directory")
    return value.st_dev, value.st_ino


def _inspect_child_directory(parent_fd: int, name: str, label: str) -> bool:
    try:
        value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise MaterializationError(f"could not inspect {label}") from error
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
        raise MaterializationError(f"{label} must be a real directory")
    return True


def _open_child_directory(parent_fd: int, name: str, label: str) -> int:
    try:
        return os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise MaterializationError(f"could not bind {label}") from error


class BoundDirectory:
    def __init__(
        self, lexical_path: Path, descriptor: int, identity: tuple[int, int], label: str
    ) -> None:
        self.lexical_path = lexical_path
        self.descriptor = descriptor
        self.identity = identity
        self.label = label

    @property
    def path(self) -> Path:
        return Path(f"/proc/self/fd/{self.descriptor}")

    def assert_current(self) -> None:
        try:
            current = self.lexical_path.stat(follow_symlinks=False)
        except OSError as error:
            raise MaterializationError(f"{self.label} path incarnation changed") from error
        if stat.S_ISLNK(current.st_mode) or _directory_identity(current) != self.identity:
            raise MaterializationError(f"{self.label} path incarnation changed")


@contextmanager
def _bound_existing_directory(path: Path, label: str) -> Iterator[BoundDirectory]:
    absolute = Path(os.path.abspath(path))
    _assert_real_directory(absolute)
    _reject_symlink_components(absolute)
    try:
        descriptor = os.open(
            absolute,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as error:
        raise MaterializationError(f"could not bind {label}") from error
    bound = BoundDirectory(absolute, descriptor, _directory_identity(os.fstat(descriptor)), label)
    try:
        yield bound
    finally:
        os.close(descriptor)


@contextmanager
def _bound_output_directory(path: Path, label: str) -> Iterator[BoundDirectory]:
    absolute = Path(os.path.abspath(path))
    if not absolute.exists() and not absolute.is_symlink():
        name = _safe_component(absolute.name, label)
        with _bound_existing_directory(absolute.parent, f"{label} parent") as parent:
            try:
                os.mkdir(name, mode=0o700, dir_fd=parent.descriptor)
                os.fsync(parent.descriptor)
            except OSError as error:
                raise MaterializationError(f"could not create {label}") from error
            parent.assert_current()
    with _bound_existing_directory(absolute, label) as bound:
        yield bound


class BoundProjectLayout:
    def __init__(
        self,
        repo: BoundDirectory,
        lake: BoundDirectory,
        packages: BoundDirectory,
        runtime: BoundDirectory | None,
    ) -> None:
        self.repo = repo
        self.lake = lake
        self.packages = packages
        self.runtime = runtime

    @property
    def override(self) -> Path:
        return self.lake.path / "package-overrides.json"

    def assert_current(self) -> None:
        self.repo.assert_current()
        self.lake.assert_current()
        self.packages.assert_current()
        if self.runtime is not None:
            self.runtime.assert_current()


class BoundTransaction:
    def __init__(
        self,
        root: BoundDirectory,
        backup: BoundDirectory,
        staged: BoundDirectory,
        publication_path: Path,
        marker: Mapping[str, Any],
    ) -> None:
        self.root = root
        self.backup = backup
        self.staged = staged
        self.publication_path = publication_path
        self.marker = dict(marker)

    def assert_current(self) -> None:
        self.root.assert_current()
        self.backup.assert_current()
        self.staged.assert_current()

    def close(self) -> None:
        os.close(self.staged.descriptor)
        os.close(self.backup.descriptor)
        os.close(self.root.descriptor)


def _preflight_override(lake_fd: int) -> None:
    try:
        value = os.stat("package-overrides.json", dir_fd=lake_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as error:
        raise MaterializationError("could not inspect Lake package override") from error
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise MaterializationError("Lake package override must be one regular file")


@contextmanager
def _bound_project_layout(
    repo_root: Path, *, create: bool, include_runtime: bool
) -> Iterator[BoundProjectLayout]:
    with _bound_existing_directory(repo_root, "repository root") as repo:
        lake_exists = _inspect_child_directory(repo.descriptor, ".lake", ".lake")
        if not lake_exists:
            if not create:
                raise MaterializationError(".lake directory is unavailable")
            os.mkdir(".lake", mode=0o775, dir_fd=repo.descriptor)
            os.fsync(repo.descriptor)
        lake_fd = _open_child_directory(repo.descriptor, ".lake", ".lake")
        lake = BoundDirectory(
            repo_root / ".lake", lake_fd, _directory_identity(os.fstat(lake_fd)), ".lake"
        )
        package_fd: int | None = None
        runtime_fd: int | None = None
        try:
            _preflight_override(lake_fd)
            packages_exists = _inspect_child_directory(
                lake_fd, "packages", ".lake/packages"
            )
            runtime_exists = _inspect_child_directory(
                lake_fd, "lake-package-materialization", "package runtime"
            )
            if not packages_exists:
                if not create:
                    raise MaterializationError(".lake/packages directory is unavailable")
                os.mkdir("packages", mode=0o775, dir_fd=lake_fd)
            if include_runtime and not runtime_exists:
                if not create:
                    raise MaterializationError("package runtime directory is unavailable")
                os.mkdir("lake-package-materialization", mode=0o700, dir_fd=lake_fd)
            os.fsync(lake_fd)
            package_fd = _open_child_directory(lake_fd, "packages", ".lake/packages")
            packages = BoundDirectory(
                repo_root / PACKAGES_DIRECTORY,
                package_fd,
                _directory_identity(os.fstat(package_fd)),
                ".lake/packages",
            )
            runtime: BoundDirectory | None = None
            if include_runtime:
                runtime_fd = _open_child_directory(
                    lake_fd, "lake-package-materialization", "package runtime"
                )
                runtime = BoundDirectory(
                    repo_root / RUNTIME_DIRECTORY,
                    runtime_fd,
                    _directory_identity(os.fstat(runtime_fd)),
                    "package runtime",
                )
            yield BoundProjectLayout(repo, lake, packages, runtime)
        finally:
            if runtime_fd is not None:
                os.close(runtime_fd)
            if package_fd is not None:
                os.close(package_fd)
            os.close(lake_fd)


def _manifest_entries(document: Mapping[str, Any], label: str) -> list[dict[str, Any]]:
    packages = document.get("packages")
    if document.get("version") != LAKE_SCHEMA_VERSION or not isinstance(packages, list):
        raise MaterializationError(f"{label} has an unsupported schema")
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(packages):
        if not isinstance(entry, dict):
            raise MaterializationError(f"{label}.packages[{index}] is not an object")
        _exact_keys(entry, MANIFEST_ENTRY_KEYS, f"{label}.packages[{index}]")
        result.append(entry)
    return result


def validate_manifests(repo_root: Path, pin: Mapping[str, Any]) -> None:
    root_path = repo_root / ROOT_MANIFEST
    mathlib_path = repo_root / MATHLIB_MANIFEST_SNAPSHOT
    if (
        _file_sha256(root_path) != pin["root_manifest_sha256"]
        or _file_sha256(mathlib_path) != pin["mathlib_manifest_sha256"]
    ):
        raise MaterializationError("Lake manifest checksum differs from the package pin")
    root = _load_json(root_path, "root Lake manifest")
    mathlib = _load_json(mathlib_path, "Mathlib Lake manifest")
    root_entries = _manifest_entries(root, "root Lake manifest")
    mathlib_entries = _manifest_entries(mathlib, "Mathlib Lake manifest")
    if root.get("packagesDir") != PACKAGES_DIRECTORY.as_posix() or root.get("name") != "QPBT":
        raise MaterializationError("root Lake manifest identity differs")
    if mathlib.get("packagesDir") != PACKAGES_DIRECTORY.as_posix() or mathlib.get("name") != "mathlib":
        raise MaterializationError("Mathlib Lake manifest identity differs")
    root_by_name = {entry["name"]: entry for entry in root_entries}
    mathlib_by_name = {entry["name"]: entry for entry in mathlib_entries}
    if len(root_by_name) != len(root_entries) or len(mathlib_by_name) != len(mathlib_entries):
        raise MaterializationError("duplicate package name in Lake manifest")
    if set(root_by_name) != {"mathlib", *(package["name"] for package in pin["packages"])}:
        raise MaterializationError("root Lake manifest package set differs from pin")
    if set(mathlib_by_name) != {package["name"] for package in pin["packages"]}:
        raise MaterializationError("Mathlib Lake manifest package set differs from pin")
    for package in pin["packages"]:
        expected_common = {
            "url": package["repository_url"], "type": "git", "subDir": None,
            "scope": package["scope"], "rev": package["revision"], "name": package["name"],
            "manifestFile": package["manifest_file"], "inputRev": package["input_revision"],
            "configFile": package["config_file"],
        }
        for label, entry, inherited in (
            ("root", root_by_name[package["name"]], package["root_inherited"]),
            ("Mathlib", mathlib_by_name[package["name"]], package["mathlib_inherited"]),
        ):
            expected = {**expected_common, "inherited": inherited}
            if entry != expected:
                raise MaterializationError(f"{label} manifest entry differs for {package['name']}")


def _read_regular_exact_at(
    directory_fd: int, name: str, expected_bytes: int, label: str
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as error:
        raise MaterializationError(f"could not open {label}: {error}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != expected_bytes:
            raise MaterializationError(f"{label} identity or byte count differs")
        chunks: list[bytes] = []
        total = 0
        while total <= expected_bytes:
            chunk = os.read(descriptor, min(1024 * 1024, expected_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_nlink)
        if identity(before) != identity(after) or total != expected_bytes:
            raise MaterializationError(f"{label} changed while read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_regular_exact(path: Path, expected_bytes: int) -> bytes:
    with _bound_existing_directory(path.parent, "archive directory") as directory:
        payload = _read_regular_exact_at(
            directory.descriptor, path.name, expected_bytes, f"archive {path.name}"
        )
        directory.assert_current()
        return payload


def _decompress_exact(compressed: bytes, expected_bytes: int) -> bytes:
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = bytearray()
    try:
        for offset in range(0, len(compressed), 64 * 1024):
            remaining = expected_bytes + 1 - len(output)
            if remaining <= 0:
                raise MaterializationError("gzip output exceeds the pinned tar size")
            output.extend(decompressor.decompress(compressed[offset:offset + 64 * 1024], remaining))
            if decompressor.unconsumed_tail:
                raise MaterializationError("gzip output exceeds the pinned tar size")
        output.extend(decompressor.flush(expected_bytes + 1 - len(output)))
    except zlib.error as error:
        raise MaterializationError(f"invalid gzip archive: {error}") from error
    if not decompressor.eof or decompressor.unused_data or len(output) != expected_bytes:
        raise MaterializationError("gzip stream termination or tar byte count differs")
    return bytes(output)


def _octal(field: bytes, label: str) -> int:
    stripped = field.rstrip(b"\0 ").lstrip(b" ")
    if not stripped:
        return 0
    if any(character not in b"01234567" for character in stripped):
        raise MaterializationError(f"tar {label} is not canonical octal")
    return int(stripped, 8)


def _text(field: bytes, label: str) -> str:
    raw, separator, padding = field.partition(b"\0")
    if separator and any(padding):
        raise MaterializationError(f"tar {label} has nonzero NUL padding")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError(f"tar {label} is not UTF-8") from error


def _pax(payload: bytes) -> dict[str, str]:
    records: dict[str, str] = {}
    offset = 0
    while offset < len(payload):
        space = payload.find(b" ", offset)
        if space < 0 or not payload[offset:space].isdigit():
            raise MaterializationError("invalid global PAX length")
        length = int(payload[offset:space])
        record = payload[offset:offset + length]
        if len(record) != length or not record.endswith(b"\n"):
            raise MaterializationError("global PAX record length differs")
        key_value = record[space - offset + 1:-1]
        key, separator, value = key_value.partition(b"=")
        if not separator:
            raise MaterializationError("global PAX record lacks '='")
        try:
            decoded_key, decoded_value = key.decode("ascii"), value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MaterializationError("global PAX record is not text") from error
        if decoded_key in records:
            raise MaterializationError("duplicate global PAX key")
        records[decoded_key] = decoded_value
        offset += length
    return records


def _member_path(name: str, exact_prefix: str, *, directory: bool) -> str:
    if "\\" in name or name.startswith("/") or "\0" in name:
        raise MaterializationError(f"unsafe tar path {name!r}")
    if directory and not name.endswith("/"):
        raise MaterializationError(f"directory lacks trailing slash: {name!r}")
    normalized = name[:-1] if directory else name
    root = exact_prefix[:-1]
    if normalized == root:
        relative = ""
    elif normalized.startswith(exact_prefix):
        relative = normalized[len(exact_prefix):]
    else:
        raise MaterializationError(f"tar member is outside prefix {exact_prefix!r}")
    parts = relative.split("/") if relative else []
    if any(part in {"", ".", ".."} for part in parts):
        raise MaterializationError(f"unsafe normalized tar path {relative!r}")
    return relative


def _safe_symlink_target(relative: str, target: str) -> None:
    if not target or "\\" in target or target.startswith("/") or "\0" in target:
        raise MaterializationError(f"unsafe symlink target {target!r}")
    parts: list[str] = list(PurePosixPath(relative).parent.parts)
    for part in PurePosixPath(target).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise MaterializationError(f"symlink escapes package: {relative!r}")
            parts.pop()
        else:
            parts.append(part)


def _inventory_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        if entry["kind"] == "directory":
            line = f"d\0{entry['path']}\n"
        elif entry["kind"] == "symlink":
            line = f"l\0{entry['path']}\0{entry['target']}\n"
        else:
            line = f"f\0{entry['path']}\0{entry['mode']:o}\0{entry['size']}\0{entry['sha256']}\n"
        digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def inspect_archive_bytes(
    compressed: bytes, package: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    archive_pin = package["archive"]
    if len(compressed) > HARD_MAX_ARCHIVE_BYTES:
        raise MaterializationError("compressed archive exceeds hard bound")
    tar_bytes = _decompress_exact(compressed, archive_pin["tar_bytes"])
    if len(tar_bytes) > HARD_MAX_TAR_BYTES:
        raise MaterializationError("tar archive exceeds hard bound")
    offset = members = directories = regular_files = symlinks = regular_bytes = max_member = 0
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    global_pax = False
    complete = False
    while offset + BLOCK <= len(tar_bytes):
        header = tar_bytes[offset:offset + BLOCK]
        if header == bytes(BLOCK):
            if tar_bytes[offset + BLOCK:offset + 2 * BLOCK] != bytes(BLOCK) or any(tar_bytes[offset + 2 * BLOCK:]):
                raise MaterializationError("tar end markers or trailing bytes differ")
            complete = True
            break
        checksum = _octal(header[148:156], "checksum")
        if sum(header[:148] + b" " * 8 + header[156:]) != checksum:
            raise MaterializationError("tar header checksum mismatch")
        if header[257:263] != b"ustar\0" or header[263:265] != b"00":
            raise MaterializationError("tar member is not canonical ustar")
        name = _text(header[:100], "name")
        prefix = _text(header[345:500], "prefix")
        if prefix:
            name = f"{prefix}/{name}"
        link_name = _text(header[157:257], "link name")
        size = _octal(header[124:136], "size")
        mode = _octal(header[100:108], "mode")
        kind = header[156:157]
        payload_start = offset + BLOCK
        payload_end = payload_start + size
        padded_end = payload_start + ((size + BLOCK - 1) // BLOCK) * BLOCK
        if padded_end > len(tar_bytes) or any(tar_bytes[payload_end:padded_end]):
            raise MaterializationError("tar payload is truncated or padding is nonzero")
        payload = tar_bytes[payload_start:payload_end]
        offset = padded_end
        if size > HARD_MAX_MEMBER_BYTES:
            raise MaterializationError("tar member exceeds hard size bound")
        if kind == b"g":
            if (
                global_pax or members or name != "pax_global_header"
                or _pax(payload) != {"comment": package["revision"]}
            ):
                raise MaterializationError("global PAX header differs from exact revision")
            global_pax = True
            continue
        if kind not in {b"0", b"5", b"2"}:
            raise MaterializationError("tar contains a hardlink, special file, extension, or unsupported type")
        directory = kind == b"5"
        relative = _member_path(name, archive_pin["exact_prefix"], directory=directory)
        if relative in seen:
            raise MaterializationError(f"duplicate tar path {relative!r}")
        seen.add(relative)
        members += 1
        if members > HARD_MAX_MEMBERS:
            raise MaterializationError("tar member count exceeds hard bound")
        if relative == ".gitmodules":
            raise MaterializationError("package may contain gitlinks; .gitmodules is forbidden")
        if kind == b"5":
            if size or link_name or mode != CANONICAL_ARCHIVE_DIRECTORY_MODE:
                raise MaterializationError("directory metadata differs from canonical Git archive")
            directories += 1
            entries.append({"kind": "directory", "path": relative})
        elif kind == b"2":
            if size or mode != 0o777:
                raise MaterializationError("symlink metadata differs from canonical Git archive")
            _safe_symlink_target(relative, link_name)
            symlinks += 1
            entries.append({"kind": "symlink", "path": relative, "target": link_name})
        else:
            if link_name or mode not in CANONICAL_ARCHIVE_REGULAR_MODES:
                raise MaterializationError("regular file metadata differs from canonical Git archive")
            normalized_mode = CANONICAL_ARCHIVE_REGULAR_MODES[mode]
            regular_files += 1
            regular_bytes += size
            max_member = max(max_member, size)
            if regular_bytes > HARD_MAX_REGULAR_BYTES:
                raise MaterializationError("tar regular bytes exceed hard bound")
            entries.append({
                "kind": "file", "path": relative, "mode": normalized_mode, "size": size,
                "sha256": hashlib.sha256(payload).hexdigest(), "payload": payload,
            })
    if not complete or not global_pax:
        raise MaterializationError("tar archive is incomplete or lacks exact global provenance")
    entry_kinds = {entry["path"]: entry["kind"] for entry in entries}
    if entry_kinds.get("") != "directory":
        raise MaterializationError("tar archive lacks its exact root directory")
    for entry in entries:
        parent = PurePosixPath(entry["path"]).parent
        while parent != PurePosixPath("."):
            parent_text = parent.as_posix()
            if entry_kinds.get(parent_text) != "directory":
                raise MaterializationError(
                    f"tar member has a missing or non-directory parent: {entry['path']!r}"
                )
            parent = parent.parent
    gitlinks = _gitlinks(package["output"]["gitlinks"], "package output gitlinks")
    gitlink_paths = {gitlink["path"] for gitlink in gitlinks}
    for path in gitlink_paths:
        if entry_kinds.get(path) != "directory" or any(
            entry_path.startswith(path + "/") for entry_path in entry_kinds
        ):
            raise MaterializationError(f"Gitlink placeholder is missing or nonempty: {path}")
    for path, kind in entry_kinds.items():
        if not path or kind != "directory" or path in gitlink_paths:
            continue
        if not any(entry_path.startswith(path + "/") for entry_path in entry_kinds):
            raise MaterializationError(f"unpinned empty archive directory: {path}")
    facts = {
        "archive": {
            "sha256": hashlib.sha256(compressed).hexdigest(), "bytes": len(compressed),
            "tar_sha256": hashlib.sha256(tar_bytes).hexdigest(), "tar_bytes": len(tar_bytes),
            "exact_prefix": archive_pin["exact_prefix"], "members": members,
            "directories": directories, "regular_files": regular_files, "symlinks": symlinks,
            "regular_bytes": regular_bytes, "max_member_bytes": max_member,
        },
        "output": {
            "directories": directories, "files": regular_files + symlinks,
            "regular_files": regular_files, "symlinks": symlinks, "bytes": regular_bytes,
            "max_file_bytes": max_member, "inventory_sha256": _inventory_digest(entries),
            "gitlinks": gitlinks,
        },
    }
    return facts, entries


def _compare_facts(package: Mapping[str, Any], facts: Mapping[str, Any]) -> None:
    for section in ("archive", "output"):
        for key, observed in facts[section].items():
            expected = package[section][key]
            if observed != expected:
                raise MaterializationError(
                    f"{package['name']} {section}.{key} differs: expected {expected!r}, got {observed!r}"
                )


def _write_entries(destination: Path, entries: Sequence[Mapping[str, Any]]) -> None:
    destination.mkdir(mode=0o700)
    for entry in sorted(entries, key=lambda item: (item["path"].count("/"), item["path"])):
        path = destination / entry["path"]
        if entry["kind"] == "directory":
            path.mkdir(mode=0o755, exist_ok=True)
        elif entry["kind"] == "symlink":
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            os.symlink(entry["target"], path)
        else:
            path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, entry["mode"])
            try:
                view = memoryview(entry["payload"])
                while view:
                    written = os.write(descriptor, view)
                    view = view[written:]
                os.fchmod(descriptor, entry["mode"])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    for directory, _, _ in os.walk(destination, topdown=False, followlinks=False):
        _fsync_directory(Path(directory))


def _git_environment() -> dict[str, str]:
    environment = {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "LANG": "C"}
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})
    return environment


def _run_git(arguments: Sequence[str], cwd: Path) -> str:
    command = ["git", *arguments]
    inherited_descriptors: set[int] = set()
    marker = "/proc/self/fd/"
    for value in (str(cwd), *arguments):
        offset = 0
        while (position := value.find(marker, offset)) >= 0:
            start = position + len(marker)
            end = start
            while end < len(value) and value[end].isdigit():
                end += 1
            if end > start:
                inherited_descriptors.add(int(value[start:end]))
            offset = end
    try:
        result = subprocess.run(
            command, cwd=cwd, env=_git_environment(), text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, shell=False, timeout=30,
            pass_fds=tuple(sorted(inherited_descriptors)),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise MaterializationError(f"bounded Git tree command failed: {error}") from error
    if result.returncode != 0:
        raise MaterializationError(f"Git tree command failed: {result.stderr.strip()}")
    return result.stdout.strip()


def compute_tree_sha(
    source: Path, scratch: Path, gitlinks: Sequence[Mapping[str, str]]
) -> str:
    scratch.mkdir(parents=True)
    bare = scratch / "tree.git"
    _run_git(["init", "--bare", "--quiet", str(bare)], scratch)
    prefix = [
        f"--git-dir={bare}", f"--work-tree={source}",
        "-c", "core.autocrlf=false", "-c", "core.filemode=true",
        "-c", "core.symlinks=true",
    ]
    _run_git([*prefix, "add", "--all", "--force"], scratch)
    for gitlink in _gitlinks(list(gitlinks), "Git tree gitlinks"):
        placeholder = source / gitlink["path"]
        if placeholder.is_symlink() or not placeholder.is_dir() or any(placeholder.iterdir()):
            raise MaterializationError(f"Gitlink placeholder is missing or nonempty: {gitlink['path']}")
        _run_git(
            [
                *prefix, "update-index", "--add", "--cacheinfo",
                gitlink["mode"], gitlink["sha"], gitlink["path"],
            ],
            scratch,
        )
    tree = _run_git([*prefix, "write-tree"], scratch)
    return _full_sha1(tree, "computed Git tree")


def _materialize_archive_bytes(
    compressed: bytes, package: Mapping[str, Any], stage: Path
) -> tuple[dict[str, Any], Path]:
    facts, entries = inspect_archive_bytes(compressed, package)
    _compare_facts(package, facts)
    source = stage / package["name"]
    _write_entries(source, entries)
    for required in (package["config_file"], package["manifest_file"]):
        required_path = source / required
        if not required_path.is_file() or required_path.is_symlink():
            raise MaterializationError(f"{package['name']} lacks required regular file {required}")
    archive_tree = compute_tree_sha(source, stage / f".{package['name']}-archive-git", [])
    if archive_tree != package["output"]["archive_tree_sha"]:
        raise MaterializationError(
            f"{package['name']} archive Git tree differs: "
            f"expected {package['output']['archive_tree_sha']}, got {archive_tree}"
        )
    tree = compute_tree_sha(source, stage / f".{package['name']}-git", package["output"]["gitlinks"])
    if tree != package["output"]["tree_sha"]:
        raise MaterializationError(
            f"{package['name']} Git tree differs: expected {package['output']['tree_sha']}, got {tree}"
        )
    facts["output"]["archive_tree_sha"] = archive_tree
    facts["output"]["tree_sha"] = tree
    return facts, source


def inspect_archive(path: Path, package: Mapping[str, Any], stage: Path) -> tuple[dict[str, Any], Path]:
    compressed = _read_regular_exact(path, package["archive"]["bytes"])
    return _materialize_archive_bytes(compressed, package, stage)


def _inspect_archive_at(
    archive_directory_fd: int,
    archive_name: str,
    package: Mapping[str, Any],
    stage: Path,
) -> tuple[dict[str, Any], Path]:
    compressed = _read_regular_exact_at(
        archive_directory_fd,
        archive_name,
        package["archive"]["bytes"],
        f"archive {archive_name}",
    )
    return _materialize_archive_bytes(compressed, package, stage)


def override_document(pin: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": LAKE_SCHEMA_VERSION,
        "packages": [
            {
                "type": "path", "name": package["name"], "scope": package["scope"],
                "inherited": package["root_inherited"],
                "dir": (PACKAGES_DIRECTORY / package["name"]).as_posix(),
                "configFile": package["config_file"], "manifestFile": package["manifest_file"],
            }
            for package in pin["packages"]
        ],
    }


def _atomic_json(path: Path, value: Any) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        payload = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("ascii")
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _locked(path: Path, *, parent_descriptor: int | None = None) -> Iterator[None]:
    if parent_descriptor is None:
        try:
            parent_descriptor = os.open(
                path.parent,
                os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            )
        except OSError as error:
            raise MaterializationError("could not bind package materialization lock directory") from error
    else:
        try:
            parent_descriptor = os.dup(parent_descriptor)
        except OSError as error:
            raise MaterializationError("could not duplicate package materialization lock directory") from error
    try:
        # Lock the stable runtime directory so replacing the lock pathname cannot
        # create a second election while another materializer is active.
        fcntl.flock(parent_descriptor, fcntl.LOCK_EX)
    except OSError as error:
        os.close(parent_descriptor)
        raise MaterializationError("could not acquire package materialization lock directory") from error
    try:
        descriptor = os.open(
            path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
    except OSError as error:
        fcntl.flock(parent_descriptor, fcntl.LOCK_UN)
        os.close(parent_descriptor)
        raise MaterializationError("could not bind package materialization lock") from error
    try:
        lock_stat = os.fstat(descriptor)
        path_stat = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(lock_stat.st_mode)
            or lock_stat.st_nlink != 1
            or lock_stat.st_dev != path_stat.st_dev
            or lock_stat.st_ino != path_stat.st_ino
        ):
            raise MaterializationError("package materialization lock is not one bound regular file")
        yield
    finally:
        os.close(descriptor)
        fcntl.flock(parent_descriptor, fcntl.LOCK_UN)
        os.close(parent_descriptor)


TRANSACTION_SCHEMA_VERSION = 1
TRANSACTION_NAME = "transaction"
TRANSACTION_CLEANUP_NAME = "transaction.cleanup"


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _child_identity_matches(parent_fd: int, name: str, identity: tuple[int, int]) -> bool:
    try:
        value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise MaterializationError(f"could not inspect selected transaction path {name}") from error
    return stat.S_ISDIR(value.st_mode) and _directory_identity(value) == identity


class BoundChild:
    def __init__(
        self,
        descriptor: int,
        identity: tuple[int, ...],
        is_directory: bool,
        label: str,
    ) -> None:
        self.descriptor = descriptor
        self.identity = identity
        self.is_directory = is_directory
        self.label = label

    def matches(self, parent_fd: int, name: str) -> bool:
        try:
            value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return False
        except OSError as error:
            raise MaterializationError(f"could not inspect {self.label}") from error
        expected_type = stat.S_ISDIR if self.is_directory else stat.S_ISREG
        identity = (value.st_dev, value.st_ino)
        if not self.is_directory:
            identity += (value.st_size, value.st_mtime_ns, value.st_nlink)
        return expected_type(value.st_mode) and identity == self.identity

    def close(self) -> None:
        os.close(self.descriptor)


def _bind_child(parent_fd: int, name: str, label: str, *, directory: bool) -> BoundChild:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if directory:
        flags |= os.O_DIRECTORY
    else:
        flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise MaterializationError(f"could not bind {label}") from error
    try:
        value = os.fstat(descriptor)
        expected_type = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected_type(value.st_mode) or (not directory and value.st_nlink != 1):
            raise MaterializationError(f"{label} has an unsafe type or link count")
        identity = (value.st_dev, value.st_ino)
        if not directory:
            identity += (value.st_size, value.st_mtime_ns, value.st_nlink)
        bound = BoundChild(descriptor, identity, directory, label)
        if not bound.matches(parent_fd, name):
            raise MaterializationError(f"{label} changed while binding")
        return bound
    except Exception:
        os.close(descriptor)
        raise


def _locate_bound_child(
    child: BoundChild, parents: Sequence[BoundDirectory]
) -> tuple[BoundDirectory, str] | None:
    for parent in parents:
        try:
            names = os.listdir(parent.descriptor)
        except OSError as error:
            raise MaterializationError(f"could not search for {child.label}") from error
        for name in names:
            if child.matches(parent.descriptor, name):
                return parent, name
    return None


def _child_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise MaterializationError(f"could not inspect selected child {name}") from error
    return True


def _quarantine_child(
    layout: BoundProjectLayout, parent_fd: int, name: str, label: str
) -> None:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    quarantine = f"rejected-{label}-{value.st_dev:x}-{value.st_ino:x}"
    if _child_exists(layout.runtime.descriptor, quarantine):
        raise MaterializationError(f"quarantine destination already exists for {label}")
    os.rename(
        name,
        quarantine,
        src_dir_fd=parent_fd,
        dst_dir_fd=layout.runtime.descriptor,
    )
    os.fsync(parent_fd)
    os.fsync(layout.runtime.descriptor)


def _move_bound_child(
    child: BoundChild,
    source: tuple[BoundDirectory, str],
    destination: tuple[BoundDirectory, str],
) -> None:
    source_parent, source_name = source
    destination_parent, destination_name = destination
    os.rename(
        source_name,
        destination_name,
        src_dir_fd=source_parent.descriptor,
        dst_dir_fd=destination_parent.descriptor,
    )
    os.fsync(source_parent.descriptor)
    if source_parent.descriptor != destination_parent.descriptor:
        os.fsync(destination_parent.descriptor)
    if not child.matches(destination_parent.descriptor, destination_name):
        raise MaterializationError(f"{child.label} changed during descriptor-relative move")


def _transaction_entries_current(runtime: BoundDirectory, transaction: BoundTransaction) -> bool:
    return (
        _child_identity_matches(
            runtime.descriptor, TRANSACTION_NAME, transaction.root.identity
        )
        and _child_identity_matches(
            transaction.root.descriptor, "backup", transaction.backup.identity
        )
        and _child_identity_matches(
            transaction.root.descriptor, "new", transaction.staged.identity
        )
    )


def _clear_directory_descriptor(descriptor: int) -> None:
    for name in os.listdir(descriptor):
        value = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        if stat.S_ISDIR(value.st_mode):
            child = _open_child_directory(descriptor, name, "selected transaction child")
            identity = _directory_identity(os.fstat(child))
            try:
                _clear_directory_descriptor(child)
            finally:
                os.close(child)
            if not _child_identity_matches(descriptor, name, identity):
                raise MaterializationError("selected transaction child changed during cleanup")
            os.rmdir(name, dir_fd=descriptor)
        else:
            os.unlink(name, dir_fd=descriptor)
    os.fsync(descriptor)


def _dispose_bound_transaction(runtime: BoundDirectory, transaction: BoundTransaction) -> None:
    if not _transaction_entries_current(runtime, transaction):
        raise MaterializationError("selected transaction path incarnation changed")
    try:
        os.stat(TRANSACTION_CLEANUP_NAME, dir_fd=runtime.descriptor, follow_symlinks=False)
    except FileNotFoundError:
        pass
    except OSError as error:
        raise MaterializationError("could not inspect transaction cleanup") from error
    else:
        raise MaterializationError("stale committed transaction cleanup exists")
    os.rename(
        TRANSACTION_NAME,
        TRANSACTION_CLEANUP_NAME,
        src_dir_fd=runtime.descriptor,
        dst_dir_fd=runtime.descriptor,
    )
    os.fsync(runtime.descriptor)
    if not _child_identity_matches(
        runtime.descriptor, TRANSACTION_CLEANUP_NAME, transaction.root.identity
    ):
        raise MaterializationError("selected transaction changed during cleanup")
    _clear_directory_descriptor(transaction.root.descriptor)
    os.rmdir(TRANSACTION_CLEANUP_NAME, dir_fd=runtime.descriptor)
    os.fsync(runtime.descriptor)


def _disarm_selected_transaction(transaction: BoundTransaction) -> None:
    try:
        value = os.stat("transaction.json", dir_fd=transaction.root.descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    except OSError as error:
        raise MaterializationError("could not inspect selected transaction marker") from error
    if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise MaterializationError("selected transaction marker is not one regular file")
    os.unlink("transaction.json", dir_fd=transaction.root.descriptor)
    os.fsync(transaction.root.descriptor)


def _transaction_marker(pin: Mapping[str, Any], packages_root: Path, override: Path) -> dict[str, Any]:
    packages = [package["name"] for package in pin["packages"]]
    return {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "packages": packages,
        "original_presence": {
            name: (packages_root / name).exists() or (packages_root / name).is_symlink()
            for name in packages
        },
        "override_present": override.exists() or override.is_symlink(),
    }


def _load_transaction_marker(transaction: Path, pin: Mapping[str, Any]) -> dict[str, Any]:
    marker = _load_json(transaction / "transaction.json", "package transaction marker")
    expected_names = [package["name"] for package in pin["packages"]]
    _exact_keys(
        marker,
        {"schema_version", "packages", "original_presence", "override_present"},
        "package transaction marker",
    )
    if marker["schema_version"] != TRANSACTION_SCHEMA_VERSION or marker["packages"] != expected_names:
        raise MaterializationError("package transaction marker differs from the exact pin")
    presence = marker["original_presence"]
    if (
        not isinstance(presence, dict)
        or set(presence) != set(expected_names)
        or any(not isinstance(value, bool) for value in presence.values())
        or not isinstance(marker["override_present"], bool)
    ):
        raise MaterializationError("package transaction marker has invalid presence facts")
    return marker


def _bind_existing_transaction(
    layout: BoundProjectLayout, pin: Mapping[str, Any]
) -> BoundTransaction | None:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    if not _inspect_child_directory(
        layout.runtime.descriptor, TRANSACTION_NAME, "package transaction state"
    ):
        return None
    root_fd = _open_child_directory(
        layout.runtime.descriptor, TRANSACTION_NAME, "package transaction"
    )
    backup_fd: int | None = None
    staged_fd: int | None = None
    try:
        backup_fd = _open_child_directory(root_fd, "backup", "package transaction backup")
        staged_fd = _open_child_directory(root_fd, "new", "package transaction stage")
        lexical_root = layout.runtime.lexical_path / TRANSACTION_NAME
        marker = _load_transaction_marker(Path(f"/proc/self/fd/{root_fd}"), pin)
        transaction = BoundTransaction(
            BoundDirectory(
                lexical_root, root_fd, _directory_identity(os.fstat(root_fd)), "package transaction"
            ),
            BoundDirectory(
                lexical_root / "backup",
                backup_fd,
                _directory_identity(os.fstat(backup_fd)),
                "package transaction backup",
            ),
            BoundDirectory(
                lexical_root / "new",
                staged_fd,
                _directory_identity(os.fstat(staged_fd)),
                "package transaction stage",
            ),
            lexical_root,
            marker,
        )
        layout.assert_current()
        transaction.assert_current()
        if not _transaction_entries_current(layout.runtime, transaction):
            raise MaterializationError("package transaction identity changed while binding")
        return transaction
    except Exception:
        if staged_fd is not None:
            os.close(staged_fd)
        if backup_fd is not None:
            os.close(backup_fd)
        os.close(root_fd)
        raise


def _restore_bound_transaction(
    layout: BoundProjectLayout, transaction: BoundTransaction
) -> None:
    marker = transaction.marker
    packages_root = layout.packages.path
    override = layout.override
    backup = transaction.backup.path
    override_backup = transaction.root.path / "override.json"
    for name in reversed(marker["packages"]):
        destination = packages_root / name
        saved = backup / name
        if marker["original_presence"][name]:
            if saved.exists() or saved.is_symlink():
                if saved.is_symlink() or not saved.is_dir():
                    raise MaterializationError(f"unsafe backup package {name}")
                _remove_path(destination)
                os.replace(saved, destination)
                os.fsync(transaction.backup.descriptor)
                os.fsync(layout.packages.descriptor)
            elif not destination.is_dir() or destination.is_symlink():
                raise MaterializationError(f"cannot recover original package {name}")
        else:
            if saved.exists() or saved.is_symlink():
                raise MaterializationError(f"unexpected backup for absent package {name}")
            _remove_path(destination)
    if marker["override_present"]:
        if override_backup.exists() or override_backup.is_symlink():
            if override_backup.is_symlink() or not override_backup.is_file():
                raise MaterializationError("unsafe backup Lake package override")
            _remove_path(override)
            os.replace(override_backup, override)
            os.fsync(transaction.root.descriptor)
            os.fsync(layout.lake.descriptor)
        elif not override.is_file() or override.is_symlink():
            raise MaterializationError("cannot recover original Lake package override")
    else:
        if override_backup.exists() or override_backup.is_symlink():
            raise MaterializationError("unexpected backup for absent Lake package override")
        _remove_path(override)
    os.fsync(layout.packages.descriptor)
    os.fsync(layout.lake.descriptor)


def _restore_selected_transaction(
    layout: BoundProjectLayout,
    transaction: BoundTransaction,
    original_packages: Mapping[str, BoundChild],
    staged_packages: Mapping[str, BoundChild],
    original_override: BoundChild | None,
) -> None:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    marker = transaction.marker
    for name in reversed(marker["packages"]):
        original = original_packages.get(name)
        staged = staged_packages[name]
        if original is not None and original.matches(layout.packages.descriptor, name):
            continue
        if _child_exists(layout.packages.descriptor, name):
            if staged.matches(layout.packages.descriptor, name):
                if _child_exists(transaction.staged.descriptor, name):
                    _quarantine_child(
                        layout, transaction.staged.descriptor, name, f"stage-slot-{name}"
                    )
                _move_bound_child(
                    staged,
                    (layout.packages, name),
                    (transaction.staged, name),
                )
            else:
                _quarantine_child(layout, layout.packages.descriptor, name, f"package-{name}")
        if original is not None:
            selected = _locate_bound_child(
                original, (layout.packages, transaction.backup)
            )
            if selected is None:
                raise MaterializationError(f"cannot locate selected original package {name}")
            _move_bound_child(original, selected, (layout.packages, name))
        if _child_exists(transaction.backup.descriptor, name):
            _quarantine_child(
                layout, transaction.backup.descriptor, name, f"backup-package-{name}"
            )

    override_current = original_override is not None and original_override.matches(
        layout.lake.descriptor, "package-overrides.json"
    )
    if not override_current:
        if _child_exists(layout.lake.descriptor, "package-overrides.json"):
            _quarantine_child(
                layout,
                layout.lake.descriptor,
                "package-overrides.json",
                "published-override",
            )
        if original_override is not None:
            selected_override = _locate_bound_child(
                original_override, (layout.lake, transaction.root)
            )
            if selected_override is None:
                raise MaterializationError("cannot locate selected original Lake package override")
            _move_bound_child(
                original_override,
                selected_override,
                (layout.lake, "package-overrides.json"),
            )
    if _child_exists(transaction.root.descriptor, "override.json"):
        _quarantine_child(
            layout,
            transaction.root.descriptor,
            "override.json",
            "backup-override",
        )
    os.fsync(layout.packages.descriptor)
    os.fsync(layout.lake.descriptor)


def _rollback_bound_transaction(
    layout: BoundProjectLayout,
    transaction: BoundTransaction,
    *,
    original_packages: Mapping[str, BoundChild] | None = None,
    staged_packages: Mapping[str, BoundChild] | None = None,
    original_override: BoundChild | None = None,
) -> None:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    if original_packages is None or staged_packages is None:
        _restore_bound_transaction(layout, transaction)
    else:
        _restore_selected_transaction(
            layout,
            transaction,
            original_packages,
            staged_packages,
            original_override,
        )
    if _transaction_entries_current(layout.runtime, transaction):
        _dispose_bound_transaction(layout.runtime, transaction)
    else:
        _clear_directory_descriptor(transaction.backup.descriptor)
        _clear_directory_descriptor(transaction.staged.descriptor)
        _disarm_selected_transaction(transaction)


def _recover_transaction(layout: BoundProjectLayout, pin: Mapping[str, Any]) -> bool:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    layout.assert_current()
    runtime = layout.runtime.path
    cleanup = runtime / TRANSACTION_CLEANUP_NAME
    if cleanup.exists() or cleanup.is_symlink():
        if cleanup.is_symlink() or not cleanup.is_dir():
            raise MaterializationError("unsafe committed transaction cleanup")
        shutil.rmtree(cleanup)
        _fsync_directory(runtime)
    transaction = _bind_existing_transaction(layout, pin)
    if transaction is None:
        return False
    try:
        _restore_bound_transaction(layout, transaction)
        layout.assert_current()
        transaction.assert_current()
        _dispose_bound_transaction(layout.runtime, transaction)
        return True
    finally:
        transaction.close()


def _begin_transaction(
    layout: BoundProjectLayout, pin: Mapping[str, Any], *, replace_existing: bool
) -> BoundTransaction:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    layout.assert_current()
    packages_root = layout.packages.path
    runtime = layout.runtime.path
    override = layout.override
    for package in pin["packages"]:
        destination = packages_root / package["name"]
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise MaterializationError(f"unsafe existing package destination {destination}")
            if not replace_existing:
                raise MaterializationError(f"package destination already exists: {destination}")
    if override.exists() or override.is_symlink():
        if override.is_symlink() or not override.is_file():
            raise MaterializationError("unsafe existing Lake package override")
    transaction = runtime / TRANSACTION_NAME
    transaction.mkdir(mode=0o700)
    (transaction / "backup").mkdir()
    (transaction / "new").mkdir()
    marker = _transaction_marker(pin, packages_root, override)
    _atomic_json(transaction / "transaction.json", marker)
    _fsync_directory(transaction)
    _fsync_directory(runtime)
    root_fd = _open_child_directory(layout.runtime.descriptor, TRANSACTION_NAME, "package transaction")
    backup_fd: int | None = None
    staged_fd: int | None = None
    try:
        backup_fd = _open_child_directory(root_fd, "backup", "package transaction backup")
        staged_fd = _open_child_directory(root_fd, "new", "package transaction stage")
        lexical_root = layout.runtime.lexical_path / TRANSACTION_NAME
        bound = BoundTransaction(
            BoundDirectory(
                lexical_root, root_fd, _directory_identity(os.fstat(root_fd)), "package transaction"
            ),
            BoundDirectory(
                lexical_root / "backup",
                backup_fd,
                _directory_identity(os.fstat(backup_fd)),
                "package transaction backup",
            ),
            BoundDirectory(
                lexical_root / "new",
                staged_fd,
                _directory_identity(os.fstat(staged_fd)),
                "package transaction stage",
            ),
            transaction,
            marker,
        )
        bound.assert_current()
        return bound
    except Exception:
        if staged_fd is not None:
            os.close(staged_fd)
        if backup_fd is not None:
            os.close(backup_fd)
        os.close(root_fd)
        raise


def _publish(
    layout: BoundProjectLayout,
    pin: Mapping[str, Any],
    transaction: BoundTransaction,
    *,
    replace: Callable[[os.PathLike[str] | str, os.PathLike[str] | str], None] = os.replace,
) -> None:
    if layout.runtime is None:
        raise MaterializationError("package runtime is not bound")
    layout.assert_current()
    transaction.assert_current()
    packages_root = layout.packages.path
    backup = transaction.backup.path
    staged = transaction.staged.path
    override = layout.override
    override_backup = transaction.root.path / "override.json"
    selected_children: list[BoundChild] = []
    original_packages: dict[str, BoundChild] = {}
    staged_packages: dict[str, BoundChild] = {}
    original_override: BoundChild | None = None
    bindings_complete = False
    try:
        for package in pin["packages"]:
            name = package["name"]
            if transaction.marker["original_presence"][name]:
                original = _bind_child(
                    layout.packages.descriptor,
                    name,
                    f"selected original package {name}",
                    directory=True,
                )
                original_packages[name] = original
                selected_children.append(original)
            selected = _bind_child(
                transaction.staged.descriptor,
                name,
                f"selected staged package {name}",
                directory=True,
            )
            staged_packages[name] = selected
            selected_children.append(selected)
        if transaction.marker["override_present"]:
            original_override = _bind_child(
                layout.lake.descriptor,
                "package-overrides.json",
                "selected original Lake package override",
                directory=False,
            )
            selected_children.append(original_override)
        bindings_complete = True

        for package in pin["packages"]:
            name = package["name"]
            destination = packages_root / name
            original = original_packages.get(name)
            if original is not None and not original.matches(layout.packages.descriptor, name):
                raise MaterializationError(
                    f"selected original package {name} changed before publication"
                )
            if original is None and _child_exists(layout.packages.descriptor, name):
                raise MaterializationError(
                    f"unexpected package destination {name} appeared before publication"
                )
            if destination.exists() or destination.is_symlink():
                replace(destination, backup / name)
                if original is None or not original.matches(transaction.backup.descriptor, name):
                    raise MaterializationError(
                        f"selected original package {name} changed during publication"
                    )
                layout.assert_current()
                transaction.assert_current()
                _fsync_directory(packages_root)
                _fsync_directory(backup)
            if not staged_packages[name].matches(transaction.staged.descriptor, name):
                raise MaterializationError(
                    f"selected staged package {name} changed before publication"
                )
            replace(staged / name, destination)
            if not staged_packages[name].matches(layout.packages.descriptor, name):
                raise MaterializationError(
                    f"selected staged package {name} changed during publication"
                )
            layout.assert_current()
            transaction.assert_current()
            _fsync_directory(staged)
            _fsync_directory(packages_root)
        if override.exists() or override.is_symlink():
            if original_override is None or not original_override.matches(
                layout.lake.descriptor, "package-overrides.json"
            ):
                raise MaterializationError(
                    "selected original Lake package override changed before publication"
                )
            if override.is_symlink() or not override.is_file():
                raise MaterializationError("unsafe existing Lake package override")
            replace(override, override_backup)
            if original_override is None or not original_override.matches(
                transaction.root.descriptor, "override.json"
            ):
                raise MaterializationError(
                    "selected original Lake package override changed during publication"
                )
            layout.assert_current()
            transaction.assert_current()
            _fsync_directory(override.parent)
            _fsync_directory(transaction.root.path)
        _atomic_json(override, override_document(pin))
        layout.assert_current()
        transaction.assert_current()
        _fsync_directory(packages_root)
        _fsync_directory(override.parent)
    except Exception as error:
        try:
            _rollback_bound_transaction(
                layout,
                transaction,
                original_packages=original_packages if bindings_complete else None,
                staged_packages=staged_packages if bindings_complete else None,
                original_override=original_override if bindings_complete else None,
            )
        except Exception as rollback_error:
            raise MaterializationError(
                f"publication failed ({error}); rollback incomplete in "
                f"{transaction.publication_path}: {rollback_error}"
            ) from rollback_error
        raise MaterializationError(f"publication failed and was rolled back: {error}") from error
    else:
        layout.assert_current()
        transaction.assert_current()
        for name, selected in staged_packages.items():
            if not selected.matches(layout.packages.descriptor, name):
                raise MaterializationError(f"published package {name} identity differs")
        _dispose_bound_transaction(layout.runtime, transaction)
    finally:
        for child in reversed(selected_children):
            child.close()


def materialize(
    repo_root: Path,
    pin_path: Path,
    archive_directory: Path,
    *,
    replace_existing: bool = False,
    _replace: Callable[[os.PathLike[str] | str, os.PathLike[str] | str], None] = os.replace,
) -> dict[str, Any]:
    started = time.monotonic()
    repo_root = Path(os.path.abspath(repo_root))
    _assert_real_directory(repo_root)
    _assert_real_directory(archive_directory)
    _reject_symlink_components(repo_root)
    _reject_symlink_components(archive_directory)
    expected_pin = repo_root / PIN_RELATIVE_PATH
    if Path(os.path.abspath(pin_path)) != expected_pin:
        raise MaterializationError(f"pin path must be {PIN_RELATIVE_PATH}")
    pin = load_pin(pin_path)
    validate_manifests(repo_root, pin)
    with (
        _bound_existing_directory(archive_directory, "archive directory") as archive_root,
        _bound_project_layout(repo_root, create=True, include_runtime=True) as layout,
    ):
        if layout.runtime is None:
            raise MaterializationError("package runtime is not bound")
        with _locked(layout.runtime.path / "lock", parent_descriptor=layout.runtime.descriptor):
            layout.assert_current()
            archive_root.assert_current()
            _recover_transaction(layout, pin)
            transaction = _begin_transaction(layout, pin, replace_existing=replace_existing)
            try:
                stage = transaction.staged.path
                facts: dict[str, Any] = {}
                publication_started = False
                try:
                    for package in pin["packages"]:
                        archive_name = f"{package['name']}-{package['revision']}.tar.gz"
                        observed, _ = _inspect_archive_at(
                            archive_root.descriptor, archive_name, package, stage
                        )
                        archive_root.assert_current()
                        layout.assert_current()
                        transaction.assert_current()
                        facts[package["name"]] = observed
                    _fsync_directory(stage)
                    publication_started = True
                    _publish(layout, pin, transaction, replace=_replace)
                except Exception:
                    if not publication_started:
                        _rollback_bound_transaction(layout, transaction)
                    raise
            finally:
                transaction.close()
            layout.assert_current()
            archive_root.assert_current()
    return {
        "status": "published", "packages": [package["name"] for package in pin["packages"]],
        "override": OVERRIDE_PATH.as_posix(), "facts": facts,
        "elapsed_seconds": round(time.monotonic() - started, 6),
    }


def _scan_tree(root: Path) -> None:
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in [*names, *files]:
            path = base / name
            mode = path.stat(follow_symlinks=False).st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
                raise MaterializationError(f"materialized package contains a special file: {path}")


def verify(repo_root: Path, pin_path: Path) -> dict[str, Any]:
    repo_root = Path(os.path.abspath(repo_root))
    _assert_real_directory(repo_root)
    _reject_symlink_components(repo_root)
    pin = load_pin(pin_path)
    validate_manifests(repo_root, pin)
    with _bound_project_layout(repo_root, create=False, include_runtime=False) as layout:
        expected_override = override_document(pin)
        actual_override = _load_json(layout.override, "Lake package override")
        if actual_override != expected_override:
            raise MaterializationError("Lake package override differs from exact pin")
        verified: list[str] = []
        with tempfile.TemporaryDirectory(prefix="lake-package-verify-") as temporary:
            scratch_root = Path(temporary)
            for package in pin["packages"]:
                source = layout.packages.path / package["name"]
                if source.is_symlink() or not source.is_dir():
                    raise MaterializationError(f"materialized package is unavailable: {package['name']}")
                _scan_tree(source)
                archive_tree = compute_tree_sha(source, scratch_root / f"{package['name']}-archive", [])
                if archive_tree != package["output"]["archive_tree_sha"]:
                    raise MaterializationError(f"materialized archive tree differs for {package['name']}")
                tree = compute_tree_sha(
                    source, scratch_root / package["name"], package["output"]["gitlinks"]
                )
                if tree != package["output"]["tree_sha"]:
                    raise MaterializationError(f"materialized Git tree differs for {package['name']}")
                layout.assert_current()
                verified.append(package["name"])
    return {"status": "verified", "packages": verified, "override": OVERRIDE_PATH.as_posix()}


def _safe_transport_argv(
    template: Sequence[str], package: Mapping[str, Any], output: Path, timeout: float
) -> list[str]:
    if not template or any(not isinstance(token, str) or not token for token in template):
        raise MaterializationError("transport argv must be a non-empty string array")
    lowered = " ".join(template).lower()
    for forbidden in ("authorization:", "bearer ", "password=", "token=", "gh_token", "github_token"):
        if forbidden in lowered:
            raise MaterializationError("credentials must not appear in transport argv")
    substitutions = {
        "{url}": package["archive_url"], "{output}": str(output),
        "{max_bytes}": str(package["archive"]["bytes"]), "{timeout_seconds}": str(timeout),
    }
    counts = {placeholder: template.count(placeholder) for placeholder in substitutions}
    if counts["{url}"] != 1 or counts["{output}"] != 1 or any(count > 1 for count in counts.values()):
        raise MaterializationError("transport argv placeholders are missing or duplicated")
    return [substitutions.get(token, token) for token in template]


def _run_bounded_argv(
    argv: Sequence[str], timeout: float, *, cwd: Path, pass_fds: Sequence[int] = ()
) -> None:
    environment_names = (
        "PATH", "LANG", "LC_ALL", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy",
        "NO_PROXY", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR",
    )
    environment = {name: os.environ[name] for name in environment_names if name in os.environ}
    try:
        process = subprocess.Popen(
            list(argv), cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False, start_new_session=True,
            pass_fds=tuple(pass_fds),
        )
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        def group_exists() -> bool:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            return True

        def wait_for_group(seconds: float) -> bool:
            deadline = time.monotonic() + seconds
            while group_exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            return not group_exists()

        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if not wait_for_group(2.0):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if not wait_for_group(2.0):
                raise MaterializationError(
                    "transport command timed out and its process group could not be reaped"
                ) from error
        raise MaterializationError("transport command exceeded its timeout") from error
    except OSError as error:
        raise MaterializationError(f"transport command failed to start: {error}") from error
    if process.returncode != 0:
        raise MaterializationError(f"transport command failed with exit code {process.returncode}")


def fetch_archives(
    repo_root: Path,
    pin_path: Path,
    archive_directory: Path,
    transport_template: Sequence[str],
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    runner: Callable[[Sequence[str], float], None] | None = None,
) -> list[Path]:
    pin = load_pin(pin_path)
    validate_manifests(repo_root, pin)
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise MaterializationError("transport timeout must be positive")
    outputs: list[Path] = []
    archive_directory = Path(os.path.abspath(archive_directory))
    with _bound_output_directory(archive_directory, "archive output directory") as archive_root:
        for package in pin["packages"]:
            output_name = f"{package['name']}-{package['revision']}.tar.gz"
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{output_name}.", dir=archive_root.path
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                argv = _safe_transport_argv(
                    transport_template, package, temporary, float(timeout_seconds)
                )
                if runner is None:
                    _run_bounded_argv(
                        argv,
                        float(timeout_seconds),
                        cwd=repo_root,
                        pass_fds=(archive_root.descriptor,),
                    )
                else:
                    runner(argv, float(timeout_seconds))
                compressed = _read_regular_exact_at(
                    archive_root.descriptor,
                    temporary.name,
                    package["archive"]["bytes"],
                    f"archive {output_name}",
                )
                facts, _ = inspect_archive_bytes(compressed, package)
                _compare_facts(package, facts)
                os.replace(temporary, archive_root.path / output_name)
                _fsync_directory(archive_root.path)
                archive_root.assert_current()
                outputs.append(archive_directory / output_name)
            finally:
                temporary.unlink(missing_ok=True)
    return outputs


def _transport_template(path: Path) -> list[str]:
    document = _load_json(path, "transport argv")
    _exact_keys(document, {"argv"}, "transport argv")
    if not isinstance(document["argv"], list):
        raise MaterializationError("transport argv must be an array")
    return document["argv"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--pin", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    materialize_parser = commands.add_parser("materialize")
    archive_source = materialize_parser.add_mutually_exclusive_group(required=True)
    archive_source.add_argument("--archive-directory", type=Path)
    archive_source.add_argument("--archive-directory-env")
    materialize_parser.add_argument("--replace-existing", action="store_true")
    commands.add_parser("verify")
    fetch = commands.add_parser("fetch-materialize")
    fetch.add_argument("--archive-directory", type=Path, required=True)
    fetch.add_argument("--transport-argv-file", type=Path, required=True)
    fetch.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    fetch.add_argument("--replace-existing", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    repo_root = Path(os.path.abspath(arguments.repo_root))
    pin_path = arguments.pin or repo_root / PIN_RELATIVE_PATH
    try:
        if arguments.command == "verify":
            result = verify(repo_root, pin_path)
        else:
            if arguments.command == "fetch-materialize":
                fetch_archives(
                    repo_root, pin_path, arguments.archive_directory,
                    _transport_template(arguments.transport_argv_file),
                    timeout_seconds=arguments.timeout_seconds,
                )
            archive_directory = arguments.archive_directory
            if arguments.command == "materialize" and arguments.archive_directory_env:
                raw_archive_directory = os.environ.get(arguments.archive_directory_env)
                if not raw_archive_directory:
                    raise MaterializationError(
                        f"archive directory environment variable {arguments.archive_directory_env!r} is unset"
                    )
                archive_directory = Path(raw_archive_directory)
            result = materialize(
                repo_root, pin_path, archive_directory,
                replace_existing=arguments.replace_existing,
            )
    except MaterializationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
