# QPBT-021 / LPR-010 Current-Head Audit

Logical session: `i000-auditor-a44-qpbt021-current`
Audited main: `5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6`
Main tree: `544aac816db08aea60ef231bbc951992bc86f9e5`
Candidate: `2b161993ed258ee8f0bd99d591fcabdcb47ffe43`
Candidate tree: `f72a535413e8d9627654ca43a5a789632d5e83bc`
Candidate base: `7669f70be786a53ba1a0a92c1d347f5fe7544681`

This is a read-only current-head audit. No source, blueprint, canonical state,
PR, metric, or candidate files were edited. No network, Lean, Lake, cache warm,
or cache build was run.

## Immutable identity and ancestry

The candidate worktree `.workflow-runtime/worktrees/qpbt-021-rebase` is clean
on branch `issue/qpbt-021-local-mathlib-a04`; its parent is exactly the
registered old base. The candidate has five changed paths and 1,849 additions /
10 deletions relative to `7669f70`:

```
protocols/CHANGELOG.md
protocols/orchestration.md
scripts/hot_main_cache.py
tests/test_hot_main_cache.py
workflow/README.md
```

Current main is a descendant of the old base but is not the candidate head.
Current main changed all five candidate paths after that base (313 lines of
later changes), including the LPR-011 shared-runtime changes in
`scripts/hot_main_cache.py` and its tests. A direct cherry-pick or merge into
main is therefore not a clean integration operation; preserve the candidate
worktree and replay it in a new owned worktree based on current main, resolving
the five path overlaps and then freezing a new SHA/tree.

## Findings (ordered by severity)

### Blocker: F-LPR010-A06-001 remains open

The PR record (`workflow/state/prs.json:2856-2867`) records that the required
serial aggregate command failed after 180 tests with
`FileNotFoundError` for the `child-terminated` marker at
`tests/test_local_agent.py:500`, exit 1. The exact immutable review output
reports 127.575 seconds reported by unittest and 129.07 seconds wall time. The
same test failed from a clean archive of the unchanged old base, so this is a
baseline/environment failure rather than evidence against a QPBT-021 changed
path. It is nevertheless a real acceptance blocker: the registered aggregate
gate is not clean. A later checker run reported 180/180, but that does not
erase the failed exact aggregate result. Do not waive this implicitly; either
rerun the exact aggregate successfully on the frozen rebased head or record an
explicit protocol-approved baseline waiver.

No QPBT-021 fixer should modify `tests/test_local_agent.py` merely to clear this
finding. Any harness repair needs its own owner/issue and must be rebased from
current main; QPBT-021's changed paths do not include that file.

### Medium: F-LPR010-A06-002 remains open

The PR record (`workflow/state/prs.json:2818-2825`) marks this malformed command
as passed:

```
git diff --check 7669f70be786a53ba1a0a92c1d347f8f0bd99d591fcabdcb47ffe43
```

It concatenates revisions and exits 128 (`unknown revision`). The corrected
two-dot command recorded at `workflow/state/prs.json:2828-2835` passes. The
stale passed check must be reconciled by the coordinator before integration;
it is not a source-code defect.

### Informational: current canonical checker state is dirty

On current main, `python3 scripts/check_workflow.py` reported
`stages[3].subagents_issued: expected 116, got 113`, while
`python3 scripts/workflow.py validate` passed. The worktree already contains
coordinator changes in `workflow/events.jsonl` and
`workflow/state/sessions.json`; this checker discrepancy is not attributable
to the candidate and must not be used as candidate approval evidence.

## Candidate implementation and focused evidence

The candidate's local-input implementation authenticates the pinned Mathlib
commit/tree in `scripts/hot_main_cache.py:963-1061`, rejects unsafe Git metadata
before object reads, supports exactly one `MATHLIB_SOURCE` or `MATHLIB_ARCHIVE`
input at `:1636-1688`, validates the archive at `:1691-1724`, and rechecks the
source before publication at `:2093-2107`. It constructs a deterministic local
Lake map while retaining cache identity and singleton locking. The candidate
focused run completed fresh in 12.179 seconds:

```
Ran 37 tests in 12.179s
OK
```

The current main (which does not yet contain the LPR-010 local-Mathlib code)
focused suite completed 28/28 in 3.490 seconds. Existing immutable candidate
evidence also records compileall, workflow validation, corrected diff hygiene,
and a later workflow checker result of 180/180. None of these results clears
F-LPR010-A06-001 without a clean exact aggregate or explicit waiver.

## Local source, archive, and cache readiness

The pinned project provenance identifies Mathlib commit
`81a5d257c8e410db227a6665ed08f64fea08e997`; the candidate binds tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`. Available local evidence:

```
/tmp/qpbt018-mathlib-source.t8E8oS/mathlib
  HEAD 81a5d257c8e410db227a6665ed08f64fea08e997
  tree 5ea66b811b8461daae82f14d356fed2a287d7c40
  clean detached shallow source; fsck --full passed
/tmp/mathlib-81a5d257-shallow-repo.tar.gz
  bytes 51938317; sha256 c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7
/tmp/mathlib-81a5d257c8e410db227a6665ed08f64fea08e997.bundle
  sha256 a0cf67420c92a39a29fc785ad4014c5db9aa12baaf372598cb12414c7a671ffc
  git bundle verify: is okay; ref 81a5d257... HEAD
```

All eight pinned Lake package archives are present under
`.workflow-runtime/acquisitions/lake-packages-20260830/`. However,
`MATHLIB_SOURCE`, `MATHLIB_ARCHIVE`, and `LAKE_PACKAGE_ARCHIVES` are unset in
the audit environment, and no MIPStarRE archive was found under the local
acquisition directory. Current main's read-only cache status is:

```
cache_key 808d09441cd2f4c44c49597304d458ab2a78b6e4dcf6970f98603260281f69e6
main_commit 5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6
status miss
recipe qpbt-hot-main version 4
```

Therefore the singleton cache gate is not runnable yet. After a reviewed
current-head candidate, the elected warm must set exactly one authenticated
Mathlib input plus `MIPSTARRE_ARCHIVE` and `LAKE_PACKAGE_ARCHIVES`, then run
one shared-runtime `hot_main_cache.py warm` under its lock. Only the immutable
published cache may be seeded into private issue worktrees; no second builder
or shared writable `.lake/build` is admissible.

## Go / no-go and next action

**Verdict: no-go / request changes.** The candidate implementation has no new
security finding in this audit, and its focused regressions pass, but the open
blocker aggregate gate and stale ledger evidence prevent approval. A bounded
current-head repair/rebase lane is safe in a fresh owned worktree because the
candidate is clean and QPBT-021's five paths are distinct from the unrelated
baseline test. It must not cherry-pick directly onto current main.

Exact next action:

1. Rebase/replay the candidate's five paths onto `5d36cdf`, preserving the
   local Mathlib source/archive contract and LPR-011 runtime behavior.
2. Reconcile F-LPR010-A06-002 in the canonical PR record and run the exact
   focused, serial aggregate, checker, compileall, validation, and corrected
   diff gates on the frozen rebased SHA. Treat a repeated line-500 failure as
   requiring an explicit baseline waiver, not a silent pass.
3. With fresh immutable approval and all authenticated archives/environment
   inputs present, execute exactly one singleton warm, record lock/build/cache
   evidence, then seed a private issue cache.

Accounting: elapsed approximately 25 minutes including the fresh 37-test run;
Lean/Lake/build invocations 0; network requests 0; cache warm/builds 0;
subagents dispatched 0; token usage unavailable (`null`) and not estimated.
