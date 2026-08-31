# QPBT-013 Leaf Contract Audit

Session `i000-scout-a39-leaf-contract` was a fresh, read-only audit of main
SHA `8bf8ee89d24d833c28ecce6ce7e08c42e28b614f` (tree
`74011bb473b30b32b696c9e6a6bcb744519f735d`), with base
`7669f70be786a53ba1a0a92c1d347f5fe7544681` (ancestor). No source, state,
Lean, cache, build, or network changes were made. Review elapsed time was
approximately 2 seconds of bounded shell/API inspection; token usage was not
exposed.

## Verdict

**BLOCKED for writer dispatch.** The blueprint freezes names, carriers,
universes, and instance policy, but does not freeze callable parameter and
return signatures. The paper also has finite question indexes and
distributions that the F03/F04 boundary text omits. F01 additionally requires
a self-dual normal basis theorem absent from the pinned APIs.

## Verified contract

`blueprint/metadata/nodes.json:34-49` and the generated mirror
`blueprint/src/generated/chapter-02-entries.tex:2-12` establish F01:

- namespace/module `MIPStarRE.QPBT.Basic.Field`, names
  `MIPStarRE.QPBT.FieldData`, `fieldDataOfOddExponent`, and `fieldTrace`;
- direct carrier `GaloisField 2 k`, with vectors `Fin n -> GaloisField 2 k`;
- derive `Field`, `Fintype`, `DecidableEq`, `CharP`, cardinality,
  finite-dimensional `Algebra`, trace, and self-dual-basis data from odd `k`;
- callers must not supply duplicate field/cardinality/characteristic/algebra
  instances, and reusable carrier APIs must expose explicit universes.

`nodes.json:70-85` / generated entries `:26-36` establish F03:

- module `MIPStarRE.QPBT.Basic.Approximation`, names
  `MeasurementFamily`, `ProjectiveMeasurementFamily`, and
  `observableOfMeasurement`;
- qualified `MIPStarRE.Quantum.Measurement` is the POVM representation;
  projectivity is a separate predicate and the LDT measurement hierarchy is
  not to be opened or inherited;
- universes `uOutcome uCoord`, instances
  `[Fintype Outcome] [DecidableEq Outcome] [Fintype Coord] [DecidableEq Coord]`,
  scalar `Complex`, finite-dimensional coordinates.

`nodes.json:88-103` / generated entries `:38-48` establish F04:

- same Approximation module, names `PureStrategy`, `BipartiteIsometry`,
  `BipartiteIsometry.conjugate`, `stateDependentDistance`, and `familyApprox`;
- F03 is a prerequisite; universes are `uAlice uBob uAuxAlice uAuxBob`, with
  corresponding finite and decidable instances;
- carriers are `EuclideanSpace Complex`; adapters among EuclideanSpace,
  `WithLp 2`, matrices, `Module.End`, and operators must be explicit;
  strategies bundle a norm-one proof; conjugation is explicitly
  `V * A * V.adjoint` on each side; every `Real.rpow` use has a proved
  nonnegativity premise.

Issue QPBT-013 requires the exact signatures/imports/instances before
implementation (`workflow/state/issues.json:398-428`). No such signatures are
present in metadata or generated chapter entries.

## Findings (ordered)

1. **Blocker: no exact public signatures.** There is no
   `MIPStarRE/QPBT/Basic/Field.lean` or `Approximation.lean` in this snapshot,
   and no QPBT declaration in materialized `.lean` files. `rg --files MIPStarRE`
   reports that the authored source tree is absent; root `MIPStarRE.lean:1-2`
   only imports `MIPStarRE.Quantum` and `MIPStarRE.LDT`. Thus a writer cannot
   satisfy the acceptance gate without inventing arguments, result types, or
   imports. In particular, F03 does not say what type indexes the superscript
   family, whether `X` has `Fintype`/`DecidableEq`, or how postprocessing and
   projectivity are exposed. `observableOfMeasurement` is also underdetermined:
   the paper only defines an observable as a unitary matrix, not a canonical
   conversion from an arbitrary POVM.

2. **Blocker: F04 omits required domains and measures.** The source defines a
   finite question set and distribution `mu` for consistency and POVM distance,
   then a game tuple and two strategy families. These are explicit in the exact
   source fragments `measurements.tex:21-47` and
   `strategies-distance.tex:226-282` (materialized under
   `.workflow-runtime/worktrees/qpbt-002/references/2001.04383v3/sections/dependencies/`).
   The F04 boundary lists only Alice/Bob/aux carrier universes and instances;
   it does not freeze question/outcome index types, distributions, state
   carrier dimensions, or whether distances return `Real`, an asymptotic
   relation, or an explicit bound. Any guessed API would be a source-fidelity
   risk.

3. **Blocker: F01 self-dual normal basis proof is unavailable.** The paper
   requires a self-dual normal basis for `GaloisField 2 k` when `k` is odd
   (`finite-fields.tex:62-83,283-317`). Mathlib's pinned sources provide direct
   `GaloisField` instances (`.lake/packages/mathlib/Mathlib/FieldTheory/Finite/GaloisField.lean:67-83,131-135`),
   finite-field trace/nondegeneracy (`.../Finite/Trace.lean:8-42`), and
   `Module.Basis.traceDual` (`.../RingTheory/Trace/Basic.lean:547-573`), but no
   self-dual-normal existence theorem or odd-degree criterion. The prior
   reconnaissance records that the generic orthogonal-basis route requires
   invertible 2 and fails in characteristic two
   (`workflow/reviews/qpbt-013-selfdual-scout.md:7-19`). A constructor cannot
   honestly claim exact F01 by `infer_instance` or an untracked assumption.

4. **Dependency risk: existing APIs are not a silent substitute.** The pinned
   Quantum API is `MIPStarRE.Quantum.Measurement` with
   `Measurement (alpha : Type*) [Fintype alpha] (d : Type*) [Fintype d]
   [DecidableEq d]`, effects `alpha -> Op d`, and `sum_eq_one`
   (`.workflow-runtime/worktrees/qpbt-004/MIPStarRE/Quantum/Measurement.lean:26-48`);
   postprocessing additionally needs decidability on source and target outcomes
   (`:67-75,127-145`). The LDT `IdxMeas`/`OpFamily` hierarchy has different
   structures and namespaces (`.../LDT/Basic/SubMeasurementFamilies.lean:16-34`,
   `.../LDT/Basic/OpFamily.lean:29-36`) and must not be exposed as the QPBT
   contract. Existing LDT `PureState` is a useful implementation reference but
   is density-matrix based (`.../LDT/Basic/QuantumState.lean:25-68`) and does
   not freeze the requested F04 strategy signature.

## Source provenance and dependency order

The source map pins arXiv:2001.04383v3 and archive/PDF hashes
(`references/2001.04383v3/QPBT_SOURCE_MAP.md:6-15`), and records finite-field,
measurement, and strategy source ranges (`:93-101`). The intended order is
F01 -> F02/F05; F03 -> F04 -> downstream analysis. F01 should import the
Mathlib finite Galois-field/cardinality/trace modules plus a proven basis
result. Approximation should import qualified Quantum.Measurement and finite
Hilbert/state/adapters, not LDT measurement structures. The authenticated
upstream manifest names Quantum.Measurement, LDT QuantumState, DistanceBounds,
and FiniteFields (`references/mipstarre-upstream.json:45-68`), but does not add
QPBT declarations.

## Checks

- `git rev-parse HEAD`, `git rev-parse 8bf8ee...^{tree}`: exact SHA/tree above.
- `git merge-base --is-ancestor 7669f70... 8bf8ee...`: pass.
- `python3 scripts/workflow.py validate`: pass; 23 issues, 11 PRs, 242 issued
  sessions, 7 stages; elapsed 0.16s.
- `python3 blueprint/check.py --check`: pass; 48 nodes, 12 chapters,
  acyclic graph, deterministic outputs; elapsed 0.10s.
- `git diff --check 8bf8ee...^ 8bf8ee...`: pass; elapsed 0.01s.
- Negative searches for `MIPStarRE/QPBT`, `FieldData`, `MeasurementFamily`,
  and `PureStrategy` in current `.lean` files found no declarations; no Lean,
  Lake, network, or build command was run.

## Recommended next action

Before dispatching QPBT-013, amend the blueprint/issue contract with explicit
Lean signatures (all family/question/outcome types, finite/decidable instances,
distribution and state representations, return/error domains, and exact
imports). Open a paper-gap/dependency for the self-dual-normal-basis existence
proof or an explicitly tracked boundary. Then re-run blueprint/workflow checks
and obtain an independent contract review; do not issue a writer against the
current underspecified API.
