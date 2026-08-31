from __future__ import annotations

from contextlib import redirect_stderr
import fcntl
import hashlib
import io
import json
import multiprocessing
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import hot_main_cache as cache_module  # noqa: E402


TEST_RECIPE = cache_module.BuildRecipe.for_testing(
    dependency_command=("fake", "deps"),
    build_command=("fake", "build"),
)

MATERIALIZING_TEST_RECIPE = cache_module.BuildRecipe.for_testing(
    materialize_command=("fake", "materialize"),
    dependency_command=("fake", "deps"),
    build_command=("fake", "build"),
    additional_identity_files=(
        "references/mipstarre-upstream.json",
        "scripts/materialize_mipstarre.py",
    ),
    recipe_id="test-fake-materializing-build",
)

PACKAGE_MATERIALIZING_TEST_RECIPE = cache_module.BuildRecipe.for_testing(
    package_materialize_command=("fake", "package-materialize"),
    package_verify_command=("fake", "package-verify"),
    dependency_command=("fake", "deps"),
    build_command=("fake", "build"),
    additional_identity_files=(
        "references/lake-packages.json",
        "references/mathlib-lake-manifest.json",
        "scripts/materialize_lake_packages.py",
    ),
    recipe_id="test-fake-package-materializing-build",
)


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        text=True,
        capture_output=True,
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def initialize_repository(root: Path) -> str:
    root.mkdir(parents=True)
    run_git(root, "init", "-b", "main")
    run_git(root, "config", "user.name", "Workflow Test")
    run_git(root, "config", "user.email", "workflow@example.invalid")
    (root / "lean-toolchain").write_text("leanprover/lean4:v4.19.0\n", encoding="utf-8")
    (root / "lakefile.toml").write_text("name = \"QPBT\"\n", encoding="utf-8")
    (root / "lake-manifest.json").write_text("{\"version\": 1}\n", encoding="utf-8")
    (root / "MIPStarRE").mkdir()
    (root / "MIPStarRE" / "Basic.lean").write_text("def answer := 42\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        ".lake/\nMIPStarRE/materialized-marker\n", encoding="utf-8"
    )
    (root / "references").mkdir()
    (root / "references" / "mipstarre-upstream.json").write_text(
        json.dumps(
            {
                "source": {"commit": "1" * 40},
                "output": {
                    "inventory_sha256": hashlib.sha256(b"materialized\n").hexdigest(),
                    "files": 1,
                    "bytes": len(b"materialized\n"),
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "scripts").mkdir()
    (root / "scripts" / "materialize_mipstarre.py").write_text("# test materializer\n", encoding="utf-8")
    (root / "references" / "lake-packages.json").write_text("{}\n", encoding="ascii")
    (root / "references" / "mathlib-lake-manifest.json").write_text(
        "{\"name\":\"mathlib\"}\n", encoding="ascii"
    )
    (root / "scripts" / "materialize_lake_packages.py").write_text(
        "# test package materializer\n", encoding="ascii"
    )
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "initial")
    return run_git(root, "rev-parse", "HEAD")


def fake_success(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
    if list(command) == ["fake", "materialize"]:
        (project / "MIPStarRE" / "materialized-marker").write_text(
            "materialized\n", encoding="utf-8"
        )
    elif list(command) == ["fake", "package-materialize"]:
        if not (project / "references" / "mathlib-lake-manifest.json").is_file():
            return 8
        if (project / ".lake" / "packages" / "mathlib" / "lake-manifest.json").exists():
            return 8
        packages = project / ".lake" / "packages" / "fixture"
        packages.mkdir(parents=True, exist_ok=True)
        (packages / "marker").write_text("package\n", encoding="ascii")
        (project / ".lake" / "package-overrides.json").write_text("{}\n", encoding="ascii")
    elif list(command) == ["fake", "package-verify"]:
        marker = project / ".lake" / "packages" / "fixture" / "marker"
        if not marker.is_file() or marker.read_text(encoding="ascii") != "package\n":
            return 9
    elif list(command) == ["fake", "deps"]:
        package = project / ".lake" / "packages" / "mathlib"
        package.mkdir(parents=True, exist_ok=True)
        (package / "marker").write_text("dependency\n", encoding="utf-8")
    elif list(command) == ["fake", "build"]:
        build = project / ".lake" / "build"
        build.mkdir(parents=True, exist_ok=True)
        (build / "QPBT.olean").write_text("compiled-main\n", encoding="utf-8")
    return 0


def fake_source_verifier(project: Path) -> dict[str, object]:
    marker = (project / "MIPStarRE" / "materialized-marker").read_bytes()
    if marker != b"materialized\n":
        raise cache_module.CacheError("fake foundation source verification failed")
    pin_sha256 = cache_module.sha256_file(project / "references" / "mipstarre-upstream.json")
    return {
        "schema_version": cache_module.SOURCE_EVIDENCE_SCHEMA_VERSION,
        "pin_sha256": pin_sha256,
        "source_commit": "1" * 40,
        "inventory_sha256": hashlib.sha256(marker).hexdigest(),
        "files": 1,
        "bytes": len(marker),
        "authored_qpbt_files": 0,
        "authored_qpbt_bytes": 0,
        "authored_qpbt_sha256": hashlib.sha256().hexdigest(),
    }


def contention_worker(repo: str, runtime: str, counter: str) -> None:
    manager = cache_module.HotMainCache(
        Path(repo),
        Path(repo),
        Path(runtime),
        _test_recipe=MATERIALIZING_TEST_RECIPE,
    )

    def callback(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
        if list(command) in (["fake", "materialize"], ["fake", "build"]):
            with Path(counter).open("a+", encoding="utf-8") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                stream.write(f"{command[1]}\n")
                stream.flush()
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            time.sleep(0.25)
        return fake_success(project, command, log_path)

    manager.warm(
        _test_command_callback=callback,
        _test_source_verifier=fake_source_verifier,
    )


def linked_worktree_contention_worker(worktree: str, counter: str) -> None:
    """Warm from a linked checkout using its omitted-runtime default."""

    project = Path(worktree)
    runtime = cache_module.default_runtime_dir(project)
    manager = cache_module.HotMainCache(
        project,
        project,
        runtime,
        _test_recipe=TEST_RECIPE,
    )

    def callback(
        callback_project: Path,
        command: list[str] | tuple[str, ...],
        log_path: Path,
    ) -> int:
        if list(command) == ["fake", "build"]:
            with Path(counter).open("a+", encoding="utf-8") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                stream.write("build\n")
                stream.flush()
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            time.sleep(0.25)
        return fake_success(callback_project, command, log_path)

    manager.warm(_test_command_callback=callback)


class HotMainCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.commit = initialize_repository(self.repo)
        self.runtime = self.base / "runtime"

    def tearDown(self) -> None:
        if self.base.exists():
            cache_module.make_owner_writable(self.base)
        self.temporary.cleanup()

    def manager(
        self,
        *,
        runtime: Path | None = None,
        recipe: cache_module.BuildRecipe = TEST_RECIPE,
    ) -> cache_module.HotMainCache:
        return cache_module.HotMainCache(
            self.repo,
            self.repo,
            runtime or self.runtime,
            _test_recipe=recipe,
        )

    def issue_worktree(self, name: str = "issue-worktree") -> Path:
        target = self.base / name
        run_git(self.repo, "worktree", "add", "--detach", str(target), self.commit)
        return target

    def test_identity_comes_from_exact_main_not_dirty_worktree(self) -> None:
        first = self.manager().identity
        (self.repo / "lakefile.toml").write_text("dirty feature content\n", encoding="utf-8")
        second = self.manager().identity
        self.assertEqual(first.cache_key, second.cache_key)
        self.assertEqual(self.commit, second.main_commit)

    def test_warm_hits_then_seed_is_private_and_writable(self) -> None:
        manager = self.manager()
        calls: list[list[str]] = []

        def callback(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            calls.append(list(command))
            return fake_success(project, command, log_path)

        built = manager.warm(_test_command_callback=callback)
        self.assertEqual("built", built["result"])
        self.assertTrue(manager.is_ready())
        hit = manager.warm(_test_command_callback=callback)
        self.assertEqual("hit", hit["result"])
        self.assertEqual([["fake", "deps"], ["fake", "build"]], calls)

        target = self.issue_worktree()
        seeded = manager.seed(target)
        self.assertEqual("seeded", seeded["result"])
        cached_file = manager.build_dir / "QPBT.olean"
        target_file = target / ".lake" / "build" / "QPBT.olean"
        self.assertNotEqual(cached_file.stat().st_ino, target_file.stat().st_ino)
        self.assertTrue(target_file.stat().st_mode & stat.S_IWUSR)
        target_file.write_text("issue change\n", encoding="utf-8")
        self.assertEqual("compiled-main\n", cached_file.read_text(encoding="utf-8"))
        self.assertTrue((target / ".lake" / "packages" / "mathlib" / "marker").is_file())

    def test_elected_builder_materializes_once_and_identity_binds_materializer(self) -> None:
        manager = self.manager(recipe=MATERIALIZING_TEST_RECIPE)
        calls: list[list[str]] = []

        def callback(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            calls.append(list(command))
            return fake_success(project, command, log_path)

        built = manager.warm(
            _test_command_callback=callback,
            _test_source_verifier=fake_source_verifier,
        )
        self.assertEqual("built", built["result"])
        self.assertEqual(
            [["fake", "materialize"], ["fake", "deps"], ["fake", "build"]],
            calls,
        )
        self.assertEqual(
            "hit",
            manager.warm(
                _test_command_callback=callback,
                _test_source_verifier=fake_source_verifier,
            )["result"],
        )
        self.assertEqual(3, len(calls))
        self.assertIn("references/mipstarre-upstream.json", manager.identity.inputs)
        self.assertIn("scripts/materialize_mipstarre.py", manager.identity.inputs)
        self.assertNotIn(str(self.base), json.dumps(manager.identity.recipe))
        self.assertEqual("1" * 40, manager.identity.source_contract["source_commit"])
        self.assertEqual(0, manager.identity.source_contract["authored_qpbt_files"])
        manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual("1" * 40, manifest["source_evidence"]["source_commit"])
        self.assertEqual(1, manifest["source_evidence"]["files"])
        self.assertEqual(13, manifest["source_evidence"]["bytes"])

        original_key = manager.identity.cache_key
        (self.repo / "scripts" / "materialize_mipstarre.py").write_text(
            "# dirty materializer does not affect committed identity\n", encoding="utf-8"
        )
        self.assertEqual(
            original_key,
            self.manager(recipe=MATERIALIZING_TEST_RECIPE).identity.cache_key,
        )
        run_git(self.repo, "add", "scripts/materialize_mipstarre.py")
        run_git(self.repo, "commit", "-m", "change materializer")
        self.assertNotEqual(
            original_key,
            self.manager(recipe=MATERIALIZING_TEST_RECIPE).identity.cache_key,
        )

    def test_packages_are_identity_bound_materialized_and_verified_before_lake_steps(self) -> None:
        manager = self.manager(recipe=PACKAGE_MATERIALIZING_TEST_RECIPE)
        calls: list[list[str]] = []

        def callback(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            calls.append(list(command))
            return fake_success(project, command, log_path)

        self.assertEqual("built", manager.warm(_test_command_callback=callback)["result"])
        self.assertEqual(
            [
                ["fake", "package-materialize"],
                ["fake", "package-verify"],
                ["fake", "deps"],
                ["fake", "build"],
                ["fake", "package-verify"],
            ],
            calls,
        )
        self.assertIn("references/lake-packages.json", manager.identity.inputs)
        self.assertIn("references/mathlib-lake-manifest.json", manager.identity.inputs)
        self.assertIn("scripts/materialize_lake_packages.py", manager.identity.inputs)
        manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(manifest["package_materialize_seconds"], 0)
        self.assertGreaterEqual(manifest["package_verify_seconds"], 0)

    def test_warm_rejects_post_build_package_drift(self) -> None:
        manager = self.manager(
            runtime=self.base / "runtime-package-drift",
            recipe=PACKAGE_MATERIALIZING_TEST_RECIPE,
        )

        def mutate_package(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            result = fake_success(project, command, log_path)
            if list(command) == ["fake", "build"]:
                (project / ".lake" / "packages" / "fixture" / "marker").write_text(
                    "tampered\n", encoding="ascii"
                )
            return result

        with self.assertRaisesRegex(
            cache_module.CacheError, "Lake package verification command failed"
        ):
            manager.warm(_test_command_callback=mutate_package)
        self.assertFalse(manager.is_ready())
        failures = list((manager.runtime_dir / "cache" / "failures").iterdir())
        self.assertEqual(1, len(failures))
        failure = json.loads((failures[0] / "failure.json").read_text(encoding="utf-8"))
        self.assertIn("Lake package verification command failed", failure["error"])

    def test_canonical_lake_commands_require_override_and_reject_updates(self) -> None:
        canonical = cache_module.CANONICAL_BUILD_RECIPE
        for command in (canonical.dependency_command, canonical.build_command):
            self.assertEqual(1, command.count(cache_module.LAKE_OVERRIDE_ARGUMENT))
            self.assertNotIn("update", command)
            self.assertNotIn("--update", command)
        self.assertEqual(
            {
                "references/lake-packages.json",
                "references/mathlib-lake-manifest.json",
                "scripts/materialize_lake_packages.py",
            },
            set(canonical.additional_identity_files)
            & {
                "references/lake-packages.json",
                "references/mathlib-lake-manifest.json",
                "scripts/materialize_lake_packages.py",
            },
        )
        valid = ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "build")
        invalid_commands = (
            ("lake", "build"),
            ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "update"),
            ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "build", "--update"),
            ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "build", "-U"),
            ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "build", "-qU"),
            ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "build", "-Uq"),
            ("lake", cache_module.LAKE_OVERRIDE_ARGUMENT, "--packages=other.json", "build"),
        )
        for invalid in invalid_commands:
            with self.subTest(command=invalid), self.assertRaisesRegex(ValueError, "Lake"):
                cache_module.BuildRecipe.for_testing(
                    dependency_command=invalid,
                    build_command=valid,
                )

    def test_warm_rejects_post_build_materialized_source_drift(self) -> None:
        manager = self.manager(
            runtime=self.base / "runtime-materialized-drift",
            recipe=MATERIALIZING_TEST_RECIPE,
        )

        def mutate_source(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            result = fake_success(project, command, log_path)
            if list(command) == ["fake", "build"]:
                with log_path.open("ab") as log:
                    log.write(b"build completed before source verification\n")
                (project / "MIPStarRE" / "materialized-marker").write_text(
                    "tampered\n", encoding="utf-8"
                )
            return result

        with self.assertRaisesRegex(cache_module.CacheError, "source verification failed"):
            manager.warm(
                _test_command_callback=mutate_source,
                _test_source_verifier=fake_source_verifier,
            )
        self.assertFalse(manager.is_ready())
        failures = list((manager.runtime_dir / "cache" / "failures").iterdir())
        self.assertEqual(1, len(failures))
        self.assertTrue((failures[0] / "build.log").is_file())
        failure = json.loads((failures[0] / "failure.json").read_text(encoding="utf-8"))
        self.assertIn("source verification failed", failure["error"])

    def test_warm_rejects_build_created_untracked_qpbt_source(self) -> None:
        manager = self.manager(
            runtime=self.base / "runtime-untracked-qpbt",
            recipe=MATERIALIZING_TEST_RECIPE,
        )

        def generate_source(
            project: Path, command: list[str] | tuple[str, ...], log_path: Path
        ) -> int:
            result = fake_success(project, command, log_path)
            if list(command) == ["fake", "build"]:
                authored = project / "MIPStarRE" / "QPBT"
                authored.mkdir()
                (authored / "Generated.lean").write_text(
                    "def generated := true\n", encoding="utf-8"
                )
            return result

        with self.assertRaisesRegex(cache_module.CacheError, "project source changed"):
            manager.warm(
                _test_command_callback=generate_source,
                _test_source_verifier=fake_source_verifier,
            )
        self.assertFalse(manager.is_ready())

    def test_committed_authored_qpbt_tree_is_bound_into_cache_identity(self) -> None:
        before = self.manager(recipe=MATERIALIZING_TEST_RECIPE).identity
        authored = self.repo / "MIPStarRE" / "QPBT"
        authored.mkdir()
        payload = b"def committed := true\n"
        (authored / "Committed.lean").write_bytes(payload)
        run_git(self.repo, "add", "MIPStarRE/QPBT/Committed.lean")
        run_git(self.repo, "commit", "-m", "add committed QPBT source")
        after = self.manager(recipe=MATERIALIZING_TEST_RECIPE).identity
        self.assertNotEqual(before.cache_key, after.cache_key)
        self.assertEqual(1, after.source_contract["authored_qpbt_files"])
        self.assertEqual(len(payload), after.source_contract["authored_qpbt_bytes"])

    def test_ready_and_seed_require_valid_source_evidence(self) -> None:
        manager = self.manager(
            runtime=self.base / "runtime-source-evidence",
            recipe=MATERIALIZING_TEST_RECIPE,
        )
        manager.warm(
            _test_command_callback=fake_success,
            _test_source_verifier=fake_source_verifier,
        )
        target = self.issue_worktree("source-evidence-target")
        cache_module.make_owner_writable(manager.snapshot_dir)
        manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
        manifest["source_evidence"]["inventory_sha256"] = "invalid"
        manager.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manager.ready_path.write_text(
            cache_module.sha256_file(manager.manifest_path) + "\n", encoding="ascii"
        )
        self.assertFalse(manager.is_ready())
        with self.assertRaisesRegex(cache_module.CacheError, "deep artifact verification"):
            manager.seed(target)

    def test_ready_rejects_valid_shaped_semantic_source_evidence_tampering(self) -> None:
        manager = self.manager(
            runtime=self.base / "runtime-semantic-source-evidence",
            recipe=MATERIALIZING_TEST_RECIPE,
        )
        manager.warm(
            _test_command_callback=fake_success,
            _test_source_verifier=fake_source_verifier,
        )
        cache_module.make_owner_writable(manager.snapshot_dir)
        original = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
        mutations = {
            "source_commit": "2" * 40,
            "inventory_sha256": "2" * 64,
            "files": original["source_evidence"]["files"] + 1,
            "bytes": original["source_evidence"]["bytes"] + 1,
            "authored_qpbt_files": 1,
            "authored_qpbt_bytes": 1,
            "authored_qpbt_sha256": "2" * 64,
        }
        for field, replacement in mutations.items():
            with self.subTest(field=field):
                manifest = json.loads(json.dumps(original))
                manifest["source_evidence"][field] = replacement
                manager.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                manager.ready_path.write_text(
                    cache_module.sha256_file(manager.manifest_path) + "\n", encoding="ascii"
                )
                self.assertFalse(manager.is_ready(deep=True))

    def test_seed_rechecks_source_evidence_after_copy(self) -> None:
        manager = self.manager(
            runtime=self.base / "runtime-seed-source-race",
            recipe=MATERIALIZING_TEST_RECIPE,
        )
        manager.warm(
            _test_command_callback=fake_success,
            _test_source_verifier=fake_source_verifier,
        )
        target = self.issue_worktree("seed-source-race-target")
        original_copy = cache_module.reflink_copytree

        def copy_then_tamper(source: Path, destination: Path) -> cache_module.CopyStats:
            copied = original_copy(source, destination)
            cache_module.make_owner_writable(manager.snapshot_dir)
            manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
            manifest["source_evidence"]["pin_sha256"] = "0" * 64
            manager.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            manager.ready_path.write_text(
                cache_module.sha256_file(manager.manifest_path) + "\n", encoding="ascii"
            )
            return copied

        with mock.patch.object(cache_module, "reflink_copytree", side_effect=copy_then_tamper):
            with self.assertRaisesRegex(cache_module.CacheError, "lost source evidence"):
                manager.seed(target)
        self.assertFalse((target / ".lake").exists())

    def test_failed_build_is_retained_but_never_published(self) -> None:
        manager = self.manager()

        def fail(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            if list(command) == ["fake", "build"]:
                return 7
            return fake_success(project, command, log_path)

        with self.assertRaises(cache_module.CacheError):
            manager.warm(_test_command_callback=fail)
        self.assertFalse(manager.is_ready())
        failures = list((self.runtime / "cache" / "failures").iterdir())
        self.assertEqual(1, len(failures))
        self.assertFalse((failures[0] / "READY").exists())

    def test_seed_refuses_existing_or_missing_target(self) -> None:
        manager = self.manager()
        manager.warm(_test_command_callback=fake_success)
        target = self.issue_worktree("issue")
        (target / ".lake").mkdir()
        with self.assertRaises(cache_module.CacheError):
            manager.seed(target)
        with self.assertRaises(cache_module.CacheError):
            manager.seed(self.base / "typo")

    def test_recipe_is_bound_to_identity_and_readiness(self) -> None:
        test_manager = self.manager()
        canonical = cache_module.HotMainCache(self.repo, self.repo, self.runtime)
        self.assertNotEqual(test_manager.identity.cache_key, canonical.identity.cache_key)
        self.assertTrue(test_manager.identity.recipe["test_only"])
        self.assertFalse(canonical.identity.recipe["test_only"])

        with self.assertRaisesRegex(cache_module.CacheError, "test recipe"):
            canonical.warm(_test_command_callback=fake_success)
        self.assertFalse(canonical.is_ready())

        test_manager.warm(_test_command_callback=fake_success)
        manifest = json.loads(test_manager.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(test_manager.identity.recipe, manifest["recipe"])
        cache_module.make_owner_writable(test_manager.snapshot_dir)
        manifest["recipe"]["version"] += 1
        test_manager.manifest_path.write_text(
            __import__("json").dumps(manifest),
            encoding="utf-8",
        )
        self.assertFalse(test_manager.is_ready())

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cache_module.build_parser().parse_args(["warm", "--build-command", "true"])

    def test_seed_deeply_rejects_corrupted_published_artifact(self) -> None:
        manager = self.manager(runtime=self.base / "runtime-corrupt")
        manager.warm(_test_command_callback=fake_success)
        self.assertTrue(manager.is_ready())
        cache_module.make_owner_writable(manager.lake_dir)
        artifact = manager.build_dir / "QPBT.olean"
        artifact.write_text("corrupted\n", encoding="utf-8")
        self.assertTrue(manager.is_ready())
        self.assertFalse(manager.is_ready(deep=True))
        target = self.issue_worktree("corrupt-target")
        with self.assertRaisesRegex(cache_module.CacheError, "deep artifact verification"):
            manager.seed(target)

    def test_ready_marker_binds_manifest_bytes(self) -> None:
        manager = self.manager(runtime=self.base / "runtime-ready")
        manager.warm(_test_command_callback=fake_success)
        manifest = json.loads(manager.manifest_path.read_text(encoding="utf-8"))
        cache_module.make_owner_writable(manager.snapshot_dir)
        manifest["created_at"] = "tampered"
        manager.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertFalse(manager.is_ready())

    def test_warm_rechecks_key_inputs_after_build(self) -> None:
        manager = self.manager(runtime=self.base / "runtime-pins")

        def mutate_pin(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            result = fake_success(project, command, log_path)
            if list(command) == ["fake", "build"]:
                (project / "lakefile.toml").write_text("changed during build\n", encoding="utf-8")
            return result

        with self.assertRaisesRegex(cache_module.CacheError, "cache-key inputs changed"):
            manager.warm(_test_command_callback=mutate_pin)
        self.assertFalse(manager.is_ready())

    def test_warm_rejects_post_build_tracked_source_changes(self) -> None:
        manager = self.manager(runtime=self.base / "runtime-source")

        def mutate_source(project: Path, command: list[str] | tuple[str, ...], log_path: Path) -> int:
            result = fake_success(project, command, log_path)
            if list(command) == ["fake", "build"]:
                (project / "MIPStarRE" / "Basic.lean").write_text(
                    "def answer := 99\n",
                    encoding="utf-8",
                )
            return result

        with self.assertRaisesRegex(cache_module.CacheError, "project source changed"):
            manager.warm(_test_command_callback=mutate_source)
        self.assertFalse(manager.is_ready())

    def test_seed_rejects_wrong_or_incompatible_worktrees(self) -> None:
        manager = self.manager()
        manager.warm(_test_command_callback=fake_success)

        unregistered = self.base / "unregistered"
        unregistered.mkdir()
        for source in ("lean-toolchain", "lakefile.toml", "lake-manifest.json"):
            shutil.copy2(self.repo / source, unregistered / source)
        with self.assertRaisesRegex(cache_module.CacheError, "registered Git worktree"):
            manager.seed(unregistered)
        with self.assertRaisesRegex(cache_module.CacheError, "main worktree"):
            manager.seed(self.repo)

        incompatible = self.issue_worktree("incompatible")
        (incompatible / "lean-toolchain").write_text("different toolchain\n", encoding="utf-8")
        with self.assertRaisesRegex(cache_module.CacheError, "incompatible"):
            manager.seed(incompatible)

        stale = self.issue_worktree("stale")
        stale.rename(self.base / "stale-original")
        stale.mkdir()
        for source in ("lean-toolchain", "lakefile.toml", "lake-manifest.json"):
            shutil.copy2(self.repo / source, stale / source)
        with self.assertRaisesRegex(cache_module.CacheError, "live Git worktree"):
            manager.seed(stale)

    def test_seed_rejects_symlink_component_before_resolution(self) -> None:
        manager = self.manager()
        manager.warm(_test_command_callback=fake_success)
        real_parent = self.base / "real-parent"
        target = real_parent / "issue"
        run_git(self.repo, "worktree", "add", "--detach", str(target), self.commit)
        alias_parent = self.base / "alias-parent"
        alias_parent.symlink_to(real_parent, target_is_directory=True)

        with self.assertRaisesRegex(cache_module.CacheError, "symlink component"):
            manager.seed(alias_parent / "issue")

    def test_seed_replace_rolls_back_original_on_post_publish_failure(self) -> None:
        manager = self.manager()
        manager.warm(_test_command_callback=fake_success)
        target = self.issue_worktree("rollback")
        original = target / ".lake"
        original.mkdir()
        (original / "original-marker").write_text("keep me\n", encoding="utf-8")

        with mock.patch.object(
            manager,
            "_validate_seeded_destination",
            side_effect=cache_module.CacheError("injected validation failure"),
        ):
            with self.assertRaisesRegex(cache_module.CacheError, "injected validation failure"):
                manager.seed(target, replace=True)

        self.assertEqual("keep me\n", (original / "original-marker").read_text(encoding="utf-8"))
        self.assertFalse((original / "build" / "QPBT.olean").exists())
        self.assertEqual([], list(target.glob(".lake.backup-*")))
        self.assertEqual([], list(target.glob(".lake-seed-*")))

    def test_two_processes_elect_exactly_one_builder(self) -> None:
        counter = self.base / "build-count.txt"
        context = multiprocessing.get_context("fork")
        first = context.Process(target=contention_worker, args=(str(self.repo), str(self.runtime), str(counter)))
        second = context.Process(target=contention_worker, args=(str(self.repo), str(self.runtime), str(counter)))
        first.start()
        second.start()
        first.join(10)
        second.join(10)
        self.assertEqual(0, first.exitcode)
        self.assertEqual(0, second.exitcode)
        self.assertEqual(
            ["materialize", "build"],
            counter.read_text(encoding="utf-8").splitlines(),
        )
        metrics = [
            json.loads(line)
            for line in (self.runtime / "metrics" / "hot-main.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(1, sum(item["builds"] for item in metrics))
        self.assertEqual(1, sum(item["lock_waited"] for item in metrics))

    def test_linked_worktrees_share_omitted_runtime_and_builder_lock(self) -> None:
        first = self.issue_worktree("linked-first")
        second = self.issue_worktree("linked-second")
        first_runtime = cache_module.default_runtime_dir(first)
        second_runtime = cache_module.default_runtime_dir(second)
        self.assertEqual(first_runtime, second_runtime)
        self.assertEqual(self.repo.resolve() / ".workflow-runtime", first_runtime)

        counter = self.base / "linked-build-count.txt"
        context = multiprocessing.get_context("fork")
        first_process = context.Process(
            target=linked_worktree_contention_worker,
            args=(str(first), str(counter)),
        )
        second_process = context.Process(
            target=linked_worktree_contention_worker,
            args=(str(second), str(counter)),
        )
        first_process.start()
        second_process.start()
        first_process.join(10)
        second_process.join(10)
        self.assertEqual(0, first_process.exitcode)
        self.assertEqual(0, second_process.exitcode)
        self.assertEqual(["build"], counter.read_text(encoding="utf-8").splitlines())
        metrics = [
            json.loads(line)
            for line in (first_runtime / "metrics" / "hot-main.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(1, sum(item["builds"] for item in metrics))
        self.assertEqual(1, sum(item["lock_waited"] for item in metrics))

    def test_default_runtime_skips_prunable_unresolvable_worktree(self) -> None:
        stale = self.issue_worktree("stale-loop")
        shutil.rmtree(stale)
        stale.symlink_to(stale)

        records = cache_module.git_worktrees(self.repo)
        self.assertTrue(next(record for record in records if record.path == stale).prunable)
        self.assertEqual(
            self.repo.resolve() / ".workflow-runtime",
            cache_module.default_runtime_dir(self.repo),
        )

    def test_default_runtime_resolution_errors_fail_closed(self) -> None:
        class BrokenPath:
            def __init__(self, error: BaseException):
                self.error = error

            def resolve(self, *, strict: bool = False) -> Path:
                raise self.error

        for error in (RuntimeError("symlink loop"), PermissionError("denied")):
            with self.subTest(error=type(error).__name__):
                records = [
                    cache_module.WorktreeRecord(
                        path=BrokenPath(error),
                        head=self.commit,
                        bare=False,
                        prunable=False,
                    )
                ]
                with mock.patch.object(cache_module, "git_worktrees", return_value=records):
                    with self.assertRaisesRegex(cache_module.CacheError, "pass --runtime-dir"):
                        cache_module.default_runtime_dir(self.repo)

    def test_cli_default_runtime_resolution_failures_are_concise(self) -> None:
        missing = self.base / "missing-repository"
        loop = self.base / "repository-loop"
        loop.symlink_to(loop)
        for repo_root in (missing, loop):
            with self.subTest(repo_root=repo_root.name):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    result = cache_module.main(
                        ["--repo-root", str(repo_root), "status"]
                    )
                self.assertEqual(2, result)
                self.assertTrue(stderr.getvalue().startswith("error: "))
                self.assertIn("pass --runtime-dir explicitly", stderr.getvalue())

    def test_cli_runtime_default_and_explicit_override(self) -> None:
        parser = cache_module.build_parser()
        with mock.patch.object(cache_module, "HotMainCache") as constructor:
            constructor.return_value.status.return_value = {}

            cache_module.run_cli(
                parser.parse_args(["--repo-root", str(self.repo), "status"])
            )
            self.assertEqual(
                self.repo.resolve() / ".workflow-runtime",
                constructor.call_args.args[2],
            )

            constructor.reset_mock()
            cache_module.run_cli(
                parser.parse_args(
                    [
                        "--repo-root",
                        str(self.repo),
                        "--runtime-dir",
                        "custom-runtime",
                        "status",
                    ]
                )
            )
            self.assertEqual(self.repo.resolve() / "custom-runtime", constructor.call_args.args[2])

            constructor.reset_mock()
            absolute_runtime = self.base / "absolute-runtime"
            cache_module.run_cli(
                parser.parse_args(
                    [
                        "--repo-root",
                        str(self.repo),
                        "--runtime-dir",
                        str(absolute_runtime),
                        "status",
                    ]
                )
            )
            self.assertEqual(absolute_runtime, constructor.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
