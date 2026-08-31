# Stage 04A Approved-Queue Scout

Logical session: `i000-scout-a32-approved-queue` (read-only under `QPBT-000`).
Main inspected at `d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1`, tree
`860c40b9c184ee30af4f3daa999c7be2c8cbeae1`. No files, state ledgers, Git
refs, caches, or worktrees were modified. No network, Lean, Lake, or build
commands were run.

## PR inventory

| PR | Status and immutable head | Base / integration fact | Exact changed paths | Queue finding |
| --- | --- | --- | --- | --- |
| LPR-001 / QPBT-010 | `ready`; head `e93d949d06af2a7f4407d198a37aad315deac6aa` | base `77aa1a4ac947c1632ea57262d29d2753ba163c8a`; fresh immutable review `review-qpbt-010-a04-immutable` approved with no findings | `scripts/reference_transport.py`, `tests/test_reference_transport.py`, `workflow/reviews/qpbt-010-reference-transport.md` | First transport prerequisite. It is not yet integrated despite approval. |
| LPR-002 / QPBT-002 | `approved`; head `63037ddceada7a88436f9afa9ed1ef4d74319098` | base exactly LPR-001 head `e93d949...`; fresh immutable review `review-qpbt-002-a20-reference-recovery-immutable` approved | `scripts/reference_source.py`, `tests/test_reference_source.py`, `references/2001.04383v3/source-pin.json`, `split-manifest.json`, `RIGHTS.md`, `QPBT_SOURCE_MAP.md`, `workflow/reviews/qpbt-002-reference-split.md` | Must follow LPR-001. QPBT-002 remains blocked in the issue ledger only because QPBT-010 has not been integrated/disposed. |
| LPR-003 / QPBT-012 | `merged`; head `67ead7513109a4dd76ba367c1368f7d7c4e364f3`, integration `9755f1749d9db75449a48a2d0bffea5dc2a6979d` | `9755f17` is an ancestor of current main (`d9dd6f2`); no new integration is needed | `scripts/local_agent.py`, `scripts/workflow.py`, `scripts/check_workflow.py`, `tests/test_local_agent.py`, `tests/test_workflow.py`, review doc | Already present through the current main ancestry; include only as provenance in the second-commit reconciliation. |
| LPR-004 / QPBT-003+009 | `approved`; head `3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd` | base `77aa1a4ac947c1632ea57262d29d2753ba163c8a`; fresh full immutable blueprint review `review-qpbt-003-a30-full-blueprint-immutable` approved | 55 blueprint files under `blueprint/` (chapters, generated entries/graph, metadata, checker, tests) | Can apply after LPR-002; no changed-path overlap with LPR-001/002. This is the blueprint half of the required second main commit. |
| LPR-009 / QPBT-020 | `approved`; head `e0bab14a1489e1b7344dfef63061f515ca0db0b2`; base `7669f70be786a53ba1a0a92c1d347f5fe7544681`; review `review-qpbt-020-a08-immutable` approved | candidate worktree `/tmp/qpbt020-fix-a06`; current main contains the base and QPBT-022's later cache changes | `protocols/CHANGELOG.md`, `protocols/orchestration.md`, `scripts/local_agent.py`, `tests/test_local_agent.py`, `workflow/README.md` | Integrate after the source/blueprint ranges or immediately onto current main. It overlaps LPR-011 only at `protocols/CHANGELOG.md`; inspect the two append-only hunks before integration. |
| LPR-010 / QPBT-021 | `changes_requested`; head `2b161993ed258ee8f0bd99d591fcabdcb47ffe43` | base `7669f70...`; immutable review `review-qpbt-021-a06-immutable` blocked on baseline aggregate failure at `tests/test_local_agent.py:500` | `protocols/CHANGELOG.md`, `protocols/orchestration.md`, `scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`, `workflow/README.md` | Do not integrate. Rebase a changed candidate after LPR-009 and current cache changes; its hot-cache paths overlap LPR-011 and its baseline test blocker overlaps LPR-009 ownership. |
| LPR-011 / QPBT-022 | `merged`; head/integration `d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1` | base `7669f70...`; fresh immutable review approved | `scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`, `protocols/local-development.md`, `protocols/CHANGELOG.md` | Already current main. Its cache singleton/runtime behavior is the base for all future warm/seed gates. |

## Second-main-commit order

The QPBT-003 issue records a disposable rehearsal of the exact ranges
QPBT-010, QPBT-002, QPBT-012, and the blueprint. The safe real-tree order is:

1. Apply approved LPR-001 (`e93d949...`) to current main.
2. Apply LPR-002 (`63037dd...`) next; its declared base is exactly LPR-001's
   head, and it supplies the authenticated split manifest/source map required
   by QPBT-003.
3. Reconcile LPR-003/QPBT-012 as already integrated by ancestor `9755f17`; do
   not cherry-pick `67ead751...` a second time.
4. Apply LPR-004 (`3f4d4b3...`) for the 55-file blueprint range. It is based on
   the old first commit but has no path overlap with LPR-001/002.
5. Run the combined second-commit gates and create one new main commit. The
   rehearsal evidence reports zero conflicts/overlaps and passing 191 aggregate
   tests, source checks, 26 blueprint tests, graph/PDF, compile, workflow, and
   hygiene checks; the real tree must reproduce those exact commands on the
   resulting snapshot.

LPR-009 can be integrated as a separate approved current-main operation before
or after this range, but the resulting head must be recorded before any new
QPBT-021 rebase. Because LPR-009 changes `protocols/CHANGELOG.md`, inspect the
append-only QPBT-022 and QPBT-020 entries rather than auto-accepting a conflict.
LPR-010 cannot be prepared from its frozen head: its cache files changed in
LPR-011 and its process-timeout finding requires files owned by LPR-009.

## Why no concurrent approved integration wave exists

LPR-001 and LPR-002 are dependency-ordered, and LPR-004 is the dependent
blueprint closure; Git integration should be serialized by the coordinator even
though their disjoint path sets make the resulting merge mechanically simple.
LPR-011 is already integrated. LPR-009 is the only remaining approved writer,
but it shares protocol text with LPR-011 and must be imported/validated as one
immutable head. Thus the safe speed-up is parallel read-only review/preflight,
not concurrent writes to main. Once the second commit and LPR-009 are in main,
QPBT-004 must be rebound to that exact current head because LPR-005's recorded
integration `687e182` predates the package/cache fixes and its singleton
cache-get/Lake build gate was never executed.

## Required validation and blockers

For LPR-001/002/004 integration, run the registered exact focused tests and
source/blueprint checks, then `python3 scripts/check_workflow.py`,
`python3 -m compileall -q scripts tests`, `python3 scripts/workflow.py validate`,
and `git diff --check`. Re-run the blueprint declaration/source synchronization,
graph, and forced PDF checks for LPR-004. The QPBT-004 rebinding then requires
one elected `python3 scripts/hot_main_cache.py warm` using the authenticated
local Mathlib source plus the eight local Lake archives, followed by private
`seed --worktree PATH`; no duplicate warm or shared writable `.lake/build` is
permitted.

Current issue blockers remain: QPBT-002 waits for LPR-001 integration; QPBT-003
waits for the full second commit; QPBT-004 is planned with an unexecuted cache
gate; QPBT-021 is blocked on its baseline aggregate finding. `workflow.py ready`
therefore must not be bypassed by issuing implementation writers early.

Scout accounting: approximately 7 minutes elapsed (`2026-08-31T08:46Z` to
`2026-08-31T08:53Z`), network 0, Lean/Lake/build/cache actions 0, subagents 0,
canonical edits 0. Token usage is unavailable from the collaboration backend
and is intentionally recorded without estimation.
