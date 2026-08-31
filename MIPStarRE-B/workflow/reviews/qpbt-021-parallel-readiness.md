# QPBT-021 Parallel Readiness Report

Read-only scout session: `i000-scout-a26-mathlib-readiness` (QPBT-000).
Evidence was collected from the current main tree and existing candidate
worktrees. No canonical state or PR ledger was edited.

## Exact objects and reusable inputs

- Current main: `d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1`, tree
  `860c40b9c184ee30af4f3daa999c7be2c8cbeae1`.
- QPBT-021/LPR-010 candidate: branch
  `issue/qpbt-021-local-mathlib-a04`, worktree
  `.workflow-runtime/worktrees/qpbt-021-rebase`, head
  `2b161993ed258ee8f0bd99d591fcabdcb47ffe43`, tree
  `f72a535413e8d9627654ca43a5a789632d5e83bc`, base
  `7669f70be786a53ba1a0a92c1d347f5fe7544681`.
- Older pre-rebase QPBT-021 candidate remains available at
  `.workflow-runtime/worktrees/qpbt-021`:
  `54fb701176383d23e5dc1ba9d73c3cb53e06e1d6` (tree
  `2f9fa93ffe961addab7ca9dcd33b169220b2aa13`). It is provenance only; it is
  based on `687e182`, not current main.
- Authenticated local Mathlib Git source:
  `/tmp/qpbt018-mathlib-source.t8E8oS/mathlib`, commit
  `81a5d257c8e410db227a6665ed08f64fea08e997`, tree
  `5ea66b811b8461daae82f14d356fed2a287d7c40`, clean shallow repository,
  `git fsck --full` passed. Pack SHA-256 is
  `4659f2a0cabfec474474f5e83ea3d495e711b735418742dd3d642328adcada02`.
- Normalized source archive:
  `/tmp/mathlib-81a5d257-shallow-repo.tar.gz`, SHA-256
  `c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`.
- Authenticated Lake package archives are in
  `.workflow-runtime/acquisitions/lake-packages-20260830/` (the eight files
  named by `references/lake-packages.json`).

The usable candidate commands are the exact local-input forms documented in
`.workflow-runtime/worktrees/qpbt-021-rebase/protocols/orchestration.md`:
`MATHLIB_SOURCE=/absolute/path/to/mathlib` or
`MATHLIB_ARCHIVE=/absolute/path/to/mathlib-81a5d257-shallow-repo.tar.gz`,
`LAKE_PACKAGE_ARCHIVES=/home/drx/MIPStarRE-auto/.workflow-runtime/acquisitions/lake-packages-20260830`,
then the candidate's absolute `scripts/hot_main_cache.py ... warm` command.
The warm must be elected through the shared default runtime and singleton
`flock`; do not start a second builder or share a writable `.lake/build`.

## Blocker and ownership boundary

LPR-010 is `changes_requested` at head `2b161993...`. Existing immutable review
`review-qpbt-021-a06-immutable` reports:

1. blocker `F-LPR010-A06-001`: the registered serial aggregate command failed
   at `tests/test_local_agent.py:500` (`child-terminated` marker missing), and
   the same failure reproduced on clean base `7669f70...`; this is an
   acceptance blocker despite a later 180/180 rerun;
2. medium `F-LPR010-A06-002`: an earlier malformed diff-check command was
   recorded as passed (the corrected binding passes).

The aggregate failure is outside the QPBT-021 changed paths but repairing it
would require `tests/test_local_agent.py` (and possibly
`scripts/local_agent.py`). Those are owned by the active QPBT-020 session
(`scripts/local_agent.py`, `tests/test_local_agent.py`, plus its protocol and
workflow files). Therefore no QPBT-021 writable fixer may touch those files
until QPBT-020 is integrated or its ownership lease is explicitly released.
Rebase QPBT-021 onto the then-current main before any such harness repair.
The QPBT-021 cache implementation paths (`scripts/hot_main_cache.py`,
`tests/test_hot_main_cache.py`, `protocols/CHANGELOG.md`,
`protocols/orchestration.md`, `workflow/README.md`) are otherwise disjoint
from QPBT-020 and can be audited or repaired independently.

## Shortest safe parallel path

1. While QPBT-020's fresh review/fix lane is active, issue only read-only
   QPBT-021 source/archive and candidate audits; do not issue a writable
   QPBT-021 fixer against the shared candidate.
2. After QPBT-020 is approved/integrated, rebase a new QPBT-021 fixer from
   `main`, preserving the exact local Mathlib inputs above. First repair the
   aggregate test's process-group/marker race in its now-free owner scope,
   then address the malformed historical check by immutable ledger disposition.
3. Run the exact focused, serial aggregate, checker, compileall, workflow
   validation, and diff-check commands on the frozen new head. Execute one
   authenticated singleton warm with the local source/archive and eight Lake
   archives; record cache lock wait/build/result evidence.
4. Dispatch a fresh immutable reviewer only after the new head and all checks
   are frozen. LPR-010 cannot be approved from the existing head solely by
   repeating a flaky aggregate run unless the acceptance protocol records an
   explicit baseline waiver, which is not currently present.

QPBT-018/LPR-007 is not an independent implementation lane: its required
singleton warm is blocked by the same local Mathlib acquisition gate. Its
candidate remains `e21c9cda11803f7564a500c005fd55882530538d` (tree
`a64c98c23f34416f60cf9c9127655ed108f3e64e`) in `/tmp/qpbt018-review-clone`,
with no code findings but a blocked warm. It can receive a read-only review
after QPBT-021's warm succeeds, but must not run a competing warm.

## Immediate independent work after QPBT-020

- QPBT-021: one orchestrated fixer/reviewer pair, with disjoint cache files;
  defer any `test_local_agent.py` repair until QPBT-020 ownership ends.
- QPBT-018: read-only acceptance preparation and exact-input audit only;
  integration remains dependent on QPBT-021.
- Formalization issues QPBT-013 onward remain dependency-blocked by QPBT-004
  and are not dispatchable (`workflow.py ready` currently returns no rows).

## Commands and accounting

Read-only commands used included `git worktree list --porcelain`, exact
`git -C ... rev-parse HEAD HEAD^{tree}`, `git status --short`, `git log`,
`git diff --name-status`, `find`, `sha256sum`, `sed`/`nl`, `rg`, and
`python3 scripts/workflow.py show issue/pr` plus `workflow.py ready`.
No Lean, Lake, build, cache warm, or network command was run. Network count:
`0`; build/Lake count: `0`; file edits outside this worker-owned report:
`0`. Scout elapsed time was approximately 9 minutes (first timestamp
`2026-08-31T08:11Z`, report completed `2026-08-31T08:20Z`); collaboration token
usage is unavailable and is intentionally not estimated.
