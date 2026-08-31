from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import workflow  # noqa: E402
import check_workflow  # noqa: E402


NOW = "2026-08-30T00:00:00Z"
CHECKED = "2026-08-30T00:01:00Z"
REVIEW_STARTED = "2026-08-30T00:02:00Z"
REVIEW_ENDED = "2026-08-30T00:03:00Z"
REVIEW2_STARTED = "2026-08-30T00:04:00Z"
REVIEW2_ENDED = "2026-08-30T00:05:00Z"
BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40


def unavailable_tokens() -> dict[str, object]:
    return {
        "input": None,
        "output": None,
        "total": None,
        "availability_reason": "not exposed",
    }


def issue(issue_id: str, status: str, dependencies: list[str] | None = None, **extra: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": issue_id,
        "title": issue_id,
        "kind": "formalization",
        "status": status,
        "parent_id": None,
        "dependency_ids": dependencies or [],
        "labels": [],
        "acceptance_gates": [],
        "owner_session_id": None,
        "source_refs": [],
        "created_at": NOW,
        "updated_at": NOW,
    }
    value.update(extra)
    return value


def issued_session(
    session_id: str,
    *,
    issue_id: str = "QPBT-002",
    pr_id: str | None = None,
    role: str = "prover",
    status: str = "archived",
    read_only: bool = False,
    owned_paths: list[str] | None = None,
    started_at: str | None = REVIEW_STARTED,
    ended_at: str | None = REVIEW_ENDED,
    elapsed_seconds: float | None = 60.0,
) -> dict[str, object]:
    if owned_paths is None:
        owned_paths = [] if read_only else ["MIPStarRE/QPBT/Test.lean"]
    archived = status == "archived"
    return {
        "id": session_id,
        "name": session_id,
        "backend": "codex-cli",
        "role": role,
        "status": status,
        "issue_id": issue_id,
        "pr_id": pr_id,
        "parent_session_id": None,
        "external_id": f"thread-{session_id}",
        "attempt": 1,
        "read_only": read_only,
        "base_revision": BASE_SHA,
        "worktree": "/tmp/qpbt-worktree",
        "owned_paths": owned_paths,
        "validation_command": "lake env lean MIPStarRE/QPBT/Test.lean",
        "result_envelope_path": f".workflow-runtime/runs/{session_id}/result.json",
        "started_at": started_at,
        "ended_at": ended_at,
        "elapsed_seconds": elapsed_seconds,
        "token_usage": unavailable_tokens(),
        "archive_status": "archived" if archived else "active",
        "outcome_path": f".workflow-runtime/runs/{session_id}/result.json" if archived else None,
    }


def planned_session(
    session_id: str,
    *,
    issue_id: str = "QPBT-002",
    role: str = "reviewer",
    read_only: bool = True,
    worktree: str = "/tmp/qpbt-worktree",
    owned_paths: list[str] | None = None,
) -> dict[str, object]:
    """Build a complete planned row suitable for dispatch materialization."""

    if owned_paths is None:
        owned_paths = [] if read_only else ["MIPStarRE/QPBT/Test.lean"]
    record = issued_session(
        session_id,
        issue_id=issue_id,
        role=role,
        status="issued",
        read_only=read_only,
        owned_paths=owned_paths,
        started_at=None,
        ended_at=None,
        elapsed_seconds=None,
    )
    record["worktree"] = worktree
    record["status"] = "planned"
    record["external_id"] = None
    record["archive_status"] = "not_requested"
    record["outcome_path"] = None
    return record


def check_evidence(*, head_sha: str = HEAD_SHA, status: str = "passed") -> dict[str, object]:
    return {
        "id": "check-full-build",
        "name": "full build",
        "command": "lake build",
        "status": status,
        "base_sha": BASE_SHA,
        "head_sha": head_sha,
        "completed_at": CHECKED,
        "result_path": ".workflow-runtime/checks/full-build.log",
    }


def review_evidence(
    reviewer_id: str = "i002-reviewer-a01-source",
    *,
    review_id: str = "review-001",
    head_sha: str = HEAD_SHA,
    verdict: str = "approve",
    finding_ids: list[str] | None = None,
    started_at: str = REVIEW_STARTED,
    completed_at: str = REVIEW_ENDED,
) -> dict[str, object]:
    return {
        "id": review_id,
        "reviewer_session_id": reviewer_id,
        "verdict": verdict,
        "base_sha": BASE_SHA,
        "head_sha": head_sha,
        "started_at": started_at,
        "completed_at": completed_at,
        "result_path": f".workflow-runtime/reviews/{review_id}.json",
        "finding_ids": finding_ids or [],
    }


def pull_request(
    *,
    status: str = "approved",
    head_sha: str = HEAD_SHA,
    checks: list[dict[str, object]] | None = None,
    reviews: list[dict[str, object]] | None = None,
    findings: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "id": "LPR-001",
        "title": "feat(QPBT/Test): test",
        "status": status,
        "issue_ids": ["QPBT-002"],
        "base": "main",
        "head": "issue/qpbt-002",
        "base_sha": BASE_SHA,
        "head_sha": head_sha,
        "implementer_session_ids": ["i002-prover-a01-implementation"],
        "checks": [check_evidence(head_sha=head_sha)] if checks is None else checks,
        "reviews": [review_evidence(head_sha=head_sha)] if reviews is None else reviews,
        "findings": [] if findings is None else findings,
        "integration_sha": None,
        "merged_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }


def add_pr_sessions(state: dict[str, object]) -> None:
    state["sessions.json"]["issued"] = [
        issued_session("i002-prover-a01-implementation", pr_id="LPR-001"),
        issued_session(
            "i002-reviewer-a01-source",
            pr_id="LPR-001",
            role="reviewer",
            read_only=True,
        ),
    ]


def documents() -> dict[str, object]:
    return {
        "issues.json": {
            "schema_version": 1,
            "next_sequence": 3,
            "issues": [issue("QPBT-001", "done"), issue("QPBT-002", "planned", ["QPBT-001"], note="keep")],
        },
        "prs.json": {"schema_version": 1, "next_sequence": 1, "pull_requests": []},
        "sessions.json": {"schema_version": 1, "planned": [], "issued": []},
        "stages.json": {
            "schema_version": 1,
            "stages": [
                {
                    "id": "STAGE-01",
                    "name": "test",
                    "status": "in_progress",
                    "issue_ids": ["QPBT-002"],
                    "started_at": NOW,
                    "ended_at": None,
                    "elapsed_seconds": None,
                    "token_usage": unavailable_tokens(),
                    "subagents_issued": 0,
                    "max_concurrency": 1,
                    "outputs": [],
                    "incident_ids": ["INC-001"],
                }
            ],
        },
        "protocols.json": {
            "schema_version": 1,
            "active_revision": "0.1.0",
            "revisions": [
                {
                    "revision": "0.1.0",
                    "status": "active",
                    "effective_at": NOW,
                    "cause": "test protocol",
                    "evidence_ids": [],
                    "review_pr_id": None,
                    "retirement_condition": "re-evaluate after three uses",
                }
            ],
        },
    }


class WorkflowValidationTests(unittest.TestCase):
    def test_valid_documents_and_dependency_ready(self) -> None:
        state = documents()
        workflow.validate_documents(state)
        self.assertEqual(["QPBT-002"], [item["id"] for item in workflow.dependency_ready_issues(state)])

    def test_active_non_coordinator_count_excludes_coordinator_and_terminal_sessions(self) -> None:
        state = documents()
        coordinator = issued_session(
            "i001-coordinator-a01-active",
            issue_id="QPBT-001",
            role="coordinator",
            status="running",
            read_only=False,
            owned_paths=["workflow/"],
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        active = issued_session(
            "i002-prover-a01-active",
            status="running",
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        terminal = issued_session("i002-reviewer-a01-terminal", read_only=True)
        state["sessions.json"]["issued"] = [coordinator, active, terminal]
        self.assertEqual(1, workflow.active_non_coordinator_count(state))
        self.assertEqual(1, workflow.active_non_coordinator_count(state, stage_id="STAGE-01"))

    def test_active_count_is_conservative_across_backends(self) -> None:
        state = documents()
        cli_session = issued_session(
            "i002-prover-a01-cli-active",
            status="running",
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        collaboration_session = issued_session(
            "i002-reviewer-a01-collaboration-active",
            role="reviewer",
            read_only=True,
            status="issued",
            started_at=None,
            ended_at=None,
            elapsed_seconds=None,
        )
        collaboration_session["backend"] = "codex-collaboration"
        state["sessions.json"]["issued"] = [cli_session, collaboration_session]
        self.assertEqual(2, workflow.active_non_coordinator_count(state))
        result = workflow.plan_dispatch(state, capacity=2, stage_id="STAGE-01")
        self.assertEqual("stage", result["capacity_scope"])
        self.assertEqual("all", result["backend_scope"])

    def test_stage_count_ignores_active_issue_without_stage_mapping(self) -> None:
        state = documents()
        unrelated = issued_session(
            "i001-reviewer-a01-unmapped-active",
            issue_id="QPBT-001",
            role="reviewer",
            read_only=True,
            status="running",
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        state["sessions.json"]["issued"] = [unrelated]
        self.assertEqual(1, workflow.active_non_coordinator_count(state))
        self.assertEqual(0, workflow.active_non_coordinator_count(state, stage_id="STAGE-01"))

    def test_stage_count_fails_closed_on_any_ambiguous_active_mapping(self) -> None:
        state = documents()
        duplicate_stage = copy.deepcopy(state["stages.json"]["stages"][0])
        duplicate_stage["id"] = "STAGE-02"
        duplicate_stage["issue_ids"] = ["QPBT-001"]
        state["stages.json"]["stages"][0]["issue_ids"].append("QPBT-001")
        state["stages.json"]["stages"].append(duplicate_stage)
        active = issued_session(
            "i001-reviewer-a01-ambiguous-active",
            issue_id="QPBT-001",
            role="reviewer",
            read_only=True,
            status="running",
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        state["sessions.json"]["issued"] = [active]
        with self.assertRaisesRegex(workflow.WorkflowError, "ambiguous stage mapping"):
            workflow.active_non_coordinator_count(state, stage_id="STAGE-01")

    def test_dispatch_requires_explicit_capacity_and_rejects_invalid_values(self) -> None:
        state = documents()
        for capacity in (None, -1, True, 1.5):
            with self.assertRaises(workflow.WorkflowError):
                workflow.plan_dispatch(state, capacity=capacity)  # type: ignore[arg-type]

    def test_unknown_capacity_does_not_mask_dag_diagnostics(self) -> None:
        state = documents()
        state["issues.json"]["issues"][0]["status"] = "planned"
        state["issues.json"]["issues"][0]["dependency_ids"] = ["QPBT-002"]
        state["issues.json"]["issues"][1]["dependency_ids"] = ["QPBT-001"]
        with self.assertRaisesRegex(workflow.ValidationError, "issue dependencies: cycle detected"):
            workflow.plan_dispatch(state, capacity=None)

    def test_unknown_capacity_preserves_dag_and_ownership_diagnostics(self) -> None:
        state = documents()
        blocked_issue = issue("QPBT-003", "planned", ["QPBT-002"])
        state["issues.json"]["issues"].append(blocked_issue)
        state["stages.json"]["stages"][0]["issue_ids"].append("QPBT-003")
        active = issued_session(
            "i002-prover-a01-unknown-capacity-owner",
            role="prover",
            status="running",
            read_only=False,
            owned_paths=["MIPStarRE/QPBT/Conflict.lean"],
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        conflicting = planned_session(
            "i002-prover-a02-unknown-capacity-conflict",
            role="prover",
            read_only=False,
            owned_paths=["MIPStarRE/QPBT/Conflict.lean"],
        )
        dependency_blocked = planned_session(
            "i003-reviewer-a01-unknown-capacity-blocked",
            issue_id="QPBT-003",
        )
        state["sessions.json"]["issued"] = [active]
        state["sessions.json"]["planned"] = [conflicting, dependency_blocked]
        with self.assertRaisesRegex(workflow.WorkflowError, "capacity is unknown") as caught:
            workflow.plan_dispatch(
                state,
                capacity=None,
                stage_id="STAGE-01",
                session_ids=[conflicting["id"], dependency_blocked["id"]],
            )
        message = str(caught.exception)
        self.assertIn("ownership-conflict", message)
        self.assertIn("dependencies-not-done", message)

    def test_dispatch_plan_reports_sorted_queue_and_dependency_block(self) -> None:
        state = documents()
        blocked_issue = issue("QPBT-003", "planned", ["QPBT-002"])
        state["issues.json"]["issues"].append(blocked_issue)
        state["stages.json"]["stages"][0]["issue_ids"].append("QPBT-003")
        state["sessions.json"]["planned"] = [
            planned_session("i003-reviewer-a01-blocked", issue_id="QPBT-003"),
            planned_session("i002-reviewer-a02-queued"),
            planned_session("i002-reviewer-a01-queued"),
        ]
        result = workflow.plan_dispatch(
            state,
            capacity=1,
            stage_id="STAGE-01",
            session_ids=[
                "i003-reviewer-a01-blocked",
                "i002-reviewer-a02-queued",
                "i002-reviewer-a01-queued",
            ],
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual(["i002-reviewer-a01-queued"], result["dispatchable"])
        self.assertEqual(
            [{"id": "i002-reviewer-a02-queued", "reason": "capacity-exhausted"}],
            result["queued"],
        )
        self.assertEqual("dependencies-not-done", result["blocked"][0]["reason"])

    def test_dispatch_plan_reports_writable_ownership_conflict(self) -> None:
        state = documents()
        active = issued_session(
            "i002-prover-a01-active-owner",
            status="running",
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
            owned_paths=["MIPStarRE/QPBT/Test.lean"],
        )
        state["sessions.json"]["issued"] = [active]
        state["sessions.json"]["planned"] = [
            planned_session(
                "i002-prover-a02-conflict",
                role="prover",
                read_only=False,
                owned_paths=["MIPStarRE/QPBT/Test.lean"],
            )
        ]
        result = workflow.plan_dispatch(state, capacity=2, stage_id="STAGE-01")
        self.assertEqual("blocked", result["status"])
        self.assertEqual("ownership-conflict", result["blocked"][0]["reason"])
        self.assertEqual("i002-prover-a01-active-owner", result["blocked"][0]["with_session_id"])

    def test_dispatch_rejects_duplicate_planned_orchestrators_for_one_issue(self) -> None:
        state = documents()
        first = planned_session(
            "i002-orchestrator-a01-duplicate",
            role="orchestrator",
            read_only=False,
            owned_paths=["MIPStarRE/QPBT/First.lean"],
        )
        second = planned_session(
            "i002-orchestrator-a02-duplicate",
            role="orchestrator",
            read_only=False,
            owned_paths=["MIPStarRE/QPBT/Second.lean"],
        )
        state["sessions.json"]["planned"] = [first, second]
        result = workflow.plan_dispatch(
            state,
            capacity=2,
            stage_id="STAGE-01",
            session_ids=[first["id"], second["id"]],
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual(
            [first["id"], second["id"]],
            [entry["id"] for entry in result["blocked"]],
        )
        self.assertTrue(
            all(entry["reason"] == "duplicate-orchestrator" for entry in result["blocked"])
        )

    def test_dispatch_rejects_orchestrator_when_active_attempt_exists(self) -> None:
        state = documents()
        active = issued_session(
            "i002-orchestrator-a01-active",
            role="orchestrator",
            status="running",
            read_only=False,
            owned_paths=["MIPStarRE/QPBT/Existing.lean"],
            started_at=REVIEW_STARTED,
            ended_at=None,
            elapsed_seconds=None,
        )
        candidate = planned_session(
            "i002-orchestrator-a02-active-duplicate",
            role="orchestrator",
            read_only=False,
            owned_paths=["MIPStarRE/QPBT/Candidate.lean"],
        )
        state["sessions.json"]["issued"] = [active]
        state["sessions.json"]["planned"] = [candidate]
        result = workflow.plan_dispatch(
            state,
            capacity=2,
            stage_id="STAGE-01",
            session_ids=[candidate["id"]],
        )
        self.assertEqual("duplicate-orchestrator", result["blocked"][0]["reason"])
        self.assertEqual([active["id"]], result["blocked"][0]["with_session_ids"])

    def test_dispatch_plan_rejects_cross_candidate_batch_conflict(self) -> None:
        state = documents()
        first = planned_session("i002-reviewer-a01-batch-conflict")
        second = planned_session("i002-reviewer-a02-batch-conflict")
        state["sessions.json"]["planned"] = [first, second]
        result = workflow.plan_dispatch(
            state,
            capacity=2,
            session_ids=[first["id"], second["id"]],
            session_overrides={
                first["id"]: {"external_id": "shared-external-id"},
                second["id"]: {"external_id": "shared-external-id"},
            },
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual(
            [first["id"], second["id"]],
            [entry["id"] for entry in result["blocked"]],
        )
        self.assertTrue(all(entry["reason"] == "batch-validation-failure" for entry in result["blocked"]))

    def test_queued_cross_candidate_conflict_is_deferred_until_admission(self) -> None:
        state = documents()
        first = planned_session("i002-reviewer-a01-queued-conflict")
        second = planned_session("i002-reviewer-a02-queued-conflict")
        state["sessions.json"]["planned"] = [first, second]
        result = workflow.plan_dispatch(
            state,
            capacity=1,
            session_ids=[first["id"], second["id"]],
            session_overrides={
                first["id"]: {"external_id": "shared-queued-external-id"},
                second["id"]: {"external_id": "shared-queued-external-id"},
            },
        )
        self.assertEqual("queued", result["status"])
        self.assertEqual([first["id"]], result["dispatchable"])
        self.assertEqual(
            [{"id": second["id"], "reason": "capacity-exhausted"}],
            result["queued"],
        )
        self.assertEqual([], result["blocked"])
        self.assertTrue(result["request_atomic"])
        self.assertFalse(result["all_or_nothing"])

    def test_dispatch_override_cannot_change_planned_authority(self) -> None:
        state = documents()
        candidate = planned_session("i002-reviewer-a01-authority")
        state["sessions.json"]["planned"] = [candidate]
        result = workflow.plan_dispatch(
            state,
            capacity=1,
            session_ids=[candidate["id"]],
            session_overrides={candidate["id"]: {"issue_id": "QPBT-001"}},
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual("invalid-dispatch-override", result["blocked"][0]["reason"])
        self.assertIn("issue_id", result["blocked"][0]["detail"])

    def test_dispatch_override_cannot_retarget_pr_or_rewrite_external_id(self) -> None:
        state = documents()
        candidate = planned_session("i002-reviewer-a01-provenance")
        candidate["pr_id"] = "LPR-001"
        candidate["external_id"] = "thread-original"
        state["sessions.json"]["planned"] = [candidate]
        cases = [
            ({"pr_id": "LPR-002"}, "pr_id", candidate),
            (
                {"external_id": "thread-new"},
                "external_id",
                {**candidate, "pr_id": None},
            ),
        ]
        for override, expected, row in cases:
            state["sessions.json"]["planned"] = [row]
            result = workflow.plan_dispatch(
                state,
                capacity=1,
                session_ids=[row["id"]],
                session_overrides={row["id"]: override},
            )
            self.assertEqual("blocked", result["status"])
            self.assertIn(expected, result["blocked"][0]["detail"])

    def test_dispatch_rejects_mixed_shape_override_object(self) -> None:
        session_id = "i002-reviewer-a01-mixed-override"
        mixed = json.dumps(
            {
                "id": session_id,
                "external_id": "thread-materialized",
                "another-session": {"external_id": "thread-other"},
            }
        )
        with self.assertRaisesRegex(
            workflow.WorkflowError,
            "cannot mix single-record and keyed shapes",
        ):
            workflow._load_dispatch_overrides(mixed, None)

        with self.assertRaisesRegex(
            workflow.WorkflowError,
            "cannot mix single-record and keyed shapes",
        ):
            workflow._load_dispatch_overrides(
                json.dumps({"id": 17, "external_id": "thread-materialized"}),
                None,
            )

    def test_protocol_ledger_requires_the_named_unique_active_revision(self) -> None:
        state = documents()
        state["protocols.json"]["active_revision"] = "0.2.0"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("unknown revision '0.2.0'", str(caught.exception))

        state = documents()
        duplicate = copy.deepcopy(state["protocols.json"]["revisions"][0])
        state["protocols.json"]["revisions"].append(duplicate)
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("duplicate '0.1.0'", str(caught.exception))

    def test_rejects_dependency_and_parent_cycles(self) -> None:
        state = documents()
        issues = state["issues.json"]["issues"]
        issues[0]["status"] = "planned"
        issues[0]["dependency_ids"] = ["QPBT-002"]
        issues[0]["parent_id"] = "QPBT-002"
        issues[1]["parent_id"] = "QPBT-001"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        message = str(caught.exception)
        self.assertIn("issue dependencies: cycle detected", message)
        self.assertIn("issue parent hierarchy: cycle detected", message)

    def test_malformed_dependency_reports_validation_error_instead_of_crashing(self) -> None:
        state = documents()
        state["issues.json"]["issues"][1]["dependency_ids"] = [{}]
        state["issues.json"]["issues"][1]["status"] = "ready"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("expected a list of issue ids", str(caught.exception))

    def test_rejects_invalid_status_and_reference(self) -> None:
        state = documents()
        state["issues.json"]["issues"][1]["status"] = "almost_done"
        state["stages.json"]["stages"][0]["issue_ids"] = ["QPBT-999"]
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("invalid issue status", str(caught.exception))
        self.assertIn("unknown issue 'QPBT-999'", str(caught.exception))

    def test_rejects_cross_bucket_session_duplicate_and_cycle(self) -> None:
        state = documents()
        planned = {
            "id": "S1",
            "name": "i002-prover-a01-one",
            "role": "prover",
            "issue_id": "QPBT-002",
            "status": "planned",
            "parent_session_id": "S2",
        }
        issued = {
            "id": "S2",
            "name": "i002-reviewer-a01-two",
            "backend": "codex-cli",
            "role": "reviewer",
            "status": "issued",
            "issue_id": "QPBT-002",
            "pr_id": None,
            "parent_session_id": "S1",
            "external_id": None,
            "attempt": 1,
            "started_at": None,
            "ended_at": None,
            "elapsed_seconds": None,
            "token_usage": unavailable_tokens(),
            "archive_status": "not_requested",
            "outcome_path": None,
        }
        state["sessions.json"]["planned"] = [planned]
        state["sessions.json"]["issued"] = [issued]
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("session parent hierarchy: cycle detected", str(caught.exception))
        issued["id"] = "S1"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("ids appear in both planned and issued", str(caught.exception))

    def test_done_tracker_requires_done_child(self) -> None:
        state = documents()
        tracker = issue("QPBT-000", "done", kind="tracking")
        state["issues.json"]["issues"].insert(0, tracker)
        state["issues.json"]["issues"][2]["parent_id"] = "QPBT-000"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("all direct children must be done", str(caught.exception))

    def test_valid_approved_pr_has_sha_bound_checks_and_independent_review(self) -> None:
        state = documents()
        state["prs.json"]["pull_requests"] = [pull_request()]
        add_pr_sessions(state)
        workflow.validate_documents(state)

    def test_rejects_stale_or_failed_pr_evidence(self) -> None:
        state = documents()
        stale_review = review_evidence(head_sha="c" * 40)
        state["prs.json"]["pull_requests"] = [
            pull_request(
                checks=[check_evidence(status="failed")],
                reviews=[stale_review],
            )
        ]
        add_pr_sessions(state)
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        message = str(caught.exception)
        self.assertIn("all current checks must pass", message)
        self.assertIn("requires a current approving review", message)

    def test_rejects_non_independent_reviewer(self) -> None:
        state = documents()
        implementer_id = "i002-prover-a01-implementation"
        state["prs.json"]["pull_requests"] = [
            pull_request(reviews=[review_evidence(implementer_id)])
        ]
        add_pr_sessions(state)
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        message = str(caught.exception)
        self.assertIn("reviewer must be a read-only reviewer session", message)
        self.assertIn("reviewer is not independent", message)

    def test_reviewer_identity_is_unique_and_bound_to_pr_base(self) -> None:
        state = documents()
        state["prs.json"]["pull_requests"] = [pull_request()]
        add_pr_sessions(state)
        implementer, reviewer = state["sessions.json"]["issued"]
        reviewer["external_id"] = implementer["external_id"]
        reviewer["base_revision"] = "c" * 40
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        message = str(caught.exception)
        self.assertIn("duplicate external_id", message)
        self.assertIn("base_revision differs from PR base_sha", message)

    def test_approved_pr_requires_a_linked_issue(self) -> None:
        state = documents()
        pr = pull_request()
        pr["issue_ids"] = []
        state["prs.json"]["pull_requests"] = [pr]
        add_pr_sessions(state)
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("must link at least one issue", str(caught.exception))

    def test_rejects_unresolved_finding_and_accepts_review_confirmed_disposition(self) -> None:
        finding = {
            "id": "F-001",
            "introduced_review_id": "review-001",
            "base_sha": BASE_SHA,
            "head_sha": HEAD_SHA,
            "severity": "high",
            "status": "open",
            "disposition": "pending",
            "disposition_evidence": None,
            "resolved_by_review_id": None,
        }
        state = documents()
        first_review = review_evidence(verdict="request_changes", finding_ids=["F-001"])
        second_reviewer = "i002-reviewer-a02-resolution"
        second_review = review_evidence(
            second_reviewer,
            review_id="review-002",
            started_at=REVIEW2_STARTED,
            completed_at=REVIEW2_ENDED,
        )
        state["prs.json"]["pull_requests"] = [
            pull_request(
                reviews=[first_review, second_review],
                findings=[finding],
            )
        ]
        add_pr_sessions(state)
        state["sessions.json"]["issued"].append(
            issued_session(
                second_reviewer,
                pr_id="LPR-001",
                role="reviewer",
                read_only=True,
                started_at=REVIEW2_STARTED,
                ended_at=REVIEW2_ENDED,
            )
        )
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("requires every finding to be resolved", str(caught.exception))

        finding["status"] = "resolved"
        finding["disposition"] = "rejected"
        finding["disposition_evidence"] = "second reviewer confirmed the report was inapplicable"
        finding["resolved_by_review_id"] = "review-002"
        workflow.validate_documents(state)

    def test_issued_session_contract_and_lifecycle_are_required(self) -> None:
        state = documents()
        session = issued_session(
            "i002-prover-a01-lifecycle",
            status="running",
            started_at=None,
            ended_at=REVIEW_ENDED,
            elapsed_seconds=1.0,
        )
        session.pop("result_envelope_path")
        state["sessions.json"]["issued"] = [session]
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        message = str(caught.exception)
        self.assertIn("missing required field 'result_envelope_path'", message)
        self.assertIn("started_at: required for running session", message)
        self.assertIn("running session cannot have terminal timing", message)

    def test_terminal_session_accepts_explicit_parent_window_without_fabricated_timing(self) -> None:
        state = documents()
        session = issued_session(
            "i002-auditor-a01-interrupted",
            role="auditor",
            read_only=True,
            started_at=None,
            ended_at=None,
            elapsed_seconds=None,
        )
        session["timing_quality"] = "bounded-by-parent-window"
        session["timing_bounds"] = {
            "not_before": REVIEW_STARTED,
            "not_after": REVIEW_ENDED,
        }
        parent = issued_session("i002-auditor-a02-parent", role="auditor", read_only=True)
        session["parent_session_id"] = parent["id"]
        state["sessions.json"]["issued"] = [parent, session]
        workflow.validate_documents(state)

        session["timing_bounds"]["not_before"] = "2026-08-30T00:04:00Z"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("not_after precedes not_before", str(caught.exception))

    def test_approximate_terminal_timing_must_be_labeled(self) -> None:
        state = documents()
        session = issued_session("i002-auditor-a01-approximate", role="auditor", read_only=True)
        session["elapsed_seconds"] = 55.0
        state["sessions.json"]["issued"] = [session]
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("non-exact timing must be labeled", str(caught.exception))

        session["timing_quality"] = "agent-reported-approximate"
        workflow.validate_documents(state)

    def test_rejects_overlapping_active_writable_ownership(self) -> None:
        state = documents()
        first = issued_session(
            "i002-prover-a01-left",
            status="running",
            owned_paths=["MIPStarRE/QPBT/"],
            ended_at=None,
            elapsed_seconds=None,
        )
        second = issued_session(
            "i002-prover-a02-right",
            status="running",
            owned_paths=["MIPStarRE/QPBT/Test.lean"],
            ended_at=None,
            elapsed_seconds=None,
        )
        state["sessions.json"]["issued"] = [first, second]
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("active writable ownership overlap", str(caught.exception))

        second["worktree"] = "/tmp/qpbt-other-worktree"
        workflow.validate_documents(state)

    def test_in_progress_implementation_requires_one_matching_orchestrator(self) -> None:
        state = documents()
        implementation = state["issues.json"]["issues"][1]
        implementation["status"] = "in_progress"
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("requires exactly one active orchestrator", str(caught.exception))

        orchestrator = issued_session(
            "i002-orchestrator-a01-delivery",
            role="orchestrator",
            status="running",
            owned_paths=["MIPStarRE/QPBT/"],
            ended_at=None,
            elapsed_seconds=None,
        )
        state["sessions.json"]["issued"] = [orchestrator]
        implementation["owner_session_id"] = orchestrator["id"]
        workflow.validate_documents(state)

        implementation["execution_category"] = "preflight"
        state["sessions.json"]["issued"] = []
        implementation["owner_session_id"] = None
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.validate_documents(state)
        self.assertIn("cannot bypass implementation gates", str(caught.exception))

    def test_workflow_bootstrap_category_does_not_require_orchestrator(self) -> None:
        state = documents()
        bootstrap = state["issues.json"]["issues"][1]
        bootstrap["kind"] = "workflow"
        bootstrap["status"] = "in_progress"
        workflow.validate_documents(state)


class WorkflowStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_dir = self.root / "workflow" / "state"
        self.state_dir.mkdir(parents=True)
        for filename, value in documents().items():
            (self.state_dir / filename).write_text(json.dumps(value), encoding="utf-8")
        self.events = self.root / "workflow" / "events.jsonl"
        self.events.write_text(
            "\n"
            + json.dumps(
                {
                    "schema_version": 1,
                    "timestamp": NOW,
                    "event": "bootstrap",
                    "actor": "test",
                    "pid": 1,
                    "payload": {},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self.runtime = self.root / ".workflow-runtime"
        self.store = workflow.WorkflowStore(self.state_dir, self.runtime, self.events)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_read_only_validation_creates_no_runtime_files(self) -> None:
        self.store.validate()
        self.assertFalse(self.runtime.exists())

    def test_dispatch_batch_issues_available_prefix_when_capacity_is_exhausted(self) -> None:
        first = planned_session("i002-reviewer-a01-batch")
        second = planned_session("i002-reviewer-a02-batch")
        state = documents()
        state["sessions.json"]["planned"] = [second, first]
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )

        queued = self.store.dispatch_sessions(
            capacity=1,
            stage_id="STAGE-01",
            session_ids=[second["id"], first["id"]],
        )
        self.assertEqual("issued", queued["status"])
        self.assertEqual([first["id"]], queued["issued"])
        self.assertEqual([first["id"]], queued["dispatchable"])
        self.assertEqual(
            [{"id": second["id"], "reason": "capacity-exhausted"}],
            queued["queued"],
        )
        unchanged = self.store.validate()
        self.assertEqual([second["id"]], [row["id"] for row in unchanged["sessions.json"]["planned"]])
        self.assertEqual([first["id"]], [row["id"] for row in unchanged["sessions.json"]["issued"]])
        events = [
            json.loads(line)
            for line in self.events.read_text(encoding="utf-8").splitlines()
            if line
        ]
        self.assertFalse(events[-1]["payload"]["all_or_nothing_request"])
        self.assertTrue(events[-1]["payload"]["atomic_batch"])

    def test_dispatch_batch_issues_sorted_candidates_atomically_and_records_events(self) -> None:
        first = planned_session("i002-reviewer-a01-batch")
        second = planned_session("i002-reviewer-a02-batch")
        state = documents()
        state["sessions.json"]["planned"] = [second, first]
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )

        issued = self.store.dispatch_sessions(
            capacity=2,
            stage_id="STAGE-01",
            session_ids=[second["id"], first["id"]],
        )
        self.assertEqual("issued", issued["status"])
        self.assertEqual([first["id"], second["id"]], issued["issued"])
        loaded = self.store.validate()
        self.assertEqual([], loaded["sessions.json"]["planned"])
        self.assertEqual(
            [first["id"], second["id"]],
            [session["id"] for session in loaded["sessions.json"]["issued"]],
        )
        events = [
            json.loads(line)
            for line in self.events.read_text(encoding="utf-8").splitlines()
            if line
        ]
        self.assertEqual(
            [first["id"], second["id"]],
            [
                event["payload"]["session_id"]
                for event in events
                if event["event"] == "session.issued"
            ],
        )
        issuance_events = [event for event in events if event["event"] == "session.issued"]
        self.assertEqual(1, len({event["timestamp"] for event in issuance_events}))
        self.assertEqual("sessions.dispatched", events[-1]["event"])
        self.assertEqual(issuance_events[0]["timestamp"], events[-1]["timestamp"])
        self.assertTrue(events[-1]["payload"]["all_or_nothing_request"])
        self.assertTrue(events[-1]["payload"]["atomic_batch"])

    def test_dispatch_batch_with_blocked_member_leaves_every_candidate_planned(self) -> None:
        blocked_issue = issue("QPBT-003", "planned", ["QPBT-002"])
        state = documents()
        state["issues.json"]["issues"].append(blocked_issue)
        state["stages.json"]["stages"][0]["issue_ids"].append("QPBT-003")
        eligible = planned_session("i002-reviewer-a01-eligible")
        blocked = planned_session("i003-reviewer-a01-blocked", issue_id="QPBT-003")
        state["sessions.json"]["planned"] = [eligible, blocked]
        (self.state_dir / "issues.json").write_text(
            json.dumps(state["issues.json"]), encoding="utf-8"
        )
        (self.state_dir / "stages.json").write_text(
            json.dumps(state["stages.json"]), encoding="utf-8"
        )
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )

        result = self.store.dispatch_sessions(
            capacity=1,
            stage_id="STAGE-01",
            session_ids=[blocked["id"], eligible["id"]],
        )
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["issued"])
        self.assertTrue(result["request_atomic"])
        self.assertTrue(result["blocked_batch_unchanged"])
        loaded = self.store.validate()
        self.assertEqual(
            sorted([blocked["id"], eligible["id"]]),
            sorted(row["id"] for row in loaded["sessions.json"]["planned"]),
        )
        self.assertEqual([], loaded["sessions.json"]["issued"])

    def test_dispatch_dry_run_and_cli_leave_state_unchanged(self) -> None:
        candidate = planned_session("i002-reviewer-a01-dry-run")
        state = documents()
        state["sessions.json"]["planned"] = [candidate]
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )
        parser = workflow.build_parser()
        result = workflow.run_cli(
            parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "dispatch",
                    "--capacity",
                    "1",
                    "--stage",
                    "STAGE-01",
                    "--session-id",
                    candidate["id"],
                    "--dry-run",
                ]
            )
        )
        self.assertEqual("ready", result["status"])
        self.assertTrue(result["dry_run"])
        self.assertEqual([], self.store.validate()["sessions.json"]["issued"])

    def test_dispatch_store_rejects_unknown_capacity_without_mutation(self) -> None:
        candidate = planned_session("i002-reviewer-a01-unknown-capacity")
        state = documents()
        state["sessions.json"]["planned"] = [candidate]
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )
        before_events = self.events.read_text(encoding="utf-8")
        with self.assertRaisesRegex(workflow.WorkflowError, "capacity is unknown"):
            self.store.dispatch_sessions(
                capacity=None,
                stage_id="STAGE-01",
                session_ids=[candidate["id"]],
            )
        loaded = self.store.validate()
        self.assertEqual([candidate["id"]], [row["id"] for row in loaded["sessions.json"]["planned"]])
        self.assertEqual([], loaded["sessions.json"]["issued"])
        self.assertEqual(before_events, self.events.read_text(encoding="utf-8"))

    def test_dispatch_rejects_invalid_existing_event_log_without_mutation(self) -> None:
        candidate = planned_session("i002-reviewer-a01-invalid-history")
        state = documents()
        state["sessions.json"]["planned"] = [candidate]
        sessions_path = self.state_dir / "sessions.json"
        sessions_path.write_text(json.dumps(state["sessions.json"]), encoding="utf-8")
        before_sessions = sessions_path.read_bytes()

        self.events.write_text("{bad}\n", encoding="utf-8")
        before_events = self.events.read_bytes()
        with self.assertRaises(workflow.ValidationError):
            self.store.dispatch_sessions(
                capacity=1,
                stage_id="STAGE-01",
                session_ids=[candidate["id"]],
            )
        self.assertEqual(before_sessions, sessions_path.read_bytes())
        self.assertEqual(before_events, self.events.read_bytes())

        def event(timestamp: str, name: str) -> str:
            return json.dumps(
                {
                    "schema_version": 1,
                    "timestamp": timestamp,
                    "event": name,
                    "actor": "test",
                    "pid": 1,
                    "payload": {},
                }
            )

        self.events.write_text(
            event(REVIEW_ENDED, "later") + "\n" + event(REVIEW_STARTED, "earlier") + "\n",
            encoding="utf-8",
        )
        before_events = self.events.read_bytes()
        with self.assertRaisesRegex(workflow.ValidationError, "chronological"):
            self.store.dispatch_sessions(
                capacity=1,
                stage_id="STAGE-01",
                session_ids=[candidate["id"]],
            )
        self.assertEqual(before_sessions, sessions_path.read_bytes())
        self.assertEqual(before_events, self.events.read_bytes())

    def test_dispatch_rolls_back_state_and_events_when_event_append_fails(self) -> None:
        candidate = planned_session("i002-reviewer-a01-event-rollback")
        state = documents()
        state["sessions.json"]["planned"] = [candidate]
        sessions_path = self.state_dir / "sessions.json"
        sessions_path.write_text(json.dumps(state["sessions.json"]), encoding="utf-8")
        before_sessions = sessions_path.read_bytes()
        before_events = self.events.read_bytes()
        original_append_event = self.store.append_event
        calls = 0

        def fail_on_summary(event: str, payload: object, **kwargs: object) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected append failure")
            original_append_event(event, payload, **kwargs)

        self.store.append_event = fail_on_summary  # type: ignore[method-assign]
        try:
            with self.assertRaisesRegex(RuntimeError, "injected append failure"):
                self.store.dispatch_sessions(
                    capacity=1,
                    stage_id="STAGE-01",
                    session_ids=[candidate["id"]],
                )
        finally:
            self.store.append_event = original_append_event  # type: ignore[method-assign]
        self.assertEqual(2, calls)
        self.assertEqual(before_sessions, sessions_path.read_bytes())
        self.assertEqual(before_events, self.events.read_bytes())
        loaded = self.store.validate()
        self.assertEqual([candidate["id"]], [row["id"] for row in loaded["sessions.json"]["planned"]])
        self.assertEqual([], loaded["sessions.json"]["issued"])

    def test_issue_session_wrapper_honors_capacity_and_authority_checks(self) -> None:
        candidate = planned_session("i002-reviewer-a01-legacy-wrapper")
        state = documents()
        state["sessions.json"]["planned"] = [candidate]
        sessions_path = self.state_dir / "sessions.json"
        sessions_path.write_text(json.dumps(state["sessions.json"]), encoding="utf-8")
        parser = workflow.build_parser()

        queued = workflow.run_cli(
            parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "issue-session",
                    candidate["id"],
                    "--capacity",
                    "0",
                    "--json",
                    "{}",
                ]
            )
        )
        self.assertEqual("queued", queued["status"])
        self.assertEqual([], self.store.validate()["sessions.json"]["issued"])

        blocked = workflow.run_cli(
            parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "issue-session",
                    candidate["id"],
                    "--capacity",
                    "1",
                    "--json",
                    json.dumps({"issue_id": "QPBT-001"}),
                ]
            )
        )
        self.assertEqual("blocked", blocked["status"])
        self.assertEqual([], self.store.validate()["sessions.json"]["issued"])

        issued = workflow.run_cli(
            parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "issue-session",
                    candidate["id"],
                    "--capacity",
                    "1",
                    "--json",
                    "{}",
                ]
            )
        )
        # Successful legacy calls retain the historical single-record shape;
        # admission metadata remains available on the dispatch command.
        self.assertEqual(candidate["id"], issued["id"])
        self.assertEqual("issued", issued["status"])
        self.assertNotIn("dispatchable", issued)
        self.assertNotIn("queued", issued)
        self.assertEqual(
            [candidate["id"]],
            [row["id"] for row in self.store.validate()["sessions.json"]["issued"]],
        )

    def test_issue_session_parser_requires_explicit_capacity(self) -> None:
        parser = workflow.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "issue-session",
                    "i002-reviewer-a01-parser-capacity",
                    "--json",
                    "{}",
                ]
            )

    def test_atomic_mutation_preserves_metadata_and_appends_event(self) -> None:
        def mutate(document: dict[str, object]) -> None:
            document["issues"][1]["title"] = "updated"

        self.store.mutate("issues.json", "record.updated", {"id": "QPBT-002"}, mutate)
        loaded = self.store.validate()
        self.assertEqual("keep", loaded["issues.json"]["issues"][1]["note"])
        entries = [json.loads(line) for line in self.events.read_text(encoding="utf-8").splitlines() if line]
        self.assertEqual("record.updated", entries[-1]["event"])
        leftovers = list(self.state_dir.glob(".*.tmp"))
        self.assertEqual([], leftovers)

    def test_pr_head_change_invalidates_approval_and_id_is_immutable(self) -> None:
        state = documents()
        state["prs.json"]["pull_requests"] = [pull_request()]
        add_pr_sessions(state)
        (self.state_dir / "prs.json").write_text(json.dumps(state["prs.json"]), encoding="utf-8")
        (self.state_dir / "sessions.json").write_text(json.dumps(state["sessions.json"]), encoding="utf-8")
        parser = workflow.build_parser()
        arguments = parser.parse_args(
            ["--root", str(self.root), "update", "pr", "LPR-001", "--set", f"head_sha={json.dumps('c' * 40)}"]
        )
        result = workflow.run_cli(arguments)
        self.assertEqual("changes_requested", result["status"])
        arguments = parser.parse_args(
            ["--root", str(self.root), "update", "pr", "LPR-001", "--set", "id=LPR-002"]
        )
        with self.assertRaises(workflow.WorkflowError):
            workflow.run_cli(arguments)

    def test_generic_update_cannot_mutate_status(self) -> None:
        parser = workflow.build_parser()
        arguments = parser.parse_args(
            ["--root", str(self.root), "update", "issue", "QPBT-002", "--set", 'status="done"']
        )
        with self.assertRaisesRegex(workflow.WorkflowError, "immutable field.*status"):
            workflow.run_cli(arguments)

        category = parser.parse_args(
            [
                "--root",
                str(self.root),
                "update",
                "issue",
                "QPBT-002",
                "--set",
                'execution_category="preflight"',
            ]
        )
        with self.assertRaisesRegex(workflow.WorkflowError, "immutable field.*execution_category"):
            workflow.run_cli(category)

    def test_generic_update_cannot_rewrite_attempt_authority_or_pr_evidence(self) -> None:
        state = documents()
        state["prs.json"]["pull_requests"] = [pull_request()]
        add_pr_sessions(state)
        (self.state_dir / "prs.json").write_text(json.dumps(state["prs.json"]), encoding="utf-8")
        (self.state_dir / "sessions.json").write_text(json.dumps(state["sessions.json"]), encoding="utf-8")
        parser = workflow.build_parser()

        authority = parser.parse_args(
            [
                "--root",
                str(self.root),
                "update",
                "issued-session",
                "i002-prover-a01-implementation",
                "--set",
                "read_only=true",
            ]
        )
        with self.assertRaisesRegex(workflow.WorkflowError, "authority field 'read_only' is immutable"):
            workflow.run_cli(authority)

        rewritten_reviews = [review_evidence(verdict="request_changes")]
        evidence = parser.parse_args(
            [
                "--root",
                str(self.root),
                "update",
                "pr",
                "LPR-001",
                "--set",
                f"reviews={json.dumps(rewritten_reviews)}",
            ]
        )
        with self.assertRaisesRegex(workflow.WorkflowError, "reviews.*append-only"):
            workflow.run_cli(evidence)

    def test_approval_and_merge_transitions_require_current_evidence(self) -> None:
        state = documents()
        state["prs.json"]["pull_requests"] = [pull_request(status="ready", reviews=[])]
        add_pr_sessions(state)
        (self.state_dir / "prs.json").write_text(json.dumps(state["prs.json"]), encoding="utf-8")
        (self.state_dir / "sessions.json").write_text(json.dumps(state["sessions.json"]), encoding="utf-8")
        parser = workflow.build_parser()
        approve = parser.parse_args(
            ["--root", str(self.root), "transition", "pr", "LPR-001", "approved"]
        )
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.run_cli(approve)
        self.assertIn("requires a current approving review", str(caught.exception))

        state["prs.json"]["pull_requests"] = [pull_request()]
        (self.state_dir / "prs.json").write_text(json.dumps(state["prs.json"]), encoding="utf-8")
        merge = parser.parse_args(
            ["--root", str(self.root), "transition", "pr", "LPR-001", "merged"]
        )
        with self.assertRaises(workflow.ValidationError) as caught:
            workflow.run_cli(merge)
        self.assertIn("integration_sha", str(caught.exception))

        integration_sha = "d" * 40
        update = parser.parse_args(
            [
                "--root",
                str(self.root),
                "update",
                "pr",
                "LPR-001",
                "--set",
                f"integration_sha={json.dumps(integration_sha)}",
            ]
        )
        workflow.run_cli(update)
        result = workflow.run_cli(merge)
        self.assertEqual("merged", result["status"])
        self.assertIsNotNone(result["merged_at"])

    def test_issue_and_transition_events_use_canonical_session_id(self) -> None:
        session_id = "i002-reviewer-a01-lifecycle"
        planned = {
            "id": session_id,
            "name": session_id,
            "role": "reviewer",
            "issue_id": "QPBT-002",
            "status": "planned",
            "parent_session_id": None,
        }
        issued = issued_session(
            session_id,
            role="reviewer",
            status="issued",
            read_only=True,
            started_at=None,
            ended_at=None,
            elapsed_seconds=None,
        )
        issued["outcome_path"] = ".workflow-runtime/runs/lifecycle/result.json"
        state = documents()
        state["sessions.json"]["planned"] = [planned]
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )
        parser = workflow.build_parser()
        issue_arguments = parser.parse_args(
            [
                "--root",
                str(self.root),
                "issue-session",
                session_id,
                "--capacity",
                "1",
                "--json",
                json.dumps(issued),
            ]
        )
        workflow.run_cli(issue_arguments)
        for status in ("running", "finished", "archived"):
            transition = parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "transition",
                    "issued-session",
                    session_id,
                    status,
                ]
            )
            workflow.run_cli(transition)
        self.store.validate()
        events = [
            json.loads(line)
            for line in self.events.read_text(encoding="utf-8").splitlines()
            if line
        ]
        lifecycle = [
            event for event in events if event["event"] in {"session.issued", "record.transitioned"}
        ]
        self.assertEqual(4, len(lifecycle))
        for event in lifecycle:
            self.assertEqual(session_id, event["payload"]["session_id"])
            self.assertNotIn("id", event["payload"])

    def test_failed_session_transition_reconciles_with_canonical_session_id(self) -> None:
        session_id = "i002-reviewer-a02-lifecycle-failure"
        session = issued_session(
            session_id,
            status="issued",
            read_only=True,
            started_at=None,
            ended_at=None,
            elapsed_seconds=None,
        )
        session["outcome_path"] = ".workflow-runtime/runs/lifecycle-failure/result.json"
        state = documents()
        state["sessions.json"]["issued"] = [session]
        (self.state_dir / "sessions.json").write_text(
            json.dumps(state["sessions.json"]), encoding="utf-8"
        )
        self.store.append_event("session.issued", {"session_id": session_id})
        parser = workflow.build_parser()
        for status in ("failed", "archived"):
            transition = parser.parse_args(
                [
                    "--root",
                    str(self.root),
                    "transition",
                    "issued-session",
                    session_id,
                    status,
                ]
            )
            workflow.run_cli(transition)
        self.store.validate()


class ResearchReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = documents()
        session = issued_session("i002-reviewer-a01-metric", read_only=True)
        self.state["sessions.json"]["issued"] = [session]
        self.state["stages.json"]["stages"][0]["subagents_issued"] = 1
        metrics = self.root / "research" / "metrics"
        metrics.mkdir(parents=True)
        (metrics / "incidents.jsonl").write_text('{"id":"INC-001"}\n', encoding="utf-8")
        (metrics / "protocol_changes.jsonl").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def validate_metric(self, **updates: object) -> None:
        metric = {
            "session_id": "i002-reviewer-a01-metric",
            "issue_id": "QPBT-002",
            "stage_id": "STAGE-01",
        }
        metric.update(updates)
        path = self.root / "research" / "metrics" / "sessions.jsonl"
        path.write_text(json.dumps(metric) + "\n", encoding="utf-8")
        check_workflow.validate_research_ledgers(self.root, self.state)

    def test_exact_metric_and_stage_reconciliation_passes(self) -> None:
        self.validate_metric()

    def test_metric_issue_and_stage_mismatches_are_rejected(self) -> None:
        with self.assertRaisesRegex(workflow.ValidationError, "issue_id: expected"):
            self.validate_metric(issue_id="QPBT-001")
        with self.assertRaisesRegex(workflow.ValidationError, "unknown stage"):
            self.validate_metric(stage_id="STAGE-404")

    def test_duplicate_issue_to_stage_mapping_is_rejected(self) -> None:
        duplicate = copy.deepcopy(self.state["stages.json"]["stages"][0])
        duplicate["id"] = "STAGE-02"
        self.state["stages.json"]["stages"].append(duplicate)
        with self.assertRaisesRegex(workflow.ValidationError, "mapped to multiple stages"):
            self.validate_metric()

    def test_stale_stage_subagent_total_is_rejected(self) -> None:
        self.state["stages.json"]["stages"][0]["subagents_issued"] = 0
        with self.assertRaisesRegex(workflow.ValidationError, "subagents_issued: expected 1"):
            self.validate_metric()


class EventLogTests(unittest.TestCase):
    @staticmethod
    def event(timestamp: str, event: str, payload: dict[str, object] | None = None) -> str:
        return json.dumps(
            {
                "schema_version": 1,
                "timestamp": timestamp,
                "event": event,
                "actor": "test",
                "pid": 1,
                "payload": payload or {},
            }
        )

    def test_blank_lines_are_allowed_but_malformed_json_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("\n" + self.event(NOW, "ok") + "\n\n", encoding="utf-8")
            workflow.validate_event_log(path)
            path.write_text("{bad}\n", encoding="utf-8")
            with self.assertRaises(workflow.ValidationError):
                workflow.validate_event_log(path)

    def test_legacy_envelope_and_reverse_chronology_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text('{"at":"old","event":"ok"}\n', encoding="utf-8")
            with self.assertRaises(workflow.ValidationError):
                workflow.validate_event_log(path)
            path.write_text(
                self.event(REVIEW_ENDED, "later")
                + "\n"
                + self.event(REVIEW_STARTED, "earlier")
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(workflow.ValidationError, "chronological"):
                workflow.validate_event_log(path)

    def test_archived_session_requires_ordered_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            state = documents()
            session = issued_session("i002-prover-a01-lifecycle")
            state["sessions.json"]["issued"] = [session]
            path.write_text(
                self.event(
                    NOW,
                    "session.issued",
                    {"session_id": session["id"]},
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(workflow.ValidationError, "terminal event"):
                workflow.validate_event_log(path, state)

            path.write_text(
                "\n".join(
                    [
                        self.event(NOW, "session.issued", {"session_id": session["id"]}),
                        self.event(REVIEW_STARTED, "session.finished", {"session_id": session["id"]}),
                        self.event(REVIEW_ENDED, "session.archived", {"session_id": session["id"]}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            workflow.validate_event_log(path, state)


if __name__ == "__main__":
    unittest.main()
