from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bootstrap_manifest  # noqa: E402


class BootstrapManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "workflow/reviews").mkdir(parents=True)
        (self.root / "workflow/state").mkdir(parents=True)
        (self.root / "research/metrics").mkdir(parents=True)
        (self.root / "core.txt").write_text("review me\n", encoding="ascii")
        (self.root / "workflow/events.jsonl").write_text("", encoding="ascii")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def freeze(self) -> dict:
        with (
            mock.patch.object(bootstrap_manifest, "_git_state", return_value="unborn-main"),
            mock.patch.object(bootstrap_manifest, "_run_checks", return_value=[]),
        ):
            return bootstrap_manifest.freeze(self.root, replace=False)

    def test_freeze_and_verify_bind_core(self) -> None:
        document = self.freeze()
        verified = bootstrap_manifest.verify(self.root, require_sealed=False)
        self.assertEqual(
            document["reviewed_snapshot_digest"], verified["reviewed_snapshot_digest"]
        )
        self.assertEqual(["core.txt"], [item["path"] for item in document["reviewed_files"]])

    def test_core_change_or_addition_invalidates_snapshot(self) -> None:
        self.freeze()
        (self.root / "core.txt").write_text("changed\n", encoding="ascii")
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "core changed"):
            bootstrap_manifest.verify(self.root, require_sealed=False)

        (self.root / "core.txt").write_text("review me\n", encoding="ascii")
        (self.root / "new.txt").write_text("new\n", encoding="ascii")
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "core changed"):
            bootstrap_manifest.verify(self.root, require_sealed=False)

    def test_freeze_rejects_blank_line_at_eof(self) -> None:
        (self.root / "core.txt").write_text("review me\n\n", encoding="ascii")
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "blank_line_at_eof"):
            self.freeze()

    def test_terminal_evidence_can_change_until_seal(self) -> None:
        self.freeze()
        events = self.root / "workflow/events.jsonl"
        events.write_text("review finished\n", encoding="ascii")
        bootstrap_manifest.verify(self.root, require_sealed=False)

        report = self.root / "workflow/reviews/stage-01-bootstrap-final.md"
        manifest = bootstrap_manifest.verify(self.root, require_sealed=False)
        digest = manifest["reviewed_snapshot_digest"]
        report.write_text(
            "- Session: i001-reviewer-a03-bootstrap\n"
            "- Verdict: approve\n"
            f"- Snapshot: {digest}\n",
            encoding="ascii",
        )
        bootstrap_manifest.seal(
            self.root,
            reviewer_session_id="i001-reviewer-a03-bootstrap",
            review_report="workflow/reviews/stage-01-bootstrap-final.md",
            reviewed_snapshot_digest=digest,
        )
        bootstrap_manifest.verify(self.root, require_sealed=True)

        events.write_text("changed after seal\n", encoding="ascii")
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "after seal"):
            bootstrap_manifest.verify(self.root, require_sealed=True)

    def test_seal_rejects_different_reviewer_digest(self) -> None:
        document = self.freeze()
        report = self.root / "workflow/reviews/stage-01-bootstrap-final.md"
        report.write_text(
            "- Session: i001-reviewer-a03-bootstrap\n"
            "- Verdict: approve\n"
            "- Snapshot: deadbeef\n",
            encoding="ascii",
        )
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "different"):
            bootstrap_manifest.seal(
                self.root,
                reviewer_session_id="i001-reviewer-a03-bootstrap",
                review_report="workflow/reviews/stage-01-bootstrap-final.md",
                reviewed_snapshot_digest="deadbeef",
            )

    def test_seal_requires_explicit_approval(self) -> None:
        document = self.freeze()
        digest = document["reviewed_snapshot_digest"]
        report = self.root / "workflow/reviews/stage-01-bootstrap-final.md"
        report.write_text(
            "- Session: i001-reviewer-a03-bootstrap\n"
            "- Verdict: request_changes\n"
            f"- Snapshot: {digest}\n",
            encoding="ascii",
        )
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "approve"):
            bootstrap_manifest.seal(
                self.root,
                reviewer_session_id="i001-reviewer-a03-bootstrap",
                review_report="workflow/reviews/stage-01-bootstrap-final.md",
                reviewed_snapshot_digest=digest,
            )

    def test_manifest_tampering_is_detected(self) -> None:
        self.freeze()
        path = self.root / bootstrap_manifest.MANIFEST_REL
        document = json.loads(path.read_text(encoding="ascii"))
        document["terminal_evidence_contract"]["rule"] = "anything may change"
        path.write_text(json.dumps(document), encoding="ascii")
        with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "digest"):
            bootstrap_manifest.verify(self.root, require_sealed=False)

    def test_refuses_after_first_commit(self) -> None:
        with (
            mock.patch.object(
                bootstrap_manifest, "_git_state", return_value="committed-head-exists"
            ),
            mock.patch.object(bootstrap_manifest, "_run_checks", return_value=[]),
        ):
            with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "forbidden"):
                bootstrap_manifest.freeze(self.root, replace=False)

    def test_symlink_cannot_escape_reviewed_core(self) -> None:
        (self.root / "linked.txt").symlink_to(self.root / "core.txt")
        with (
            mock.patch.object(bootstrap_manifest, "_git_state", return_value="unborn-main"),
            mock.patch.object(bootstrap_manifest, "_run_checks", return_value=[]),
        ):
            with self.assertRaisesRegex(bootstrap_manifest.ManifestError, "symlink"):
                bootstrap_manifest.freeze(self.root, replace=False)


if __name__ == "__main__":
    unittest.main()
