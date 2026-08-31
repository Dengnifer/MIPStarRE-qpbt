from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
REFERENCE_ROOT = Path(__file__).resolve().parents[1] / "references" / "2001.04383v3"
PINNED_ARCHIVE = Path("/tmp/2001.04383v3-source.tar")
sys.path.insert(0, str(SCRIPTS))

import reference_source as source  # noqa: E402


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def make_archive(entries: list[tuple[str, bytes, bytes]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz", format=tarfile.USTAR_FORMAT) as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.type = kind
            info.mtime = 0
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                info.linkname = "compression_arXiv_v3.tex"
                info.size = 0
                archive.addfile(info)
            else:
                archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def synthetic_pin(archive: bytes, tex: bytes, bbl: bytes) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source_id": "arxiv-2001.04383v3",
        "url": "https://arxiv.org/src/2001.04383v3",
        "allowed_hosts": ["arxiv.org", "export.arxiv.org"],
        "archive": {"bytes": len(archive), "sha256": digest(archive)},
        "members": [
            {"name": "compression_arXiv_v3.tex", "bytes": len(tex), "sha256": digest(tex), "crlf_lines": 1},
            {"name": "compression_arXiv_v3.bbl", "bytes": len(bbl), "sha256": digest(bbl), "crlf_lines": 1},
        ],
    }


class ReferenceSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pin, cls.manifest = source.validate_contracts(REFERENCE_ROOT)

    def rollback_transaction(
        self,
        transaction: Path,
        reference: Path,
        original_presence: dict[str, bool],
    ) -> tuple[list[str], bool]:
        runtime_fd = source._open_directory_at(transaction.parent)
        reference_fd = source._open_directory_at(reference)
        try:
            return source._rollback_transaction(
                transaction,
                original_presence,
                _runtime_fd=runtime_fd,
                _reference_fd=reference_fd,
            )
        finally:
            source.os.close(reference_fd)
            source.os.close(runtime_fd)

    def assert_first_stage_write_uses_selected_runtime(self, *, replacement_is_symlink: bool) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            selected_runtime = root / "selected-runtime"
            replacement = root / "replacement-runtime"
            reference.mkdir(parents=True)
            replacement.mkdir()
            (replacement / "sentinel").write_bytes(b"replacement")
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            real_write = source._write_new_file_at
            swapped = False

            def swap_before_first_stage_write(
                directory_fd: int,
                relative: str,
                payload: bytes,
            ) -> None:
                nonlocal swapped
                directory_path = Path(source.os.readlink(f"/proc/self/fd/{directory_fd}"))
                if not swapped and directory_path.name == "stage":
                    swapped = True
                    runtime.rename(selected_runtime)
                    if replacement_is_symlink:
                        runtime.symlink_to(replacement, target_is_directory=True)
                    else:
                        replacement.rename(runtime)
                real_write(directory_fd, relative, payload)

            with mock.patch.object(
                source,
                "_write_new_file_at",
                side_effect=swap_before_first_stage_write,
            ):
                result = source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)

            visible_replacement = replacement if replacement_is_symlink else runtime
            self.assertTrue(swapped)
            self.assertEqual("published", result["status"])
            self.assertEqual(b"replacement", (visible_replacement / "sentinel").read_bytes())
            self.assertEqual([], list(visible_replacement.glob("*.transaction")))
            self.assertEqual([], list(visible_replacement.glob("*.cleanup")))
            self.assertEqual([], list(visible_replacement.glob("*.lock")))
            self.assertEqual(1, len(list(selected_runtime.glob("*.lock"))))
            self.assertEqual([], list(selected_runtime.glob("*.transaction")))
            self.assertEqual([], list(selected_runtime.glob("*.cleanup")))
            self.assertEqual("verified", source.verify_materialized(reference)["status"])

    def test_committed_contracts_are_strict_and_cross_consistent(self) -> None:
        slices = source.validate_manifest(self.manifest)
        self.assertEqual(34, len(slices))
        self.assertEqual(15, sum(path.startswith("top-level/") for path, _ in slices))
        self.assertEqual(10, sum(path.startswith("qpbt/") for path, _ in slices))
        self.assertEqual(9, sum(path.startswith("dependencies/") for path, _ in slices))

    def test_manifest_rejects_gap_in_exact_cover(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["collections"][0]["slices"][1][1] += 1
        with self.assertRaisesRegex(source.SourceError, "exact ordered cover"):
            source.validate_manifest(manifest)

    def test_manifest_rejects_overlap_and_wrong_end_in_exact_cover(self) -> None:
        for collection_index, slice_index, field, delta in ((0, 1, 1, -1), (2, -1, 2, -1)):
            manifest = copy.deepcopy(self.manifest)
            manifest["collections"][collection_index]["slices"][slice_index][field] += delta
            with self.assertRaises(source.SourceError):
                source.validate_manifest(manifest)

    def test_manifest_rejects_duplicate_output_path(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["collections"][2]["slices"][0][0] = "qpbt-introduction"
        with self.assertRaisesRegex(source.SourceError, "duplicated"):
            source.validate_manifest(manifest)

    def test_manifest_rejects_label_contract_drift(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["labels"]["regex"] = ".*"
        with self.assertRaisesRegex(source.SourceError, "lexical pattern"):
            source.validate_manifest(manifest)

    def test_manifest_rejects_collection_directory_and_dependency_scope_drift(self) -> None:
        for mutate in (
            lambda value: value["collections"][0].__setitem__("output_directory", "other"),
            lambda value: value["collections"][3]["scopes"][0].__setitem__(1, 1821),
        ):
            manifest = copy.deepcopy(self.manifest)
            mutate(manifest)
            with self.assertRaises(source.SourceError):
                source.validate_manifest(manifest)

    def test_json_duplicate_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(source.SourceError, "duplicate JSON key"):
                source.load_json(path)

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_real_pinned_archive_extracts_splits_and_reconstructs(self) -> None:
        members = source.extract_pinned_members(PINNED_ARCHIVE.read_bytes(), self.pin)
        outputs, records = source.validate_and_split(members["compression_arXiv_v3.tex"], self.manifest)
        self.assertEqual(34, len(outputs))
        self.assertEqual(646, len(records))
        duplicates = [record for record in records if record["name"] == "eq:farith"]
        self.assertEqual([8928, 10391], [record["line"] for record in duplicates])
        self.assertEqual([1, 2], [record["name_ordinal"] for record in duplicates])
        self.assertTrue(all(record["output_paths"][0].startswith("top-level/") for record in records))
        reconstructed = b"".join(outputs[f"top-level/{entry[0]}.tex"] for entry in self.manifest["collections"][0]["slices"])
        self.assertEqual(members["compression_arXiv_v3.tex"], reconstructed)

    def test_crlf_validator_rejects_lf_bare_cr_and_missing_terminator(self) -> None:
        for payload in (b"one\n", b"one\rtwo\r\n", b"one"):
            with self.subTest(payload=payload), self.assertRaises(source.SourceError):
                source.validate_crlf(payload, 1, "fixture")

    def test_label_records_use_one_based_line_column_and_half_open_bytes(self) -> None:
        payload = b"x\r\n  \\label{alpha} y \\label{alpha}\r\n"
        records = source.label_records(payload)
        self.assertEqual([1, 2], [record["name_ordinal"] for record in records])
        self.assertEqual([2, 2], [record["line"] for record in records])
        self.assertEqual(3, records[0]["byte_column"])
        for record in records:
            self.assertEqual(b"\\label{alpha}", payload[record["byte_start"] : record["byte_end"]])

    def _extract_synthetic(self, entries: list[tuple[str, bytes, bytes]]) -> dict[str, bytes]:
        tex, bbl = b"tex\r\n", b"bbl\r\n"
        archive = make_archive(entries)
        pin = synthetic_pin(archive, tex, bbl)
        with mock.patch.object(source, "ARCHIVE_MAX_BYTES", len(archive)):
            return source.extract_pinned_members(archive, pin)

    def test_fixed_regular_member_archive_is_accepted(self) -> None:
        members = self._extract_synthetic([
            ("compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE),
            ("compression_arXiv_v3.bbl", b"bbl\r\n", tarfile.REGTYPE),
        ])
        self.assertEqual({"compression_arXiv_v3.tex", "compression_arXiv_v3.bbl"}, set(members))

    def test_archive_rejects_extra_duplicate_missing_and_path_members(self) -> None:
        cases = [
            [
                ("compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE),
                ("compression_arXiv_v3.bbl", b"bbl\r\n", tarfile.REGTYPE),
                ("extra.tex", b"x\r\n", tarfile.REGTYPE),
            ],
            [
                ("compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE),
                ("compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE),
                ("compression_arXiv_v3.bbl", b"bbl\r\n", tarfile.REGTYPE),
            ],
            [("compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE)],
            [
                ("dir/compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE),
                ("compression_arXiv_v3.bbl", b"bbl\r\n", tarfile.REGTYPE),
            ],
        ]
        for entries in cases:
            with self.subTest(entries=[entry[0] for entry in entries]), self.assertRaises(source.SourceError):
                self._extract_synthetic(entries)

    def test_archive_rejects_links_devices_directories_and_override_headers(self) -> None:
        forbidden_types = (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE, tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK, tarfile.GNUTYPE_SPARSE)
        for kind in forbidden_types:
            entries = [
                ("compression_arXiv_v3.tex", b"tex\r\n", kind),
                ("compression_arXiv_v3.bbl", b"bbl\r\n", tarfile.REGTYPE),
            ]
            with self.subTest(kind=kind), self.assertRaises(source.SourceError):
                self._extract_synthetic(entries)

    def test_archive_rejects_checksum_corruption_before_decompression(self) -> None:
        archive = bytearray(make_archive([
            ("compression_arXiv_v3.tex", b"tex\r\n", tarfile.REGTYPE),
            ("compression_arXiv_v3.bbl", b"bbl\r\n", tarfile.REGTYPE),
        ]))
        pin = synthetic_pin(bytes(archive), b"tex\r\n", b"bbl\r\n")
        archive[-1] ^= 1
        with mock.patch.object(source, "ARCHIVE_MAX_BYTES", len(archive)), self.assertRaisesRegex(source.SourceError, "archive bytes or checksum"):
            source.extract_pinned_members(bytes(archive), pin)

    def test_concatenated_gzip_stream_is_rejected(self) -> None:
        payload = gzip.compress(b"a") + gzip.compress(b"b")
        with self.assertRaisesRegex(source.SourceError, "concatenated"):
            source._decompress_gzip(payload)

    def test_truncated_gzip_and_decompression_bomb_are_rejected(self) -> None:
        with self.assertRaises(source.SourceError):
            source._decompress_gzip(gzip.compress(b"payload")[:-3])
        with self.assertRaisesRegex(source.SourceError, "byte bound"):
            source._decompress_gzip(gzip.compress(b"x" * (source.TAR_MAX_BYTES + 1)))

    def test_read_pinned_archive_rejects_oversize_and_symlink_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            oversized = root / "oversized"
            oversized.write_bytes(b"x" * (self.pin["archive"]["bytes"] + 1))
            with self.assertRaisesRegex(source.SourceError, "size differs"):
                source.read_pinned_archive(oversized, self.pin)
            link = root / "link"
            link.symlink_to(oversized)
            with self.assertRaisesRegex(source.SourceError, "regular file"):
                source.read_pinned_archive(link, self.pin)

    def test_acquire_archive_delegates_exact_pin_to_reference_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(source.reference_transport, "acquire", return_value={"status": "published"}) as acquire:
            destination = Path(temporary) / "archive"
            result = source.acquire_archive(self.pin, destination, 7.0)
            self.assertEqual("published", result["status"])
            transport_pin = acquire.call_args.args[0]
            self.assertEqual(self.pin["archive"]["sha256"], transport_pin.sha256)
            self.assertEqual(self.pin["archive"]["bytes"], transport_pin.max_bytes)
            self.assertEqual(("arxiv.org", "export.arxiv.org"), transport_pin.allowed_hosts)
            self.assertEqual(7.0, acquire.call_args.kwargs["timeout_seconds"])

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_materialize_is_verified_and_second_run_is_a_cache_hit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            runtime = root / ".workflow-runtime" / "reference-source"
            first = source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertEqual("published", first["status"])
            ready_before = (reference / "sections" / "READY").read_bytes()
            inventory_mtime = (reference / "sections" / "inventory.json").stat().st_mtime_ns
            second = source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertEqual("cached", second["status"])
            self.assertEqual(ready_before, (reference / "sections" / "READY").read_bytes())
            self.assertEqual(inventory_mtime, (reference / "sections" / "inventory.json").stat().st_mtime_ns)
            self.assertEqual("verified", source.verify_materialized(reference)["status"])

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_invalid_existing_materialization_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            (reference / "source").mkdir()
            sentinel = reference / "source" / "user-data"
            sentinel.write_bytes(b"preserve me")
            with self.assertRaisesRegex(source.SourceError, "was preserved"):
                source.materialize(reference, root / ".workflow-runtime" / "reference-source", archive_path=PINNED_ARCHIVE)
            self.assertEqual(b"preserve me", sentinel.read_bytes())
            self.assertFalse((reference / "sections").exists())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_destination_symlink_is_rejected_and_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            target = root / "target"
            target.mkdir()
            (reference / "source").symlink_to(target, target_is_directory=True)
            with self.assertRaisesRegex(source.SourceError, "was preserved"):
                source.materialize(reference, root / ".workflow-runtime" / "reference-source", archive_path=PINNED_ARCHIVE)
            self.assertTrue((reference / "source").is_symlink())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_explicit_replacement_rolls_back_both_trees_on_rename_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            (reference / "source").mkdir()
            (reference / "sections").mkdir()
            (reference / "source" / "old").write_bytes(b"old source")
            (reference / "sections" / "old").write_bytes(b"old sections")
            real_replace = source.os.replace
            failed = False

            def fail_new_sections(old: Path, new: Path, **arguments: object) -> None:
                nonlocal failed
                old_path = Path(old)
                source_directory_fd = arguments.get("src_dir_fd")
                source_parent = (
                    Path(source.os.readlink(f"/proc/self/fd/{source_directory_fd}")).name
                    if isinstance(source_directory_fd, int)
                    else old_path.parent.name
                )
                if not failed and old_path.name == "sections" and source_parent == "stage":
                    failed = True
                    raise OSError("injected sections rename failure")
                real_replace(old, new, **arguments)

            with mock.patch.object(source.os, "replace", side_effect=fail_new_sections), self.assertRaisesRegex(OSError, "injected"):
                source.materialize(reference, root / ".workflow-runtime" / "reference-source", archive_path=PINNED_ARCHIVE, replace_existing=True)
            self.assertEqual(b"old source", (reference / "source" / "old").read_bytes())
            self.assertEqual(b"old sections", (reference / "sections" / "old").read_bytes())
            self.assertEqual([], list(reference.glob(".reference-source-*-*")))

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_final_verification_reference_root_replacement_rolls_back_selected_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            selected_reference = root / "selected-reference"
            runtime = root / ".workflow-runtime" / "reference-source"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            primary = reference / "source" / "compression_arXiv_v3.tex"
            corrupted = b"descriptor-bound original\r\n"
            primary.write_bytes(corrupted)
            replacement_files = {
                "sentinel": b"replacement root",
                "source/sentinel": b"replacement source",
                "sections/sentinel": b"replacement sections",
            }
            real_verify = source._verify_materialized_at
            verification_calls = 0
            replaced = False

            def fail_final_verification(*arguments: object, **keywords: object) -> dict[str, object]:
                nonlocal verification_calls, replaced
                verification_calls += 1
                if verification_calls == 2:
                    reference.rename(selected_reference)
                    reference.mkdir()
                    for relative, payload in replacement_files.items():
                        destination = reference / relative
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(payload)
                    replaced = True
                    raise source.SourceError("injected final verification failure")
                return real_verify(*arguments, **keywords)

            with (
                mock.patch.object(
                    source,
                    "_verify_materialized_at",
                    side_effect=fail_final_verification,
                ),
                self.assertRaisesRegex(
                    source.SourceError,
                    "injected final verification failure",
                ),
            ):
                source.materialize(
                    reference,
                    runtime,
                    archive_path=PINNED_ARCHIVE,
                    replace_existing=True,
                )

            self.assertTrue(replaced)
            self.assertEqual(2, verification_calls)
            self.assertEqual(corrupted, (selected_reference / primary.relative_to(reference)).read_bytes())
            self.assertTrue((selected_reference / "sections" / "READY").is_file())
            self.assertEqual(
                replacement_files,
                {
                    str(path.relative_to(reference)): path.read_bytes()
                    for path in reference.rglob("*")
                    if path.is_file()
                },
            )
            self.assertEqual([], list(runtime.glob("*.transaction")))
            self.assertEqual([], list(runtime.glob("*.cleanup")))

    def test_restart_recovery_rejects_replaced_reference_directory_instance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            selected_reference = root / "selected-reference"
            runtime = root / ".workflow-runtime" / "reference-source"
            reference.mkdir(parents=True)
            runtime.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())

            lock_name = hashlib.sha256(
                str(reference.resolve()).encode("utf-8")
            ).hexdigest() + ".lock"
            transaction = runtime / f"{lock_name}.transaction"
            (transaction / "backup" / "source").mkdir(parents=True)
            (transaction / "backup" / "sections").mkdir()
            (transaction / "backup" / "source" / "saved").write_bytes(b"old source")
            (transaction / "backup" / "sections" / "saved").write_bytes(b"old sections")
            (transaction / "transaction.json").write_bytes(
                source._transaction_document(
                    str(reference.resolve()),
                    source._entry_identity(reference.stat()),
                    {"source": True, "sections": True},
                )
            )

            reference.rename(selected_reference)
            reference.mkdir()
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            (reference / "source").mkdir()
            (reference / "sections").mkdir()
            (reference / "source" / "sentinel").write_bytes(b"replacement source")
            (reference / "sections" / "sentinel").write_bytes(b"replacement sections")

            replacement_before = {
                str(path.relative_to(reference)): path.read_bytes()
                for path in reference.rglob("*")
                if path.is_file()
            }
            transaction_before = {
                str(path.relative_to(transaction)): path.read_bytes()
                for path in transaction.rglob("*")
                if path.is_file()
            }
            with self.assertRaisesRegex(
                source.SourceError,
                "reference directory identity differs; preserved",
            ):
                source.materialize(
                    reference,
                    runtime,
                    archive_path=root / "must-not-be-read.tar",
                    replace_existing=True,
                )

            self.assertEqual(
                replacement_before,
                {
                    str(path.relative_to(reference)): path.read_bytes()
                    for path in reference.rglob("*")
                    if path.is_file()
                },
            )
            self.assertEqual(
                transaction_before,
                {
                    str(path.relative_to(transaction)): path.read_bytes()
                    for path in transaction.rglob("*")
                    if path.is_file()
                },
            )
            self.assertTrue(transaction.is_dir())
            self.assertEqual([], list(runtime.glob("*.cleanup")))
            self.assertFalse((selected_reference / "source").exists())
            self.assertFalse((selected_reference / "sections").exists())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_failed_rollback_retains_both_backups_and_startup_recovers_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            (reference / "source").mkdir()
            (reference / "sections").mkdir()
            (reference / "source" / "old").write_bytes(b"old source")
            (reference / "sections" / "old").write_bytes(b"old sections")
            runtime = root / ".workflow-runtime" / "reference-source"
            real_replace = source.os.replace
            forward_failed = False

            def fail_forward_and_restores(old: Path, new: Path, **arguments: object) -> None:
                nonlocal forward_failed
                old_path = Path(old)
                source_directory_fd = arguments.get("src_dir_fd")
                source_parent = (
                    Path(source.os.readlink(f"/proc/self/fd/{source_directory_fd}")).name
                    if source_directory_fd is not None
                    else old_path.parent.name
                )
                if not forward_failed and old_path.name == "sections" and source_parent == "stage":
                    forward_failed = True
                    raise OSError("injected forward failure")
                if source_parent == "backup":
                    raise OSError(f"injected {old_path.name} restore failure")
                real_replace(old, new, **arguments)

            with mock.patch.object(source.os, "replace", side_effect=fail_forward_and_restores), self.assertRaisesRegex(source.SourceError, "preserved"):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE, replace_existing=True)
            transactions = list(runtime.glob("*.transaction"))
            self.assertEqual(1, len(transactions))
            self.assertEqual(b"old source", (transactions[0] / "backup" / "source" / "old").read_bytes())
            self.assertEqual(b"old sections", (transactions[0] / "backup" / "sections" / "old").read_bytes())
            self.assertEqual([], list(reference.glob(".reference-source-*")))
            with self.assertRaisesRegex(source.SourceError, "was preserved"):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertEqual(b"old source", (reference / "source" / "old").read_bytes())
            self.assertEqual(b"old sections", (reference / "sections" / "old").read_bytes())
            self.assertEqual([], list(runtime.glob("*.transaction")))

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_predelete_reference_fsync_failure_retains_recoverable_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            (reference / "source").mkdir()
            (reference / "sections").mkdir()
            (reference / "source" / "old").write_bytes(b"old source")
            (reference / "sections" / "old").write_bytes(b"old sections")
            runtime = root / ".workflow-runtime" / "reference-source"
            real_replace = source.os.replace
            real_fsync = source.os.fsync
            forward_failed = False
            rollback_fsync_failed = False

            def fail_forward(old: Path, new: Path, **arguments: object) -> None:
                nonlocal forward_failed
                old_path = Path(old)
                source_directory_fd = arguments.get("src_dir_fd")
                source_parent = (
                    Path(source.os.readlink(f"/proc/self/fd/{source_directory_fd}")).name
                    if isinstance(source_directory_fd, int)
                    else old_path.parent.name
                )
                if not forward_failed and old_path.name == "sections" and source_parent == "stage":
                    forward_failed = True
                    raise OSError("injected forward failure")
                real_replace(old, new, **arguments)

            def fail_rollback_fsync(descriptor: int) -> None:
                nonlocal rollback_fsync_failed
                descriptor_path = Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))
                if forward_failed and not rollback_fsync_failed and descriptor_path == reference:
                    rollback_fsync_failed = True
                    raise OSError("injected restored-root fsync failure")
                real_fsync(descriptor)

            with (
                mock.patch.object(source.os, "replace", side_effect=fail_forward),
                mock.patch.object(source.os, "fsync", side_effect=fail_rollback_fsync),
                self.assertRaisesRegex(source.SourceError, "preserved"),
            ):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE, replace_existing=True)
            transactions = list(runtime.glob("*.transaction"))
            self.assertEqual(1, len(transactions))
            self.assertTrue((transactions[0] / "transaction.json").is_file())
            self.assertEqual(b"old source", (reference / "source" / "old").read_bytes())
            self.assertEqual(b"old sections", (reference / "sections" / "old").read_bytes())
            with self.assertRaisesRegex(source.SourceError, "was preserved"):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertEqual([], list(runtime.glob("*.transaction")))

    def test_successful_rollback_cleanup_fsync_order_is_durable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            transaction = runtime / "transaction"
            reference.mkdir(parents=True)
            transaction.mkdir(parents=True)
            (transaction / "backup").mkdir()
            events: list[tuple[str, Path]] = []
            real_fsync = source.os.fsync
            real_remove_contents = source._remove_tree_contents_at
            cleanup_recorded = False

            def record_fsync(descriptor: int) -> None:
                events.append(("fsync", Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))))
                real_fsync(descriptor)

            def record_remove_contents(descriptor: int) -> None:
                nonlocal cleanup_recorded
                if not cleanup_recorded:
                    cleanup_recorded = True
                    events.append(("remove", Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))))
                real_remove_contents(descriptor)

            with mock.patch.object(source.os, "fsync", side_effect=record_fsync), mock.patch.object(source, "_remove_tree_contents_at", side_effect=record_remove_contents):
                errors, retained = self.rollback_transaction(
                    transaction, reference, {"source": False, "sections": False}
                )
            self.assertEqual([], errors)
            self.assertFalse(retained)
            self.assertEqual(
                [
                    ("fsync", reference),
                    ("fsync", runtime),
                    ("remove", source._cleanup_tombstone(transaction)),
                    ("fsync", runtime),
                ],
                events,
            )

    def test_rollback_postdelete_fsync_failure_reports_uncertain_not_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            runtime = root / "runtime"
            transaction = runtime / "transaction"
            reference.mkdir()
            (transaction / "backup").mkdir(parents=True)
            real_fsync = source.os.fsync
            runtime_fsyncs = 0

            def fail_postdelete_fsync(descriptor: int) -> None:
                nonlocal runtime_fsyncs
                descriptor_path = Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))
                if descriptor_path == runtime:
                    runtime_fsyncs += 1
                    if runtime_fsyncs == 2:
                        raise OSError("injected post-delete runtime fsync failure")
                real_fsync(descriptor)

            with mock.patch.object(source.os, "fsync", side_effect=fail_postdelete_fsync):
                errors, retained = self.rollback_transaction(
                    transaction, reference, {"source": False, "sections": False}
                )

            self.assertFalse(retained)
            self.assertIn("removal durability is uncertain", errors[0])
            self.assertFalse(transaction.exists())
            self.assertFalse(source._cleanup_tombstone(transaction).exists())

    def test_rollback_rejects_symlinked_backup_component_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            transaction = root / "runtime" / "transaction"
            external = root / "external"
            reference.mkdir()
            transaction.mkdir(parents=True)
            external.mkdir()
            for name in ("source", "sections"):
                (reference / name).mkdir()
                (reference / name / "current").write_bytes(f"current {name}".encode("ascii"))
                (external / name).mkdir()
                (external / name / "sentinel").write_bytes(f"external {name}".encode("ascii"))
            (transaction / "backup").symlink_to(external, target_is_directory=True)

            errors, retained = self.rollback_transaction(
                transaction, reference, {"source": True, "sections": True}
            )

            self.assertTrue(retained)
            self.assertIn("backup boundary", errors[0])
            self.assertTrue(transaction.is_dir())
            for name in ("source", "sections"):
                self.assertEqual(f"current {name}".encode("ascii"), (reference / name / "current").read_bytes())
                self.assertEqual(f"external {name}".encode("ascii"), (external / name / "sentinel").read_bytes())

    def test_rollback_rejects_symlinked_saved_tree_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            transaction = root / "runtime" / "transaction"
            backup = transaction / "backup"
            external = root / "external"
            reference.mkdir()
            backup.mkdir(parents=True)
            external.mkdir()
            (reference / "source").mkdir()
            (reference / "source" / "current").write_bytes(b"current")
            (external / "source").mkdir()
            (external / "source" / "sentinel").write_bytes(b"external")
            (backup / "source").symlink_to(external / "source", target_is_directory=True)

            errors, retained = self.rollback_transaction(
                transaction, reference, {"source": True, "sections": False}
            )

            self.assertTrue(retained)
            self.assertIn("unsafe rollback backup tree", errors[0])
            self.assertEqual(b"current", (reference / "source" / "current").read_bytes())
            self.assertEqual(b"external", (external / "source" / "sentinel").read_bytes())
            self.assertTrue((backup / "source").is_symlink())

    def test_rollback_rejects_nondirectory_saved_tree_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            transaction = root / "runtime" / "transaction"
            backup = transaction / "backup"
            reference.mkdir()
            backup.mkdir(parents=True)
            (reference / "source").mkdir()
            (reference / "source" / "current").write_bytes(b"current")
            (backup / "source").write_bytes(b"not a directory")

            errors, retained = self.rollback_transaction(
                transaction, reference, {"source": True, "sections": False}
            )

            self.assertTrue(retained)
            self.assertIn("unsafe rollback backup tree", errors[0])
            self.assertEqual(b"current", (reference / "source" / "current").read_bytes())
            self.assertEqual(b"not a directory", (backup / "source").read_bytes())

    def test_rollback_saved_tree_swap_retains_current_and_recovery_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            transaction = root / "runtime" / "transaction"
            backup = transaction / "backup"
            external = root / "external"
            reference.mkdir()
            backup.mkdir(parents=True)
            external.mkdir()
            (reference / "source").mkdir()
            (reference / "source" / "current").write_bytes(b"current")
            (backup / "source").mkdir()
            (backup / "source" / "original").write_bytes(b"original")
            (external / "sentinel").write_bytes(b"external")
            real_replace = source.os.replace
            raced = False

            def swap_saved_tree(old: str | Path, new: str | Path, **arguments: object) -> None:
                nonlocal raced
                source_fd = arguments.get("src_dir_fd")
                source_parent = (
                    Path(source.os.readlink(f"/proc/self/fd/{source_fd}")).name
                    if isinstance(source_fd, int)
                    else ""
                )
                if not raced and str(old) == "source" and source_parent == "backup":
                    raced = True
                    source.os.rename(backup / "source", backup / "parked-source")
                    (backup / "source").symlink_to(external, target_is_directory=True)
                real_replace(old, new, **arguments)

            with mock.patch.object(source.os, "replace", side_effect=swap_saved_tree):
                errors, retained = self.rollback_transaction(
                    transaction, reference, {"source": True, "sections": False}
                )

            self.assertTrue(raced)
            self.assertTrue(retained)
            self.assertTrue(errors)
            self.assertEqual(b"current", (reference / "source" / "current").read_bytes())
            self.assertEqual(b"external", (external / "sentinel").read_bytes())
            self.assertTrue(transaction.is_dir())
            self.assertTrue((transaction / "restore-source").is_symlink())
            self.assertEqual(b"original", (backup / "parked-source" / "original").read_bytes())

    def test_rollback_runtime_path_swap_cannot_redirect_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            runtime = root / "runtime"
            transaction = runtime / "transaction"
            external = root / "external-runtime"
            reference.mkdir()
            (transaction / "backup").mkdir(parents=True)
            (external / "transaction").mkdir(parents=True)
            (external / "transaction" / "sentinel").write_bytes(b"external")
            real_fsync = source.os.fsync
            swapped = False

            def swap_runtime_path(descriptor: int) -> None:
                nonlocal swapped
                descriptor_path = Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))
                if not swapped and descriptor_path == reference:
                    swapped = True
                    runtime.rename(root / "runtime-old")
                    runtime.symlink_to(external, target_is_directory=True)
                real_fsync(descriptor)

            with mock.patch.object(source.os, "fsync", side_effect=swap_runtime_path):
                errors, retained = self.rollback_transaction(
                    transaction, reference, {"source": False, "sections": False}
                )

            self.assertTrue(swapped)
            self.assertEqual([], errors)
            self.assertFalse(retained)
            self.assertEqual(b"external", (external / "transaction" / "sentinel").read_bytes())
            self.assertFalse((root / "runtime-old" / "transaction").exists())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_first_stage_write_survives_runtime_directory_replacement(self) -> None:
        self.assert_first_stage_write_uses_selected_runtime(replacement_is_symlink=False)

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_first_stage_write_survives_runtime_symlink_replacement(self) -> None:
        self.assert_first_stage_write_uses_selected_runtime(replacement_is_symlink=True)

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_runtime_is_bound_before_single_relative_lock_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            selected_runtime = root / "selected-runtime"
            replacement = root / "replacement-runtime"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            real_locked_at = source._locked_at
            lock_calls: list[tuple[int, int, str]] = []

            def swap_before_lock(runtime_fd: int, lock_name: str):
                selected_metadata = source.os.fstat(runtime_fd)
                runtime.rename(selected_runtime)
                replacement.mkdir()
                (replacement / "sentinel").write_bytes(b"replacement")
                replacement.rename(runtime)
                lock_calls.append((selected_metadata.st_dev, selected_metadata.st_ino, lock_name))
                return real_locked_at(runtime_fd, lock_name)

            with mock.patch.object(source, "_locked_at", side_effect=swap_before_lock):
                result = source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)

            self.assertEqual("published", result["status"])
            self.assertEqual(1, len(lock_calls))
            selected_metadata = selected_runtime.stat()
            self.assertEqual(lock_calls[0][:2], (selected_metadata.st_dev, selected_metadata.st_ino))
            self.assertTrue((selected_runtime / lock_calls[0][2]).is_file())
            self.assertFalse((runtime / lock_calls[0][2]).exists())
            self.assertEqual(b"replacement", (runtime / "sentinel").read_bytes())
            self.assertEqual([], list(selected_runtime.glob("*.transaction")))
            self.assertEqual([], list(selected_runtime.glob("*.cleanup")))
            self.assertEqual("verified", source.verify_materialized(reference)["status"])

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_default_acquisition_publishes_cache_only_to_selected_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            selected_runtime = root / "selected-runtime"
            replacement = root / "replacement-runtime"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            real_locked_at = source._locked_at
            acquired_destinations: list[Path] = []

            def swap_before_lock(runtime_fd: int, lock_name: str):
                runtime.rename(selected_runtime)
                replacement.mkdir()
                (replacement / "sentinel").write_bytes(b"replacement")
                replacement.rename(runtime)
                return real_locked_at(runtime_fd, lock_name)

            def acquire_without_network(
                pin: dict[str, object],
                destination: Path,
                timeout_seconds: float,
            ) -> dict[str, object]:
                self.assertEqual(self.pin["archive"], pin["archive"])
                self.assertEqual(30.0, timeout_seconds)
                self.assertFalse(destination.is_relative_to(selected_runtime))
                self.assertFalse(destination.is_relative_to(runtime))
                acquired_destinations.append(destination)
                destination.write_bytes(PINNED_ARCHIVE.read_bytes())
                return {"status": "published", "network": False}

            with (
                mock.patch.object(source, "_locked_at", side_effect=swap_before_lock),
                mock.patch.object(source, "acquire_archive", side_effect=acquire_without_network),
            ):
                result = source.materialize(reference, runtime)

            self.assertEqual("published", result["status"])
            self.assertEqual("bound-runtime:2001.04383v3-source.tar", result["archive"])
            self.assertEqual("published-to-bound-runtime", result["acquisition"]["cache"])
            self.assertEqual(1, len(acquired_destinations))
            self.assertFalse(acquired_destinations[0].parent.exists())
            self.assertEqual(
                PINNED_ARCHIVE.read_bytes(),
                (selected_runtime / source.ARCHIVE_CACHE_NAME).read_bytes(),
            )
            self.assertEqual(
                {"sentinel": b"replacement"},
                {
                    str(path.relative_to(runtime)): path.read_bytes()
                    for path in runtime.rglob("*")
                    if path.is_file()
                },
            )
            self.assertEqual([], list(selected_runtime.glob("*.partial")))
            self.assertEqual("verified", source.verify_materialized(reference)["status"])

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_default_acquisition_rejects_link_created_during_cache_fsync(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            alias = root / "cache-staging-alias"
            unrelated = root / "unrelated"
            reference.mkdir(parents=True)
            unrelated.mkdir()
            (unrelated / "sentinel").write_bytes(b"unchanged")
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            real_fsync = source.os.fsync
            linked = False

            def acquire_without_network(
                pin: dict[str, object],
                destination: Path,
                timeout_seconds: float,
            ) -> dict[str, object]:
                self.assertEqual(self.pin["archive"], pin["archive"])
                self.assertEqual(30.0, timeout_seconds)
                destination.write_bytes(PINNED_ARCHIVE.read_bytes())
                return {"status": "published", "network": False}

            def fsync_then_link(descriptor: int) -> None:
                nonlocal linked
                real_fsync(descriptor)
                descriptor_path = Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))
                if not linked and descriptor_path.name.endswith(".partial"):
                    source.os.link(descriptor_path, alias)
                    linked = True

            with (
                mock.patch.object(source, "acquire_archive", side_effect=acquire_without_network),
                mock.patch.object(source.os, "fsync", side_effect=fsync_then_link),
                self.assertRaisesRegex(source.SourceError, "single-link invariant"),
            ):
                source.materialize(reference, runtime)

            self.assertTrue(linked)
            self.assertFalse((runtime / source.ARCHIVE_CACHE_NAME).exists())
            self.assertEqual([], list(runtime.glob("*.partial")))
            self.assertEqual(PINNED_ARCHIVE.read_bytes(), alias.read_bytes())
            self.assertEqual(b"unchanged", (unrelated / "sentinel").read_bytes())
            self.assertFalse((reference / "source").exists())
            self.assertFalse((reference / "sections").exists())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_success_cleanup_runtime_swap_uses_selected_runtime_without_redirecting_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            external = root / "external-runtime"
            reference.mkdir(parents=True)
            external.mkdir()
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            lock_name = hashlib.sha256(str(reference.resolve()).encode("utf-8")).hexdigest() + ".lock"
            transaction_name = f"{lock_name}.transaction"
            (external / transaction_name).mkdir()
            (external / transaction_name / "sentinel").write_bytes(b"external")
            real_replace = source.os.replace
            swapped = False

            def swap_runtime(old: str | Path, new: str | Path, **arguments: object) -> None:
                nonlocal swapped
                if (
                    not swapped
                    and str(old) == transaction_name
                    and arguments.get("src_dir_fd") is not None
                ):
                    swapped = True
                    runtime.rename(root / "runtime-old")
                    runtime.symlink_to(external, target_is_directory=True)
                real_replace(old, new, **arguments)

            with mock.patch.object(source.os, "replace", side_effect=swap_runtime):
                result = source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)

            self.assertTrue(swapped)
            self.assertEqual("published", result["status"])
            self.assertEqual(b"external", (external / transaction_name / "sentinel").read_bytes())
            self.assertFalse((root / "runtime-old" / transaction_name).exists())
            self.assertEqual("verified", source.verify_materialized(reference)["status"])

    def test_markerless_startup_cleanup_runtime_swap_uses_bound_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "runtime"
            cleanup_name = "transaction.cleanup"
            cleanup = runtime / cleanup_name
            external = root / "external-runtime"
            cleanup.mkdir(parents=True)
            (cleanup / "real-authority").write_bytes(b"real")
            (external / cleanup_name).mkdir(parents=True)
            (external / cleanup_name / "sentinel").write_bytes(b"external")
            runtime_fd = source._open_directory_at(runtime)
            real_remove_contents = source._remove_tree_contents_at
            swapped = False

            def swap_runtime(descriptor: int) -> None:
                nonlocal swapped
                if not swapped:
                    swapped = True
                    runtime.rename(root / "runtime-old")
                    runtime.symlink_to(external, target_is_directory=True)
                real_remove_contents(descriptor)

            try:
                with mock.patch.object(source, "_remove_tree_contents_at", side_effect=swap_runtime):
                    self.assertTrue(
                        source._finish_cleanup_tombstone_at(runtime_fd, cleanup_name)
                    )
            finally:
                source.os.close(runtime_fd)

            self.assertTrue(swapped)
            self.assertEqual(b"external", (external / cleanup_name / "sentinel").read_bytes())
            self.assertFalse((root / "runtime-old" / cleanup_name).exists())

    def test_rollback_missing_candidate_restores_current_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            transaction = root / "runtime" / "transaction"
            backup = transaction / "backup"
            reference.mkdir()
            backup.mkdir(parents=True)
            (reference / "source").mkdir()
            (reference / "source" / "current").write_bytes(b"current")
            (backup / "source").mkdir()
            (backup / "source" / "original").write_bytes(b"original")
            real_replace = source.os.replace
            raced = False

            def remove_candidate(old: str | Path, new: str | Path, **arguments: object) -> None:
                nonlocal raced
                source_fd = arguments.get("src_dir_fd")
                source_parent = (
                    Path(source.os.readlink(f"/proc/self/fd/{source_fd}")).name
                    if isinstance(source_fd, int)
                    else ""
                )
                if not raced and str(old) == "restore-source" and source_parent == "transaction":
                    raced = True
                    source.os.rename(
                        transaction / "restore-source",
                        transaction / "parked-source",
                    )
                real_replace(old, new, **arguments)

            with mock.patch.object(source.os, "replace", side_effect=remove_candidate):
                errors, retained = self.rollback_transaction(
                    transaction, reference, {"source": True, "sections": False}
                )

            self.assertTrue(raced)
            self.assertTrue(retained)
            self.assertTrue(errors)
            self.assertEqual(b"current", (reference / "source" / "current").read_bytes())
            self.assertEqual(b"original", (transaction / "parked-source" / "original").read_bytes())
            self.assertTrue(transaction.is_dir())

    def test_rollback_presence_incoherence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "reference"
            transaction = root / "runtime" / "transaction"
            reference.mkdir()
            (transaction / "backup").mkdir(parents=True)

            errors, retained = self.rollback_transaction(
                transaction, reference, {"source": True, "sections": False}
            )
            self.assertTrue(retained)
            self.assertIn("no saved or current tree", errors[0])
            self.assertTrue(transaction.is_dir())

            unexpected = root / "runtime" / "unexpected"
            (unexpected / "backup" / "source").mkdir(parents=True)
            errors, retained = self.rollback_transaction(
                unexpected, reference, {"source": False, "sections": False}
            )
            self.assertTrue(retained)
            self.assertIn("unexpected saved tree", errors[0])
            self.assertTrue(unexpected.is_dir())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_markerless_cleanup_tombstone_after_success_is_finished_on_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            runtime = root / ".workflow-runtime" / "reference-source"
            real_remove_contents = source._remove_tree_contents_at
            interrupted = False

            def interrupt_cleanup(descriptor: int) -> None:
                nonlocal interrupted
                if not interrupted:
                    interrupted = True
                    source.os.unlink("transaction.json", dir_fd=descriptor)
                    raise OSError("injected cleanup interruption")
                real_remove_contents(descriptor)

            with mock.patch.object(source, "_remove_tree_contents_at", side_effect=interrupt_cleanup), self.assertRaisesRegex(source.SourceError, "tombstone was preserved"):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            tombstones = list(runtime.glob("*.cleanup"))
            self.assertEqual(1, len(tombstones))
            self.assertFalse((tombstones[0] / "transaction.json").exists())
            self.assertEqual("verified", source.verify_materialized(reference)["status"])
            self.assertEqual("cached", source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)["status"])
            self.assertEqual([], list(runtime.glob("*.cleanup")))

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_markerless_cleanup_tombstone_after_stale_recovery_is_restartable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            runtime = root / ".workflow-runtime" / "reference-source"
            source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            lock_name = hashlib.sha256(str(reference.resolve()).encode("utf-8")).hexdigest() + ".lock"
            transaction = runtime / f"{lock_name}.transaction"
            transaction.mkdir()
            (transaction / "transaction.json").write_bytes(
                source._transaction_document(
                    str(reference.resolve()),
                    source._entry_identity(reference.stat()),
                    {"source": False, "sections": False},
                )
            )
            real_remove_contents = source._remove_tree_contents_at
            interrupted = False

            def interrupt_cleanup(descriptor: int) -> None:
                nonlocal interrupted
                if not interrupted:
                    interrupted = True
                    source.os.unlink("transaction.json", dir_fd=descriptor)
                    raise OSError("injected stale cleanup interruption")
                real_remove_contents(descriptor)

            with mock.patch.object(source, "_remove_tree_contents_at", side_effect=interrupt_cleanup), self.assertRaisesRegex(source.SourceError, "tombstone was preserved"):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertEqual(1, len(list(runtime.glob("*.cleanup"))))
            self.assertEqual("cached", source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)["status"])
            self.assertEqual([], list(runtime.glob("*.cleanup")))

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_rollback_cleanup_interruption_retains_restartable_markerless_tombstone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            runtime = root / ".workflow-runtime" / "reference-source"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            lock_name = hashlib.sha256(str(reference.resolve()).encode("utf-8")).hexdigest() + ".lock"
            transaction = runtime / f"{lock_name}.transaction"
            (transaction / "backup").mkdir(parents=True)
            (transaction / "transaction.json").write_bytes(
                source._transaction_document(
                    str(reference.resolve()),
                    source._entry_identity(reference.stat()),
                    {"source": False, "sections": False},
                )
            )

            def interrupt_cleanup(descriptor: int) -> None:
                source.os.unlink("transaction.json", dir_fd=descriptor)
                raise OSError("injected rollback cleanup interruption")

            with mock.patch.object(source, "_remove_tree_contents_at", side_effect=interrupt_cleanup):
                errors, retained = self.rollback_transaction(
                    transaction, reference, {"source": False, "sections": False}
                )
            self.assertTrue(retained)
            self.assertIn("injected rollback cleanup interruption", errors[0])
            cleanup = source._cleanup_tombstone(transaction)
            self.assertTrue(cleanup.is_dir())
            self.assertFalse((cleanup / "transaction.json").exists())
            self.assertEqual(
                "published",
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)["status"],
            )
            self.assertFalse(cleanup.exists())

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_initialization_interruption_leaves_only_recognizable_cleanup_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            runtime = root / ".workflow-runtime" / "reference-source"
            real_fsync = source.os.fsync
            real_remove_contents = source._remove_tree_contents_at
            preparation_failed = False
            cleanup_interrupted = False

            def fail_preparation_fsync(descriptor: int) -> None:
                nonlocal preparation_failed
                candidate = Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))
                if not preparation_failed and candidate.name.endswith(".cleanup"):
                    preparation_failed = True
                    raise OSError("injected preparation fsync failure")
                real_fsync(descriptor)

            def interrupt_cleanup(descriptor: int) -> None:
                nonlocal cleanup_interrupted
                if preparation_failed and not cleanup_interrupted:
                    cleanup_interrupted = True
                    source.os.unlink("transaction.json", dir_fd=descriptor)
                    raise OSError("injected preparation cleanup interruption")
                real_remove_contents(descriptor)

            with (
                mock.patch.object(source.os, "fsync", side_effect=fail_preparation_fsync),
                mock.patch.object(source, "_remove_tree_contents_at", side_effect=interrupt_cleanup),
                self.assertRaisesRegex(source.SourceError, "cleanup state was preserved"),
            ):
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertEqual([], list(runtime.glob("*.transaction")))
            self.assertEqual(1, len(list(runtime.glob("*.cleanup"))))
            self.assertEqual("published", source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)["status"])
            self.assertEqual([], list(runtime.glob("*.cleanup")))

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_initialization_postdelete_fsync_failure_reports_uncertain_not_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            runtime = root / ".workflow-runtime" / "reference-source"
            real_descriptor_fsync = source.os.fsync
            preparation_failed = False
            removal_fsync_failed = False

            def fail_removal_fsync(descriptor: int) -> None:
                nonlocal preparation_failed, removal_fsync_failed
                descriptor_path = Path(source.os.readlink(f"/proc/self/fd/{descriptor}"))
                if not preparation_failed and descriptor_path.name.endswith(".cleanup"):
                    preparation_failed = True
                    raise OSError("injected preparation failure")
                if preparation_failed and not removal_fsync_failed and descriptor_path == runtime:
                    removal_fsync_failed = True
                    raise OSError("injected post-delete parent fsync failure")
                real_descriptor_fsync(descriptor)

            with (
                mock.patch.object(source.os, "fsync", side_effect=fail_removal_fsync),
            ):
                with self.assertRaisesRegex(source.SourceError, "cleanup removal durability is uncertain") as raised:
                    source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)
            self.assertNotIn("preserved", str(raised.exception))
            self.assertEqual([], list(runtime.glob("*.transaction")))
            self.assertEqual([], list(runtime.glob("*.cleanup")))
            self.assertEqual(
                "published",
                source.materialize(reference, runtime, archive_path=PINNED_ARCHIVE)["status"],
            )

    @unittest.skipUnless(PINNED_ARCHIVE.is_file(), "pinned archive fixture is unavailable")
    def test_verify_rejects_oversized_expected_section_with_descriptor_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            source.materialize(reference, root / ".workflow-runtime" / "reference-source", archive_path=PINNED_ARCHIVE)
            fragment = reference / "sections" / "top-level" / "preamble.tex"
            fragment.write_bytes(b"x" * 20000)
            with self.assertRaisesRegex(source.SourceError, "size differs"):
                source.verify_materialized(reference)

    def test_materialize_rejects_an_unignored_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            reference = root / "references" / "2001.04383v3"
            reference.mkdir(parents=True)
            for name in ("source-pin.json", "split-manifest.json"):
                (reference / name).write_bytes((REFERENCE_ROOT / name).read_bytes())
            with self.assertRaisesRegex(source.SourceError, "ignored reference-source"):
                source.materialize(reference, root / "runtime", archive_path=PINNED_ARCHIVE)


if __name__ == "__main__":
    unittest.main()
