# Stage 04A Next-Frontier Scout

Logical session: `i000-scout-a30-next-frontier` (fresh read-only scout under
`QPBT-000`). Main snapshot inspected: `d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1`.
The canonical checkout does not currently contain the ignored paper split,
blueprint, or materialized upstream `MIPStarRE` tree, so the source evidence
was read from the available immutable worktrees:

- split source: `.workflow-runtime/worktrees/qpbt-002/references/2001.04383v3/`
- blueprint: `.workflow-runtime/worktrees/stage-02-03/blueprint/`, commit
  `3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd`
- materialized upstream project/foundation: `.workflow-runtime/worktrees/qpbt-004/`,
  commit `4de452495228aad3debe05f166097e746b97b2e5` (tree
  `5b43ca5c46120ebc1de3e005af3ea11cd439f4cf`), based on old main
  `687e182c7ad41520c226a59160c084ab53ad6f38`.

No files other than this worker-owned report were edited. No network, Lean,
Lake, cache warm/seed, or build command was run.

## Source and blueprint spine

The pinned source map (`qpbt-002/.../QPBT_SOURCE_MAP.md:51-69,95-109`) assigns
the primary paper ranges as follows: Section 7.3 game/completeness/soundness
and binary corollary, original lines 5028-5639; canonical parameters and
complexity 5640-5766; dependencies finite fields 1317-1728, low-degree code
1729-1822, measurements 1854-1948, generalized Pauli 1949-2162,
conditionally-linear maps 2163-2877, typed games 3567-4148, classical LDT
4163-4659, and Magic Square 4660-5027. Appendix A.2-A.6 is the later
soundness spine, original lines 13196-14930.

The generated blueprint is source-faithful and gives exact declaration modules
and prerequisites. Key entries are in
`stage-02-03/blueprint/src/generated/chapter-02-entries.tex:2-108`,
`chapter-03-entries.tex:2-63`, and `chapter-11-entries.tex:2-46`.

## Safe issue sequence after QPBT-020

| Issue | Exact anchors and declarations | Owned paths | Earliest safe gate / blocker |
| --- | --- | --- | --- |
| QPBT-004 | Foundation/API materialization; blueprint F01-F10 and reusable `MIPStarRE.Quantum` imports | project/config and materialization scope recorded by LPR-005 | **Not issuable yet.** Depends on QPBT-003 and the required second main commit. Existing LPR-005 is merged at old integration `687e182`; its singleton cache-get/Lake build acceptance gate was never executed and current main is `d9dd6f2`. |
| QPBT-013 | `finite-fields.tex:1-412` (orig. 1317-1728), `measurements.tex:35-50`/F03, `strategies-distance.tex:214-405` (orig. 3097-3288); F01/F03/F04 declarations in `chapter-02-entries.tex:2-48` | `MIPStarRE/QPBT/Basic/Field.lean`, `MIPStarRE/QPBT/Basic/Approximation.lean` | Can issue only after QPBT-004 is done and a private cache is seeded. Type-check both files, declaration-integrity scan, no `sorry`/axiom/constant. |
| QPBT-014 | `low-degree-code.tex:1-94` (orig. 1729-1822), `pauli.tex:1-214` (orig. 1949-2162), `types.tex:1-582` (orig. 3567-4148), `qpbt-game-and-soundness.tex:60-63` for admissibility; F02/F05/F06/F07/G01 blueprint entries | `MIPStarRE/QPBT/Basic/Polynomial.lean`, `Basic/Pauli.lean`, `Game/Types.lean`, `Game/Parameters.lean` | Sequentially after QPBT-013. Must preserve the corrected trace-valued Pauli phase and no abstract duplicate field assumptions. |
| QPBT-015 | `magic-square.tex:1-368` (orig. 4660-5027), `qpbt-game-and-soundness.tex:1-328` (orig. 5048-5374); F08/G02 entries and seven-check encoding | `MIPStarRE/QPBT/Game/MagicSquare.lean`, `Game/Verifier.lean` | Sequentially after QPBT-014. Verify exhaustive typed seven-check constructors and exact dependent answer fibers. |
| QPBT-016 | Appendix A.6 `appendix-separate-xz-conclude.tex:255-446` (orig. 14708-14899), A.1 theorem statement `qpbt-game-and-soundness.tex:533-547` (orig. 5579-5593); A15/S01 in `chapter-11-entries.tex:2-46` | `MIPStarRE/QPBT/Analysis/Extraction.lean`, `MIPStarRE/QPBT/Soundness.lean` (plus declared root-import synchronization) | Sequentially after QPBT-015. Exactly one intended `pauliSoundness` sorry in the minimal skeleton; preserve SquaredRealizes versus Realizes and `Real.rpow` probability-domain boundary. |
| QPBT-017 | Canonical recipe identity and archive prerequisites `scripts/hot_main_cache.py:103-168`, `protocols/local-development.md:19-50` | Documentation/changelog paths named by issue; no Lean overlap | **Independent of QPBT-013-016 after QPBT-004**, so it is the best parallel lane. It still cannot issue before QPBT-004's dependency is marked done; requires focused omission regression and fresh documentation review. |

Thus the first useful wave after QPBT-004 is **QPBT-013 + QPBT-017**. QPBT-014
then QPBT-015 then QPBT-016 form a dependency-respecting chain. There is no
safe parallel writer split inside that chain because QPBT-014 supplies the
typed/algebra interfaces consumed by QPBT-015, and QPBT-015 supplies the game
surface consumed by QPBT-016. Read-only source or blueprint scouts can fan out,
but writable issue leases must keep these exact paths disjoint.

## Current blockers and second-commit/cache gates

`workflow/state/issues.json` currently records QPBT-002 and QPBT-003 as
blocked. QPBT-003's unblock condition is to integrate approved QPBT-010,
QPBT-002, QPBT-012, and blueprint ranges in the rehearsed order, rerun the
combined source/blueprint/graph/PDF/workflow gates, and create the second main
commit. Therefore QPBT-004 and every QPBT-013-017 implementation record remain
planned and `python3 scripts/workflow.py ready` currently returns no rows.

Before QPBT-004 review, use the current hot-main protocol: one elected
`python3 scripts/hot_main_cache.py warm` under the shared default runtime and
lock, then private `seed --worktree PATH` for each issue worktree. The candidate
must consume the exact local Mathlib source/archive and eight package archives;
no writable `.lake/build` may be shared. The full integration gate is the
registered package/materialization tests, aggregate workflow tests,
`python3 scripts/check_workflow.py`, `python3 -m compileall -q scripts tests`,
workflow validation, diff hygiene, then the singleton cache-get and Lake build
once the local pinned Mathlib gate is approved. QPBT-021 remains blocked by its
baseline process-timeout aggregate finding and QPBT-018 remains blocked on the
same singleton warm, so neither can substitute for QPBT-004's second-commit
dependency.

## Dispatch recommendation

Do not issue QPBT-004 or QPBT-013-017 yet: dependency admission correctly
rejects them. Once QPBT-003 is integrated and QPBT-004 completes, issue one
orchestrator for QPBT-013 and one for QPBT-017 in the same capacity-aware wave;
issue QPBT-014, QPBT-015, and QPBT-016 only as each predecessor closes. The
observed collaboration ceiling is four aggregate slots including the root,
and the hot-main builder remains a singleton regardless of dispatch capacity.

Scout accounting: approximately 8 minutes elapsed (first inspection
`2026-08-31T08:31Z`, report completed `2026-08-31T08:39Z`); network 0, Lean/Lake/
build/cache actions 0, subagents 0, canonical edits 0. Token usage is not
exposed by this backend and is recorded as unavailable rather than estimated.
