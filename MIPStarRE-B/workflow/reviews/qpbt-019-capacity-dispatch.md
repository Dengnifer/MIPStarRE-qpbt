# QPBT-019 Capacity-Aware Dispatch Candidate

Candidate evidence for the immutable review of QPBT-019.

- Base commit: `687e182c7ad41520c226a59160c084ab53ad6f38`
- Candidate commit: `e6c3ecae625cce065ef8a6df685afe28709ab412`
- Candidate tree: `6a19a836eeb78932e5babdad300536d100bc856e`
- Candidate worktree: `.workflow-runtime/worktrees/qpbt-019`
- Changed paths: `protocols/CHANGELOG.md`, `protocols/orchestration.md`, `scripts/workflow.py`, `tests/test_workflow.py`, `workflow/README.md`

## Acceptance checks

- Focused workflow tests: `python3 -m unittest discover -s tests -p 'test_workflow.py'` -- 54 passed.
- Aggregate workflow tests: `python3 -m unittest discover -s tests -p 'test_*.py'` -- 161 passed in 107.139 seconds of unittest time (105.04 seconds wall time reported by the candidate run).
- Workflow checker: `python3 tests/test_check_workflow.py` -- 3 passed.
- Python compilation: `python3 -m compileall -q scripts tests` -- passed.
- Diff hygiene: `git diff --check 687e182c7ad41520c226a59160c084ab53ad6f38..e6c3ecae625cce065ef8a6df685afe28709ab412` -- passed.
- Candidate worktree was clean at the reviewed commit.

The issued session's historical validation command used the package-style
`python3 -m unittest tests.test_workflow -v`, which fails because this test
tree is not a Python package. The correct discover command above was run and
passed; the stale command is retained as provenance and is tracked by the
existing workflow incident ledger.

## Behavioral scope

The candidate computes dependency readiness, active leases, backend capacity,
and writable ownership under the workflow lock. It deterministically sorts
candidate IDs, admits only a capacity prefix, rejects unknown capacity, and
validates cross-candidate conflicts before admission. Batch state and event
append operations roll back to exact pre-mutation bytes on validation or append
failure. Legacy `issue-session` admission is capacity-gated. Overrides cannot
rewrite planned authority, PR binding, or external identity.

Crash-time external Codex launch journaling is intentionally deferred to
QPBT-020; this candidate covers synchronous mutation and append failures.

No external endpoint review has been requested or supplied. The independent
local immutable reviewer must inspect this exact base/head pair and return an
append-only verdict before the issue can advance.

## Review round 1: request changes

Reviewer session: `i019-reviewer-a03-capacity-dispatch` (fresh logical
reviewer, physical worker recycled from the preflight lane).

Checks on the unchanged candidate passed: 54 focused workflow tests, 161
aggregate tests, 3 workflow-checker tests, compileall, and diff hygiene. The
reviewer found these blockers:

1. `plan_dispatch` admits two planned `role=orchestrator` sessions for the
   same issue when the issue is still planned. This can create duplicate active
   orchestrators and violates the no-duplicate-attempt contract.
2. Unknown capacity is rejected before ownership analysis, so a caller cannot
   receive the required independent DAG and writable-ownership diagnostics in
   the same fail-closed plan.

Compatibility/design findings requiring an explicit disposition:

3. Capacity is intentionally aggregate across all backends (`backend_scope:
   all`); the protocol must state that this is the local service ceiling rather
   than a per-backend quota.
4. The compatibility `issue-session` wrapper now returns a planner envelope
   rather than the historical issued-record shape; callers and tests need an
   explicit contract.

The reviewer also identified a malformed mixed-shape override object that the
parser should reject rather than silently treating as a single record. No
candidate files were changed. The PR remains `changes_requested` pending a
new immutable head and review round.

## Review round 2: approved

Retry session `i019-orchestrator-a02-admission-fix` produced immutable head
`7669f70be786a53ba1a0a92c1d347f5fe7544681` with tree
`48f451bc82f2037abe09e9d97130fdb4d0cbdd53`. The five-path scope was unchanged.
It rejects a second planned or active orchestrator for an issue, collects DAG
and ownership diagnostics before unknown-capacity failure, documents aggregate
all-backend capacity, restores the successful compatibility return shape, and
rejects mixed override shapes.

The retry passed 59 focused workflow tests in 0.752 seconds, 166 aggregate
tests in 129.192 seconds, three checker tests in 0.021 seconds, compilation,
workflow validation, and diff hygiene. Fresh reviewer session
`i019-reviewer-a04-admission-fix` repeated the gates against the exact head
(59 focused in 0.719 seconds and 166 aggregate in 130.938 seconds) and approved
with no findings. All five round-one findings are resolved in LPR-008.

## Local integration

LPR-008 fast-forwarded `main` from
`687e182c7ad41520c226a59160c084ab53ad6f38` to the approved head
`7669f70be786a53ba1a0a92c1d347f5fe7544681`. The post-integration gate passed:
59 focused tests, 166 aggregate tests in 111.220 seconds, three checker tests,
compilation, workflow validation, and diff hygiene. The PR is `merged` and
QPBT-019 is `done`. Crash-time child launch journaling remains owned by
QPBT-020 and was not folded into this accepted scope.
