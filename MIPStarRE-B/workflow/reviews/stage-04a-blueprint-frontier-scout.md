# Stage 04A Blueprint Frontier Scout

## Session and scope

- Logical session: `i000-scout-a28-blueprint-frontier`
- Snapshot: `d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1d`
- Role: read-only reconnaissance under `QPBT-000`
- Agent-reported window: `2026-08-31T08:24:10Z` to `2026-08-31T08:27:00Z` (approximately 170 seconds)
- Lean/Lake/hot-main builds: 0; network requests: 0; canonical edits: 0

This is preparation evidence, not an implementation approval. The scout
examined the pinned source map and immutable blueprint metadata from the
available worktree and identified the next dependency-respecting lanes.

## Source anchors

The QPBT source map pins arXiv `2001.04383v3` (archive SHA-256
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`; PDF
SHA-256 `3310802ab185fb1c7051a274064ed16d5a8ce70444ab784d68f349de12777017`).
Primary anchors are Section 7.3 (`compression_arXiv_v3.tex:5028-5639`, labels
`sec:pauli-verifier`, `lem:pauli-completeness`, `thm:pauli`,
`cor:pauli-binary`) and Appendix A.1-A.6 (`:13032-14930`, labels
`sec:qld-prelim`, `sec:commutation`, `sec:expanding`, `sec:combining`,
`sec:apply-ldt`, `sec:separating`).

The provisional blueprint at commit `3f4d4b3` has 48 nodes and targets
`G03-COMPLETENESS`, `S01-SOUNDNESS`, `B01-BINARY`, and `K04-GAME-COMPLEXITY`.
Paper-gap entries `G01-G15` and external boundaries remain explicit; none may
be converted into Lean axioms by listing them in metadata.

## Dependency-respecting queue

| Lane | Proposed path root | Gate |
| --- | --- | --- |
| QPBT-004 | `MIPStarRE/QPBT/Basic/` and project import/config files | QPBT-003 accepted after QPBT-002 and QPBT-009; private hot-main cache |
| QPBT-013 | `MIPStarRE/QPBT/Game/` | QPBT-004 complete; typed game/completeness nodes discharged |
| QPBT-014 | `MIPStarRE/QPBT/Analysis/Naimark.lean`, `Preliminaries.lean`, `StrategyConsequences.lean` | QPBT-013 complete; reductions proved, not assumed |
| QPBT-015 | `MIPStarRE/QPBT/Analysis/ExpandedObservables.lean`, `JointMeasurements.lean`, `FiberLinearity.lean` | QPBT-014 complete; good/bad-fiber conditioning proved |
| QPBT-016 | `MIPStarRE/QPBT/Analysis/ClassicalLDTAdapter.lean`, `RestrictedLines.lean`, `GlobalMeasurement.lean`, `ExactPauli.lean` | QPBT-015 complete; direct-axis LDT adapter and dimension obligations resolved |
| QPBT-017 | `MIPStarRE/QPBT/Analysis/Extraction.lean`, `Robustness.lean`, `Soundness.lean`, `Binary.lean`, `CanonicalParameters.lean` | QPBT-016 complete; public theorem retains arbitrary POVMs and source quantifiers |

These are queue proposals, not yet dispatchable issue records. Disjoint path
roots permit scouting in parallel, but proof work remains sequential where the
blueprint edges require it. QPBT-021's `local_agent.py`/test ownership also
overlaps the active QPBT-020 repair and must wait for that head to integrate.

## Must-wait conditions

1. QPBT-002 and QPBT-009 must complete before QPBT-003 can be accepted.
2. The second main commit must contain the source split and regenerated
   blueprint before implementation issues are issued.
3. Every Lean/Lake command must use a private seeded cache; the hot-main build
   remains singleton per cache identity.
4. QPBT-013 through QPBT-017 need actual issue records, dependencies, owned
   paths, and acceptance gates before dispatch.

`python3 scripts/workflow.py validate` passed for the inspected snapshot. No
approval, source-root completion, or Lean declaration was claimed.
