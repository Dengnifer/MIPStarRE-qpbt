from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "materialize_lake_packages", ROOT / "scripts" / "materialize_lake_packages.py"
)
assert SPEC and SPEC.loader
source = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(source)


def is_transaction_stage(path: Path) -> bool:
    try:
        return Path(os.readlink(path.parent)).name == "new"
    except OSError:
        return path.parent.name == "new"


def pax_record(key: str, value: str) -> bytes:
    body = f"{key}={value}\n".encode()
    length = len(body) + 2
    while True:
        record = f"{length} ".encode() + body
        if len(record) == length:
            return record
        length = len(record)


def tar_header(
    name: str,
    kind: bytes,
    size: int = 0,
    *,
    mode: int = 0o644,
    link: str = "",
) -> bytes:
    encoded_name = name.encode()
    if len(encoded_name) > 100:
        raise ValueError("fixture path is too long")
    header = bytearray(512)
    header[: len(encoded_name)] = encoded_name
    header[100:108] = f"{mode:07o}\0".encode()
    header[108:116] = b"0000000\0"
    header[116:124] = b"0000000\0"
    header[124:136] = f"{size:011o}\0".encode()
    header[136:148] = b"00000000000\0"
    header[148:156] = b"        "
    header[156:157] = kind
    encoded_link = link.encode()
    header[157 : 157 + len(encoded_link)] = encoded_link
    header[257:263] = b"ustar\0"
    header[263:265] = b"00"
    checksum = sum(header)
    header[148:156] = f"{checksum:06o}\0 ".encode()
    return bytes(header)


def tar_member(name: str, kind: bytes, payload: bytes = b"", *, mode: int = 0o644, link: str = "") -> bytes:
    return (
        tar_header(name, kind, len(payload), mode=mode, link=link)
        + payload
        + bytes((-len(payload)) % 512)
    )


def make_archive(
    package: dict,
    *,
    extra: list[tuple[str, bytes, bytes, int, str]] | None = None,
    replace_entries: list[tuple[str, bytes, bytes, int, str]] | None = None,
    directory_mode: int = 0o775,
) -> tuple[bytes, bytes]:
    prefix = package["archive"]["exact_prefix"]
    config = package["config_file"]
    entries = replace_entries or [
        (prefix, b"5", b"", directory_mode, ""),
        (prefix + config, b"0", f"name = \"{package['name']}\"\n".encode(), 0o664, ""),
        (prefix + "lake-manifest.json", b"0", b"{}\n", 0o664, ""),
        (prefix + "src/", b"5", b"", directory_mode, ""),
        (prefix + "src/source.txt", b"0", f"{package['name']}\n".encode(), 0o664, ""),
        (prefix + "tool", b"0", b"#!/bin/sh\nexit 0\n", 0o775, ""),
        (prefix + "src/source-link", b"2", b"", 0o777, "source.txt"),
    ]
    if extra:
        entries += extra
    pax = pax_record("comment", package["revision"])
    raw = tar_member("pax_global_header", b"g", pax)
    for name, kind, payload, mode, link in entries:
        raw += tar_member(name, kind, payload, mode=mode, link=link)
    raw += bytes(1024)
    return gzip.compress(raw, mtime=0), raw


def manifest_entry(package: dict, *, inherited: bool) -> dict:
    return {
        "url": package["repository_url"],
        "type": "git",
        "subDir": None,
        "scope": package["scope"],
        "rev": package["revision"],
        "name": package["name"],
        "manifestFile": package["manifest_file"],
        "inputRev": package["input_revision"],
        "inherited": inherited,
        "configFile": package["config_file"],
    }


class LakePackageMaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.archives = Path(self.temporary.name) / "archives"
        self.archives.mkdir()
        specifications = [
            ("plausible", "leanprover-community/plausible", "lakefile.toml", False),
            ("LeanSearchClient", "leanprover-community/LeanSearchClient", "lakefile.toml", False),
            ("importGraph", "leanprover-community/import-graph", "lakefile.toml", False),
            ("proofwidgets", "leanprover-community/ProofWidgets4", "lakefile.lean", False),
            ("aesop", "leanprover-community/aesop", "lakefile.toml", False),
            ("Qq", "leanprover-community/quote4", "lakefile.toml", False),
            ("batteries", "leanprover-community/batteries", "lakefile.toml", False),
            ("Cli", "leanprover/lean4-cli", "lakefile.toml", True),
        ]
        self.packages: list[dict] = []
        self.archive_bytes: dict[str, bytes] = {}
        for index, (name, repository, config, mathlib_inherited) in enumerate(specifications, 1):
            revision = f"{index:x}" * 40
            scope = repository.split("/")[0]
            package = {
                "name": name,
                "scope": scope,
                "repository": repository,
                "repository_url": f"https://github.com/{repository}",
                "revision": revision,
                "input_revision": "main",
                "config_file": config,
                "manifest_file": "lake-manifest.json",
                "root_inherited": True,
                "mathlib_inherited": mathlib_inherited,
                "archive_url": f"https://codeload.github.com/{repository}/tar.gz/{revision}",
                "archive": {
                    "sha256": None,
                    "bytes": None,
                    "tar_sha256": None,
                    "tar_bytes": None,
                    "exact_prefix": f"{repository.split('/')[1]}-{revision}/",
                    "members": None,
                    "directories": None,
                    "regular_files": None,
                    "symlinks": None,
                    "regular_bytes": None,
                    "max_member_bytes": None,
                },
                "output": {
                    "directories": None,
                    "files": None,
                    "regular_files": None,
                    "symlinks": None,
                    "bytes": None,
                    "max_file_bytes": None,
                    "inventory_sha256": None,
                    "archive_tree_sha": None,
                    "tree_sha": None,
                    "gitlinks": [],
                },
                "pending_reason": None,
            }
            compressed, raw = make_archive(package)
            package["archive"]["tar_bytes"] = len(raw)
            facts, entries = source.inspect_archive_bytes(compressed, package)
            with tempfile.TemporaryDirectory() as tree_temporary:
                tree_root = Path(tree_temporary)
                extracted = tree_root / "source"
                source._write_entries(extracted, entries)
                tree_sha = source.compute_tree_sha(extracted, tree_root / "scratch", [])
            facts["output"]["archive_tree_sha"] = tree_sha
            facts["output"]["tree_sha"] = tree_sha
            package["archive"] = facts["archive"]
            package["output"] = facts["output"]
            self.packages.append(package)
            self.archive_bytes[name] = compressed
            (self.archives / f"{name}-{revision}.tar.gz").write_bytes(compressed)
        mathlib_entry = {
            "url": "https://github.com/leanprover-community/mathlib4",
            "type": "git",
            "subDir": None,
            "scope": "leanprover-community",
            "rev": "f" * 40,
            "name": "mathlib",
            "manifestFile": "lake-manifest.json",
            "inputRev": "v4.fixture",
            "inherited": False,
            "configFile": "lakefile.lean",
        }
        self.root_manifest = {
            "version": "1.2.0",
            "packagesDir": ".lake/packages",
            "packages": [mathlib_entry] + [manifest_entry(p, inherited=p["root_inherited"]) for p in self.packages],
            "name": "QPBT",
            "lakeDir": ".lake",
            "fixedToolchain": False,
        }
        self.mathlib_manifest = {
            "version": "1.2.0",
            "packagesDir": ".lake/packages",
            "packages": [manifest_entry(p, inherited=p["mathlib_inherited"]) for p in self.packages],
            "name": "mathlib",
            "lakeDir": ".lake",
            "fixedToolchain": True,
        }
        self.root_manifest_path = self.root / "lake-manifest.json"
        self.mathlib_manifest_path = self.root / source.MATHLIB_MANIFEST_SNAPSHOT
        self._write_json(self.root_manifest_path, self.root_manifest)
        self._write_json(self.mathlib_manifest_path, self.mathlib_manifest)
        self.pin = {
            "schema_version": source.SCHEMA_VERSION,
            "lake_manifest_version": "1.2.0",
            "packages_directory": ".lake/packages",
            "override_path": ".lake/package-overrides.json",
            "root_manifest_sha256": source._file_sha256(self.root_manifest_path),
            "mathlib_manifest_sha256": source._file_sha256(self.mathlib_manifest_path),
            "packages": self.packages,
        }
        self.pin_path = self.root / "references" / "lake-packages.json"
        self._write_json(self.pin_path, self.pin)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def _materialize(self, **kwargs: object) -> dict:
        return source.materialize(self.root, self.pin_path, self.archives, **kwargs)

    def test_replaced_lock_path_cannot_admit_concurrent_materializer(self) -> None:
        runtime = self.root / source.RUNTIME_DIRECTORY
        runtime.mkdir(parents=True)
        lock = runtime / "lock"
        first_entered = threading.Event()
        release = threading.Event()
        second_entered = threading.Event()

        def hold_lock() -> None:
            with source._locked(lock):
                first_entered.set()
                release.wait(3)

        def contend() -> None:
            with source._locked(lock):
                second_entered.set()

        first = threading.Thread(target=hold_lock)
        first.start()
        self.assertTrue(first_entered.wait(2))
        lock.rename(runtime / "old-lock")
        lock.write_text("", encoding="ascii")
        second = threading.Thread(target=contend)
        second.start()
        self.assertFalse(second_entered.wait(0.2))
        release.set()
        first.join(2)
        second.join(2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertTrue(second_entered.is_set())

    def _seed_prior_publication(self) -> Path:
        (self.root / ".lake/packages").mkdir(parents=True)
        for package in self.packages:
            destination = self.root / ".lake/packages" / package["name"]
            destination.mkdir()
            (destination / "old").write_text(package["name"])
        override = self.root / ".lake/package-overrides.json"
        override.write_text('{"old":true}\n')
        return override

    def _assert_prior_publication_restored(self, override: Path) -> None:
        for package in self.packages:
            destination = self.root / ".lake/packages" / package["name"]
            self.assertEqual(["old"], sorted(path.name for path in destination.iterdir()))
            self.assertEqual(package["name"], (destination / "old").read_text())
        self.assertEqual('{"old":true}\n', override.read_text())

    def _exercise_selected_transaction_replacement(self, component: str) -> None:
        override = self._seed_prior_publication()
        replaced = False
        replacement: Path | None = None

        def swapping_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal replaced, replacement
            old_path, new_path = Path(old), Path(new)
            if not replaced and new_path.name == "plausible":
                runtime = self.root / source.RUNTIME_DIRECTORY
                transaction = runtime / source.TRANSACTION_NAME
                backup_move = Path(os.readlink(new_path.parent)).name == "backup"
                stage_move = is_transaction_stage(old_path)
                selected: Path | None = None
                if component == "transaction" and backup_move:
                    selected = transaction
                elif component == "backup" and backup_move:
                    selected = transaction / "backup"
                elif component == "stage" and stage_move:
                    selected = transaction / "new"
                if selected is not None:
                    replacement = selected
                    selected.rename(selected.with_name(selected.name + "-selected"))
                    selected.mkdir()
                    (selected / "replacement-sentinel").write_text("untouched\n")
                    replaced = True
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "rolled back"):
            self._materialize(replace_existing=True, _replace=swapping_replace)
        self.assertTrue(replaced)
        assert replacement is not None
        self.assertEqual(
            ["replacement-sentinel"], sorted(path.name for path in replacement.iterdir())
        )
        self.assertEqual("untouched\n", (replacement / "replacement-sentinel").read_text())
        self._assert_prior_publication_restored(override)

    def test_publish_verify_override_and_file_modes(self) -> None:
        self.assertFalse((self.root / ".lake").exists())
        result = self._materialize()
        self.assertEqual("published", result["status"])
        self.assertEqual([p["name"] for p in self.packages], result["packages"])
        override = json.loads((self.root / ".lake/package-overrides.json").read_text())
        self.assertEqual(source.override_document(self.pin), override)
        self.assertEqual(8, len(override["packages"]))
        for package in self.packages:
            package_root = self.root / ".lake/packages" / package["name"]
            self.assertTrue((package_root / "tool").stat().st_mode & 0o111)
            self.assertTrue((package_root / "src/source-link").is_symlink())
            self.assertEqual("source.txt", os.readlink(package_root / "src/source-link"))
        self.assertEqual("verified", source.verify(self.root, self.pin_path)["status"])
        (self.root / ".lake/packages/plausible/src/source.txt").write_text("tampered\n")
        with self.assertRaisesRegex(source.MaterializationError, "tree differs"):
            source.verify(self.root, self.pin_path)

    def test_manifest_semantic_tampering_fails_after_checksum_is_rebound(self) -> None:
        document = copy.deepcopy(self.root_manifest)
        document["packages"][1]["rev"] = "0" * 40
        self._write_json(self.root_manifest_path, document)
        pin = copy.deepcopy(self.pin)
        pin["root_manifest_sha256"] = source._file_sha256(self.root_manifest_path)
        self._write_json(self.pin_path, pin)
        with self.assertRaisesRegex(source.MaterializationError, "entry differs"):
            source.materialize(self.root, self.pin_path, self.archives)

    def test_package_names_are_closed_safe_path_components(self) -> None:
        for unsafe_name in (
            "../escape", "/absolute", "nested/name", ".hidden", "name with space",
            "name\\component", "package$", "e" + chr(233),
        ):
            with self.subTest(name=unsafe_name):
                pin = copy.deepcopy(self.pin)
                pin["packages"][0]["name"] = unsafe_name
                self._write_json(self.pin_path, pin)
                with self.assertRaisesRegex(source.MaterializationError, "safe ASCII path component"):
                    source.load_pin(self.pin_path)
        self._write_json(self.pin_path, self.pin)

    def test_symlinked_lake_intermediates_fail_before_external_writes(self) -> None:
        cases = ("lake", "packages", "runtime", "override", "lock", "transaction")
        for case in cases:
            with self.subTest(case=case):
                lake = self.root / ".lake"
                if lake.is_symlink():
                    lake.unlink()
                elif lake.exists():
                    shutil.rmtree(lake)
                outside = Path(self.temporary.name) / f"outside-{case}"
                outside.mkdir()
                sentinel = outside / "sentinel"
                sentinel.write_text("unchanged\n")
                if case == "lake":
                    lake.symlink_to(outside, target_is_directory=True)
                else:
                    lake.mkdir()
                    if case == "packages":
                        (lake / "packages").symlink_to(outside, target_is_directory=True)
                    elif case == "runtime":
                        (lake / "lake-package-materialization").symlink_to(
                            outside, target_is_directory=True
                        )
                    elif case == "override":
                        (lake / "package-overrides.json").symlink_to(sentinel)
                    else:
                        (lake / "packages").mkdir()
                        runtime = lake / "lake-package-materialization"
                        runtime.mkdir()
                        target = sentinel if case == "lock" else outside
                        (runtime / case).symlink_to(
                            target, target_is_directory=case == "transaction"
                        )
                with self.assertRaises(source.MaterializationError):
                    self._materialize()
                self.assertEqual("unchanged\n", sentinel.read_text())
                self.assertEqual(["sentinel"], sorted(path.name for path in outside.iterdir()))

    def test_package_root_incarnation_swap_is_detected_and_confined(self) -> None:
        swapped = False

        def swapping_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal swapped
            old_path, new_path = Path(old), Path(new)
            if not swapped and new_path.name == "plausible" and is_transaction_stage(old_path):
                swapped = True
                packages = self.root / ".lake/packages"
                packages.rename(self.root / ".lake/packages-bound")
                packages.mkdir()
                (packages / "replacement-sentinel").write_text("untouched\n")
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "incarnation changed"):
            self._materialize(_replace=swapping_replace)
        replacement = self.root / ".lake/packages"
        self.assertEqual(
            ["replacement-sentinel"], sorted(path.name for path in replacement.iterdir())
        )
        self.assertEqual("untouched\n", (replacement / "replacement-sentinel").read_text())
        self.assertFalse((self.root / ".lake/packages-bound/plausible").exists())

    def test_lake_root_incarnation_swap_is_detected_and_confined(self) -> None:
        swapped = False

        def swapping_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal swapped
            old_path, new_path = Path(old), Path(new)
            if not swapped and new_path.name == "plausible" and is_transaction_stage(old_path):
                swapped = True
                lake = self.root / ".lake"
                lake.rename(self.root / ".lake-bound")
                lake.mkdir()
                (lake / "replacement-sentinel").write_text("untouched\n")
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "incarnation changed"):
            self._materialize(_replace=swapping_replace)
        replacement = self.root / ".lake"
        self.assertEqual(
            ["replacement-sentinel"], sorted(path.name for path in replacement.iterdir())
        )
        self.assertEqual("untouched\n", (replacement / "replacement-sentinel").read_text())
        self.assertFalse((self.root / ".lake-bound/packages/plausible").exists())

    def test_archive_checksum_and_git_tree_mismatches_fail(self) -> None:
        archive = self.archives / f"plausible-{self.packages[0]['revision']}.tar.gz"
        payload = bytearray(archive.read_bytes())
        payload[-1] ^= 1
        archive.write_bytes(payload)
        with self.assertRaises(source.MaterializationError):
            self._materialize()
        archive.write_bytes(self.archive_bytes["plausible"])
        pin = copy.deepcopy(self.pin)
        pin["packages"][0]["output"]["tree_sha"] = "0" * 40
        self._write_json(self.pin_path, pin)
        with self.assertRaisesRegex(source.MaterializationError, "Git tree differs"):
            self._materialize()

    def test_canonical_codeload_modes_normalize_to_exact_git_tree(self) -> None:
        package = copy.deepcopy(self.packages[0])
        compressed, raw = make_archive(package, directory_mode=0o775)
        package["archive"]["tar_bytes"] = len(raw)
        _, entries = source.inspect_archive_bytes(compressed, package)
        file_modes = {
            entry["path"]: entry["mode"] for entry in entries if entry["kind"] == "file"
        }
        self.assertEqual(0o644, file_modes[package["config_file"]])
        self.assertEqual(0o755, file_modes["tool"])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extracted = root / "source"
            source._write_entries(extracted, entries)
            self.assertEqual(
                package["output"]["tree_sha"],
                source.compute_tree_sha(extracted, root / "scratch", []),
            )

    def test_exact_gitlink_placeholder_reconstructs_tree_and_rejects_omissions(self) -> None:
        package = copy.deepcopy(self.packages[0])
        prefix = package["archive"]["exact_prefix"]
        gitlink = {
            "path": "vendor/std",
            "mode": "160000",
            "type": "commit",
            "sha": "a" * 40,
        }
        package["output"]["gitlinks"] = [gitlink]
        compressed, raw = make_archive(
            package,
            extra=[(prefix + "vendor/", b"5", b"", 0o775, ""),
                   (prefix + "vendor/std/", b"5", b"", 0o775, "")],
        )
        package["archive"]["tar_bytes"] = len(raw)
        _, entries = source.inspect_archive_bytes(compressed, package)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            extracted = root / "source"
            source._write_entries(extracted, entries)
            first = source.compute_tree_sha(extracted, root / "first", [gitlink])
            changed = dict(gitlink, sha="b" * 40)
            second = source.compute_tree_sha(extracted, root / "second", [changed])
            self.assertNotEqual(first, second)

        unpinned = copy.deepcopy(package)
        unpinned["output"]["gitlinks"] = []
        with self.assertRaisesRegex(source.MaterializationError, "unpinned empty"):
            source.inspect_archive_bytes(compressed, unpinned)

        nonempty, nonempty_raw = make_archive(
            package,
            extra=[(prefix + "vendor/", b"5", b"", 0o775, ""),
                   (prefix + "vendor/std/", b"5", b"", 0o775, ""),
                   (prefix + "vendor/std/file", b"0", b"unexpected", 0o664, "")],
        )
        package["archive"]["tar_bytes"] = len(nonempty_raw)
        with self.assertRaisesRegex(source.MaterializationError, "missing or nonempty"):
            source.inspect_archive_bytes(nonempty, package)

    def test_traversal_duplicate_special_gitlink_and_oversize_are_rejected(self) -> None:
        package = copy.deepcopy(self.packages[0])
        prefix = package["archive"]["exact_prefix"]
        attacks = [
            [(prefix + "../escape", b"0", b"x", 0o644, "")],
            [(prefix + "same", b"0", b"x", 0o644, ""), (prefix + "same", b"0", b"x", 0o644, "")],
            [(prefix + "device", b"3", b"", 0o644, "")],
            [(prefix + ".gitmodules", b"0", b"[submodule]\n", 0o644, "")],
            [(prefix + "hard", b"1", b"", 0o644, "target")],
            [
                (prefix, b"5", b"", 0o755, ""),
                (prefix + "redirect", b"2", b"", 0o777, "src"),
                (prefix + "redirect/child", b"0", b"x", 0o644, ""),
            ],
        ]
        for entries in attacks:
            with self.subTest(entries=entries):
                compressed, raw = make_archive(package, replace_entries=entries)
                candidate = copy.deepcopy(package)
                candidate["archive"]["tar_bytes"] = len(raw)
                with self.assertRaises(source.MaterializationError):
                    source.inspect_archive_bytes(compressed, candidate)
        compressed, raw = make_archive(
            package,
            replace_entries=[(prefix + "large", b"0", b"x" * 33, 0o644, "")],
        )
        candidate = copy.deepcopy(package)
        candidate["archive"]["tar_bytes"] = len(raw)
        with mock.patch.object(source, "HARD_MAX_MEMBER_BYTES", 32), self.assertRaisesRegex(
            source.MaterializationError, "hard size"
        ):
            source.inspect_archive_bytes(compressed, candidate)

    def test_unsafe_symlink_is_rejected_but_safe_symlink_text_is_preserved(self) -> None:
        package = copy.deepcopy(self.packages[0])
        prefix = package["archive"]["exact_prefix"]
        compressed, raw = make_archive(
            package,
            replace_entries=[(prefix + "escape", b"2", b"", 0o777, "../../outside")],
        )
        package["archive"]["tar_bytes"] = len(raw)
        with self.assertRaisesRegex(source.MaterializationError, "escapes"):
            source.inspect_archive_bytes(compressed, package)

    def test_publication_failure_restores_all_existing_packages_and_override(self) -> None:
        override = self._seed_prior_publication()
        failed = False

        def flaky_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal failed
            old_path, new_path = Path(old), Path(new)
            if not failed and new_path.name == "LeanSearchClient" and is_transaction_stage(old_path):
                failed = True
                raise OSError("injected publication failure")
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "rolled back"):
            self._materialize(replace_existing=True, _replace=flaky_replace)
        self._assert_prior_publication_restored(override)

    def test_transaction_instance_replacement_rolls_back_through_selected_descriptors(self) -> None:
        self._exercise_selected_transaction_replacement("transaction")

    def test_backup_instance_replacement_rolls_back_through_selected_descriptors(self) -> None:
        self._exercise_selected_transaction_replacement("backup")

    def test_stage_instance_replacement_rolls_back_through_selected_descriptors(self) -> None:
        self._exercise_selected_transaction_replacement("stage")

    def test_existing_package_substitution_restores_selected_original(self) -> None:
        override = self._seed_prior_publication()
        substituted = False

        def swapping_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal substituted
            old_path, new_path = Path(old), Path(new)
            backup_move = Path(os.readlink(new_path.parent)).name == "backup"
            if not substituted and old_path.name == "plausible" and backup_move:
                selected = self.root / ".lake/packages/plausible-selected"
                old_path.rename(selected)
                old_path.mkdir()
                (old_path / "replacement-sentinel").write_text("untouched\n")
                substituted = True
            if new_path.name == "LeanSearchClient" and is_transaction_stage(old_path):
                raise OSError("injected publication failure")
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "rolled back"):
            self._materialize(replace_existing=True, _replace=swapping_replace)
        self.assertTrue(substituted)
        self._assert_prior_publication_restored(override)
        self.assertFalse((self.root / ".lake/packages/plausible-selected").exists())
        rejected = list(
            (self.root / source.RUNTIME_DIRECTORY).glob("rejected-backup-package-plausible-*")
        )
        self.assertEqual(1, len(rejected))
        self.assertEqual(
            ["replacement-sentinel"], sorted(path.name for path in rejected[0].iterdir())
        )
        self.assertEqual("untouched\n", (rejected[0] / "replacement-sentinel").read_text())

    def test_override_substitution_restores_selected_original(self) -> None:
        override = self._seed_prior_publication()
        substituted = False

        def swapping_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal substituted
            old_path, new_path = Path(old), Path(new)
            if old_path.name == "package-overrides.json" and new_path.name == "override.json":
                selected = self.root / ".lake/package-overrides-selected.json"
                old_path.rename(selected)
                old_path.write_text("replacement\n")
                os.replace(old, new)
                substituted = True
                raise OSError("injected override failure")
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "rolled back"):
            self._materialize(replace_existing=True, _replace=swapping_replace)
        self.assertTrue(substituted)
        self._assert_prior_publication_restored(override)
        self.assertFalse((self.root / ".lake/package-overrides-selected.json").exists())
        rejected = list(
            (self.root / source.RUNTIME_DIRECTORY).glob("rejected-backup-override-*")
        )
        self.assertEqual(1, len(rejected))
        self.assertEqual("replacement\n", rejected[0].read_text())

    def test_staged_package_substitution_never_publishes_replacement(self) -> None:
        substituted = False

        def swapping_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal substituted
            old_path, new_path = Path(old), Path(new)
            if (
                not substituted
                and old_path.name == new_path.name == "plausible"
                and is_transaction_stage(old_path)
            ):
                old_path.rename(old_path.with_name("plausible-selected"))
                old_path.mkdir()
                (old_path / "replacement-sentinel").write_text("untouched\n")
                substituted = True
            os.replace(old, new)

        with self.assertRaisesRegex(source.MaterializationError, "rolled back"):
            self._materialize(_replace=swapping_replace)
        self.assertTrue(substituted)
        self.assertFalse((self.root / ".lake/packages/plausible").exists())
        rejected = list(
            (self.root / source.RUNTIME_DIRECTORY).glob("rejected-package-plausible-*")
        )
        self.assertEqual(1, len(rejected))
        self.assertEqual(
            ["replacement-sentinel"], sorted(path.name for path in rejected[0].iterdir())
        )
        self.assertEqual("untouched\n", (rejected[0] / "replacement-sentinel").read_text())

    def test_interrupted_publication_is_recovered_before_retry(self) -> None:
        (self.root / ".lake/packages").mkdir(parents=True)
        for package in self.packages:
            destination = self.root / ".lake/packages" / package["name"]
            destination.mkdir()
            (destination / "old").write_text(package["name"])
        override = self.root / ".lake/package-overrides.json"
        override.write_text('{"old":true}\n')
        interrupted = False

        def interrupting_replace(old: os.PathLike[str] | str, new: os.PathLike[str] | str) -> None:
            nonlocal interrupted
            old_path, new_path = Path(old), Path(new)
            if not interrupted and new_path.name == "LeanSearchClient" and is_transaction_stage(old_path):
                interrupted = True
                raise KeyboardInterrupt("injected process interruption")
            os.replace(old, new)

        with self.assertRaisesRegex(KeyboardInterrupt, "process interruption"):
            self._materialize(replace_existing=True, _replace=interrupting_replace)
        transaction = self.root / source.RUNTIME_DIRECTORY / source.TRANSACTION_NAME
        self.assertTrue(transaction.is_dir())
        self.assertFalse((self.root / ".lake/packages/plausible/old").exists())

        self.assertEqual("published", self._materialize(replace_existing=True)["status"])
        self.assertFalse(transaction.exists())
        self.assertEqual("verified", source.verify(self.root, self.pin_path)["status"])
        for package in self.packages:
            self.assertFalse((self.root / ".lake/packages" / package["name"] / "old").exists())

    def test_pending_pin_fails_closed_and_production_pin_is_complete(self) -> None:
        pending = copy.deepcopy(self.pin)
        for package in pending["packages"]:
            package["archive"] = {
                key: value if key == "exact_prefix" else None
                for key, value in package["archive"].items()
            }
            package["output"] = {key: None for key in package["output"]}
            package["pending_reason"] = "Facts unavailable in test."
        self._write_json(self.pin_path, pending)
        with self.assertRaisesRegex(source.MaterializationError, "pending"):
            source.load_pin(self.pin_path)
        pending = source.load_pin(self.pin_path, allow_pending=True)
        self.assertEqual(8, len(pending["packages"]))
        production = source.load_pin(ROOT / "references/lake-packages.json")
        self.assertEqual(8, len(production["packages"]))
        source.validate_manifests(ROOT, production)

    def test_transport_is_direct_argv_bounded_and_contains_no_credentials(self) -> None:
        download = Path(self.temporary.name) / "downloads"
        calls: list[list[str]] = []

        def runner(argv: list[str], timeout: float) -> None:
            calls.append(list(argv))
            url = argv[3]
            output = Path(argv[4])
            package = next(package for package in self.packages if package["archive_url"] == url)
            output.write_bytes(self.archive_bytes[package["name"]])
            self.assertEqual(17.0, timeout)

        template = ["transport", "--config", "auth.cfg", "{url}", "{output}", "{max_bytes}", "{timeout_seconds}"]
        outputs = source.fetch_archives(
            self.root, self.pin_path, download, template, timeout_seconds=17, runner=runner
        )
        self.assertEqual(8, len(outputs))
        self.assertEqual(8, len(calls))
        self.assertFalse(
            any(
                "token" in token.lower() or "bearer" in token.lower()
                for call in calls for token in call
            )
        )
        with self.assertRaisesRegex(source.MaterializationError, "credentials"):
            source._safe_transport_argv(
                ["curl", "Authorization: Bearer secret", "{url}", "{output}"],
                self.packages[0], download / "bad", 1,
            )
        process = mock.Mock(returncode=0)
        process.wait.return_value = None
        with mock.patch.object(source.subprocess, "Popen", return_value=process) as popen:
            source._run_bounded_argv(["transport", "arg"], 1, cwd=self.root)
        self.assertIs(popen.call_args.kwargs["shell"], False)
        self.assertEqual(["transport", "arg"], popen.call_args.args[0])
        self.assertEqual((), popen.call_args.kwargs["pass_fds"])

        with source._bound_existing_directory(download, "test archive output") as bound:
            output = bound.path / "descriptor-output"
            source._run_bounded_argv(
                [
                    sys.executable,
                    "-c",
                    "import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'bound\\n')",
                    str(output),
                ],
                2,
                cwd=self.root,
                pass_fds=(bound.descriptor,),
            )
            bound.assert_current()
        self.assertEqual(b"bound\n", (download / "descriptor-output").read_bytes())

    def test_transport_timeout_waits_for_descendant_process_group(self) -> None:
        descendant_pid_path = Path(self.temporary.name) / "descendant.pid"
        program = """
import os, pathlib, signal, sys, time
child = os.fork()
if child == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))
    time.sleep(0.6)
    os._exit(0)
while True:
    time.sleep(1)
"""
        started = time.monotonic()
        with self.assertRaisesRegex(source.MaterializationError, "exceeded its timeout"):
            source._run_bounded_argv(
                [sys.executable, "-c", program, str(descendant_pid_path)],
                0.2,
                cwd=self.root,
            )
        elapsed = time.monotonic() - started
        self.assertGreaterEqual(elapsed, 0.5)
        descendant_pid = int(descendant_pid_path.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(descendant_pid, 0)

    def test_transport_timeout_escalates_a_remaining_process_group(self) -> None:
        process = mock.Mock(pid=4242)
        process.wait.side_effect = source.subprocess.TimeoutExpired(["transport"], 1)
        process.poll.return_value = 0
        group_alive = True
        signals: list[int] = []

        def kill_group(_pid: int, sent_signal: int) -> None:
            nonlocal group_alive
            if sent_signal == 0:
                if not group_alive:
                    raise ProcessLookupError
                return
            signals.append(sent_signal)
            if sent_signal == source.signal.SIGKILL:
                group_alive = False

        with (
            mock.patch.object(source.subprocess, "Popen", return_value=process),
            mock.patch.object(source.os, "killpg", side_effect=kill_group),
            mock.patch.object(source.time, "monotonic", side_effect=[0.0, 3.0, 4.0]),
            self.assertRaisesRegex(source.MaterializationError, "exceeded its timeout"),
        ):
            source._run_bounded_argv(["transport"], 1, cwd=self.root)
        self.assertEqual([source.signal.SIGTERM, source.signal.SIGKILL], signals)

    def test_duplicate_pin_key_and_incomplete_override_are_rejected(self) -> None:
        duplicate = self.pin_path.read_text().replace(
            '"schema_version": 2,', '"schema_version": 2, "schema_version": 2,', 1
        )
        self.pin_path.write_text(duplicate)
        with self.assertRaisesRegex(source.MaterializationError, "duplicate JSON key"):
            source.load_pin(self.pin_path)
        self._write_json(self.pin_path, self.pin)
        self._materialize()
        override = self.root / ".lake/package-overrides.json"
        document = json.loads(override.read_text())
        document["packages"].pop()
        self._write_json(override, document)
        with self.assertRaisesRegex(source.MaterializationError, "override differs"):
            source.verify(self.root, self.pin_path)


if __name__ == "__main__":
    unittest.main()
