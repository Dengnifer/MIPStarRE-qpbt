#!/usr/bin/env python3
"""Build, publish, and seed a local hot cache for Lean's ``.lake`` tree.

One process wins an ``fcntl`` lock for each exact main snapshot.  It builds in a
detached local clone, then publishes the immutable staged result with one
rename.  Issue worktrees receive private copy-on-write reflink copies (with a
byte-copy fallback), never a symlink or hardlink to writable build output.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import datetime as dt
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = 3
BUILD_RECIPE_SCHEMA_VERSION = 3
ARTIFACT_INVENTORY_SCHEMA_VERSION = 1
SOURCE_EVIDENCE_SCHEMA_VERSION = 1
FICLONE = 0x40049409
REFLINK_FALLBACK_ERRNOS = {
    errno.EXDEV,
    errno.EINVAL,
    errno.ENOTTY,
    errno.EOPNOTSUPP,
    errno.ENOSYS,
    errno.EPERM,
}


class CacheError(Exception):
    """A cache operation failed in a way suitable for concise CLI output."""


LAKE_OVERRIDE_ARGUMENT = "--packages=.lake/package-overrides.json"


def _validate_lake_command(command: Sequence[str]) -> None:
    """Require the exact local package override and reject manifest updates."""

    if command[0] != "lake":
        return
    package_arguments = [token for token in command if token.startswith("--packages")]
    if package_arguments != [LAKE_OVERRIDE_ARGUMENT]:
        raise ValueError(
            f"Lake commands require exactly {LAKE_OVERRIDE_ARGUMENT!r}"
        )
    if any(token == "update" or token == "--update" or token.startswith("--update=") for token in command):
        raise ValueError("Lake update modes are forbidden in the hot-cache build recipe")
    if any(
        token.startswith("-")
        and not token.startswith("--")
        and "U" in token[1:]
        for token in command
    ):
        raise ValueError("Lake short update modes are forbidden in the hot-cache build recipe")


@dataclass(frozen=True)
class BuildRecipe:
    """An identity-bearing, immutable recipe for one cache build."""

    recipe_id: str
    version: int
    dependency_command: tuple[str, ...]
    build_command: tuple[str, ...]
    test_only: bool = False
    materialize_command: tuple[str, ...] = ()
    package_materialize_command: tuple[str, ...] = ()
    package_verify_command: tuple[str, ...] = ()
    additional_identity_files: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.recipe_id or self.version < 1:
            raise ValueError("a build recipe needs a non-empty id and positive version")
        if not self.dependency_command or not self.build_command:
            raise ValueError("dependency and build commands cannot be empty")
        if bool(self.package_materialize_command) != bool(self.package_verify_command):
            raise ValueError("package materialization and verification commands must be paired")
        _validate_lake_command(self.dependency_command)
        _validate_lake_command(self.build_command)
        for relative in self.additional_identity_files:
            path = Path(relative)
            if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
                raise ValueError(f"identity file must be a safe project-relative path: {relative!r}")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": BUILD_RECIPE_SCHEMA_VERSION,
            "recipe_id": self.recipe_id,
            "version": self.version,
            "dependency_command": list(self.dependency_command),
            "build_command": list(self.build_command),
            "materialize_command": list(self.materialize_command),
            "package_materialize_command": list(self.package_materialize_command),
            "package_verify_command": list(self.package_verify_command),
            "additional_identity_files": list(self.additional_identity_files),
            "test_only": self.test_only,
        }

    @classmethod
    def for_testing(
        cls,
        *,
        dependency_command: Sequence[str],
        build_command: Sequence[str],
        materialize_command: Sequence[str] = (),
        package_materialize_command: Sequence[str] = (),
        package_verify_command: Sequence[str] = (),
        additional_identity_files: Sequence[str] = (),
        recipe_id: str = "test-fake-build",
        version: int = 1,
    ) -> "BuildRecipe":
        """Create a recipe whose artifacts cannot share the canonical key."""

        return cls(
            recipe_id=recipe_id,
            version=version,
            dependency_command=tuple(dependency_command),
            build_command=tuple(build_command),
            materialize_command=tuple(materialize_command),
            package_materialize_command=tuple(package_materialize_command),
            package_verify_command=tuple(package_verify_command),
            additional_identity_files=tuple(additional_identity_files),
            test_only=True,
        )


CANONICAL_BUILD_RECIPE = BuildRecipe(
    recipe_id="qpbt-hot-main",
    version=4,
    dependency_command=("lake", LAKE_OVERRIDE_ARGUMENT, "exe", "cache", "get"),
    build_command=("lake", LAKE_OVERRIDE_ARGUMENT, "build"),
    materialize_command=(
        "python3", "scripts/materialize_mipstarre.py", "materialize",
        "--archive-env", "MIPSTARRE_ARCHIVE",
    ),
    package_materialize_command=(
        "python3", "scripts/materialize_lake_packages.py", "materialize",
        "--archive-directory-env", "LAKE_PACKAGE_ARCHIVES",
    ),
    package_verify_command=(
        "python3", "scripts/materialize_lake_packages.py", "verify",
    ),
    additional_identity_files=(
        "references/mipstarre-upstream.json",
        "scripts/materialize_mipstarre.py",
        "references/lake-packages.json",
        "references/mathlib-lake-manifest.json",
        "scripts/materialize_lake_packages.py",
    ),
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def artifact_inventory(root: Path) -> dict[str, Any]:
    """Return a content-addressed inventory without following symlinks."""

    if not root.is_dir() or root.is_symlink():
        raise CacheError(f"artifact inventory root must be a real directory: {root}")
    digest = hashlib.sha256()
    files = 0
    directories = 0
    symlinks = 0
    total_bytes = 0

    def add(kind: str, relative: str, payload: str = "") -> None:
        digest.update(kind.encode("ascii"))
        digest.update(b"\0")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")

    for directory, dir_names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        relative_base = base.relative_to(root).as_posix()
        if relative_base != ".":
            add("directory", relative_base)
            directories += 1
        dir_names.sort()
        file_names.sort()
        retained: list[str] = []
        for name in dir_names:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                add("symlink", relative, os.readlink(path))
                symlinks += 1
            elif path.is_dir():
                retained.append(name)
            else:
                raise CacheError(f"unsupported artifact entry type: {path}")
        dir_names[:] = retained
        for name in file_names:
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                add("symlink", relative, os.readlink(path))
                symlinks += 1
            elif path.is_file():
                size = path.stat(follow_symlinks=False).st_size
                add("file", relative, f"{size}:{sha256_file(path)}")
                files += 1
                total_bytes += size
            else:
                raise CacheError(f"unsupported artifact entry type: {path}")
    return {
        "schema_version": ARTIFACT_INVENTORY_SCHEMA_VERSION,
        "sha256": digest.hexdigest(),
        "files": files,
        "directories": directories,
        "symlinks": symlinks,
        "bytes": total_bytes,
    }


def _is_lower_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_source_evidence(value: Any, expected_contract: Mapping[str, Any]) -> bool:
    """Validate the bounded source-verification record sealed into a snapshot."""

    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "pin_sha256",
        "source_commit",
        "inventory_sha256",
        "files",
        "bytes",
        "authored_qpbt_files",
        "authored_qpbt_bytes",
        "authored_qpbt_sha256",
    }:
        return False
    counts = (
        value["files"],
        value["bytes"],
        value["authored_qpbt_files"],
        value["authored_qpbt_bytes"],
    )
    return value == expected_contract and (
        value["schema_version"] == SOURCE_EVIDENCE_SCHEMA_VERSION
        and _is_lower_hex(value["pin_sha256"], 64)
        and _is_lower_hex(value["source_commit"], 40)
        and _is_lower_hex(value["inventory_sha256"], 64)
        and _is_lower_hex(value["authored_qpbt_sha256"], 64)
        and all(
            isinstance(count, int) and not isinstance(count, bool) and count >= 0
            for count in counts
        )
    )


def _git_command_bytes(repo_root: Path, arguments: Sequence[str]) -> bytes:
    command = ["git", "-C", str(repo_root), *arguments]
    try:
        result = subprocess.run(command, capture_output=True, check=False, shell=False)
    except OSError as error:
        raise CacheError(f"could not run git: {error}") from error
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or f"exit {result.returncode}"
        raise CacheError(f"git command failed: {message}")
    return result.stdout


def authored_tree_facts_at_commit(
    repo_root: Path,
    project_dir: Path,
    commit: str,
) -> dict[str, Any]:
    try:
        project_relative = project_dir.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise CacheError("project directory must be inside the repository") from error
    authored_prefix = project_relative / "MIPStarRE" / "QPBT"
    listing = _git_command_bytes(
        repo_root,
        ["ls-tree", "-rz", "--full-tree", commit, "--", authored_prefix.as_posix()],
    )
    records: list[tuple[str, bytes]] = []
    for raw_record in listing.split(b"\0"):
        if not raw_record:
            continue
        metadata, separator, raw_path = raw_record.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3 or fields[1] != b"blob":
            raise CacheError("committed QPBT tree contains an unsupported Git entry")
        mode, _, object_id = fields
        if mode not in (b"100644", b"100755"):
            raise CacheError("committed QPBT tree contains a non-regular entry")
        path = Path(os.fsdecode(raw_path))
        try:
            relative = path.relative_to(authored_prefix).as_posix()
        except ValueError as error:
            raise CacheError("Git returned a QPBT entry outside the requested tree") from error
        payload = _git_command_bytes(repo_root, ["cat-file", "blob", object_id.decode("ascii")])
        records.append((relative, payload))
    records.sort(key=lambda item: item[0])
    digest = hashlib.sha256()
    for relative, payload in records:
        digest.update(
            f"{relative}\0{len(payload)}\0{hashlib.sha256(payload).hexdigest()}\n".encode()
        )
    return {
        "authored_qpbt_files": len(records),
        "authored_qpbt_bytes": sum(len(payload) for _, payload in records),
        "authored_qpbt_sha256": digest.hexdigest(),
    }


def source_contract_at_commit(
    repo_root: Path,
    project_dir: Path,
    commit: str,
    inputs: Mapping[str, str],
    recipe: BuildRecipe,
) -> dict[str, Any] | None:
    if not recipe.materialize_command:
        return None
    pin_relative = Path("references/mipstarre-upstream.json")
    expected_pin_sha256 = inputs.get(pin_relative.as_posix())
    if not isinstance(expected_pin_sha256, str):
        raise CacheError("materializing cache identity omits the upstream provenance pin")
    try:
        project_relative = project_dir.resolve().relative_to(repo_root.resolve())
        pin_bytes = git_blob(repo_root, commit, project_relative / pin_relative)
        pin = json.loads(pin_bytes)
        source = pin["source"]
        output = pin["output"]
        contract = {
            "schema_version": SOURCE_EVIDENCE_SCHEMA_VERSION,
            "pin_sha256": expected_pin_sha256,
            "source_commit": source["commit"],
            "inventory_sha256": output["inventory_sha256"],
            "files": output["files"],
            "bytes": output["bytes"],
            **authored_tree_facts_at_commit(repo_root, project_dir, commit),
        }
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CacheError("could not derive exact source provenance from the committed pin") from error
    if not validate_source_evidence(contract, contract):
        raise CacheError("committed source provenance contains invalid exact facts")
    return contract


def discover_inputs(project_dir: Path, recipe: BuildRecipe | None = None) -> list[Path]:
    """Resolve every versioned identity input in the local detached clone."""

    required = [
        project_dir / "lean-toolchain",
        project_dir / "lakefile.toml",
        project_dir / "lake-manifest.json",
    ] + [project_dir / relative for relative in (recipe.additional_identity_files if recipe else ())]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise CacheError("missing cache-key input(s): " + ", ".join(missing))
    return required


def hash_inputs(
    project_dir: Path, recipe: BuildRecipe | None = None
) -> dict[str, str]:
    return {
        path.relative_to(project_dir).as_posix(): sha256_file(path)
        for path in discover_inputs(project_dir, recipe)
    }


def git_blob(repo_root: Path, commit: str, relative_path: Path) -> bytes:
    git_path = relative_path.as_posix()
    command = ["git", "-C", str(repo_root), "show", f"{commit}:{git_path}"]
    try:
        result = subprocess.run(command, capture_output=True, check=False, shell=False)
    except OSError as error:
        raise CacheError(f"could not run git: {error}") from error
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip() or f"exit {result.returncode}"
        raise CacheError(f"could not read {git_path!r} from main commit {commit}: {message}")
    return result.stdout


def hash_inputs_at_commit(
    repo_root: Path, project_dir: Path, commit: str, recipe: BuildRecipe | None = None
) -> dict[str, str]:
    try:
        project_relative = project_dir.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        raise CacheError("project directory must be inside the repository") from error
    names = (
        "lean-toolchain", "lakefile.toml", "lake-manifest.json",
        *(recipe.additional_identity_files if recipe else ()),
    )
    inputs: dict[str, str] = {}
    for name in names:
        relative = project_relative / name
        inputs[name] = hashlib.sha256(git_blob(repo_root, commit, relative)).hexdigest()
    return inputs


def git_commit(repo_root: Path, ref: str) -> str:
    command = ["git", "-C", str(repo_root), "rev-parse", f"{ref}^{{commit}}"]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, shell=False)
    except OSError as error:
        raise CacheError(f"could not run git: {error}") from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise CacheError(f"could not resolve {ref!r}: {message}")
    commit = result.stdout.strip()
    if not re_full_sha(commit):
        raise CacheError(f"git returned an invalid commit id: {commit!r}")
    return commit


def re_full_sha(value: str) -> bool:
    return len(value) == 40 and all(character in "0123456789abcdefABCDEF" for character in value)


def git_source_changes(repo_root: Path) -> list[str]:
    command = [
        "git",
        "-C",
        str(repo_root),
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignore-submodules=none",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, shell=False)
    except OSError as error:
        raise CacheError(f"could not run git: {error}") from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise CacheError(f"could not inspect detached checkout cleanliness: {message}")
    return [line for line in result.stdout.splitlines() if line]


@dataclass(frozen=True)
class WorktreeRecord:
    path: Path
    head: str | None
    bare: bool
    prunable: bool


def git_worktrees(repo_root: Path) -> list[WorktreeRecord]:
    """Read registered worktrees using Git's stable porcelain format."""

    command = ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, shell=False)
    except OSError as error:
        raise CacheError(f"could not run git: {error}") from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise CacheError(f"could not list registered worktrees: {message}")

    records: list[WorktreeRecord] = []
    for block in result.stdout.strip().split("\n\n"):
        if not block:
            continue
        values: dict[str, str] = {}
        flags: set[str] = set()
        for line in block.splitlines():
            key, separator, value = line.partition(" ")
            if separator:
                values[key] = value
            else:
                flags.add(key)
        path = values.get("worktree")
        if path is None:
            raise CacheError("git worktree porcelain output omitted a worktree path")
        records.append(
            WorktreeRecord(
                path=Path(path),
                head=values.get("HEAD"),
                bare="bare" in flags,
                prunable="prunable" in flags or "prunable" in values,
            )
        )
    return records


def default_runtime_dir(repo_root: Path) -> Path:
    """Return the runtime directory shared by all linked worktrees.

    The command-line default used to be resolved beneath the checkout that
    contained the script. Linked issue worktrees therefore received distinct
    lock files and could rebuild one main snapshot independently. Git's
    porcelain worktree list identifies the primary worktree (the only normal
    worktree with a real ``.git`` directory); use that root for the omitted
    runtime argument. Callers that supply ``--runtime-dir`` keep their explicit
    path semantics.
    """

    try:
        resolved_root = repo_root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise CacheError(
            "could not resolve the repository root for the default runtime directory; "
            "pass --runtime-dir explicitly"
        ) from error
    records = git_worktrees(resolved_root)
    candidates: list[Path] = []
    for record in records:
        if record.bare or record.prunable:
            continue
        try:
            candidate = record.path.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        metadata = candidate / ".git"
        if metadata.is_dir() and not metadata.is_symlink():
            candidates.append(candidate)
    if not candidates:
        raise CacheError(
            "could not identify a primary Git worktree for the default runtime directory; "
            "pass --runtime-dir explicitly"
        )
    # Porcelain lists the primary worktree first. Prefer the caller when it is
    # itself primary, otherwise retain that deterministic ordering.
    if resolved_root in candidates:
        primary = resolved_root
    else:
        primary = candidates[0]
    return primary / ".workflow-runtime"


def git_resolved_path(repo_root: Path, argument: str) -> Path:
    command = ["git", "-C", str(repo_root), "rev-parse", argument]
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, shell=False)
    except OSError as error:
        raise CacheError(f"could not run git: {error}") from error
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise CacheError(f"target is not a live Git worktree: {message}")
    value = Path(result.stdout.strip())
    if not value.is_absolute():
        value = repo_root / value
    try:
        return value.resolve(strict=True)
    except FileNotFoundError as error:
        raise CacheError(f"Git returned a missing path for {argument}: {value}") from error


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def reject_symlink_components(path: Path) -> Path:
    """Return a lexical absolute path after rejecting ``..`` and symlinks."""

    if ".." in path.parts:
        raise CacheError(f"target worktree path cannot contain '..': {path}")
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        if component in ("", "."):
            continue
        current /= component
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            continue
        except OSError as error:
            raise CacheError(f"could not inspect target path component {current}: {error}") from error
        if stat.S_ISLNK(mode):
            raise CacheError(f"target worktree path contains a symlink component: {current}")
    return absolute


@dataclass(frozen=True)
class CacheIdentity:
    cache_key: str
    main_commit: str
    inputs: dict[str, str]
    recipe: dict[str, Any]
    source_contract: dict[str, Any] | None

    @classmethod
    def create(
        cls,
        repo_root: Path,
        project_dir: Path,
        recipe: BuildRecipe,
        main_ref: str = "main",
        main_commit: str | None = None,
    ) -> "CacheIdentity":
        commit = main_commit or git_commit(repo_root, main_ref)
        if not re_full_sha(commit):
            raise CacheError(f"invalid main commit {commit!r}; expected a full 40-character SHA")
        inputs = hash_inputs_at_commit(repo_root, project_dir, commit, recipe)
        recipe_payload = recipe.identity_payload()
        source_contract = source_contract_at_commit(
            repo_root, project_dir, commit, inputs, recipe
        )
        payload = json.dumps(
            {
                "main_commit": commit.lower(),
                "inputs": inputs,
                "recipe": recipe_payload,
                "source_contract": source_contract,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        return cls(
            hashlib.sha256(payload).hexdigest(),
            commit.lower(),
            inputs,
            recipe_payload,
            source_contract,
        )


@dataclass
class CopyStats:
    files: int = 0
    bytes: int = 0
    reflinked: int = 0
    copied: int = 0
    symlinks: int = 0


def _copy_regular_file(source: Path, destination: Path, stats: CopyStats) -> None:
    size = source.stat(follow_symlinks=False).st_size
    source_fd = os.open(source, os.O_RDONLY)
    destination_fd: int | None = None
    try:
        destination_fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            fcntl.ioctl(destination_fd, FICLONE, source_fd)
            stats.reflinked += 1
        except OSError as error:
            if error.errno not in REFLINK_FALLBACK_ERRNOS:
                raise
            os.close(destination_fd)
            destination_fd = None
            destination.unlink()
            shutil.copy2(source, destination, follow_symlinks=False)
            stats.copied += 1
        else:
            shutil.copystat(source, destination, follow_symlinks=False)
    finally:
        os.close(source_fd)
        if destination_fd is not None:
            os.close(destination_fd)
    stats.files += 1
    stats.bytes += size


def reflink_copytree(source: Path, destination: Path) -> CopyStats:
    """Copy a tree using Linux reflinks where available, never hardlinks."""

    if not source.is_dir() or source.is_symlink():
        raise CacheError(f"copy source must be a real directory: {source}")
    if destination.exists() or destination.is_symlink():
        raise CacheError(f"copy destination already exists: {destination}")
    stats = CopyStats()
    destination.mkdir(parents=True)

    def visit(source_dir: Path, destination_dir: Path) -> None:
        for entry in os.scandir(source_dir):
            source_path = Path(entry.path)
            destination_path = destination_dir / entry.name
            if entry.is_symlink():
                os.symlink(os.readlink(source_path), destination_path)
                try:
                    shutil.copystat(source_path, destination_path, follow_symlinks=False)
                except (NotImplementedError, OSError):
                    pass
                stats.symlinks += 1
            elif entry.is_dir(follow_symlinks=False):
                destination_path.mkdir()
                visit(source_path, destination_path)
                shutil.copystat(source_path, destination_path, follow_symlinks=False)
            elif entry.is_file(follow_symlinks=False):
                _copy_regular_file(source_path, destination_path, stats)
            else:
                raise CacheError(f"unsupported cache entry type: {source_path}")

    visit(source, destination)
    shutil.copystat(source, destination, follow_symlinks=False)
    return stats


def _walk_without_following(root: Path) -> list[Path]:
    paths: list[Path] = [root]
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        paths.extend(base / name for name in names)
        paths.extend(base / name for name in files)
    return paths


def make_read_only(root: Path) -> None:
    for path in reversed(_walk_without_following(root)):
        if path.is_symlink():
            continue
        mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), follow_symlinks=False)


def make_owner_writable(root: Path) -> None:
    for path in _walk_without_following(root):
        if path.is_symlink():
            continue
        mode = stat.S_IMODE(path.stat(follow_symlinks=False).st_mode)
        path.chmod(mode | stat.S_IWUSR, follow_symlinks=False)


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class ExclusiveLock:
    def __init__(self, path: Path):
        self.path = path
        self.stream: Any = None
        self.waited = False
        self.wait_seconds = 0.0

    def __enter__(self) -> "ExclusiveLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+", encoding="utf-8")
        started = time.monotonic()
        try:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.waited = True
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX)
            self.wait_seconds = time.monotonic() - started
        return self

    def __exit__(self, exception_type: Any, exception: Any, traceback: Any) -> None:
        if self.stream is not None:
            fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()


CommandCallback = Callable[[Path, Sequence[str], Path], int | None]
SourceVerifier = Callable[[Path], Mapping[str, Any]]


class HotMainCache:
    """Operations for one identity-keyed main cache snapshot."""

    def __init__(
        self,
        repo_root: Path,
        project_dir: Path,
        runtime_dir: Path,
        *,
        main_ref: str = "main",
        main_commit: str | None = None,
        _test_recipe: BuildRecipe | None = None,
    ):
        self.repo_root = repo_root.resolve()
        self.project_dir = project_dir.resolve()
        self.runtime_dir = runtime_dir.resolve()
        self.main_ref = main_ref
        if _test_recipe is not None and not _test_recipe.test_only:
            raise CacheError("the internal recipe override only accepts test-only recipes")
        self.recipe = _test_recipe or CANONICAL_BUILD_RECIPE
        self.identity = CacheIdentity.create(
            self.repo_root,
            self.project_dir,
            self.recipe,
            main_ref=main_ref,
            main_commit=main_commit,
        )
        self.cache_root = self.runtime_dir / "cache" / "main"
        self.snapshot_dir = self.cache_root / self.identity.cache_key
        self.lake_dir = self.snapshot_dir / ".lake"
        self.build_dir = self.lake_dir / "build"
        self.manifest_path = self.snapshot_dir / "manifest.json"
        self.ready_path = self.snapshot_dir / "READY"
        self.lock_path = self.runtime_dir / "locks" / f"hot-main-{self.identity.cache_key}.lock"
        self.metrics_path = self.runtime_dir / "metrics" / "hot-main.jsonl"
        self.metrics_lock_path = self.runtime_dir / "locks" / "hot-main-metrics.lock"

    def is_ready(self, *, deep: bool = False) -> bool:
        if not self.ready_path.is_file() or not self.manifest_path.is_file() or not self.build_dir.is_dir():
            return False
        try:
            with self.manifest_path.open("r", encoding="utf-8") as stream:
                manifest = json.load(stream)
        except (OSError, json.JSONDecodeError):
            return False
        try:
            ready_digest = self.ready_path.read_text(encoding="ascii").strip()
            manifest_digest = sha256_file(self.manifest_path)
        except (OSError, UnicodeDecodeError):
            return False
        if ready_digest != manifest_digest:
            return False
        source_evidence_ready = (
            validate_source_evidence(
                manifest.get("source_evidence"), self.identity.source_contract
            )
            if self.recipe.materialize_command
            and isinstance(self.identity.source_contract, dict)
            else manifest.get("source_evidence") is None
        )
        shallow_ready = (
            manifest.get("schema_version") == SCHEMA_VERSION
            and manifest.get("cache_key") == self.identity.cache_key
            and manifest.get("main_commit") == self.identity.main_commit
            and manifest.get("inputs") == self.identity.inputs
            and manifest.get("recipe") == self.identity.recipe
            and manifest.get("source_contract") == self.identity.source_contract
            and isinstance(manifest.get("artifact_inventory"), dict)
            and source_evidence_ready
        )
        if not shallow_ready or not deep:
            return shallow_ready
        try:
            return manifest["artifact_inventory"] == artifact_inventory(self.lake_dir)
        except (CacheError, OSError):
            return False

    def status(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            **asdict(self.identity),
            "status": "hit" if self.is_ready() else "miss",
            "snapshot_dir": str(self.snapshot_dir),
            "build_dir": str(self.build_dir),
            "lock_path": str(self.lock_path),
        }

    def _append_metric(self, metric: Mapping[str, Any]) -> None:
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": utc_now(),
            "pid": os.getpid(),
            "cache_key": self.identity.cache_key,
            "main_commit": self.identity.main_commit,
            **metric,
        }
        encoded = (json.dumps(envelope, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
        with ExclusiveLock(self.metrics_lock_path):
            self.metrics_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.metrics_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(descriptor, encoded)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    @staticmethod
    def _run_logged(build_root: Path, command: Sequence[str], log_path: Path) -> int:
        try:
            with log_path.open("ab") as log:
                result = subprocess.run(
                    list(command),
                    cwd=build_root,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    shell=False,
                )
        except OSError as error:
            raise CacheError(f"could not run build command {command[0]!r}: {error}") from error
        return result.returncode

    def _detached_clone(self, staging: Path, log_path: Path) -> Path:
        checkout = staging / "checkout"
        commands = (
            ["git", "clone", "--local", "--no-checkout", str(self.repo_root), str(checkout)],
            ["git", "-C", str(checkout), "checkout", "--detach", self.identity.main_commit],
        )
        for command in commands:
            return_code = self._run_logged(staging, command, log_path)
            if return_code != 0:
                raise CacheError(f"detached clone command failed with exit code {return_code}")
        return checkout

    def _verify_materialized_source(
        self,
        detached_project: Path,
        test_verifier: SourceVerifier | None,
    ) -> dict[str, Any] | None:
        if not self.recipe.materialize_command:
            if test_verifier is not None:
                raise CacheError("a source verifier requires a materializing build recipe")
            return None

        pin_relative = "references/mipstarre-upstream.json"
        expected_pin_sha256 = self.identity.inputs.get(pin_relative)
        if not isinstance(expected_pin_sha256, str):
            raise CacheError("materializing cache identity omits the upstream provenance pin")

        if test_verifier is not None:
            raw_evidence = dict(test_verifier(detached_project))
        else:
            if self.recipe.test_only:
                raise CacheError("a materializing test recipe requires an exact test source verifier")
            module_path = detached_project / "scripts" / "materialize_mipstarre.py"
            spec = importlib.util.spec_from_file_location("_hot_cache_materializer", module_path)
            if spec is None or spec.loader is None:
                raise CacheError("could not load the identity-bound foundation verifier")
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
                pin = module.load_pin(detached_project / pin_relative)
                module.validate_project_pins(detached_project, pin)
                verified = module.verify_materialized(detached_project, pin)
                raw_evidence = {
                    "schema_version": SOURCE_EVIDENCE_SCHEMA_VERSION,
                    "pin_sha256": expected_pin_sha256,
                    "source_commit": pin["source"]["commit"],
                    "inventory_sha256": verified["inventory_sha256"],
                    "files": verified["files"],
                    "bytes": verified["bytes"],
                    "authored_qpbt_files": verified["authored_qpbt_files"],
                    "authored_qpbt_bytes": verified["authored_qpbt_bytes"],
                    "authored_qpbt_sha256": verified["authored_qpbt_sha256"],
                }
            except Exception as error:
                raise CacheError(f"foundation source verification failed: {error}") from error

        if not isinstance(self.identity.source_contract, dict) or not validate_source_evidence(
            raw_evidence, self.identity.source_contract
        ):
            raise CacheError("foundation source verifier differs from exact committed provenance")
        return raw_evidence

    def warm(
        self,
        *,
        dry_run: bool = False,
        _test_command_callback: CommandCallback | None = None,
        _test_source_verifier: SourceVerifier | None = None,
    ) -> dict[str, Any]:
        if (
            _test_command_callback is not None or _test_source_verifier is not None
        ) and not self.recipe.test_only:
            raise CacheError("test callbacks are allowed only with an identity-isolated test recipe")
        dependency_command = self.recipe.dependency_command
        materialize_command = self.recipe.materialize_command
        package_materialize_command = self.recipe.package_materialize_command
        package_verify_command = self.recipe.package_verify_command
        command = self.recipe.build_command
        if dry_run:
            return {
                **self.status(),
                "action": "warm",
                "dry_run": True,
                "source": f"detached local clone at {self.identity.main_commit}",
                "materialize_command": list(materialize_command),
                "package_materialize_command": list(package_materialize_command),
                "package_verify_command": list(package_verify_command),
                "dependency_command": list(dependency_command),
                "command": list(command),
                "would_build": not self.is_ready(),
            }
        started = time.monotonic()
        if self.is_ready():
            result = {
                **self.status(),
                "action": "warm",
                "result": "hit",
                "cache_hit": 1,
                "cache_miss": 0,
                "lock_waited": 0,
                "lock_wait_seconds": 0.0,
                "builds": 0,
                "build_seconds": 0.0,
                "elapsed_seconds": round(time.monotonic() - started, 6),
            }
            self._append_metric(result)
            return result

        with ExclusiveLock(self.lock_path) as cache_lock:
            if self.is_ready():
                result = {
                    **self.status(),
                    "action": "warm",
                    "result": "hit_after_wait" if cache_lock.waited else "hit",
                    "cache_hit": 1,
                    "cache_miss": 0,
                    "lock_waited": int(cache_lock.waited),
                    "lock_wait_seconds": round(cache_lock.wait_seconds, 6),
                    "builds": 0,
                    "build_seconds": 0.0,
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                }
                self._append_metric(result)
                return result

            build_started = time.monotonic()
            metric_base = {
                "action": "warm",
                "cache_hit": 0,
                "cache_miss": 1,
                "lock_waited": int(cache_lock.waited),
                "lock_wait_seconds": round(cache_lock.wait_seconds, 6),
                "builds": 1,
                "elected_owner": {"pid": os.getpid(), "host": socket.gethostname()},
                "materialize_command": list(materialize_command),
                "package_materialize_command": list(package_materialize_command),
                "package_verify_command": list(package_verify_command),
                "dependency_command": list(dependency_command),
                "command": list(command),
            }
            callback = _test_command_callback or self._run_logged
            self.cache_root.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(prefix=f".{self.identity.cache_key}.staging-", dir=self.cache_root)
            )
            log_path = staging / "build.log"
            try:
                checkout = self._detached_clone(staging, log_path)
                project_relative = self.project_dir.relative_to(self.repo_root)
                detached_project = checkout / project_relative
                if hash_inputs(detached_project, self.recipe) != self.identity.inputs:
                    raise CacheError("detached clone metadata does not match the main cache identity")

                materialize_seconds = 0.0
                if materialize_command:
                    materialize_started = time.monotonic()
                    return_code = callback(detached_project, materialize_command, log_path)
                    materialize_seconds = time.monotonic() - materialize_started
                    if return_code not in (None, 0):
                        raise CacheError(
                            f"foundation materialization command failed with exit code {return_code}"
                        )

                package_materialize_seconds = 0.0
                package_verify_seconds = 0.0
                if package_materialize_command:
                    package_materialize_started = time.monotonic()
                    return_code = callback(detached_project, package_materialize_command, log_path)
                    package_materialize_seconds = time.monotonic() - package_materialize_started
                    if return_code not in (None, 0):
                        raise CacheError(
                            f"Lake package materialization command failed with exit code {return_code}"
                        )
                    package_verify_started = time.monotonic()
                    return_code = callback(detached_project, package_verify_command, log_path)
                    package_verify_seconds = time.monotonic() - package_verify_started
                    if return_code not in (None, 0):
                        raise CacheError(
                            f"Lake package verification command failed with exit code {return_code}"
                        )

                dependency_started = time.monotonic()
                return_code = callback(detached_project, dependency_command, log_path)
                dependency_seconds = time.monotonic() - dependency_started
                if return_code not in (None, 0):
                    raise CacheError(f"dependency cache command failed with exit code {return_code}")

                compilation_started = time.monotonic()
                return_code = callback(detached_project, command, log_path)
                compilation_seconds = time.monotonic() - compilation_started
                if return_code not in (None, 0):
                    raise CacheError(f"build command failed with exit code {return_code}")
                if package_verify_command:
                    package_verify_started = time.monotonic()
                    return_code = callback(detached_project, package_verify_command, log_path)
                    package_verify_seconds += time.monotonic() - package_verify_started
                    if return_code not in (None, 0):
                        raise CacheError(
                            f"Lake package verification command failed with exit code {return_code}"
                        )
                if git_commit(checkout, "HEAD") != self.identity.main_commit:
                    raise CacheError("detached checkout HEAD changed during the cache build")
                if hash_inputs(detached_project, self.recipe) != self.identity.inputs:
                    raise CacheError("cache-key inputs changed during the cache build")
                source_changes = git_source_changes(checkout)
                if source_changes:
                    preview = ", ".join(source_changes[:5])
                    raise CacheError(f"project source changed during the cache build: {preview}")
                source_evidence = self._verify_materialized_source(
                    detached_project, _test_source_verifier
                )
                source_lake = detached_project / ".lake"
                source_build = source_lake / "build"
                if not source_build.is_dir() or source_build.is_symlink():
                    raise CacheError(f"build succeeded but produced no real directory at {source_build}")

                os.replace(source_lake, staging / ".lake")
                shutil.rmtree(checkout)
                build_seconds = time.monotonic() - build_started
                make_read_only(staging / ".lake")
                inventory = artifact_inventory(staging / ".lake")
                manifest = {
                    "schema_version": SCHEMA_VERSION,
                    **asdict(self.identity),
                    "created_at": utc_now(),
                    "source": "detached-local-clone",
                    "materialize_command": list(materialize_command),
                    "package_materialize_command": list(package_materialize_command),
                    "package_verify_command": list(package_verify_command),
                    "dependency_command": list(dependency_command),
                    "command": list(command),
                    "materialize_seconds": round(materialize_seconds, 6),
                    "package_materialize_seconds": round(package_materialize_seconds, 6),
                    "package_verify_seconds": round(package_verify_seconds, 6),
                    "dependency_cache_seconds": round(dependency_seconds, 6),
                    "build_seconds": round(compilation_seconds, 6),
                    "total_prepare_seconds": round(build_seconds, 6),
                    "log_path": str(self.snapshot_dir / "build.log"),
                    "artifact_inventory": inventory,
                    "source_evidence": source_evidence,
                }
                atomic_write_json(staging / "manifest.json", manifest)
                (staging / "READY").write_text(
                    f"{sha256_file(staging / 'manifest.json')}\n", encoding="ascii"
                )
                make_read_only(staging)
                if self.snapshot_dir.exists():
                    raise CacheError(
                        f"an invalid cache snapshot already exists at {self.snapshot_dir}; "
                        "cache cleanup is an explicit maintenance operation"
                    )
                os.replace(staging, self.snapshot_dir)
                result = {
                    **self.status(),
                    **metric_base,
                    "result": "built",
                    "materialize_seconds": round(materialize_seconds, 6),
                    "package_materialize_seconds": round(package_materialize_seconds, 6),
                    "package_verify_seconds": round(package_verify_seconds, 6),
                    "dependency_cache_seconds": round(dependency_seconds, 6),
                    "build_seconds": round(compilation_seconds, 6),
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "log_path": str(self.snapshot_dir / "build.log"),
                }
                self._append_metric(result)
                return result
            except Exception as error:
                build_seconds = time.monotonic() - build_started
                retained_path: Path | None = None
                if staging.exists():
                    failures = self.runtime_dir / "cache" / "failures"
                    failures.mkdir(parents=True, exist_ok=True)
                    retained_path = failures / (
                        f"{self.identity.cache_key}-{dt.datetime.now().strftime('%Y%m%dT%H%M%S')}-{os.getpid()}"
                    )
                    retained_path.mkdir()
                    if (staging / "build.log").is_file():
                        os.replace(staging / "build.log", retained_path / "build.log")
                    atomic_write_json(
                        retained_path / "failure.json",
                        {
                            "schema_version": SCHEMA_VERSION,
                            **asdict(self.identity),
                            "failed_at": utc_now(),
                            "error": str(error),
                        },
                    )
                    make_owner_writable(staging)
                    shutil.rmtree(staging)
                failed = {
                    **metric_base,
                    "result": "failed",
                    "build_seconds": round(build_seconds, 6),
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "error": str(error),
                    "log_path": str(retained_path / "build.log") if retained_path else None,
                }
                self._append_metric(failed)
                if isinstance(error, CacheError):
                    raise
                raise CacheError(str(error)) from error

    def _eligible_seed_target(self, supplied_target: Path) -> tuple[Path, Path]:
        lexical_target = reject_symlink_components(supplied_target)
        if not lexical_target.is_dir():
            raise CacheError(f"target worktree must be an existing real directory: {lexical_target}")
        target_project = lexical_target.resolve(strict=True)
        project_relative = self.project_dir.relative_to(self.repo_root)

        matched: WorktreeRecord | None = None
        matched_root: Path | None = None
        for record in git_worktrees(self.repo_root):
            try:
                worktree_root = record.path.resolve(strict=True)
            except FileNotFoundError:
                continue
            candidate = (worktree_root / project_relative).resolve(strict=False)
            if candidate == target_project:
                matched = record
                matched_root = worktree_root
                break
        if matched is None or matched_root is None:
            raise CacheError(
                f"target is not the project root of a registered Git worktree: {target_project}"
            )
        if matched.bare or matched.prunable or not matched.head or not re_full_sha(matched.head):
            raise CacheError(f"target is not an eligible live Git worktree: {matched_root}")
        if matched_root == self.repo_root:
            raise CacheError("refusing to seed the main worktree")
        if path_is_within(target_project, self.cache_root) or path_is_within(
            self.cache_root, target_project
        ):
            raise CacheError("target worktree must be distinct from the hot-cache storage")
        if git_resolved_path(matched_root, "--show-toplevel") != matched_root:
            raise CacheError(f"target path is not its Git worktree root: {matched_root}")
        if git_resolved_path(matched_root, "--git-common-dir") != git_resolved_path(
            self.repo_root, "--git-common-dir"
        ):
            raise CacheError("target worktree is not attached to the main repository")

        target_inputs = discover_inputs(target_project, self.recipe)
        symlinked_inputs = [str(path) for path in target_inputs if path.is_symlink()]
        if symlinked_inputs:
            raise CacheError("target cache-key inputs cannot be symlinks: " + ", ".join(symlinked_inputs))
        if hash_inputs(target_project, self.recipe) != self.identity.inputs:
            raise CacheError("target worktree has cache-key inputs incompatible with this cache")
        return target_project, matched_root

    def _validate_seeded_destination(self, destination: Path) -> None:
        if not self.is_ready(deep=True):
            raise CacheError("published cache changed or lost source evidence during seed")
        if not destination.is_dir() or destination.is_symlink():
            raise CacheError(f"seed publication did not create a real directory: {destination}")
        build = destination / "build"
        if not build.is_dir() or build.is_symlink():
            raise CacheError(f"seed publication has no real build directory: {build}")
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CacheError(f"could not read cache manifest after seed: {error}") from error
        if artifact_inventory(destination) != manifest.get("artifact_inventory"):
            raise CacheError("seeded cache artifact inventory does not match the published cache")

    @staticmethod
    def _rollback_seed_replacement(
        destination: Path,
        backup: Path,
        rollback_new: Path,
        *,
        moved_old: bool,
    ) -> list[str]:
        errors: list[str] = []
        if destination.exists() or destination.is_symlink():
            try:
                os.replace(destination, rollback_new)
            except OSError as error:
                errors.append(f"could not withdraw failed publication: {error}")
        if moved_old and (backup.exists() or backup.is_symlink()):
            if destination.exists() or destination.is_symlink():
                errors.append(f"original cache remains recoverable at {backup}")
            else:
                try:
                    os.replace(backup, destination)
                except OSError as error:
                    errors.append(f"could not restore original cache from {backup}: {error}")
        elif moved_old:
            errors.append(f"original cache backup disappeared: {backup}")
        return errors

    def seed(self, target_project: Path, *, replace: bool = False, dry_run: bool = False) -> dict[str, Any]:
        target_project, worktree_root = self._eligible_seed_target(target_project)
        destination = target_project / ".lake"
        target_digest = hashlib.sha256(str(destination).encode("utf-8")).hexdigest()
        target_lock = self.runtime_dir / "locks" / f"seed-{target_digest}.lock"
        if dry_run:
            return {
                **self.status(),
                "action": "seed",
                "dry_run": True,
                "target": str(destination),
                "worktree_root": str(worktree_root),
                "replace": replace,
            }
        started = time.monotonic()
        # Join the cache election before taking the target lock.  A seed racing
        # an elected builder waits and consumes its publication.
        with ExclusiveLock(self.lock_path) as cache_lock:
            if not self.is_ready(deep=True):
                raise CacheError(
                    "hot-main cache is missing or failed deep artifact verification"
                )
        with ExclusiveLock(target_lock) as seed_lock:
            checked_target, checked_root = self._eligible_seed_target(target_project)
            if checked_target != target_project or checked_root != worktree_root:
                raise CacheError("target worktree identity changed while waiting for the seed lock")
            if destination.is_symlink():
                raise CacheError(f"refusing to replace symlinked .lake directory: {destination}")
            if destination.exists() and not destination.is_dir():
                raise CacheError(f"target .lake must be a real directory: {destination}")
            if destination.exists() and not replace:
                raise CacheError(
                    f"target .lake already exists; pass --replace to replace it: {destination}"
                )
            staging_root = Path(tempfile.mkdtemp(prefix=".lake-seed-", dir=target_project))
            backup = target_project / f".lake.backup-{os.getpid()}-{time.monotonic_ns()}"
            rollback_new = staging_root / ".lake-failed-publication"
            moved_old = False
            try:
                staging_lake = staging_root / ".lake"
                copy_stats = reflink_copytree(self.lake_dir, staging_lake)
                make_owner_writable(staging_lake)
                if destination.exists():
                    os.replace(destination, backup)
                    moved_old = True
                try:
                    os.replace(staging_lake, destination)
                    self._validate_seeded_destination(destination)
                except Exception as error:
                    rollback_errors = self._rollback_seed_replacement(
                        destination,
                        backup,
                        rollback_new,
                        moved_old=moved_old,
                    )
                    if rollback_errors:
                        details = "; ".join(rollback_errors)
                        raise CacheError(f"seed failed ({error}); rollback incomplete: {details}") from error
                    raise
                backup_retained: str | None = None
                if moved_old and backup.exists():
                    try:
                        make_owner_writable(backup)
                        shutil.rmtree(backup)
                    except OSError:
                        backup_retained = str(backup)
                result = {
                    **self.status(),
                    "action": "seed",
                    "result": "seeded",
                    "target": str(destination),
                    "worktree_root": str(worktree_root),
                    "replaced": moved_old,
                    "backup_retained": backup_retained,
                    "cache_hit": 1,
                    "cache_miss": 0,
                    "lock_waited": int(cache_lock.waited or seed_lock.waited),
                    "lock_wait_seconds": round(cache_lock.wait_seconds + seed_lock.wait_seconds, 6),
                    "builds": 0,
                    "build_seconds": 0.0,
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "copy": asdict(copy_stats),
                }
                self._append_metric(result)
                return result
            finally:
                if staging_root.exists():
                    make_owner_writable(staging_root)
                    shutil.rmtree(staging_root)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--repo-root", default=str(default_root))
    parser.add_argument("--project-dir", default=".", help="Lake project root, relative to repository")
    parser.add_argument(
        "--runtime-dir",
        default=None,
        help="runtime/cache root (omitted: .workflow-runtime under the primary Git worktree)",
    )
    parser.add_argument("--main-ref", default="main")
    parser.add_argument("--main-commit", help="full SHA override, useful for detached/offline operation")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status", help="report the current identity and cache availability")

    warm = commands.add_parser("warm", help="elect one builder and atomically publish the main cache")
    warm.add_argument("--dry-run", action="store_true")

    seed = commands.add_parser("seed", help="copy the hot cache into an issue worktree")
    seed.add_argument("--worktree", required=True, help="target issue worktree / Lake project root")
    seed.add_argument("--replace", action="store_true")
    seed.add_argument("--dry-run", action="store_true")
    return parser


def run_cli(arguments: argparse.Namespace) -> dict[str, Any]:
    try:
        repo_root = Path(arguments.repo_root).resolve()
    except (OSError, RuntimeError) as error:
        raise CacheError(
            "could not resolve the repository root for the cache command; "
            "pass --runtime-dir explicitly"
        ) from error
    try:
        project_dir = _resolve(repo_root, arguments.project_dir).resolve()
    except (OSError, RuntimeError) as error:
        raise CacheError(f"could not resolve the project directory: {error}") from error
    runtime_dir = (
        default_runtime_dir(repo_root)
        if arguments.runtime_dir is None
        else _resolve(repo_root, arguments.runtime_dir)
    )
    cache = HotMainCache(
        repo_root,
        project_dir,
        runtime_dir,
        main_ref=arguments.main_ref,
        main_commit=arguments.main_commit,
    )
    if arguments.command == "status":
        return cache.status()
    if arguments.command == "warm":
        return cache.warm(dry_run=arguments.dry_run)
    if arguments.command == "seed":
        return cache.seed(
            _resolve(repo_root, arguments.worktree),
            replace=arguments.replace,
            dry_run=arguments.dry_run,
        )
    raise CacheError(f"unsupported command {arguments.command!r}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        result = run_cli(arguments)
    except CacheError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
