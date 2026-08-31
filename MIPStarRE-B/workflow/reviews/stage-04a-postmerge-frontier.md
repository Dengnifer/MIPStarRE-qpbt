# Stage 04A Post-QPBT-020 Frontier

Read-only scout session: `i000-scout-a34-frontier-postmerge`.
Main snapshot is `e2446272a3cc904a612d7e0e5003074ef4a680ad`, tree
`6506703b5dcf2abd20b00cd7bd454a6b79ec0534`, parent `4bfdd120bda296691569fc2743a94454eca9b723`.
The QPBT-020 merge is recorded, and `QPBT-020`/LPR-009 is now `done`/`merged`
at integration `4bfdd120...`; QPBT-022/LPR-011 remains merged in its ancestor
`d9dd6f2...`.

The current main checkout still has no materialized
`references/2001.04383v3/sections`, `blueprint/src/chapter`, or
`MIPStarRE/QPBT` files. The authoritative ignored inputs remain in
`.workflow-runtime/worktrees/qpbt-002` (split source),
`.workflow-runtime/worktrees/stage-02-03` (blueprint commit
`3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd`), and
`.workflow-runtime/worktrees/qpbt-004` (foundation candidate
`4de452495228aad3debe05f166097e746b97b2e5`).

## Immediate queue

1. **LPR-001/QPBT-010, then LPR-002/QPBT-002.** LPR-001 head
   `e93d949d06af2a7f4407d198a37aad315deac6aa` is reviewed/ready, base
   `77aa1a4...`; LPR-002 head `63037ddceada7a88436f9afa9ed1ef4d74319098`
   is approved and has exact base LPR-001's head. Their path sets are
   disjoint, but the base edge requires serial integration. LPR-001 adds
   `scripts/reference_transport.py`, its focused tests, and review evidence;
   LPR-002 adds `scripts/reference_source.py`, pinned source manifests/rights/
   source map, focused tests, and review evidence.
2. **LPR-004/QPBT-003+009.** Approved head
   `3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd`, base `77aa1a4...`, with 55
   blueprint files. It has no path overlap with LPR-001/002 and should follow
   the source split. The second-main-commit issue requires the resulting
   source/blueprint ranges plus already-ancestral QPBT-012 (`9755f17`).
3. **QPBT-021/LPR-010 repair.** QPBT-020 ownership is now released, so its
   baseline blocker at `tests/test_local_agent.py:500` can be repaired in a
   fresh candidate. The frozen LPR-010 head `2b161993...` must not be reused:
   rebase after `e244627...` (and after any LPR-001/002/004 changes), then fix
   the process-timeout setup race and obtain a fresh immutable review. Its
   cache paths overlap already-integrated LPR-011, not an active writer.

The first two are the required second-main-commit lane; QPBT-021 can be
prepared in parallel in a private worktree because LPR-001/002/004 do not
touch its six cache/protocol paths. Do not run its singleton warm until the
rebased head and review pass. QPBT-018/LPR-007 remains review/draft and is
blocked on that same local Mathlib warm, so it is audit-only and cannot launch
a competing builder.

## Post-second-commit implementation wave

After the second main commit and QPBT-004's rebinding/cache acceptance, issue
the independent first wave:

- QPBT-013 owns `MIPStarRE/QPBT/Basic/Field.lean` and
  `Basic/Approximation.lean`; source anchors are finite fields
  `finite-fields.tex:1-412` (original 1317-1728), measurements
  `measurements.tex:35-50`/F03, and strategies-distance
  `strategies-distance.tex:214-405` (original 3097-3288). Blueprint anchors:
  F01/F03/F04 in `blueprint/src/generated/chapter-02-entries.tex:2-48`.
- QPBT-017 owns only cache documentation/changelog synchronization and is
  disjoint from QPBT-013; source anchors are `scripts/hot_main_cache.py:103-168`
  and `protocols/local-development.md:19-50`.

Then keep the formal chain sequential: QPBT-014 (Polynomial/Pauli/Types/
Parameters, F02/F05/F06/F07/G01) -> QPBT-015 (MagicSquare/Verifier, F08/G02;
paper `magic-square.tex:1-368`, `qpbt-game-and-soundness.tex:1-328`) -> QPBT-016
(Extraction/Soundness, A15/S01; blueprint
`chapter-11-entries.tex:2-46`, paper A.6 `appendix-separate-xz-conclude.tex:255-446`).
Their declared dependencies prohibit parallel writable sessions despite
disjoint eventual files.

## Gates and blockers

`workflow/state/issues.json` still reports QPBT-002 and QPBT-003 blocked,
QPBT-004 planned, QPBT-021 blocked, and `workflow.py ready` is therefore not a
dispatch authorization for Lean lanes. To unblock the second commit, integrate
LPR-001 -> LPR-002 -> LPR-004, reconcile QPBT-012 as an existing ancestor, then
run the exact source split/manifest checks, blueprint 26-test/graph/PDF checks,
aggregate workflow tests, compileall, `workflow.py validate`, and
`git diff --check` before one new main commit. QPBT-004 then needs a fresh
current-main candidate and the singleton hot-main `warm` using the authenticated
local Mathlib input plus eight local Lake archives, followed by private `seed`;
no shared writable `.lake/build` is allowed.

No source/state edits, network, Lean, Lake, build, cache warm/seed, or agent
dispatch occurred. Scout elapsed approximately 6 minutes
(`2026-08-31T09:13Z` to `09:19Z`); subagents 0; token usage unavailable and not
estimated.
