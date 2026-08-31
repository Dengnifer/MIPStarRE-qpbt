#!/usr/bin/env python3
"""Verify and locally materialize the exact unlicensed MIPStarRE foundation."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
from typing import Any, Iterator, Mapping, Sequence
import zlib


SCHEMA_VERSION = 1
HARD_MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
HARD_MAX_TAR_BYTES = 64 * 1024 * 1024
HARD_MAX_MEMBERS = 5000
HARD_MAX_MEMBER_BYTES = 2 * 1024 * 1024
HARD_MAX_REGULAR_BYTES = 64 * 1024 * 1024
BLOCK = 512


class MaterializationError(Exception):
    """A pinned-source operation failed without making upstream bytes canonical."""


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise MaterializationError(
            f"{label} keys differ: expected {sorted(expected)}, got {sorted(value)}"
        )


def _lower_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise MaterializationError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _positive_int(value: Any, label: str, *, allow_zero: bool = False) -> int:
    lower = 0 if allow_zero else 1
    if not isinstance(value, int) or isinstance(value, bool) or value < lower:
        raise MaterializationError(f"{label} must be an integer >= {lower}")
    return value


def load_pin(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_object_without_duplicates
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MaterializationError(f"could not load upstream pin: {error}") from error
    if not isinstance(value, dict):
        raise MaterializationError("upstream pin must be an object")
    _exact_keys(
        value,
        {"schema_version", "source", "rights", "archive", "output", "lean_pins", "foundations"},
        "upstream pin",
    )
    if value["schema_version"] != SCHEMA_VERSION:
        raise MaterializationError("unsupported upstream pin schema version")
    source = value["source"]
    rights = value["rights"]
    archive = value["archive"]
    output = value["output"]
    lean_pins = value["lean_pins"]
    foundations = value["foundations"]
    for label, item in (
        ("source", source),
        ("rights", rights),
        ("archive", archive),
        ("output", output),
        ("lean_pins", lean_pins),
    ):
        if not isinstance(item, dict):
            raise MaterializationError(f"{label} pin must be an object")
    _exact_keys(
        source,
        {"id", "repository", "repository_url", "commit", "archive_url", "acquisition_evidence"},
        "source",
    )
    _exact_keys(rights, {"license_file", "redistribution_permission", "policy"}, "rights")
    _exact_keys(
        archive,
        {
            "format", "sha256", "bytes", "tar_sha256", "tar_bytes", "exact_prefix",
            "global_pax_comment", "members", "regular_files", "directories",
            "regular_bytes", "max_member_bytes",
        },
        "archive",
    )
    _exact_keys(
        output,
        {
            "path", "archive_subtree", "reserved_authored_subtree", "directories", "files",
            "bytes", "max_file_bytes", "inventory_sha256",
        },
        "output",
    )
    _exact_keys(
        lean_pins, {"toolchain", "mathlib_input_revision", "mathlib_commit"}, "lean_pins"
    )
    if rights["license_file"] is not None:
        raise MaterializationError("pin must not imply a license file absent from the snapshot")
    if rights["redistribution_permission"] != "not-established":
        raise MaterializationError("pin must preserve the unresolved redistribution status")
    commit = source["commit"]
    if not isinstance(commit, str) or len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise MaterializationError("source commit must be a full lowercase Git SHA")
    if archive["global_pax_comment"] != commit:
        raise MaterializationError("global PAX comment must equal the source commit")
    if archive["format"] != "gzip-ustar-with-exact-global-pax-comment":
        raise MaterializationError("unsupported archive format")
    if archive["exact_prefix"] != f"MIPStarRE-{commit}/":
        raise MaterializationError("archive prefix does not bind the source commit")
    for key in ("sha256", "tar_sha256"):
        _lower_sha(archive[key], f"archive.{key}")
    for key in (
        "bytes", "tar_bytes", "members", "regular_files", "directories", "regular_bytes",
        "max_member_bytes",
    ):
        _positive_int(archive[key], f"archive.{key}")
    if archive["bytes"] > HARD_MAX_ARCHIVE_BYTES or archive["tar_bytes"] > HARD_MAX_TAR_BYTES:
        raise MaterializationError("archive pin exceeds the hard byte bounds")
    if archive["members"] > HARD_MAX_MEMBERS or archive["max_member_bytes"] > HARD_MAX_MEMBER_BYTES:
        raise MaterializationError("archive pin exceeds the hard member bounds")
    if archive["regular_bytes"] > HARD_MAX_REGULAR_BYTES:
        raise MaterializationError("archive pin exceeds the hard regular-byte bound")
    if output["path"] != "MIPStarRE" or output["archive_subtree"] != "MIPStarRE/":
        raise MaterializationError("output paths must retain the MIPStarRE module namespace")
    if output["reserved_authored_subtree"] != "QPBT/":
        raise MaterializationError("QPBT/ must remain reserved for project-authored files")
    for key in ("directories", "files", "bytes", "max_file_bytes"):
        _positive_int(output[key], f"output.{key}", allow_zero=key in {"files", "bytes"})
    _lower_sha(output["inventory_sha256"], "output.inventory_sha256")
    if not isinstance(foundations, list) or not foundations:
        raise MaterializationError("foundations must be a non-empty array")
    foundation_paths: set[str] = set()
    for index, foundation in enumerate(foundations):
        if not isinstance(foundation, dict):
            raise MaterializationError(f"foundations[{index}] must be an object")
        _exact_keys(foundation, {"module", "path", "sha256", "purpose"}, f"foundations[{index}]")
        path_value = foundation["path"]
        if not isinstance(path_value, str) or not path_value.startswith("MIPStarRE/"):
            raise MaterializationError(f"foundations[{index}].path is outside MIPStarRE")
        if path_value in foundation_paths:
            raise MaterializationError(f"duplicate foundation path {path_value!r}")
        foundation_paths.add(path_value)
        _lower_sha(foundation["sha256"], f"foundations[{index}].sha256")
        for key in ("module", "purpose"):
            if not isinstance(foundation[key], str) or not foundation[key]:
                raise MaterializationError(f"foundations[{index}].{key} must be non-empty")
    return value


def _assert_real_directory(path: Path) -> None:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as error:
        raise MaterializationError(f"required directory is unavailable: {path}") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise MaterializationError(f"required path is not a real directory: {path}")


def _reject_symlink_components(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            continue
        except OSError as error:
            raise MaterializationError(f"could not inspect path component {current}") from error
        if stat.S_ISLNK(mode):
            raise MaterializationError(f"path contains a symlink component: {current}")


def _read_regular_exact(path: Path, expected_bytes: int) -> bytes:
    _reject_symlink_components(path.parent)
    flags = os.O_RDONLY
    for name in ("O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, name, 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise MaterializationError(f"could not open pinned archive: {path}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise MaterializationError("pinned archive must be a regular file")
        if before.st_size != expected_bytes:
            raise MaterializationError(
                f"pinned archive size differs: expected {expected_bytes}, got {before.st_size}"
            )
        chunks: list[bytes] = []
        total = 0
        while total <= expected_bytes:
            block = os.read(descriptor, min(1024 * 1024, expected_bytes + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
        after = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        if identity(before) != identity(after):
            raise MaterializationError("pinned archive changed while it was read")
        if total != expected_bytes:
            raise MaterializationError(
                f"pinned archive read differs: expected {expected_bytes}, got {total}"
            )
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _decompress_gzip_exact(compressed: bytes, expected_bytes: int) -> bytes:
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = bytearray()
    try:
        for start in range(0, len(compressed), 64 * 1024):
            remaining = expected_bytes + 1 - len(output)
            if remaining <= 0:
                raise MaterializationError("gzip output exceeds the pinned tar byte bound")
            output.extend(decompressor.decompress(compressed[start : start + 64 * 1024], remaining))
            if decompressor.unconsumed_tail:
                raise MaterializationError("gzip output exceeds the pinned tar byte bound")
        if len(output) > expected_bytes:
            raise MaterializationError("gzip output exceeds the pinned tar byte bound")
        output.extend(decompressor.flush(expected_bytes + 1 - len(output)))
    except zlib.error as error:
        raise MaterializationError(f"invalid or truncated gzip archive: {error}") from error
    if not decompressor.eof:
        raise MaterializationError("gzip archive ended before the compressed stream")
    if decompressor.unused_data:
        raise MaterializationError("gzip archive contains a concatenated stream or trailing bytes")
    if len(output) != expected_bytes:
        raise MaterializationError(
            f"tar byte count differs: expected {expected_bytes}, got {len(output)}"
        )
    return bytes(output)


def _octal(field: bytes, label: str) -> int:
    stripped = field.rstrip(b"\0 ").lstrip(b" ")
    if not stripped:
        return 0
    if any(character not in b"01234567" for character in stripped):
        raise MaterializationError(f"tar {label} is not canonical octal")
    return int(stripped, 8)


def _string_field(field: bytes, label: str) -> str:
    raw, separator, padding = field.partition(b"\0")
    if separator and any(padding):
        raise MaterializationError(f"tar {label} has nonzero bytes after NUL")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MaterializationError(f"tar {label} is not UTF-8") from error


def _pax_records(payload: bytes) -> dict[str, str]:
    records: dict[str, str] = {}
    offset = 0
    while offset < len(payload):
        space = payload.find(b" ", offset)
        if space < 0 or not payload[offset:space].isdigit():
            raise MaterializationError("global PAX record has an invalid length")
        length = int(payload[offset:space])
        record = payload[offset : offset + length]
        if length <= space - offset + 2 or len(record) != length or not record.endswith(b"\n"):
            raise MaterializationError("global PAX record length does not match its bytes")
        key_value = record[space - offset + 1 : -1]
        key, separator, value = key_value.partition(b"=")
        if not separator:
            raise MaterializationError("global PAX record lacks '='")
        try:
            decoded_key = key.decode("ascii")
            decoded_value = value.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MaterializationError("global PAX record is not valid text") from error
        if decoded_key in records:
            raise MaterializationError(f"duplicate global PAX key {decoded_key!r}")
        records[decoded_key] = decoded_value
        offset += length
    return records


def _safe_member_path(name: str, exact_prefix: str, *, directory: bool) -> str:
    if "\\" in name or name.startswith("/"):
        raise MaterializationError(f"unsafe tar member path {name!r}")
    if directory and not name.endswith("/"):
        raise MaterializationError(f"tar directory lacks a trailing slash: {name!r}")
    normalized_name = name[:-1] if directory else name
    root = exact_prefix[:-1]
    if normalized_name == root:
        relative = ""
    elif normalized_name.startswith(exact_prefix):
        relative = normalized_name[len(exact_prefix) :]
    else:
        raise MaterializationError(f"tar member is outside exact prefix {exact_prefix!r}: {name!r}")
    parts = relative.split("/") if relative else []
    if relative and any(part in {"", ".", ".."} for part in parts):
        raise MaterializationError(f"unsafe normalized tar path {relative!r}")
    return "/".join(parts)


def _inventory_digest(
    directories: Sequence[str], files: Sequence[tuple[str, bytes]]
) -> str:
    digest = hashlib.sha256()
    for relative in sorted(directories):
        digest.update(f"d\0MIPStarRE{('/' + relative) if relative else ''}\n".encode("utf-8"))
    for relative, payload in sorted(files):
        path = f"MIPStarRE/{relative}"
        digest.update(
            f"f\0{path}\0{len(payload)}\0{hashlib.sha256(payload).hexdigest()}\n".encode("utf-8")
        )
    return digest.hexdigest()


def inspect_archive_bytes(
    compressed: bytes,
    *,
    commit: str,
    exact_prefix: str,
    archive_subtree: str = "MIPStarRE/",
    reserved_authored_subtree: str = "QPBT/",
    expected_tar_bytes: int,
) -> tuple[dict[str, Any], list[str], list[tuple[str, bytes]]]:
    if len(compressed) > HARD_MAX_ARCHIVE_BYTES:
        raise MaterializationError("compressed archive exceeds the hard byte bound")
    tar_bytes = _decompress_gzip_exact(compressed, expected_tar_bytes)
    if len(tar_bytes) > HARD_MAX_TAR_BYTES:
        raise MaterializationError("tar archive exceeds the hard byte bound")
    offset = 0
    members = 0
    regular_files = 0
    directories = 0
    regular_bytes = 0
    max_member_bytes = 0
    seen: set[str] = set()
    global_pax_seen = False
    output_directories: list[str] = []
    output_files: list[tuple[str, bytes]] = []
    while offset + BLOCK <= len(tar_bytes):
        header = tar_bytes[offset : offset + BLOCK]
        if header == bytes(BLOCK):
            if tar_bytes[offset + BLOCK : offset + 2 * BLOCK] != bytes(BLOCK):
                raise MaterializationError("tar archive lacks the second end marker")
            if any(tar_bytes[offset + 2 * BLOCK :]):
                raise MaterializationError("tar archive has nonzero bytes after its end markers")
            break
        stored_checksum = _octal(header[148:156], "checksum")
        checksum_header = header[:148] + b" " * 8 + header[156:]
        if sum(checksum_header) != stored_checksum:
            raise MaterializationError("tar header checksum mismatch")
        if header[257:263] != b"ustar\0" or header[263:265] != b"00":
            raise MaterializationError("tar member is not canonical POSIX ustar")
        name = _string_field(header[:100], "name")
        prefix = _string_field(header[345:500], "prefix")
        if prefix:
            name = f"{prefix}/{name}"
        link_name = _string_field(header[157:257], "link name")
        size = _octal(header[124:136], "size")
        type_flag = header[156:157]
        payload_start = offset + BLOCK
        payload_end = payload_start + size
        padded_end = payload_start + ((size + BLOCK - 1) // BLOCK) * BLOCK
        if payload_end > len(tar_bytes) or padded_end > len(tar_bytes):
            raise MaterializationError("tar member payload is truncated")
        payload = tar_bytes[payload_start:payload_end]
        if any(tar_bytes[payload_end:padded_end]):
            raise MaterializationError("tar member padding is nonzero")
        offset = padded_end
        if size > HARD_MAX_MEMBER_BYTES:
            raise MaterializationError("tar member exceeds the hard size bound")
        if type_flag == b"g":
            if global_pax_seen or members or name != "pax_global_header":
                raise MaterializationError("global PAX header must occur exactly once before members")
            if _pax_records(payload) != {"comment": commit}:
                raise MaterializationError("global PAX header differs from the exact commit comment")
            global_pax_seen = True
            continue
        if type_flag not in {b"0", b"5"}:
            raise MaterializationError(
                f"tar type {type_flag!r} is forbidden (links, devices, local PAX, and GNU extensions)"
            )
        if link_name:
            raise MaterializationError("regular/directory tar member has a link target")
        directory = type_flag == b"5"
        if directory and size:
            raise MaterializationError("tar directory has a nonzero payload")
        relative = _safe_member_path(name, exact_prefix, directory=directory)
        if relative in seen:
            raise MaterializationError(f"duplicate tar member path {relative!r}")
        seen.add(relative)
        members += 1
        if members > HARD_MAX_MEMBERS:
            raise MaterializationError("tar member count exceeds the hard bound")
        if directory:
            directories += 1
        else:
            regular_files += 1
            regular_bytes += size
            max_member_bytes = max(max_member_bytes, size)
            if regular_bytes > HARD_MAX_REGULAR_BYTES:
                raise MaterializationError("tar regular bytes exceed the hard bound")
        if relative == archive_subtree[:-1] and directory:
            output_directories.append("")
        elif relative.startswith(archive_subtree):
            output_relative = relative[len(archive_subtree) :]
            if output_relative == reserved_authored_subtree[:-1] or output_relative.startswith(
                reserved_authored_subtree
            ):
                raise MaterializationError("upstream archive occupies the project-authored QPBT namespace")
            if directory:
                output_directories.append(output_relative)
            else:
                output_files.append((output_relative, payload))
    else:
        raise MaterializationError("tar archive has no complete end markers")
    if not global_pax_seen:
        raise MaterializationError("tar archive lacks the exact global provenance header")
    output_bytes = sum(len(payload) for _, payload in output_files)
    facts = {
        "archive": {
            "sha256": hashlib.sha256(compressed).hexdigest(),
            "bytes": len(compressed),
            "tar_sha256": hashlib.sha256(tar_bytes).hexdigest(),
            "tar_bytes": len(tar_bytes),
            "members": members,
            "regular_files": regular_files,
            "directories": directories,
            "regular_bytes": regular_bytes,
            "max_member_bytes": max_member_bytes,
        },
        "output": {
            "directories": len(output_directories),
            "files": len(output_files),
            "bytes": output_bytes,
            "max_file_bytes": max((len(payload) for _, payload in output_files), default=0),
            "inventory_sha256": _inventory_digest(output_directories, output_files),
        },
    }
    return facts, output_directories, output_files


def _compare_facts(pin: Mapping[str, Any], facts: Mapping[str, Any]) -> None:
    for section in ("archive", "output"):
        for key, observed in facts[section].items():
            expected = pin[section][key]
            if observed != expected:
                raise MaterializationError(
                    f"{section}.{key} differs: expected {expected!r}, got {observed!r}"
                )


def inspect_archive(path: Path, pin: Mapping[str, Any]) -> tuple[dict[str, Any], list[str], list[tuple[str, bytes]]]:
    compressed = _read_regular_exact(path, pin["archive"]["bytes"])
    facts, directories, files = inspect_archive_bytes(
        compressed,
        commit=pin["source"]["commit"],
        exact_prefix=pin["archive"]["exact_prefix"],
        archive_subtree=pin["output"]["archive_subtree"],
        reserved_authored_subtree=pin["output"]["reserved_authored_subtree"],
        expected_tar_bytes=pin["archive"]["tar_bytes"],
    )
    _compare_facts(pin, facts)
    foundation_hashes = {f"MIPStarRE/{relative}": hashlib.sha256(payload).hexdigest() for relative, payload in files}
    for foundation in pin["foundations"]:
        if foundation_hashes.get(foundation["path"]) != foundation["sha256"]:
            raise MaterializationError(f"foundation pin differs for {foundation['path']}")
    return facts, directories, files


def _read_output_file(path: Path, max_bytes: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise MaterializationError(f"could not safely open materialized file: {path}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise MaterializationError(f"unsafe or oversized materialized file: {path}")
        chunks: list[bytes] = []
        total = 0
        while total <= max_bytes:
            block = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise MaterializationError(f"materialized file changed while read: {path}")
        if total != before.st_size:
            raise MaterializationError(f"materialized file size changed while read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _scan_authored_tree(root: Path) -> tuple[int, int, str]:
    if not root.exists() and not root.is_symlink():
        return 0, 0, hashlib.sha256().hexdigest()
    metadata = root.stat(follow_symlinks=False)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise MaterializationError("project-authored QPBT path must be a real directory")
    records: list[tuple[str, bytes]] = []
    for directory, names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        names.sort()
        file_names.sort()
        for name in names:
            path = base / name
            mode = path.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise MaterializationError(f"unsafe project-authored directory: {path}")
        for name in file_names:
            path = base / name
            records.append((path.relative_to(root).as_posix(), _read_output_file(path, HARD_MAX_MEMBER_BYTES)))
    digest = hashlib.sha256()
    for relative, payload in records:
        digest.update(f"{relative}\0{len(payload)}\0{hashlib.sha256(payload).hexdigest()}\n".encode())
    return len(records), sum(len(payload) for _, payload in records), digest.hexdigest()


def verify_materialized(repo_root: Path, pin: Mapping[str, Any]) -> dict[str, Any]:
    destination = repo_root / pin["output"]["path"]
    try:
        metadata = destination.stat(follow_symlinks=False)
    except OSError as error:
        raise MaterializationError("materialized MIPStarRE root is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise MaterializationError("materialized MIPStarRE root is not a real directory")
    directories: list[str] = [""]
    files: list[tuple[str, bytes]] = []
    authored = destination / pin["output"]["reserved_authored_subtree"][:-1]
    authored_facts = _scan_authored_tree(authored)
    for directory, names, file_names in os.walk(destination, topdown=True, followlinks=False):
        base = Path(directory)
        relative_base = base.relative_to(destination).as_posix()
        names.sort()
        file_names.sort()
        retained: list[str] = []
        for name in names:
            path = base / name
            mode = path.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise MaterializationError(f"unsafe materialized directory: {path}")
            if base == destination and path == authored:
                continue
            retained.append(name)
            directories.append(path.relative_to(destination).as_posix())
        names[:] = retained
        if relative_base == pin["output"]["reserved_authored_subtree"][:-1]:
            continue
        for name in file_names:
            path = base / name
            files.append(
                (path.relative_to(destination).as_posix(), _read_output_file(path, pin["output"]["max_file_bytes"]))
            )
    observed = {
        "directories": len(directories),
        "files": len(files),
        "bytes": sum(len(payload) for _, payload in files),
        "max_file_bytes": max((len(payload) for _, payload in files), default=0),
        "inventory_sha256": _inventory_digest(directories, files),
    }
    for key, value in observed.items():
        if value != pin["output"][key]:
            raise MaterializationError(
                f"materialized output {key} differs: expected {pin['output'][key]!r}, got {value!r}"
            )
    foundation_hashes = {f"MIPStarRE/{relative}": hashlib.sha256(payload).hexdigest() for relative, payload in files}
    for foundation in pin["foundations"]:
        if foundation_hashes.get(foundation["path"]) != foundation["sha256"]:
            raise MaterializationError(f"materialized foundation differs: {foundation['path']}")
    return {
        "status": "verified",
        **observed,
        "authored_qpbt_files": authored_facts[0],
        "authored_qpbt_bytes": authored_facts[1],
        "authored_qpbt_sha256": authored_facts[2],
    }


def _write_new_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_tree(root: Path) -> None:
    for directory, _, _ in os.walk(root, topdown=False, followlinks=False):
        _fsync_directory(Path(directory))


def _copy_authored_tree(source: Path, destination: Path) -> tuple[int, int, str]:
    before = _scan_authored_tree(source)
    if before[0] == 0 and not source.exists():
        return before
    destination.mkdir(parents=True)
    for directory, names, file_names in os.walk(source, followlinks=False):
        base = Path(directory)
        relative = base.relative_to(source)
        target_base = destination / relative
        names.sort()
        file_names.sort()
        for name in names:
            (target_base / name).mkdir()
        for name in file_names:
            payload = _read_output_file(base / name, HARD_MAX_MEMBER_BYTES)
            _write_new_file(target_base / name, payload)
    after = _scan_authored_tree(destination)
    if after != before:
        raise MaterializationError("project-authored QPBT tree changed while copied")
    return after


def _cleanup_tombstone(transaction: Path) -> Path:
    return transaction.with_name(f"{transaction.name}.cleanup")


def _finish_cleanup(cleanup: Path) -> None:
    if not cleanup.exists() and not cleanup.is_symlink():
        return
    mode = cleanup.stat(follow_symlinks=False).st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise MaterializationError(f"unsafe cleanup tombstone: {cleanup}")
    shutil.rmtree(cleanup)
    _fsync_directory(cleanup.parent)


def _commit_cleanup(transaction: Path) -> None:
    cleanup = _cleanup_tombstone(transaction)
    if cleanup.exists() or cleanup.is_symlink():
        raise MaterializationError(f"cleanup tombstone already exists: {cleanup}")
    os.replace(transaction, cleanup)
    _fsync_directory(cleanup.parent)
    _finish_cleanup(cleanup)


def _rollback(transaction: Path, destination: Path, original_present: bool) -> list[str]:
    errors: list[str] = []
    backup = transaction / "backup" / "MIPStarRE"
    incomplete = transaction / "incomplete-MIPStarRE"
    try:
        backup_present = backup.exists() or backup.is_symlink()
        if backup_present:
            backup_mode = backup.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(backup_mode) or not stat.S_ISDIR(backup_mode):
                raise MaterializationError("rollback backup is not a real directory")
        if original_present and not backup_present:
            if not destination.exists():
                raise MaterializationError("rollback expected a backup, but neither copy exists")
        elif original_present and backup_present:
            if destination.exists() or destination.is_symlink():
                mode = destination.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                    raise MaterializationError("unsafe destination during rollback")
                os.replace(destination, incomplete)
            os.replace(backup, destination)
        elif not original_present and (destination.exists() or destination.is_symlink()):
            mode = destination.stat(follow_symlinks=False).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise MaterializationError("unsafe new destination during rollback")
            os.replace(destination, incomplete)
    except (OSError, MaterializationError) as error:
        errors.append(str(error))
    if errors:
        return errors
    try:
        _fsync_directory(destination.parent)
        _commit_cleanup(transaction)
    except (OSError, MaterializationError) as error:
        errors.append(str(error))
    return errors


def _transaction_document(destination: Path, original_present: bool) -> bytes:
    return (
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "destination": str(destination.resolve()),
                "original_present": original_present,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("ascii")


def _recover(transaction: Path, destination: Path, pin: Mapping[str, Any]) -> None:
    if not transaction.exists() and not transaction.is_symlink():
        return
    mode = transaction.stat(follow_symlinks=False).st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise MaterializationError(f"unsafe materialization transaction: {transaction}")
    try:
        marker = json.loads(_read_output_file(transaction / "transaction.json", 4096))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, MaterializationError) as error:
        raise MaterializationError(f"invalid materialization transaction marker: {transaction}") from error
    if (
        not isinstance(marker, dict)
        or set(marker) != {"schema_version", "destination", "original_present"}
        or marker["schema_version"] != SCHEMA_VERSION
        or marker["destination"] != str(destination.resolve())
        or not isinstance(marker["original_present"], bool)
    ):
        raise MaterializationError(f"unauthorized materialization transaction: {transaction}")
    try:
        verify_materialized(destination.parent, pin)
    except (OSError, MaterializationError):
        errors = _rollback(transaction, destination, marker["original_present"])
        if errors:
            raise MaterializationError(
                f"stale transaction recovery failed; preserved {transaction}: {'; '.join(errors)}"
            )
    else:
        _commit_cleanup(transaction)


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise MaterializationError(f"could not safely open materialization lock: {path}") from error
    with os.fdopen(descriptor, "a+", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise MaterializationError(f"materialization lock is not a regular file: {path}")
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def validate_project_pins(repo_root: Path, pin: Mapping[str, Any]) -> None:
    try:
        toolchain = (repo_root / "lean-toolchain").read_text(encoding="ascii").strip()
        manifest = json.loads((repo_root / "lake-manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MaterializationError(f"could not validate authored Lean pins: {error}") from error
    if toolchain != pin["lean_pins"]["toolchain"]:
        raise MaterializationError("lean-toolchain differs from the upstream factual pin")
    packages = manifest.get("packages") if isinstance(manifest, dict) else None
    mathlib = next(
        (package for package in packages or [] if isinstance(package, dict) and package.get("name") == "mathlib"),
        None,
    )
    if (
        mathlib is None
        or mathlib.get("inputRev") != pin["lean_pins"]["mathlib_input_revision"]
        or mathlib.get("rev") != pin["lean_pins"]["mathlib_commit"]
    ):
        raise MaterializationError("lake-manifest mathlib pin differs from provenance")


def materialize(
    repo_root: Path,
    pin_path: Path,
    archive_path: Path,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    repo_root = Path(os.path.abspath(repo_root))
    _assert_real_directory(repo_root)
    expected_pin = repo_root / "references" / "mipstarre-upstream.json"
    if Path(os.path.abspath(pin_path)) != expected_pin:
        raise MaterializationError("pin path must be repository-local references/mipstarre-upstream.json")
    pin = load_pin(pin_path)
    validate_project_pins(repo_root, pin)
    destination = repo_root / pin["output"]["path"]
    runtime = repo_root / ".workflow-runtime" / "mipstarre-materialization"
    _reject_symlink_components(runtime.parent)
    runtime.mkdir(parents=True, exist_ok=True)
    _assert_real_directory(runtime)
    if repo_root.stat().st_dev != runtime.stat().st_dev:
        raise MaterializationError("runtime and destination must share one filesystem")
    transaction = runtime / "MIPStarRE.transaction"
    with _locked(runtime / "MIPStarRE.lock"):
        _finish_cleanup(_cleanup_tombstone(transaction))
        _recover(transaction, destination, pin)
        existing = destination.exists() or destination.is_symlink()
        if existing:
            try:
                evidence = verify_materialized(repo_root, pin)
            except (OSError, MaterializationError) as error:
                mode = destination.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                    raise MaterializationError("unsafe existing MIPStarRE output was preserved") from error
                if not replace_existing:
                    raise MaterializationError("invalid existing MIPStarRE output was preserved") from error
            else:
                evidence.update({"status": "cached", "elapsed_seconds": round(time.monotonic() - started, 6)})
                return evidence
        facts, directories, files = inspect_archive(archive_path, pin)
        preparation = _cleanup_tombstone(transaction)
        original_present = existing
        try:
            preparation.mkdir(mode=0o700)
            _write_new_file(preparation / "transaction.json", _transaction_document(destination, original_present))
            stage = preparation / "stage" / "MIPStarRE"
            backup = preparation / "backup"
            stage.mkdir(parents=True)
            backup.mkdir()
            for relative in sorted(directories, key=lambda value: (value.count("/"), value)):
                if relative:
                    (stage / relative).mkdir()
            for relative, payload in sorted(files):
                _write_new_file(stage / relative, payload)
            if existing:
                _copy_authored_tree(destination / "QPBT", stage / "QPBT")
            _fsync_tree(preparation)
            _fsync_directory(runtime)
            os.replace(preparation, transaction)
            _fsync_directory(runtime)
        except (OSError, MaterializationError) as error:
            try:
                if transaction.exists():
                    _commit_cleanup(transaction)
                else:
                    _finish_cleanup(preparation)
            except (OSError, MaterializationError) as cleanup_error:
                raise MaterializationError(
                    f"could not prepare transaction; cleanup state preserved: {preparation}"
                ) from cleanup_error
            raise MaterializationError("could not prepare materialization transaction") from error
        try:
            if existing:
                os.replace(destination, transaction / "backup" / "MIPStarRE")
                _fsync_directory(transaction / "backup")
                _fsync_directory(repo_root)
            os.replace(transaction / "stage" / "MIPStarRE", destination)
            _fsync_directory(repo_root)
            verified = verify_materialized(repo_root, pin)
        except BaseException as error:
            rollback_errors = _rollback(transaction, destination, original_present)
            if rollback_errors:
                raise MaterializationError(
                    f"publication failed and rollback is incomplete; preserved {transaction}: "
                    + "; ".join(rollback_errors)
                ) from error
            raise
        _commit_cleanup(transaction)
        verified.update(
            {
                "status": "published",
                "archive_sha256": facts["archive"]["sha256"],
                "source_commit": pin["source"]["commit"],
                "elapsed_seconds": round(time.monotonic() - started, 6),
            }
        )
        return verified


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(root))
    parser.add_argument("--pin", default="references/mipstarre-upstream.json")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="verify the exact archive without publication")
    materialize_parser = commands.add_parser("materialize", help="publish the ignored local foundation")
    for command in (inspect, materialize_parser):
        archive = command.add_mutually_exclusive_group(required=True)
        archive.add_argument("--archive")
        archive.add_argument("--archive-env")
    materialize_parser.add_argument("--replace-existing", action="store_true")
    commands.add_parser("verify", help="verify the existing ignored foundation")
    return parser


def _archive_argument(arguments: argparse.Namespace) -> Path:
    if arguments.archive:
        return Path(arguments.archive)
    value = os.environ.get(arguments.archive_env)
    if not value:
        raise MaterializationError(
            f"archive environment variable {arguments.archive_env!r} is unset or empty"
        )
    return Path(value)


def run_cli(arguments: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(arguments.repo_root).resolve()
    pin_path = Path(arguments.pin)
    if not pin_path.is_absolute():
        pin_path = repo_root / pin_path
    expected_pin = repo_root / "references" / "mipstarre-upstream.json"
    if Path(os.path.abspath(pin_path)) != expected_pin:
        raise MaterializationError("pin path must be repository-local references/mipstarre-upstream.json")
    pin = load_pin(pin_path)
    validate_project_pins(repo_root, pin)
    if arguments.command == "verify":
        return verify_materialized(repo_root, pin)
    archive_path = _archive_argument(arguments)
    if arguments.command == "inspect":
        facts, _, _ = inspect_archive(archive_path, pin)
        return {"status": "verified", "source_commit": pin["source"]["commit"], **facts}
    return materialize(
        repo_root,
        pin_path,
        archive_path,
        replace_existing=arguments.replace_existing,
    )


def main(argv: Sequence[str] | None = None) -> int:
    try:
        result = run_cli(build_parser().parse_args(argv))
    except (MaterializationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
