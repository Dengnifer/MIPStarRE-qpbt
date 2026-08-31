from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import materialize_mipstarre as source  # noqa: E402


COMMIT = "1" * 40
PREFIX = f"MIPStarRE-{COMMIT}/"


def pax_record(key: str, value: str) -> bytes:
    body = f" {key}={value}\n".encode()
    length = len(body) + 1
    while True:
        record = str(length).encode() + body
        if len(record) == length:
            return record
        length = len(record)


def tar_header(name: str, kind: bytes, size: int = 0, link: str = "") -> bytes:
    header = bytearray(512)

    def field(start: int, width: int, value: bytes) -> None:
        if len(value) > width:
            raise ValueError(value)
        header[start : start + len(value)] = value

    field(0, 100, name.encode())
    field(100, 8, b"0000755\0")
    field(108, 8, b"0000000\0")
    field(116, 8, b"0000000\0")
    field(124, 12, f"{size:011o}\0".encode())
    field(136, 12, b"00000000000\0")
    field(148, 8, b"        ")
    field(156, 1, kind)
    field(157, 100, link.encode())
    field(257, 6, b"ustar\0")
    field(263, 2, b"00")
    checksum = sum(header)
    field(148, 8, f"{checksum:06o}\0 ".encode())
    return bytes(header)


def make_archive(entries: list[tuple[str, bytes, bytes, str]] | None = None) -> tuple[bytes, bytes]:
    if entries is None:
        entries = [
            (PREFIX, b"5", b"", ""),
            (PREFIX + "MIPStarRE/", b"5", b"", ""),
            (PREFIX + "MIPStarRE/Quantum/", b"5", b"", ""),
            (PREFIX + "MIPStarRE/Quantum/Measurement.lean", b"0", b"def pinned := 1\n", ""),
        ]
    pax = pax_record("comment", COMMIT)
    blocks = [tar_header("pax_global_header", b"g", len(pax)), pax]
    blocks.append(bytes((-len(pax)) % 512))
    for name, kind, payload, link in entries:
        blocks.extend((tar_header(name, kind, len(payload), link), payload, bytes((-len(payload)) % 512)))
    blocks.append(bytes(1024))
    raw = b"".join(blocks)
    return gzip.compress(raw, mtime=0), raw


class MaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        (self.root / "references").mkdir()
        (self.root / "lean-toolchain").write_text("leanprover/lean4:v4.32.0\n", encoding="ascii")
        (self.root / "lake-manifest.json").write_text(
            json.dumps(
                {
                    "packages": [
                        {"name": "mathlib", "inputRev": "v4.32.0", "rev": "2" * 40}
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.compressed, self.raw = make_archive()
        facts, _, files = source.inspect_archive_bytes(
            self.compressed,
            commit=COMMIT,
            exact_prefix=PREFIX,
            expected_tar_bytes=len(self.raw),
        )
        foundation = dict(files)["Quantum/Measurement.lean"]
        self.pin = {
            "schema_version": 1,
            "source": {
                "id": "test",
                "repository": "owner/repo",
                "repository_url": "https://example.invalid/owner/repo",
                "commit": COMMIT,
                "archive_url": "https://example.invalid/archive",
                "acquisition_evidence": "test fixture",
            },
            "rights": {
                "license_file": None,
                "redistribution_permission": "not-established",
                "policy": "local verification only",
            },
            "archive": {
                "format": "gzip-ustar-with-exact-global-pax-comment",
                **facts["archive"],
                "exact_prefix": PREFIX,
                "global_pax_comment": COMMIT,
            },
            "output": {
                "path": "MIPStarRE",
                "archive_subtree": "MIPStarRE/",
                "reserved_authored_subtree": "QPBT/",
                **facts["output"],
            },
            "lean_pins": {
                "toolchain": "leanprover/lean4:v4.32.0",
                "mathlib_input_revision": "v4.32.0",
                "mathlib_commit": "2" * 40,
            },
            "foundations": [
                {
                    "module": "MIPStarRE.Quantum.Measurement",
                    "path": "MIPStarRE/Quantum/Measurement.lean",
                    "sha256": hashlib.sha256(foundation).hexdigest(),
                    "purpose": "test",
                }
            ],
        }
        self.pin_path = self.root / "references" / "mipstarre-upstream.json"
        self.pin_path.write_text(json.dumps(self.pin), encoding="utf-8")
        self.archive = Path(self.temporary.name) / "source.tar.gz"
        self.archive.write_bytes(self.compressed)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def inspect_bytes(self, compressed: bytes, raw: bytes) -> None:
        source.inspect_archive_bytes(
            compressed,
            commit=COMMIT,
            exact_prefix=PREFIX,
            expected_tar_bytes=len(raw),
        )

    def test_publish_verify_and_cached_rerun_preserve_authored_tree(self) -> None:
        authored = self.root / "MIPStarRE" / "QPBT"
        authored.mkdir(parents=True)
        (authored / "Owned.lean").write_text("def owned := true\n", encoding="utf-8")
        (self.root / "MIPStarRE" / "untrusted").write_text("replace me", encoding="utf-8")

        published = source.materialize(
            self.root, self.pin_path, self.archive, replace_existing=True
        )
        self.assertEqual("published", published["status"])
        self.assertEqual("def owned := true\n", (authored / "Owned.lean").read_text())
        self.assertFalse((self.root / "MIPStarRE" / "untrusted").exists())
        self.assertEqual(
            "cached", source.materialize(self.root, self.pin_path, self.archive)["status"]
        )
        self.assertEqual("verified", source.verify_materialized(self.root, self.pin)["status"])

    def test_raw_traversal_duplicate_and_reserved_namespace_are_rejected(self) -> None:
        attacks = [
            [(PREFIX, b"5", b"", ""), (PREFIX + "MIPStarRE/../escape", b"0", b"x", "")],
            [(PREFIX, b"5", b"", ""), (PREFIX, b"5", b"", "")],
            [(PREFIX, b"5", b"", ""), (PREFIX + "MIPStarRE/QPBT/", b"5", b"", "")],
        ]
        for entries in attacks:
            with self.subTest(entries=entries):
                compressed, raw = make_archive(entries)
                with self.assertRaises(source.MaterializationError):
                    self.inspect_bytes(compressed, raw)

    def test_links_devices_and_tar_extensions_are_rejected(self) -> None:
        for kind in (b"1", b"2", b"3", b"4", b"6", b"x", b"L", b"K"):
            with self.subTest(kind=kind):
                compressed, raw = make_archive([(PREFIX + "bad", kind, b"", "target")])
                with self.assertRaisesRegex(source.MaterializationError, "forbidden"):
                    self.inspect_bytes(compressed, raw)

    def test_wrong_prefix_checksum_and_concatenated_gzip_are_rejected(self) -> None:
        wrong, wrong_raw = make_archive([("other/file", b"0", b"x", "")])
        with self.assertRaisesRegex(source.MaterializationError, "outside exact prefix"):
            self.inspect_bytes(wrong, wrong_raw)

        damaged = bytearray(self.raw)
        damaged[0] ^= 1
        with self.assertRaisesRegex(source.MaterializationError, "checksum"):
            self.inspect_bytes(gzip.compress(bytes(damaged), mtime=0), bytes(damaged))
        with self.assertRaisesRegex(source.MaterializationError, "concatenated|trailing"):
            self.inspect_bytes(self.compressed + gzip.compress(b"extra", mtime=0), self.raw)

    def test_decompression_bound_and_truncation_are_rejected(self) -> None:
        with self.assertRaisesRegex(source.MaterializationError, "exceeds"):
            source._decompress_gzip_exact(gzip.compress(b"A" * 1024, mtime=0), 10)
        with self.assertRaisesRegex(source.MaterializationError, "ended|truncated"):
            source._decompress_gzip_exact(self.compressed[:-4], len(self.raw))

        oversized = b"x" * (source.HARD_MAX_MEMBER_BYTES + 1)
        raw = (
            tar_header("pax_global_header", b"g", len(oversized))
            + oversized
            + bytes((-len(oversized)) % 512)
            + bytes(1024)
        )
        with self.assertRaisesRegex(source.MaterializationError, "member exceeds"):
            self.inspect_bytes(gzip.compress(raw, mtime=0), raw)

    def test_archive_symlink_and_pin_mismatch_preserve_destination(self) -> None:
        destination = self.root / "MIPStarRE"
        destination.mkdir()
        (destination / "keep").write_text("original", encoding="utf-8")
        link = Path(self.temporary.name) / "archive-link"
        link.symlink_to(self.archive)
        with self.assertRaises(source.MaterializationError):
            source.materialize(self.root, self.pin_path, link, replace_existing=True)
        self.assertEqual("original", (destination / "keep").read_text())

        self.archive.write_bytes(self.compressed[:-1] + bytes([self.compressed[-1] ^ 1]))
        with self.assertRaises(source.MaterializationError):
            source.materialize(self.root, self.pin_path, self.archive, replace_existing=True)
        self.assertEqual("original", (destination / "keep").read_text())

    def test_runtime_parent_symlink_is_rejected_before_transaction_writes(self) -> None:
        redirected = Path(self.temporary.name) / "redirected-runtime"
        redirected.mkdir()
        (self.root / ".workflow-runtime").symlink_to(redirected, target_is_directory=True)
        with self.assertRaisesRegex(source.MaterializationError, "symlink component"):
            source.materialize(self.root, self.pin_path, self.archive)
        self.assertEqual([], list(redirected.iterdir()))

    def test_post_publication_failure_rolls_back_existing_tree(self) -> None:
        destination = self.root / "MIPStarRE"
        destination.mkdir()
        (destination / "keep").write_text("original", encoding="utf-8")
        real_verify = source.verify_materialized
        calls = 0

        def fail_after_publish(repo: Path, pin: dict[str, object]) -> dict[str, object]:
            nonlocal calls
            calls += 1
            if calls <= 2:
                raise source.MaterializationError("injected verification failure")
            return real_verify(repo, pin)

        with mock.patch.object(source, "verify_materialized", side_effect=fail_after_publish):
            with self.assertRaisesRegex(source.MaterializationError, "injected"):
                source.materialize(self.root, self.pin_path, self.archive, replace_existing=True)
        self.assertEqual("original", (destination / "keep").read_text())
        runtime = self.root / ".workflow-runtime" / "mipstarre-materialization"
        self.assertFalse((runtime / "MIPStarRE.transaction").exists())

    def test_rollback_retains_transaction_if_expected_backup_is_missing(self) -> None:
        transaction = self.root / "transaction"
        transaction.mkdir()
        errors = source._rollback(transaction, self.root / "MIPStarRE", True)
        self.assertTrue(errors)
        self.assertTrue(transaction.exists())

        linked_transaction = self.root / "linked-transaction"
        (linked_transaction / "backup").mkdir(parents=True)
        (linked_transaction / "backup" / "MIPStarRE").symlink_to(self.root)
        linked_errors = source._rollback(
            linked_transaction, self.root / "missing-destination", True
        )
        self.assertTrue(any("not a real directory" in error for error in linked_errors))
        self.assertTrue(linked_transaction.exists())

    def test_stale_transaction_restores_then_replaces_deterministically(self) -> None:
        runtime = self.root / ".workflow-runtime" / "mipstarre-materialization"
        transaction = runtime / "MIPStarRE.transaction"
        backup = transaction / "backup" / "MIPStarRE" / "QPBT"
        backup.mkdir(parents=True)
        (backup / "Owned.lean").write_text("def recovered := true\n", encoding="utf-8")
        (transaction / "stage" / "MIPStarRE").mkdir(parents=True)
        (transaction / "transaction.json").write_bytes(
            source._transaction_document(self.root / "MIPStarRE", True)
        )

        result = source.materialize(
            self.root, self.pin_path, self.archive, replace_existing=True
        )
        self.assertEqual("published", result["status"])
        self.assertEqual(
            "def recovered := true\n",
            (self.root / "MIPStarRE" / "QPBT" / "Owned.lean").read_text(),
        )
        self.assertFalse(transaction.exists())

    def test_verify_rejects_symlink_inside_authored_tree(self) -> None:
        source.materialize(self.root, self.pin_path, self.archive)
        authored = self.root / "MIPStarRE" / "QPBT"
        authored.mkdir()
        (authored / "escape").symlink_to(self.root / "lean-toolchain")
        with self.assertRaises(source.MaterializationError):
            source.verify_materialized(self.root, self.pin)


if __name__ == "__main__":
    unittest.main()
