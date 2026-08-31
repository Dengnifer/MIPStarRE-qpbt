#!/usr/bin/env python3
"""Validate, extract, and byte-split the pinned arXiv source archive."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping
import zlib

import reference_transport


SCHEMA_VERSION = 1
ARCHIVE_MAX_BYTES = 233859
TAR_MAX_BYTES = 2 * 1024 * 1024
CONTRACT_MAX_BYTES = 64 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LABEL_PATTERN_TEXT = r"\\label\{([^{}\r\n]+)\}"
LABEL_PATTERN = re.compile(br"\\label\{([^{}\r\n]+)\}")
EXPECTED_MEMBER_NAMES = {"compression_arXiv_v3.tex", "compression_arXiv_v3.bbl"}
ARCHIVE_CACHE_NAME = "2001.04383v3-source.tar"


class SourceError(RuntimeError):
    """A deterministic source validation or extraction failure."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SourceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_json_contract(payload: bytes, context: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceError(f"cannot decode JSON contract {context}: {error}") from error
    if not isinstance(value, dict):
        raise SourceError(f"JSON contract must be an object: {context}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise SourceError(f"cannot read JSON contract {path}: {error}") from error
    return _decode_json_contract(payload, str(path))


def _exact_keys(value: Mapping[str, Any], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise SourceError(f"{context} keys differ from schema")


def _positive_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SourceError(f"{context} must be a positive integer")
    return value


def _digest(value: Any, context: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SourceError(f"{context} must be a lowercase SHA-256 digest")
    return value


def validate_source_pin(pin: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    _exact_keys(pin, {"schema_version", "source_id", "url", "allowed_hosts", "archive", "members"}, "source pin")
    if pin["schema_version"] != SCHEMA_VERSION or pin["source_id"] != "arxiv-2001.04383v3":
        raise SourceError("source pin identity or schema is unsupported")
    if pin["url"] != "https://arxiv.org/src/2001.04383v3":
        raise SourceError("source URL is not the pinned arXiv endpoint")
    if pin["allowed_hosts"] != ["arxiv.org", "export.arxiv.org"]:
        raise SourceError("source redirect hosts differ from the audited allowlist")
    archive = pin["archive"]
    if not isinstance(archive, dict):
        raise SourceError("archive pin must be an object")
    _exact_keys(archive, {"bytes", "sha256"}, "archive pin")
    if _positive_int(archive["bytes"], "archive bytes") != ARCHIVE_MAX_BYTES:
        raise SourceError("archive size differs from the audited pin")
    _digest(archive["sha256"], "archive sha256")
    members = pin["members"]
    if not isinstance(members, list) or len(members) != 2:
        raise SourceError("source pin must contain exactly two members")
    by_name: dict[str, Mapping[str, Any]] = {}
    for member in members:
        if not isinstance(member, dict):
            raise SourceError("member pin must be an object")
        _exact_keys(member, {"name", "bytes", "sha256", "crlf_lines"}, "member pin")
        name = member["name"]
        if name not in EXPECTED_MEMBER_NAMES or name in by_name:
            raise SourceError("member name is unexpected or duplicated")
        _positive_int(member["bytes"], f"{name} bytes")
        _positive_int(member["crlf_lines"], f"{name} CRLF lines")
        _digest(member["sha256"], f"{name} sha256")
        by_name[name] = member
    if set(by_name) != EXPECTED_MEMBER_NAMES:
        raise SourceError("member allowlist is incomplete")
    return by_name


def _validate_slice(raw: Any, line_count: int, context: str) -> tuple[str, int, int, int, str, int]:
    if not isinstance(raw, list) or len(raw) != 6:
        raise SourceError(f"{context} slice must have six fields")
    identifier, first, last, byte_count, digest, label_count = raw
    if not isinstance(identifier, str) or not ID_RE.fullmatch(identifier):
        raise SourceError(f"{context} slice id is invalid")
    first = _positive_int(first, f"{identifier} first line")
    last = _positive_int(last, f"{identifier} last line")
    if first > last or last > line_count:
        raise SourceError(f"{identifier} line range is invalid")
    byte_count = _positive_int(byte_count, f"{identifier} bytes")
    digest = _digest(digest, f"{identifier} sha256")
    if isinstance(label_count, bool) or not isinstance(label_count, int) or label_count < 0:
        raise SourceError(f"{identifier} label count is invalid")
    return identifier, first, last, byte_count, digest, label_count


def validate_manifest(manifest: Mapping[str, Any]) -> list[tuple[str, tuple[str, int, int, int, str, int]]]:
    _exact_keys(manifest, {"schema_version", "source_member", "source_bytes", "source_sha256", "source_crlf_lines", "output_path_template", "collections", "slice_metadata", "labels"}, "split manifest")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest["source_member"] != "compression_arXiv_v3.tex":
        raise SourceError("split manifest identity or schema is unsupported")
    line_count = _positive_int(manifest["source_crlf_lines"], "source CRLF lines")
    _positive_int(manifest["source_bytes"], "source bytes")
    _digest(manifest["source_sha256"], "source sha256")
    if manifest["output_path_template"] != "{output_directory}/{id}.tex":
        raise SourceError("output path convention differs from the closed schema")
    collections = manifest["collections"]
    if not isinstance(collections, list) or len(collections) != 4:
        raise SourceError("split manifest must contain four collections")
    expected_collections = [
        ("top-level", "top-level", "exact", [1, 14935]),
        ("qpbt-main", "qpbt", "exact", [5028, 5766]),
        ("qpbt-appendix", "qpbt", "exact", [13032, 14930]),
        ("dependencies", "dependencies", "sparse", [[1317, 1822], [1854, 2877], [2884, 3417], [3567, 4148], [4163, 5027]]),
    ]
    result: list[tuple[str, tuple[str, int, int, int, str, int]]] = []
    output_paths: set[str] = set()
    for index, collection in enumerate(collections):
        if not isinstance(collection, dict):
            raise SourceError("collection must be an object")
        required = {"id", "output_directory", "coverage", "slices"}
        allowed = required | {"scope", "scopes"}
        if not required.issubset(collection) or not set(collection).issubset(allowed):
            raise SourceError("collection keys differ from schema")
        collection_id, expected_directory, expected_coverage, expected_scope = expected_collections[index]
        if collection["id"] != collection_id:
            raise SourceError("collection order or identity differs from contract")
        coverage = collection["coverage"]
        if coverage != expected_coverage:
            raise SourceError("collection coverage differs from the canonical descriptor")
        directory = collection["output_directory"]
        if directory != expected_directory:
            raise SourceError("collection output directory differs from the canonical descriptor")
        slices_raw = collection["slices"]
        if not isinstance(slices_raw, list) or not slices_raw:
            raise SourceError("collection must contain slices")
        parsed = [_validate_slice(item, line_count, collection_id) for item in slices_raw]
        for item in parsed:
            output_path = f"{directory}/{item[0]}.tex"
            if output_path in output_paths:
                raise SourceError("slice output path is duplicated")
            output_paths.add(output_path)
            result.append((output_path, item))
        if coverage == "exact":
            scope = collection.get("scope")
            if scope != expected_scope or "scopes" in collection:
                raise SourceError("exact collection scope differs from the canonical descriptor")
            scope_first = _positive_int(scope[0], "scope first line")
            scope_last = _positive_int(scope[1], "scope last line")
            cursor = scope_first
            for _, first, last, _, _, _ in parsed:
                if first != cursor:
                    raise SourceError(f"{collection_id} is not an exact ordered cover")
                cursor = last + 1
            if cursor != scope_last + 1:
                raise SourceError(f"{collection_id} does not end at its scope boundary")
        else:
            scopes = collection.get("scopes")
            if scopes != expected_scope or "scope" in collection:
                raise SourceError("sparse collection scopes differ from the canonical descriptor")
            slice_index = 0
            for scope_first, scope_last in scopes:
                cursor = scope_first
                while slice_index < len(parsed) and parsed[slice_index][1] <= scope_last:
                    _, first, last, _, _, _ = parsed[slice_index]
                    if first != cursor or last > scope_last:
                        raise SourceError("sparse collection does not exactly cover its declared scopes")
                    cursor = last + 1
                    slice_index += 1
                if cursor != scope_last + 1:
                    raise SourceError("sparse collection does not exactly cover its declared scopes")
            if slice_index != len(parsed):
                raise SourceError("sparse collection has slices outside its declared scopes")
    metadata = manifest["slice_metadata"]
    if not isinstance(metadata, dict) or set(metadata) != output_paths:
        raise SourceError("slice metadata paths differ from generated output paths")
    for output_path, item in metadata.items():
        if not isinstance(item, dict):
            raise SourceError(f"slice metadata must be an object: {output_path}")
        _exact_keys(item, {"heading", "qpbt_relevance"}, f"slice metadata {output_path}")
        if not isinstance(item["heading"], str) or not item["heading"].strip():
            raise SourceError(f"slice heading is empty: {output_path}")
        if item["qpbt_relevance"] not in ("core", "dependency", "context"):
            raise SourceError(f"slice relevance is invalid: {output_path}")
    labels = manifest["labels"]
    if not isinstance(labels, dict):
        raise SourceError("label contract must be an object")
    _exact_keys(labels, {"encoding", "regex", "occurrences", "unique_names", "duplicate_names", "generated_path", "generated_bytes", "generated_sha256", "records"}, "label contract")
    if labels["encoding"] != "utf-8" or labels["regex"] != LABEL_PATTERN_TEXT:
        raise SourceError("label encoding or lexical pattern differs from contract")
    if labels["occurrences"] != 646 or labels["unique_names"] != 645:
        raise SourceError("label cardinalities differ from audited values")
    if labels["duplicate_names"] != {"eq:farith": [8928, 10391]}:
        raise SourceError("label duplicate contract differs from audited values")
    if labels["generated_path"] != "sections/labels.json":
        raise SourceError("generated label path differs from the closed schema")
    _positive_int(labels["generated_bytes"], "generated label bytes")
    _digest(labels["generated_sha256"], "generated label sha256")
    if labels["records"] != ["ordinal", "name_ordinal", "name", "line", "byte_column", "byte_start", "byte_end", "output_paths"]:
        raise SourceError("label record schema differs from contract")
    return result


def _strict_octal(field: bytes, context: str) -> int:
    if field and field[0] & 0x80:
        raise SourceError(f"base-256 {context} is forbidden")
    stripped = field.rstrip(b"\0 ").lstrip(b" ")
    if not stripped or any(byte < ord("0") or byte > ord("7") for byte in stripped):
        raise SourceError(f"invalid tar {context}")
    return int(stripped, 8)


def _tar_name(header: bytes) -> str:
    name_field = header[:100]
    prefix_field = header[345:500]
    if prefix_field.strip(b"\0"):
        raise SourceError("tar prefix paths are forbidden")
    raw_name, separator, tail = name_field.partition(b"\0")
    if separator and tail.strip(b"\0"):
        raise SourceError("tar member name has nonzero bytes after NUL")
    try:
        return raw_name.decode("ascii")
    except UnicodeDecodeError as error:
        raise SourceError("tar member name is not ASCII") from error


def _decompress_gzip(archive: bytes) -> bytes:
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    output = bytearray()
    try:
        for offset in range(0, len(archive), 64 * 1024):
            output.extend(decompressor.decompress(archive[offset : offset + 64 * 1024], TAR_MAX_BYTES + 1 - len(output)))
            if len(output) > TAR_MAX_BYTES or decompressor.unconsumed_tail:
                raise SourceError("decompressed tar exceeds its byte bound")
        output.extend(decompressor.flush(TAR_MAX_BYTES + 1 - len(output)))
    except zlib.error as error:
        raise SourceError(f"invalid gzip stream: {error}") from error
    if len(output) > TAR_MAX_BYTES:
        raise SourceError("decompressed tar exceeds its byte bound")
    if not decompressor.eof or decompressor.unused_data:
        raise SourceError("gzip stream is truncated or concatenated")
    return bytes(output)


def extract_pinned_members(archive: bytes, pin: Mapping[str, Any]) -> dict[str, bytes]:
    members_by_name = validate_source_pin(pin)
    archive_pin = pin["archive"]
    if len(archive) != archive_pin["bytes"] or sha256_bytes(archive) != archive_pin["sha256"]:
        raise SourceError("archive bytes or checksum differ from pin")
    tar = _decompress_gzip(archive)
    extracted: dict[str, bytes] = {}
    offset = 0
    while offset + 512 <= len(tar):
        header = tar[offset : offset + 512]
        if header == bytes(512):
            break
        if len(header) != 512:
            raise SourceError("truncated tar header")
        checksum = _strict_octal(header[148:156], "checksum")
        checksum_bytes = header[:148] + b" " * 8 + header[156:]
        if sum(checksum_bytes) != checksum:
            raise SourceError("tar header checksum mismatch")
        name = _tar_name(header)
        typeflag = header[156:157]
        linkname = header[157:257].rstrip(b"\0")
        if typeflag != b"0" or linkname:
            raise SourceError("only explicit regular tar members are allowed")
        if name not in members_by_name or name in extracted or "/" in name or "\\" in name:
            raise SourceError("tar member is extra, duplicated, or path-bearing")
        size = _strict_octal(header[124:136], "member size")
        expected = members_by_name[name]
        if size != expected["bytes"]:
            raise SourceError("tar member size differs from pin")
        data_start = offset + 512
        data_end = data_start + size
        padded_end = data_start + ((size + 511) // 512) * 512
        if padded_end > len(tar) or any(tar[data_end:padded_end]):
            raise SourceError("tar member data or padding is invalid")
        payload = tar[data_start:data_end]
        if sha256_bytes(payload) != expected["sha256"]:
            raise SourceError("tar member checksum differs from pin")
        validate_crlf(payload, expected["crlf_lines"], name)
        extracted[name] = payload
        offset = padded_end
    trailer = tar[offset:]
    if len(trailer) < 1024 or any(trailer):
        raise SourceError("tar must end with at least two zero blocks and no trailing data")
    if set(extracted) != EXPECTED_MEMBER_NAMES:
        raise SourceError("tar is missing a pinned member")
    return extracted


def validate_crlf(payload: bytes, expected_lines: int, context: str) -> list[bytes]:
    if not payload.endswith(b"\r\n"):
        raise SourceError(f"{context} must end in CRLF")
    stripped = payload.replace(b"\r\n", b"")
    if b"\r" in stripped or b"\n" in stripped:
        raise SourceError(f"{context} contains a non-CRLF newline")
    lines = [line + b"\r\n" for line in payload[:-2].split(b"\r\n")]
    if len(lines) != expected_lines:
        raise SourceError(f"{context} CRLF line count differs from pin")
    return lines


def label_records(payload: bytes) -> list[dict[str, Any]]:
    line_starts = [0]
    for match in re.finditer(br"\r\n", payload):
        line_starts.append(match.end())
    records: list[dict[str, Any]] = []
    per_name: dict[str, int] = {}
    line_index = 0
    for ordinal, match in enumerate(LABEL_PATTERN.finditer(payload), 1):
        while line_index + 1 < len(line_starts) and line_starts[line_index + 1] <= match.start():
            line_index += 1
        try:
            name = match.group(1).decode("utf-8")
        except UnicodeDecodeError as error:
            raise SourceError("label name is not UTF-8") from error
        per_name[name] = per_name.get(name, 0) + 1
        records.append({
            "ordinal": ordinal,
            "name_ordinal": per_name[name],
            "name": name,
            "line": line_index + 1,
            "byte_column": match.start() - line_starts[line_index] + 1,
            "byte_start": match.start(),
            "byte_end": match.end(),
        })
    return records


def validate_and_split(payload: bytes, manifest: Mapping[str, Any]) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    slices = validate_manifest(manifest)
    if len(payload) != manifest["source_bytes"] or sha256_bytes(payload) != manifest["source_sha256"]:
        raise SourceError("primary TeX bytes or checksum differ from manifest")
    lines = validate_crlf(payload, manifest["source_crlf_lines"], "primary TeX")
    outputs: dict[str, bytes] = {}
    for output_path, (identifier, first, last, byte_count, digest, label_count) in slices:
        fragment = b"".join(lines[first - 1 : last])
        if len(fragment) != byte_count or sha256_bytes(fragment) != digest:
            raise SourceError(f"slice bytes or checksum differ for {identifier}")
        if len(LABEL_PATTERN.findall(fragment)) != label_count:
            raise SourceError(f"slice label count differs for {identifier}")
        outputs[output_path] = fragment
    records = label_records(payload)
    labels = manifest["labels"]
    names: dict[str, list[int]] = {}
    for record in records:
        names.setdefault(record["name"], []).append(record["line"])
    duplicates = {name: line_numbers for name, line_numbers in names.items() if len(line_numbers) > 1}
    if len(records) != labels["occurrences"] or len(names) != labels["unique_names"] or duplicates != labels["duplicate_names"]:
        raise SourceError("label index differs from audited contract")
    for record in records:
        record["output_paths"] = [
            output_path for output_path, (_, first, last, _, _, _) in slices
            if first <= record["line"] <= last
        ]
    labels_payload = _json_bytes(records)
    if len(labels_payload) != labels["generated_bytes"] or sha256_bytes(labels_payload) != labels["generated_sha256"]:
        raise SourceError("generated label index differs from its manifest pin")
    top = [outputs[output_path] for output_path, _ in slices if output_path.startswith("top-level/")]
    if b"".join(top) != payload:
        raise SourceError("top-level reconstruction differs from primary TeX")
    return outputs, records


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _assert_real_directory(path: Path, *, create: bool = False) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if not current.exists() and not current.is_symlink():
            if create:
                try:
                    current.mkdir()
                except FileExistsError:
                    pass
            else:
                raise SourceError(f"directory does not exist: {path}")
        metadata = current.stat(follow_symlinks=False)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise SourceError(f"path contains a symlink or non-directory: {current}")


def _read_regular_bounded(path: Path, max_bytes: int, *, exact_bytes: int | None = None) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise SourceError(f"cannot safely open regular file: {path}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SourceError(f"path is not a regular file: {path}")
        expected = exact_bytes
        if metadata.st_size > max_bytes or (expected is not None and metadata.st_size != expected):
            raise SourceError(f"regular file size differs from its bound: {path}")
        chunks: list[bytes] = []
        byte_count = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes - byte_count + 1))
            if not chunk:
                break
            chunks.append(chunk)
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise SourceError(f"regular file exceeds its byte bound: {path}")
        final_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(final_metadata.st_mode)
            or (final_metadata.st_dev, final_metadata.st_ino, final_metadata.st_size)
            != (metadata.st_dev, metadata.st_ino, metadata.st_size)
        ):
            raise SourceError(f"regular file identity changed while it was read: {path}")
        if expected is not None and byte_count != expected:
            raise SourceError(f"regular file changed while it was read: {path}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_regular_bounded_at(
    directory_fd: int,
    name: str,
    max_bytes: int,
    *,
    exact_bytes: int | None = None,
) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    try:
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
            raise SourceError(f"unsafe or oversized transaction file: {name}")
        if observed.st_size > max_bytes or (
            exact_bytes is not None and observed.st_size != exact_bytes
        ):
            raise SourceError(f"regular file size differs from its bound: {name}")
        descriptor = os.open(name, flags, dir_fd=directory_fd)
    except OSError as error:
        raise SourceError(f"cannot safely open transaction file: {name}") from error
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_size > max_bytes
            or _entry_identity(metadata) != _entry_identity(observed)
        ):
            raise SourceError(f"unsafe or oversized transaction file: {name}")
        if exact_bytes is not None and metadata.st_size != exact_bytes:
            raise SourceError(f"regular file size differs from its bound: {name}")
        chunks: list[bytes] = []
        byte_count = 0
        while True:
            chunk = os.read(descriptor, min(4096, max_bytes - byte_count + 1))
            if not chunk:
                break
            chunks.append(chunk)
            byte_count += len(chunk)
            if byte_count > max_bytes:
                raise SourceError(f"transaction file exceeds its byte bound: {name}")
        final_metadata = os.fstat(descriptor)
        final_observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(final_metadata.st_mode)
            or (final_metadata.st_dev, final_metadata.st_ino, final_metadata.st_size)
            != (metadata.st_dev, metadata.st_ino, metadata.st_size)
            or _entry_identity(final_observed) != _entry_identity(metadata)
            or byte_count != metadata.st_size
            or exact_bytes is not None
            and byte_count != exact_bytes
        ):
            raise SourceError(f"transaction file changed while it was read: {name}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _expected_materialized(
    members: Mapping[str, bytes],
    outputs: Mapping[str, bytes],
    records: list[dict[str, Any]],
) -> dict[str, bytes]:
    expected = {f"source/{name}": payload for name, payload in members.items()}
    expected.update({f"sections/{path}": payload for path, payload in outputs.items()})
    expected["sections/labels.json"] = _json_bytes(records)
    return expected


def _inventory_bytes(
    source_pin: bytes,
    split_manifest: bytes,
    expected: Mapping[str, bytes],
) -> bytes:
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "source_pin_sha256": sha256_bytes(source_pin),
        "split_manifest_sha256": sha256_bytes(split_manifest),
        "files": [
            {"path": path, "bytes": len(payload), "sha256": sha256_bytes(payload)}
            for path, payload in sorted(expected.items())
        ],
    }
    return _json_bytes(inventory)


def _regular_files_at(root_fd: int, prefix: str = "") -> set[str]:
    result: set[str] = set()
    for name in sorted(os.listdir(root_fd)):
        metadata = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        relative = f"{prefix}/{name}" if prefix else name
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            child_fd = _open_bound_directory(
                root_fd,
                name,
                metadata,
                "materialized directory",
            )
            try:
                result.update(_regular_files_at(child_fd, relative))
            finally:
                os.close(child_fd)
        elif stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise SourceError(f"materialized tree contains an unsafe entry: {relative}")
        else:
            result.add(relative)
    return result


def _read_regular_relative_at(directory_fd: int, relative: str, max_bytes: int) -> bytes:
    parts = relative.split("/")
    if not parts or any(part in ("", ".", "..") or "\\" in part for part in parts):
        raise SourceError(f"unsafe materialized file path: {relative}")
    parent_fd = os.dup(directory_fd)
    try:
        for component in parts[:-1]:
            metadata = _directory_entry(parent_fd, component, "materialized directory")
            if metadata is None:
                raise SourceError(f"materialized directory is missing: {component}")
            child_fd = _open_bound_directory(
                parent_fd,
                component,
                metadata,
                "materialized directory",
            )
            os.close(parent_fd)
            parent_fd = child_fd
        return _read_regular_bounded_at(
            parent_fd,
            parts[-1],
            max_bytes,
            exact_bytes=max_bytes,
        )
    finally:
        os.close(parent_fd)


def _verify_materialized_at(
    reference_fd: int,
    pin: Mapping[str, Any],
    manifest: Mapping[str, Any],
    source_pin: bytes,
    split_manifest: bytes,
) -> dict[str, Any]:
    if (
        _read_regular_bounded_at(
            reference_fd,
            "source-pin.json",
            CONTRACT_MAX_BYTES,
        )
        != source_pin
        or _read_regular_bounded_at(
            reference_fd,
            "split-manifest.json",
            CONTRACT_MAX_BYTES,
        )
        != split_manifest
    ):
        raise SourceError("materialized contracts changed after reference binding")
    source_metadata = _directory_entry(reference_fd, "source", "materialized source")
    sections_metadata = _directory_entry(reference_fd, "sections", "materialized sections")
    if source_metadata is None or sections_metadata is None:
        raise SourceError("materialized source or sections directory is missing")
    source_fd = _open_bound_directory(
        reference_fd,
        "source",
        source_metadata,
        "materialized source",
    )
    try:
        sections_fd = _open_bound_directory(
            reference_fd,
            "sections",
            sections_metadata,
            "materialized sections",
        )
    except BaseException:
        os.close(source_fd)
        raise
    members: dict[str, bytes] = {}
    try:
        for member in pin["members"]:
            payload = _read_regular_bounded_at(
                source_fd,
                member["name"],
                member["bytes"],
                exact_bytes=member["bytes"],
            )
            if len(payload) != member["bytes"] or sha256_bytes(payload) != member["sha256"]:
                raise SourceError(
                    f"materialized source member differs from pin: {member['name']}"
                )
            validate_crlf(payload, member["crlf_lines"], member["name"])
            members[member["name"]] = payload
        outputs, records = validate_and_split(
            members[manifest["source_member"]],
            manifest,
        )
        expected = _expected_materialized(members, outputs, records)
        inventory = _inventory_bytes(source_pin, split_manifest, expected)
        ready = (sha256_bytes(inventory) + "\n").encode("ascii")
        expected_with_metadata = dict(expected)
        expected_with_metadata["sections/inventory.json"] = inventory
        expected_with_metadata["sections/READY"] = ready
        actual_paths = {
            f"source/{path}" for path in _regular_files_at(source_fd)
        } | {
            f"sections/{path}" for path in _regular_files_at(sections_fd)
        }
        if actual_paths != set(expected_with_metadata):
            raise SourceError("materialized file inventory contains missing or extra paths")
        for relative, payload in expected_with_metadata.items():
            root_name, child_relative = relative.split("/", 1)
            root_fd = source_fd if root_name == "source" else sections_fd
            observed = _read_regular_relative_at(root_fd, child_relative, len(payload))
            if len(observed) != len(payload) or observed != payload:
                raise SourceError(
                    f"materialized file differs from deterministic inventory: {relative}"
                )
        if (
            _read_regular_bounded_at(
                reference_fd,
                "source-pin.json",
                CONTRACT_MAX_BYTES,
            )
            != source_pin
            or _read_regular_bounded_at(
                reference_fd,
                "split-manifest.json",
                CONTRACT_MAX_BYTES,
            )
            != split_manifest
        ):
            raise SourceError("materialized contracts changed during verification")
        _require_bound_entry(
            reference_fd,
            "source",
            source_metadata,
            "verified materialized source",
        )
        _require_bound_entry(
            reference_fd,
            "sections",
            sections_metadata,
            "verified materialized sections",
        )
        return {
            "status": "verified",
            "files": len(expected_with_metadata),
            "labels": len(records),
            "ready_sha256": sha256_bytes(ready),
            "inventory_sha256": sha256_bytes(inventory),
        }
    finally:
        os.close(sections_fd)
        os.close(source_fd)


def verify_materialized(reference_root: Path) -> dict[str, Any]:
    with _bound_directory(reference_root) as reference_fd:
        pin, manifest, source_pin, split_manifest = _validate_contracts_at(reference_fd)
        return _verify_materialized_at(
            reference_fd,
            pin,
            manifest,
            source_pin,
            split_manifest,
        )


def _locked_at(runtime_fd: int, lock_name: str):
    class LockContext:
        descriptor: int
        metadata: os.stat_result

        def __enter__(self) -> "LockContext":
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            self.descriptor = os.open(lock_name, flags, 0o600, dir_fd=runtime_fd)
            self.metadata = os.fstat(self.descriptor)
            if not stat.S_ISREG(self.metadata.st_mode):
                os.close(self.descriptor)
                raise SourceError("materialization lock is not a regular file")
            fcntl.flock(self.descriptor, fcntl.LOCK_EX)
            observed = os.stat(lock_name, dir_fd=runtime_fd, follow_symlinks=False)
            if (
                stat.S_ISLNK(observed.st_mode)
                or not stat.S_ISREG(observed.st_mode)
                or _entry_identity(observed) != _entry_identity(self.metadata)
            ):
                fcntl.flock(self.descriptor, fcntl.LOCK_UN)
                os.close(self.descriptor)
                raise SourceError("materialization lock changed while it was acquired")
            return self

        def __exit__(self, *_arguments: object) -> None:
            fcntl.flock(self.descriptor, fcntl.LOCK_UN)
            os.close(self.descriptor)

    return LockContext()


def acquire_archive(pin: Mapping[str, Any], destination: Path, timeout_seconds: float) -> dict[str, Any]:
    archive_pin = pin["archive"]
    transport_pin = reference_transport.DirectDownloadPin(
        pin["source_id"],
        pin["url"],
        archive_pin["sha256"],
        archive_pin["bytes"],
        tuple(pin["allowed_hosts"]),
    )
    return reference_transport.acquire(
        transport_pin,
        destination,
        timeout_seconds=timeout_seconds,
    )


def read_pinned_archive(path: Path, pin: Mapping[str, Any]) -> bytes:
    _assert_real_directory(path.parent)
    expected_size = pin["archive"]["bytes"]
    archive = _read_regular_bounded(path, expected_size, exact_bytes=expected_size)
    if sha256_bytes(archive) != pin["archive"]["sha256"]:
        raise SourceError("archive checksum differs from pin")
    return archive


def _read_pinned_archive_at(
    runtime_fd: int,
    archive_name: str,
    pin: Mapping[str, Any],
) -> bytes:
    expected_size = pin["archive"]["bytes"]
    archive = _read_regular_bounded_at(runtime_fd, archive_name, expected_size)
    if len(archive) != expected_size or sha256_bytes(archive) != pin["archive"]["sha256"]:
        raise SourceError("runtime archive cache differs from pin")
    return archive


def _require_bound_cache_file_at(
    runtime_fd: int,
    name: str,
    descriptor: int,
    expected_identity: tuple[int, int],
    *,
    expected_size: int | None = None,
) -> os.stat_result:
    descriptor_metadata = os.fstat(descriptor)
    named_metadata = os.stat(name, dir_fd=runtime_fd, follow_symlinks=False)
    if (
        not stat.S_ISREG(descriptor_metadata.st_mode)
        or not stat.S_ISREG(named_metadata.st_mode)
        or descriptor_metadata.st_nlink != 1
        or named_metadata.st_nlink != 1
        or _entry_identity(descriptor_metadata) != expected_identity
        or _entry_identity(named_metadata) != expected_identity
        or expected_size is not None
        and (
            descriptor_metadata.st_size != expected_size
            or named_metadata.st_size != expected_size
        )
    ):
        raise SourceError(
            "runtime archive cache identity or single-link invariant changed"
        )
    return descriptor_metadata


def _publish_archive_cache_at(
    runtime_fd: int,
    archive_name: str,
    archive: bytes,
    pin: Mapping[str, Any],
) -> None:
    archive_pin = pin["archive"]
    if len(archive) != archive_pin["bytes"] or sha256_bytes(archive) != archive_pin["sha256"]:
        raise SourceError("transport archive differs from pin")
    partial_name = f".{archive_name}.{os.getpid()}.{time.monotonic_ns()}.partial"
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor: int | None = None
    partial_metadata: os.stat_result | None = None
    replaced = False
    published = False
    try:
        descriptor = os.open(partial_name, flags, 0o600, dir_fd=runtime_fd)
        partial_metadata = os.fstat(descriptor)
        _require_bound_cache_file_at(
            runtime_fd,
            partial_name,
            descriptor,
            _entry_identity(partial_metadata),
        )
        offset = 0
        while offset < len(archive):
            written = os.write(descriptor, archive[offset:])
            if written <= 0:
                raise SourceError("runtime archive cache write made no progress")
            offset += written
        _require_bound_cache_file_at(
            runtime_fd,
            partial_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        os.fsync(descriptor)
        _require_bound_cache_file_at(
            runtime_fd,
            partial_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        remaining = archive_pin["bytes"]
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                raise SourceError("runtime archive cache staging file was truncated")
            digest.update(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1) or digest.hexdigest() != archive_pin["sha256"]:
            raise SourceError("runtime archive cache staging checksum differs from pin")
        _require_bound_cache_file_at(
            runtime_fd,
            partial_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        if _entry_exists(runtime_fd, archive_name):
            _read_pinned_archive_at(runtime_fd, archive_name, pin)
            return
        _require_bound_cache_file_at(
            runtime_fd,
            partial_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        os.replace(
            partial_name,
            archive_name,
            src_dir_fd=runtime_fd,
            dst_dir_fd=runtime_fd,
        )
        replaced = True
        _require_bound_cache_file_at(
            runtime_fd,
            archive_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        os.fsync(runtime_fd)
        _require_bound_cache_file_at(
            runtime_fd,
            archive_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        _read_pinned_archive_at(runtime_fd, archive_name, pin)
        _require_bound_cache_file_at(
            runtime_fd,
            archive_name,
            descriptor,
            _entry_identity(partial_metadata),
            expected_size=archive_pin["bytes"],
        )
        published = True
    except OSError as error:
        raise SourceError("cannot publish runtime archive cache") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if not published and partial_metadata is not None:
            cleanup_name = archive_name if replaced else partial_name
            try:
                observed = os.stat(cleanup_name, dir_fd=runtime_fd, follow_symlinks=False)
                if _entry_identity(observed) == _entry_identity(partial_metadata):
                    os.unlink(cleanup_name, dir_fd=runtime_fd)
                    os.fsync(runtime_fd)
            except FileNotFoundError:
                pass


def acquire_archive_at(
    runtime_fd: int,
    pin: Mapping[str, Any],
    timeout_seconds: float,
) -> tuple[bytes, dict[str, Any]]:
    if _entry_exists(runtime_fd, ARCHIVE_CACHE_NAME):
        return _read_pinned_archive_at(runtime_fd, ARCHIVE_CACHE_NAME, pin), {
            "status": "cached",
            "cache": "bound-runtime",
        }
    with tempfile.TemporaryDirectory(
        prefix="reference-source-transport-",
        dir="/tmp",
    ) as temporary:
        transport_destination = Path(temporary) / ARCHIVE_CACHE_NAME
        acquisition = acquire_archive(pin, transport_destination, timeout_seconds)
        archive = read_pinned_archive(transport_destination, pin)
        _publish_archive_cache_at(runtime_fd, ARCHIVE_CACHE_NAME, archive, pin)
    acquisition = dict(acquisition)
    acquisition["cache"] = "published-to-bound-runtime"
    return archive, acquisition


def _cleanup_tombstone(transaction: Path) -> Path:
    return transaction.with_name(f"{transaction.name}.cleanup")


def _open_directory_at(name: str | Path, *, dir_fd: int | None = None) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, dir_fd=dir_fd)
    try:
        metadata = os.fstat(descriptor)
    except BaseException:
        os.close(descriptor)
        raise
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise SourceError(f"transaction path is not a real directory: {name}")
    return descriptor


@contextmanager
def _bound_directory(path: Path) -> Iterable[int]:
    descriptor = _open_directory_at(path)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def _entry_at(directory_fd: int, name: str, context: str) -> os.stat_result | None:
    try:
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SourceError(f"cannot inspect {context}: {name}") from error
    return metadata


def _directory_entry(directory_fd: int, name: str, context: str) -> os.stat_result | None:
    metadata = _entry_at(directory_fd, name, context)
    if metadata is None:
        return None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise SourceError(f"unsafe {context}: {name}")
    return metadata


def _entry_identity(metadata: os.stat_result) -> tuple[int, int]:
    return metadata.st_dev, metadata.st_ino


def _open_bound_directory(
    directory_fd: int,
    name: str,
    metadata: os.stat_result,
    context: str,
) -> int:
    try:
        descriptor = _open_directory_at(name, dir_fd=directory_fd)
    except (OSError, SourceError) as error:
        raise SourceError(f"cannot bind {context}: {name}") from error
    if _entry_identity(os.fstat(descriptor)) != _entry_identity(metadata):
        os.close(descriptor)
        raise SourceError(f"raced {context}: {name}")
    return descriptor


def _create_bound_directory_at(
    directory_fd: int,
    name: str,
    context: str,
    *,
    mode: int = 0o700,
) -> tuple[int, os.stat_result]:
    if "/" in name or name in ("", ".", ".."):
        raise SourceError(f"unsafe {context} name: {name}")
    try:
        os.mkdir(name, mode=mode, dir_fd=directory_fd)
    except OSError as error:
        raise SourceError(f"cannot create {context}: {name}") from error
    metadata = _directory_entry(directory_fd, name, context)
    if metadata is None:
        raise SourceError(f"created {context} disappeared: {name}")
    return _open_bound_directory(directory_fd, name, metadata, context), metadata


def _write_new_file_at(directory_fd: int, relative: str, payload: bytes) -> None:
    parts = relative.split("/")
    if not parts or any(part in ("", ".", "..") or "\\" in part for part in parts):
        raise SourceError(f"unsafe staged file path: {relative}")
    parent_fd = os.dup(directory_fd)
    try:
        for component in parts[:-1]:
            metadata = _directory_entry(parent_fd, component, "staging directory")
            if metadata is None:
                child_fd, _ = _create_bound_directory_at(
                    parent_fd,
                    component,
                    "staging directory",
                )
            else:
                child_fd = _open_bound_directory(
                    parent_fd,
                    component,
                    metadata,
                    "staging directory",
                )
            os.close(parent_fd)
            parent_fd = child_fd
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(parts[-1], flags, 0o600, dir_fd=parent_fd)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise SourceError(f"staged output is not a regular file: {relative}")
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _fsync_tree_at(directory_fd: int) -> None:
    for name in sorted(os.listdir(directory_fd)):
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            child_fd = _open_bound_directory(
                directory_fd,
                name,
                metadata,
                "staging directory",
            )
            try:
                _fsync_tree_at(child_fd)
            finally:
                os.close(child_fd)
        elif stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise SourceError(f"unsafe staged tree entry: {name}")
    os.fsync(directory_fd)


def _require_bound_entry(
    directory_fd: int,
    name: str,
    metadata: os.stat_result,
    context: str,
) -> None:
    observed = _directory_entry(directory_fd, name, context)
    if observed is None or _entry_identity(observed) != _entry_identity(metadata):
        raise SourceError(f"raced {context}: {name}")


def _remove_tree_contents_at(directory_fd: int) -> None:
    for name in sorted(os.listdir(directory_fd)):
        metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            child_fd = _open_bound_directory(directory_fd, name, metadata, "cleanup directory")
            try:
                _remove_tree_contents_at(child_fd)
                _require_bound_entry(directory_fd, name, metadata, "cleanup directory")
                os.rmdir(name, dir_fd=directory_fd)
            finally:
                os.close(child_fd)
        else:
            observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if _entry_identity(observed) != _entry_identity(metadata):
                raise SourceError(f"raced cleanup entry: {name}")
            os.unlink(name, dir_fd=directory_fd)


def _finish_cleanup_tombstone_at(
    runtime_fd: int,
    cleanup_name: str,
    expected_metadata: os.stat_result | None = None,
) -> bool:
    metadata = _directory_entry(runtime_fd, cleanup_name, "cleanup tombstone")
    if metadata is None:
        return False
    if expected_metadata is not None and _entry_identity(metadata) != _entry_identity(
        expected_metadata
    ):
        raise SourceError(f"raced cleanup tombstone: {cleanup_name}")
    cleanup_fd = _open_bound_directory(
        runtime_fd,
        cleanup_name,
        metadata,
        "cleanup tombstone",
    )
    try:
        try:
            _remove_tree_contents_at(cleanup_fd)
            _require_bound_entry(runtime_fd, cleanup_name, metadata, "cleanup tombstone")
            os.rmdir(cleanup_name, dir_fd=runtime_fd)
        except (OSError, SourceError) as error:
            retained = _entry_exists(runtime_fd, cleanup_name)
            disposition = "was preserved" if retained else "removal state is uncertain"
            raise SourceError(
                f"materialization cleanup tombstone {disposition}: {cleanup_name}: {error}"
            ) from error
    finally:
        os.close(cleanup_fd)
    try:
        os.fsync(runtime_fd)
    except OSError as error:
        raise SourceError("cleanup tombstone removal durability is uncertain") from error
    return True


def _commit_transaction_cleanup_at(
    runtime_fd: int,
    transaction_name: str,
    transaction_fd: int,
) -> None:
    cleanup_name = f"{transaction_name}.cleanup"
    if _entry_exists(runtime_fd, cleanup_name):
        raise SourceError(f"materialization cleanup tombstone already exists: {cleanup_name}")
    transaction_metadata = os.fstat(transaction_fd)
    os.replace(
        transaction_name,
        cleanup_name,
        src_dir_fd=runtime_fd,
        dst_dir_fd=runtime_fd,
    )
    _require_bound_entry(runtime_fd, cleanup_name, transaction_metadata, "cleanup tombstone")
    try:
        os.fsync(runtime_fd)
    except OSError as error:
        raise SourceError(
            f"materialization cleanup tombstone was preserved: {cleanup_name}: {error}"
        ) from error
    _finish_cleanup_tombstone_at(runtime_fd, cleanup_name, transaction_metadata)


def _restore_current_after_race(
    reference_fd: int,
    transaction_fd: int,
    name: str,
    current_metadata: os.stat_result | None,
) -> None:
    if current_metadata is None:
        return
    try:
        observed = _directory_entry(reference_fd, name, "rollback current destination")
    except SourceError:
        observed = None
    if observed is not None and _entry_identity(observed) == _entry_identity(current_metadata):
        return
    incomplete_name = f"incomplete-{name}"
    incomplete = _directory_entry(
        transaction_fd,
        incomplete_name,
        "rollback current-tree quarantine",
    )
    if incomplete is None or _entry_identity(incomplete) != _entry_identity(current_metadata):
        return
    if _entry_exists(reference_fd, name):
        raced_name = f"raced-{name}"
        if _entry_exists(transaction_fd, raced_name):
            raise SourceError(f"rollback raced quarantine already exists: {raced_name}")
        os.replace(
            name,
            raced_name,
            src_dir_fd=reference_fd,
            dst_dir_fd=transaction_fd,
        )
    os.replace(
        incomplete_name,
        name,
        src_dir_fd=transaction_fd,
        dst_dir_fd=reference_fd,
    )
    _require_bound_entry(
        reference_fd,
        name,
        current_metadata,
        "restored current destination",
    )


def _entry_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise SourceError(f"cannot inspect transaction entry: {name}") from error
    return True


def _rollback_transaction(
    transaction: Path,
    original_presence: Mapping[str, bool],
    *,
    _runtime_fd: int | None = None,
    _reference_fd: int | None = None,
    _transaction_fd: int | None = None,
) -> tuple[list[str], bool]:
    names = ("sections", "source")
    errors: list[str] = []
    descriptors: list[int] = []
    try:
        if _runtime_fd is None:
            return ["backup boundary: bound runtime descriptor is required"], True
        if _reference_fd is None:
            return ["backup boundary: bound reference descriptor is required"], True
        runtime_fd = os.dup(_runtime_fd)
        descriptors.append(runtime_fd)
        reference_fd = os.dup(_reference_fd)
        descriptors.append(reference_fd)
        if _transaction_fd is None:
            transaction_fd = _open_directory_at(transaction.name, dir_fd=runtime_fd)
        else:
            transaction_fd = os.dup(_transaction_fd)
            _require_bound_entry(
                runtime_fd,
                transaction.name,
                os.fstat(transaction_fd),
                "materialization transaction",
            )
        descriptors.append(transaction_fd)
        backup_fd = _open_directory_at("backup", dir_fd=transaction_fd)
        descriptors.append(backup_fd)
        saved_metadata: dict[str, os.stat_result | None] = {}
        saved_parent: dict[str, int] = {}
        destination_metadata = {
            name: _directory_entry(reference_fd, name, "transaction destination")
            for name in names
        }
        for name in names:
            restore_name = f"restore-{name}"
            backup_metadata = _directory_entry(backup_fd, name, "rollback backup tree")
            restore_metadata = _directory_entry(
                transaction_fd,
                restore_name,
                "rollback restore candidate",
            )
            if backup_metadata is not None and restore_metadata is not None:
                raise SourceError(f"duplicate rollback authority for {name}")
            metadata = backup_metadata or restore_metadata
            parent_fd = backup_fd if backup_metadata is not None else transaction_fd
            if metadata is not None:
                descriptor = _open_bound_directory(
                    parent_fd,
                    name if backup_metadata is not None else restore_name,
                    metadata,
                    "rollback saved tree",
                )
                descriptors.append(descriptor)
                saved_parent[name] = parent_fd
            saved_metadata[name] = metadata
            if original_presence[name]:
                if metadata is None and destination_metadata[name] is None:
                    raise SourceError(f"rollback has no saved or current tree for {name}")
            elif metadata is not None:
                raise SourceError(f"rollback has an unexpected saved tree for {name}")
    except (OSError, SourceError) as error:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        return [f"backup boundary: {error}"], True
    try:
        # Capture and authenticate every saved tree before touching either live destination.
        for name in names:
            metadata = saved_metadata[name]
            if metadata is None or saved_parent[name] == transaction_fd:
                continue
            restore_name = f"restore-{name}"
            try:
                os.replace(
                    name,
                    restore_name,
                    src_dir_fd=backup_fd,
                    dst_dir_fd=transaction_fd,
                )
                _require_bound_entry(
                    transaction_fd,
                    restore_name,
                    metadata,
                    "rollback restore candidate",
                )
            except (OSError, SourceError) as error:
                errors.append(f"{name}: {error}")
        if errors:
            return errors, True

        for name in names:
            incomplete_name = f"incomplete-{name}"
            raced_name = f"raced-{name}"
            restore_name = f"restore-{name}"
            current_metadata = destination_metadata[name]
            saved = saved_metadata[name]
            try:
                if original_presence[name]:
                    if saved is not None:
                        if current_metadata is not None:
                            if _entry_exists(transaction_fd, incomplete_name):
                                raise SourceError(f"rollback quarantine already exists: {transaction / incomplete_name}")
                            os.replace(name, incomplete_name, src_dir_fd=reference_fd, dst_dir_fd=transaction_fd)
                            _require_bound_entry(
                                transaction_fd,
                                incomplete_name,
                                current_metadata,
                                "rollback current-tree quarantine",
                            )
                        os.replace(
                            restore_name,
                            name,
                            src_dir_fd=transaction_fd,
                            dst_dir_fd=reference_fd,
                        )
                        try:
                            _require_bound_entry(
                                reference_fd,
                                name,
                                saved,
                                "restored destination",
                            )
                        except SourceError:
                            if _entry_exists(transaction_fd, raced_name):
                                raise SourceError(f"rollback raced quarantine already exists: {transaction / raced_name}")
                            if _entry_exists(reference_fd, name):
                                os.replace(
                                    name,
                                    raced_name,
                                    src_dir_fd=reference_fd,
                                    dst_dir_fd=transaction_fd,
                                )
                            if current_metadata is not None:
                                _require_bound_entry(
                                    transaction_fd,
                                    incomplete_name,
                                    current_metadata,
                                    "rollback current-tree quarantine",
                                )
                                os.replace(
                                    incomplete_name,
                                    name,
                                    src_dir_fd=transaction_fd,
                                    dst_dir_fd=reference_fd,
                                )
                                _require_bound_entry(
                                    reference_fd,
                                    name,
                                    current_metadata,
                                    "restored current destination",
                                )
                            raise
                    elif current_metadata is not None:
                        _require_bound_entry(
                            reference_fd,
                            name,
                            current_metadata,
                            "unchanged current destination",
                        )
                elif current_metadata is not None:
                    if _entry_exists(transaction_fd, incomplete_name):
                        raise SourceError(f"rollback quarantine already exists: {transaction / incomplete_name}")
                    os.replace(name, incomplete_name, src_dir_fd=reference_fd, dst_dir_fd=transaction_fd)
                    _require_bound_entry(
                        transaction_fd,
                        incomplete_name,
                        current_metadata,
                        "rollback new-tree quarantine",
                    )
            except (OSError, SourceError) as error:
                try:
                    _restore_current_after_race(
                        reference_fd,
                        transaction_fd,
                        name,
                        current_metadata,
                    )
                except (OSError, SourceError) as restore_error:
                    errors.append(f"{name}: {error}; current restoration: {restore_error}")
                else:
                    errors.append(f"{name}: {error}")
        if errors:
            return errors, True
        for name in names:
            expected = saved_metadata[name] if original_presence[name] and saved_metadata[name] is not None else destination_metadata[name]
            if original_presence[name]:
                if expected is None:
                    raise SourceError(f"rollback final state has no authoritative tree for {name}")
                _require_bound_entry(reference_fd, name, expected, "rollback final destination")
            elif _entry_exists(reference_fd, name):
                raise SourceError(f"rollback final destination unexpectedly exists: {name}")
        os.fsync(reference_fd)
        _commit_transaction_cleanup_at(runtime_fd, transaction.name, transaction_fd)
        return [], False
    except (OSError, SourceError) as error:
        retained = _entry_exists(runtime_fd, transaction.name) or _entry_exists(
            runtime_fd, f"{transaction.name}.cleanup"
        )
        return [f"rollback boundary: {error}"], retained
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _transaction_document(
    reference_authority: str,
    reference_identity: tuple[int, int],
    original_presence: Mapping[str, bool],
) -> bytes:
    return _json_bytes({
        "schema_version": SCHEMA_VERSION,
        "reference_root": reference_authority,
        "reference_identity": {
            "device": reference_identity[0],
            "inode": reference_identity[1],
        },
        "original_presence": {
            "source": bool(original_presence["source"]),
            "sections": bool(original_presence["sections"]),
        },
    })


def _recover_transaction(
    transaction: Path,
    reference_authority: str,
    runtime_fd: int,
    reference_fd: int,
    pin: Mapping[str, Any],
    manifest: Mapping[str, Any],
    source_pin: bytes,
    split_manifest: bytes,
) -> None:
    metadata = _directory_entry(runtime_fd, transaction.name, "materialization transaction")
    if metadata is None:
        return
    transaction_fd = _open_bound_directory(
        runtime_fd,
        transaction.name,
        metadata,
        "materialization transaction",
    )
    try:
        marker_bytes = _read_regular_bounded_at(transaction_fd, "transaction.json", 4096)
        try:
            marker = json.loads(
                marker_bytes.decode("utf-8"),
                object_pairs_hook=_object_without_duplicates,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceError(f"materialization transaction marker is invalid: {transaction}") from error
        if not isinstance(marker, dict):
            raise SourceError(f"materialization transaction marker is invalid: {transaction}")
        _exact_keys(
            marker,
            {
                "schema_version",
                "reference_root",
                "reference_identity",
                "original_presence",
            },
            "transaction marker",
        )
        reference_identity = marker["reference_identity"]
        presence = marker["original_presence"]
        if (
            marker["schema_version"] != SCHEMA_VERSION
            or marker["reference_root"] != reference_authority
            or not isinstance(reference_identity, dict)
            or set(reference_identity) != {"device", "inode"}
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 0
                for value in reference_identity.values()
            )
            or not isinstance(presence, dict)
            or set(presence) != {"source", "sections"}
            or any(not isinstance(value, bool) for value in presence.values())
        ):
            raise SourceError(f"materialization transaction authority is invalid: {transaction}")
        expected_reference_identity = (
            reference_identity["device"],
            reference_identity["inode"],
        )
        if _entry_identity(os.fstat(reference_fd)) != expected_reference_identity:
            raise SourceError(
                "materialization transaction reference directory identity differs; "
                f"preserved {transaction}"
            )
        try:
            _verify_materialized_at(
                reference_fd,
                pin,
                manifest,
                source_pin,
                split_manifest,
            )
        except SourceError:
            rollback_errors, transaction_retained = _rollback_transaction(
                transaction,
                presence,
                _runtime_fd=runtime_fd,
                _reference_fd=reference_fd,
                _transaction_fd=transaction_fd,
            )
            if rollback_errors:
                disposition = (
                    f"preserved {transaction}"
                    if transaction_retained
                    else "transaction removal durability is uncertain"
                )
                raise SourceError(
                    f"stale transaction recovery failed; {disposition}: "
                    + "; ".join(rollback_errors)
                )
        else:
            _commit_transaction_cleanup_at(runtime_fd, transaction.name, transaction_fd)
    finally:
        os.close(transaction_fd)


def materialize(
    reference_root: Path,
    runtime_root: Path,
    *,
    archive_path: Path | None = None,
    timeout_seconds: float = 30.0,
    replace_existing: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    _assert_real_directory(reference_root)
    reference_authority = str(reference_root.resolve())
    expected_runtime_root = reference_root.parents[1] / ".workflow-runtime" / "reference-source"
    if Path(os.path.abspath(runtime_root)) != Path(os.path.abspath(expected_runtime_root)):
        raise SourceError("runtime root must be the repository's ignored reference-source directory")
    lock_name = hashlib.sha256(reference_authority.encode("utf-8")).hexdigest() + ".lock"
    _assert_real_directory(runtime_root, create=True)
    with (
        _bound_directory(runtime_root) as runtime_fd,
        _locked_at(runtime_fd, lock_name),
        _bound_directory(reference_root) as reference_fd,
    ):
        if os.fstat(reference_fd).st_dev != os.fstat(runtime_fd).st_dev:
            raise SourceError("runtime and reference roots must share one filesystem")
        pin, manifest, source_pin, split_manifest = _validate_contracts_at(reference_fd)
        transaction_name = f"{lock_name}.transaction"
        cleanup_name = f"{transaction_name}.cleanup"
        transaction = runtime_root / transaction_name
        _finish_cleanup_tombstone_at(runtime_fd, cleanup_name)
        _recover_transaction(
            transaction,
            reference_authority,
            runtime_fd,
            reference_fd,
            pin,
            manifest,
            source_pin,
            split_manifest,
        )
        source_metadata = _entry_at(reference_fd, "source", "existing source")
        sections_metadata = _entry_at(reference_fd, "sections", "existing sections")
        existing_source = source_metadata is not None
        existing_sections = sections_metadata is not None
        if existing_source or existing_sections:
            try:
                evidence = _verify_materialized_at(
                    reference_fd,
                    pin,
                    manifest,
                    source_pin,
                    split_manifest,
                )
            except SourceError as error:
                if not replace_existing:
                    raise SourceError("existing materialized output is invalid and was preserved") from error
                for metadata in (source_metadata, sections_metadata):
                    if metadata is not None and (
                        stat.S_ISLNK(metadata.st_mode)
                        or not stat.S_ISDIR(metadata.st_mode)
                    ):
                        raise SourceError(
                            "unsafe existing materialized output was preserved"
                        ) from error
            else:
                evidence.update({"status": "cached", "elapsed_seconds": round(time.monotonic() - started, 6)})
                return evidence
        acquisition: dict[str, Any] = {"status": "provided"}
        if archive_path is None:
            archive, acquisition = acquire_archive_at(runtime_fd, pin, timeout_seconds)
            archive_evidence = f"bound-runtime:{ARCHIVE_CACHE_NAME}"
        else:
            archive = read_pinned_archive(archive_path, pin)
            archive_evidence = str(archive_path)
        members = extract_pinned_members(archive, pin)
        outputs, records = validate_and_split(members[manifest["source_member"]], manifest)
        expected = _expected_materialized(members, outputs, records)
        inventory = _inventory_bytes(source_pin, split_manifest, expected)
        ready = (sha256_bytes(inventory) + "\n").encode("ascii")
        original_presence = {"source": existing_source, "sections": existing_sections}
        transaction_created = False
        transaction_fd: int | None = None
        staging_fd: int | None = None
        backup_fd: int | None = None
        preparation_metadata: os.stat_result | None = None
        try:
            transaction_fd, preparation_metadata = _create_bound_directory_at(
                runtime_fd,
                cleanup_name,
                "materialization preparation",
            )
            _write_new_file_at(
                transaction_fd,
                "transaction.json",
                _transaction_document(
                    reference_authority,
                    _entry_identity(os.fstat(reference_fd)),
                    original_presence,
                ),
            )
            staging_fd, _ = _create_bound_directory_at(
                transaction_fd,
                "stage",
                "materialization staging directory",
            )
            backup_fd, _ = _create_bound_directory_at(
                transaction_fd,
                "backup",
                "materialization backup directory",
            )
            os.fsync(transaction_fd)
            os.fsync(runtime_fd)
            os.replace(
                cleanup_name,
                transaction_name,
                src_dir_fd=runtime_fd,
                dst_dir_fd=runtime_fd,
            )
            _require_bound_entry(
                runtime_fd,
                transaction_name,
                preparation_metadata,
                "materialization transaction",
            )
            transaction_created = True
            os.fsync(runtime_fd)
        except (OSError, SourceError) as error:
            try:
                if transaction_created:
                    if transaction_fd is None:
                        raise SourceError("materialization transaction descriptor is unavailable")
                    _commit_transaction_cleanup_at(
                        runtime_fd,
                        transaction_name,
                        transaction_fd,
                    )
                else:
                    _finish_cleanup_tombstone_at(
                        runtime_fd,
                        cleanup_name,
                        preparation_metadata,
                    )
            except (OSError, SourceError) as cleanup_error:
                retained_names = [
                    name
                    for name in (transaction_name, cleanup_name)
                    if _entry_exists(runtime_fd, name)
                ]
                disposition = (
                    "cleanup state was preserved: "
                    + ", ".join(str(runtime_root / name) for name in retained_names)
                    if retained_names
                    else "cleanup removal durability is uncertain"
                )
                raise SourceError(
                    f"cannot create materialization transaction; {disposition}"
                ) from cleanup_error
            finally:
                for descriptor in (backup_fd, staging_fd, transaction_fd):
                    if descriptor is not None:
                        os.close(descriptor)
            raise SourceError(
                f"cannot create materialization transaction: {transaction}"
            ) from error
        assert transaction_fd is not None
        assert staging_fd is not None
        assert backup_fd is not None
        try:
            for relative, payload in sorted(expected.items()):
                _write_new_file_at(staging_fd, relative, payload)
            _write_new_file_at(staging_fd, "sections/inventory.json", inventory)
            _fsync_tree_at(staging_fd)
            if existing_source:
                os.replace(
                    "source",
                    "source",
                    src_dir_fd=reference_fd,
                    dst_dir_fd=backup_fd,
                )
            if existing_sections:
                os.replace(
                    "sections",
                    "sections",
                    src_dir_fd=reference_fd,
                    dst_dir_fd=backup_fd,
                )
            os.fsync(backup_fd)
            os.fsync(reference_fd)
            os.replace(
                "source",
                "source",
                src_dir_fd=staging_fd,
                dst_dir_fd=reference_fd,
            )
            os.replace(
                "sections",
                "sections",
                src_dir_fd=staging_fd,
                dst_dir_fd=reference_fd,
            )
            sections_metadata = _directory_entry(
                reference_fd,
                "sections",
                "published sections directory",
            )
            if sections_metadata is None:
                raise SourceError("published sections directory disappeared")
            sections_fd = _open_bound_directory(
                reference_fd,
                "sections",
                sections_metadata,
                "published sections directory",
            )
            try:
                _write_new_file_at(sections_fd, ".READY.partial", ready)
                os.replace(
                    ".READY.partial",
                    "READY",
                    src_dir_fd=sections_fd,
                    dst_dir_fd=sections_fd,
                )
                os.fsync(sections_fd)
            finally:
                os.close(sections_fd)
            os.fsync(reference_fd)
            verified = _verify_materialized_at(
                reference_fd,
                pin,
                manifest,
                source_pin,
                split_manifest,
            )
        except BaseException as error:
            os.close(backup_fd)
            backup_fd = None
            os.close(staging_fd)
            staging_fd = None
            try:
                rollback_errors, transaction_retained = _rollback_transaction(
                    transaction,
                    original_presence,
                    _runtime_fd=runtime_fd,
                    _reference_fd=reference_fd,
                    _transaction_fd=transaction_fd,
                )
            finally:
                os.close(transaction_fd)
                transaction_fd = None
            if rollback_errors:
                disposition = (
                    f"preserved {transaction}"
                    if transaction_retained
                    else "transaction removal durability is uncertain"
                )
                raise SourceError(
                    f"publication failed and rollback is incomplete; {disposition}: "
                    + "; ".join(rollback_errors)
                ) from error
            raise
        os.close(backup_fd)
        backup_fd = None
        os.close(staging_fd)
        staging_fd = None
        try:
            _commit_transaction_cleanup_at(
                runtime_fd,
                transaction_name,
                transaction_fd,
            )
        finally:
            os.close(transaction_fd)
            transaction_fd = None
        verified.update({
            "status": "published",
            "archive": archive_evidence,
            "archive_sha256": sha256_bytes(archive),
            "acquisition": acquisition,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        })
        return verified


def _validate_contract_payloads(
    source_pin: bytes,
    split_manifest: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pin = _decode_json_contract(source_pin, "source-pin.json")
    manifest = _decode_json_contract(split_manifest, "split-manifest.json")
    members = validate_source_pin(pin)
    validate_manifest(manifest)
    primary = members[manifest["source_member"]]
    if (manifest["source_bytes"], manifest["source_sha256"], manifest["source_crlf_lines"]) != (primary["bytes"], primary["sha256"], primary["crlf_lines"]):
        raise SourceError("source pin and split manifest disagree")
    return pin, manifest


def _validate_contracts_at(
    reference_fd: int,
) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    source_pin = _read_regular_bounded_at(
        reference_fd,
        "source-pin.json",
        CONTRACT_MAX_BYTES,
    )
    split_manifest = _read_regular_bounded_at(
        reference_fd,
        "split-manifest.json",
        CONTRACT_MAX_BYTES,
    )
    pin, manifest = _validate_contract_payloads(source_pin, split_manifest)
    return pin, manifest, source_pin, split_manifest


def validate_contracts(reference_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with _bound_directory(reference_root) as reference_fd:
        pin, manifest, _, _ = _validate_contracts_at(reference_fd)
        return pin, manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate-contracts", "inspect-archive", "materialize", "verify"))
    parser.add_argument("--reference-root", type=Path, default=Path(__file__).resolve().parents[1] / "references" / "2001.04383v3")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--runtime-root", type=Path, default=Path(__file__).resolve().parents[1] / ".workflow-runtime" / "reference-source")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--replace-existing", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        pin, manifest = validate_contracts(arguments.reference_root)
        evidence: dict[str, Any] = {"status": "ok", "command": arguments.command}
        if arguments.command == "inspect-archive":
            if arguments.archive is None:
                parser.error("inspect-archive requires --archive")
            archive = read_pinned_archive(arguments.archive, pin)
            members = extract_pinned_members(archive, pin)
            outputs, records = validate_and_split(members[manifest["source_member"]], manifest)
            evidence.update({"archive_bytes": len(archive), "members": sorted(members), "slices": len(outputs), "labels": len(records)})
        elif arguments.command == "materialize":
            evidence = materialize(
                arguments.reference_root,
                arguments.runtime_root,
                archive_path=arguments.archive,
                timeout_seconds=arguments.timeout_seconds,
                replace_existing=arguments.replace_existing,
            )
        elif arguments.command == "verify":
            evidence = verify_materialized(arguments.reference_root)
        print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
        return 0
    except (OSError, SourceError, reference_transport.ReferenceTransportError) as error:
        print(json.dumps({"status": "failed", "error": {"class": type(error).__name__, "message": str(error)}}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    sys.exit(main())
