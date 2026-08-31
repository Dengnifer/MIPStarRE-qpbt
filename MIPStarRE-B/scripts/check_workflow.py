#!/usr/bin/env python3
"""Run the canonical workflow-state check and dependency-free tooling tests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import unittest

import workflow


def _jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        errors.append(f"missing research ledger: {path}")
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f"{path}:{line_number}: invalid JSON: {error.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path}:{line_number}: expected an object")
            continue
        records.append(value)
    return records


def validate_research_ledgers(root: Path, documents: dict[str, Any]) -> None:
    errors: list[str] = []
    metrics = root / "research" / "metrics"
    incident_records = _jsonl(metrics / "incidents.jsonl", errors)
    session_records = _jsonl(metrics / "sessions.jsonl", errors)
    protocol_records = _jsonl(metrics / "protocol_changes.jsonl", errors)

    incident_ids: set[str] = set()
    for index, record in enumerate(incident_records):
        incident_id = record.get("id")
        if not isinstance(incident_id, str) or not incident_id:
            errors.append(f"incidents[{index}].id: expected a non-empty string")
        elif incident_id in incident_ids:
            errors.append(f"incidents[{index}].id: duplicate {incident_id!r}")
        else:
            incident_ids.add(incident_id)

    referenced_incidents: list[tuple[str, Any]] = []
    for stage in documents["stages.json"].get("stages", []):
        for incident_id in stage.get("incident_ids", []):
            referenced_incidents.append((f"stage {stage.get('id')}", incident_id))
    for revision in documents["protocols.json"].get("revisions", []):
        for incident_id in revision.get("evidence_ids", []):
            referenced_incidents.append((f"protocol {revision.get('revision')}", incident_id))
    for index, record in enumerate(protocol_records):
        for incident_id in record.get("evidence_ids", []):
            referenced_incidents.append((f"protocol_changes[{index}]", incident_id))
    for location, incident_id in referenced_incidents:
        if incident_id not in incident_ids:
            errors.append(f"{location}: unknown incident {incident_id!r}")

    issued = {
        record.get("id"): record
        for record in documents["sessions.json"].get("issued", [])
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }
    metric_ids: set[str] = set()
    for index, record in enumerate(session_records):
        session_id = record.get("session_id")
        if not isinstance(session_id, str) or session_id not in issued:
            errors.append(f"sessions metric[{index}]: unknown session {session_id!r}")
        elif session_id in metric_ids:
            errors.append(f"sessions metric[{index}]: duplicate session {session_id!r}")
        else:
            metric_ids.add(session_id)

    # Some callers use a deliberately partial synthetic document to test the
    # ledger parser. A real WorkflowStore document always includes issues.json;
    # reconcile full canonical documents deterministically here.
    if "issues.json" in documents:
        stages = documents["stages.json"].get("stages", [])
        stage_ids = {
            stage.get("id")
            for stage in stages
            if isinstance(stage, dict) and isinstance(stage.get("id"), str)
        }
        issue_stages: dict[str, list[str]] = {}
        for stage_index, stage in enumerate(stages):
            stage_id = stage.get("id")
            for issue_id in stage.get("issue_ids", []):
                issue_stages.setdefault(issue_id, []).append(stage_id)
                if len(issue_stages[issue_id]) > 1:
                    errors.append(
                        f"stages[{stage_index}].issue_ids: issue {issue_id!r} is mapped to multiple stages "
                        + repr(issue_stages[issue_id])
                    )

        for index, metric in enumerate(session_records):
            session_id = metric.get("session_id")
            session = issued.get(session_id)
            if session is None:
                continue
            metric_issue = metric.get("issue_id")
            issued_issue = session.get("issue_id")
            if metric_issue != issued_issue:
                errors.append(
                    f"sessions metric[{index}].issue_id: expected {issued_issue!r}, got {metric_issue!r}"
                )
            metric_stage = metric.get("stage_id")
            if not isinstance(metric_stage, str) or metric_stage not in stage_ids:
                errors.append(
                    f"sessions metric[{index}].stage_id: unknown stage {metric_stage!r}"
                )
            expected_stages = issue_stages.get(issued_issue, [])
            if len(expected_stages) == 1 and metric_stage != expected_stages[0]:
                errors.append(
                    f"sessions metric[{index}].stage_id: expected {expected_stages[0]!r} "
                    f"for issue {issued_issue!r}, got {metric_stage!r}"
                )
            elif len(expected_stages) == 0:
                errors.append(
                    f"sessions metric[{index}]: issued issue {issued_issue!r} has no stage mapping"
                )

        for stage_index, stage in enumerate(stages):
            issue_ids = set(stage.get("issue_ids", []))
            actual = sum(
                1
                for session in issued.values()
                if session.get("issue_id") in issue_ids and session.get("role") != "coordinator"
            )
            recorded = stage.get("subagents_issued")
            if recorded != actual:
                errors.append(
                    f"stages[{stage_index}].subagents_issued: expected {actual}, got {recorded!r}"
                )
    for session_id, record in issued.items():
        if record.get("status") in {"finished", "failed", "archived"} and session_id not in metric_ids:
            errors.append(f"terminal session {session_id!r} has no research metric")
    if errors:
        raise workflow.ValidationError(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--skip-tests", action="store_true")
    arguments = parser.parse_args()
    root = Path(arguments.root).resolve()
    store = workflow.WorkflowStore(
        root / "workflow" / "state",
        root / ".workflow-runtime",
        root / "workflow" / "events.jsonl",
    )
    try:
        documents = store.validate()
        validate_research_ledgers(root, documents)
    except workflow.ValidationError as error:
        for item in error.errors:
            print(item, file=sys.stderr)
        return 2
    print("workflow state: valid")
    if arguments.skip_tests:
        return 0
    suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
