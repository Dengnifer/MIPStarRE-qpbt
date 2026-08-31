# QPBT-004 / LPR-005 Cache-Gate Audit

Logical session: `i000-auditor-a41-q004-gate`
Audited main: `8bf8ee89d24d833c28ecce6ce7e08c42e28b614f`
Scope: QPBT-004/LPR-005 finding status, current cache readiness, and safe
next dispatch. This is a read-only audit; no source/state files were changed.

## Snapshot and ledger

```
HEAD 8bf8ee89d24d833c28ecce6ce7e08c42e28b614f
tree 65315213d047d9181804ad74d573f533c904ef4f
parent 74011bb473b30b32b696c9e6a6bcb744519f735c
chore(workflow): record canonical source and blueprint integration
```

The worktree was already dirty in `workflow/events.jsonl`,
`workflow/state/sessions.json`, and `workflow/state/stages.json`; those changes
were preserved. `python3 scripts/workflow.py validate` passed (`valid: true`,
23 issues, 11 PRs, 242 issued sessions, 7 stages).

QPBT-004 remains `planned` with dependency `QPBT-003`. QPBT-003 remains
`blocked` on QPBT-002 and QPBT-009 despite its recorded combined-tree rehearsal.
QPBT-002 is blocked on the endpoint-specific QPBT-010 disposition; QPBT-009 is
blocked on the generated QPBT-002 source base. QPBT-021 is blocked pending a
local pinned Mathlib source, and QPBT-018 is in `review` for the detached-clone
EXDEV fallback.

LPR-005 is recorded `merged` with approved candidate head
`4de452495228aad3debe05f166097e746b97b2e5` but integration SHA
`687e182c7ad41520c226a59160c084ab53ad6f38`. The approved head is not an
ancestor of current main. Current main contains the LPR-005 package/cache
implementation through that integration plus later LPR-011 changes to the
same hot-cache file. This provenance mismatch requires reconciliation before
claiming a fresh current-head acceptance gate.

## Finding disposition

Both formal high findings are fixed in the current implementation bytes:

- **F-LPR005-001 (high, resolved):**
  `scripts/hot_main_cache.py:1112-1119` invokes the identity-bound package
  verifier after the dependency/build commands and before staging `.lake` for
  publication. The regression is recorded as
  `HotMainCacheTests.test_warm_rejects_post_build_package_drift`; the approved
  repair review reports hot-cache tests `23/23`, package tests `25/25`, and
  aggregate workflow `129` tests/state valid.
- **F-LPR005-002 (high, resolved):**
  `scripts/materialize_lake_packages.py:1073-1117` locks the stable runtime
  directory, opens the lock with `O_NOFOLLOW`, and compares descriptor/path
  device and inode plus regular-file/single-link properties before yielding.
  The regression is recorded as
  `LakePackageMaterializationTests.test_replaced_lock_path_cannot_admit_concurrent_materializer`.

The current main package-materializer file is byte-identical to the approved
`4de4524` file. `scripts/hot_main_cache.py` differs only by the later LPR-011
default-runtime resolver additions, while retaining the post-build verifier.
No bounded QPBT-004 repair should be issued for these findings; reimplementing
them would duplicate already integrated fixes. A fresh immutable current-head
review remains appropriate because the formal approval was bound to `4de4524`,
not to current main.

## Cache readiness and singleton timing

The read-only command
`python3 scripts/hot_main_cache.py --repo-root /home/drx/MIPStarRE-auto status`
returned:

```
cache_key 3fa95377cec037d0036c6495919f3935af5cdce687a36410dcf438d8d046f534
main_commit 8bf8ee89d24d833c28ecce6ce7e08c42e28b614f
status miss
recipe qpbt-hot-main version 4
```

The identity binds the main SHA, three Lean/Lake pin hashes, five additional
materializer/provenance files, package materialize/verify commands, and the
exact `lake --packages=.lake/package-overrides.json` argv. The snapshot is not
READY. `MIPSTARRE_ARCHIVE` and `LAKE_PACKAGE_ARCHIVES` were both absent in the
audit environment.

The prior cache-gate audit (`i004-auditor-a36-cache-gate`) measured a per-key
`flock` election and a dry-run result `would_build`, but did not build. Its
recheck (`i004-auditor-a36-cache-gate-recheck`) found all eight pinned package
archives matching, but no MIPStarRE archive or Mathlib source/artifact; a
real warm probe failed closed in 1.3 seconds with exit 128, `Invalid
cross-device link`, and published no READY artifact. That failure is INC-032
and remains open pending QPBT-018’s bounded clone fallback. No singleton warm
or Lake build has ever been accepted for the current main key.

The exact QPBT-004 unexecuted gate is recorded in the PR:

> Lean 4.32.0, exact Mathlib, and all eight authenticated package facts must be
> present; independent package/cache review must pass before the singleton
> cache-get and Lake build gates may run.

When ready, one elected `hot_main_cache.py warm` must run with authenticated
`MIPSTARRE_ARCHIVE` and `LAKE_PACKAGE_ARCHIVES`, after QPBT-018’s EXDEV fix and
QPBT-021’s local Mathlib source are accepted. Waiters may reuse the immutable
cache; no second builder or direct writable `.lake/build` sharing is admissible.

## Other unresolved operational evidence

- **High operational blocker, INC-032 / QPBT-018:** local clone hard-link
  creation fails with EXDEV in this environment. Do not invoke the real warm
  until the independently reviewed object-copy fallback is merged and its
  exact singleton warm gate is run.
- **High acceptance blocker, QPBT-021:** no authenticated local Mathlib source
  or artifact is present; the cache recipe cannot satisfy its exact offline
  dependency input.
- **Medium protocol debt, INC-033 / QPBT-017:**
  `protocols/local-development.md:29-36` lists only three pin hashes and the
  dependency/build commands, omitting package materialization/verification,
  five additional identity files, and both archive environment prerequisites.
  QPBT-017 is correctly dependent on QPBT-004 and should not be dispatched
  ahead of that gate.
- **Ledger/provenance risk:** QPBT-004’s blocked reason still names the old
  `b92935e` findings even though both are resolved and current main has the
  repaired code. The coordinator should reconcile issue/PR statuses and
  current-head evidence rather than opening a duplicate repair issue.

## Safe parallelization and exact next action

No QPBT-004 implementation work is currently issuable: its dependency chain
and cache prerequisites are incomplete, and its two findings are already fixed
in-tree. QPBT-018 (clone portability) and QPBT-021 (local Mathlib input) have
disjoint owned paths and may proceed as separate implementation/review lanes
under the explicit aggregate collaboration capacity, but neither may share
the cache build or mutate the main worktree. QPBT-017 remains queued behind
QPBT-004.

The smallest safe next action is:

1. Reconcile QPBT-002/QPBT-003/QPBT-004 and LPR-005 against current main,
   recording F-LPR005-001/002 as fixed and preserving the immutable
   `4de4524` review provenance.
2. Complete independent approval of QPBT-018 and QPBT-021, supplying the
   EXDEV-safe clone path, local Mathlib source, and both archive inputs.
3. Issue one fresh immutable current-head cache/package reviewer; if it passes,
   execute the singleton `hot_main_cache.py warm` exactly once, then seed a
   private issue cache and run the exact empty-project Lake build gate.

Audit accounting: source edits 0, canonical state edits 0, subagents dispatched
0, Lean/Lake/build invocations 0, network requests 0; token usage unavailable
for this collaboration session.
