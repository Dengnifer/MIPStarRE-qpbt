from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_workflow  # noqa: E402
import workflow  # noqa: E402


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def documents() -> dict[str, object]:
    return {
        "sessions.json": {
            "issued": [
                {"id": "i001-reviewer-a01-test", "status": "archived"},
                {"id": "i001-coordinator-a01-test", "status": "running"},
            ]
        },
        "stages.json": {"stages": [{"id": "STAGE-01", "incident_ids": ["INC-001"]}]},
        "protocols.json": {"revisions": [{"revision": "0.1.0", "evidence_ids": ["INC-001"]}]},
    }


class ResearchLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        metrics = self.root / "research/metrics"
        write_jsonl(metrics / "incidents.jsonl", [{"id": "INC-001"}])
        write_jsonl(
            metrics / "sessions.jsonl",
            [{"session_id": "i001-reviewer-a01-test"}],
        )
        write_jsonl(
            metrics / "protocol_changes.jsonl",
            [{"evidence_ids": ["INC-001"]}],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_cross_ledger_references_are_valid(self) -> None:
        check_workflow.validate_research_ledgers(self.root, documents())

    def test_unknown_incident_is_rejected(self) -> None:
        state = documents()
        state["stages.json"]["stages"][0]["incident_ids"] = ["INC-404"]
        with self.assertRaisesRegex(workflow.ValidationError, "unknown incident"):
            check_workflow.validate_research_ledgers(self.root, state)

    def test_terminal_session_needs_one_metric(self) -> None:
        write_jsonl(self.root / "research/metrics/sessions.jsonl", [])
        with self.assertRaisesRegex(workflow.ValidationError, "no research metric"):
            check_workflow.validate_research_ledgers(self.root, documents())


if __name__ == "__main__":
    unittest.main()
