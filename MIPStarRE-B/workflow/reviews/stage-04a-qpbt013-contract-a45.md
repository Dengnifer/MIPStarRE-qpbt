# QPBT-013 contract scout (i000-scout-a45-qpbt013-contract)

## Scope and immutable evidence

This is a read-only contract report. The inspected repository snapshot is
`7526e58663f4a93c6643d936cb6cedb8df6e090b` (`git rev-parse HEAD`); the worktree
already had unrelated dirty workflow state (`workflow/events.jsonl`,
`workflow/state/issues.json`, and `workflow/state/sessions.json`). No canonical
file, ledger, metric, build output, or cache was changed.

The requested `references/2001.04383v3/sections/` directory is absent, and
`blueprint/metadata/edges.json` is absent. The pinned source archive is locally
available at `/tmp/qpbt-010-acquisition.FJmb6mA8/2001.04383v3-source.tar`, member
`compression_arXiv_v3.tex`. The source-map gate therefore cannot pass until
the archive is materialized. `references/2001.04383v3/QPBT_SOURCE_MAP.md` maps
the relevant source ranges and requires that materialization.

Commands run (all read-only):

```text
git rev-parse HEAD
ls -ld references/2001.04383v3/sections blueprint/metadata/edges.json
tar -xOf /tmp/qpbt-010-acquisition.FJmb6mA8/2001.04383v3-source.tar compression_arXiv_v3.tex | nl -ba | sed ...
rg -n ... blueprint/metadata blueprint/check.py .workflow-runtime/worktrees/qpbt-004/.lake/packages/mathlib/Mathlib
```

No network commands, Lean/Lake invocations, builds, `hot_main_cache.py`
commands, or nested agents were used (each count 0). Wall-clock elapsed time
was not instrumented; exposed token usage is unavailable (`null`, with this
reason).

## F01-FIELD: exact source and callable boundary

Blueprint anchors are `blueprint/metadata/nodes.json:34-49`, generated entry
`blueprint/src/generated/chapter-02-entries.tex`, and
`blueprint/src/chapter/02-foundations.tex:8-14`. The node points to
`references/2001.04383v3/sections/dependencies/finite-fields.tex`, label
`sec:finite-fields`, original lines 1317-1728. The archive confirms:

* Trace is an `F_q`-linear map (`compression_arXiv_v3.tex:1378-1389`).
* A self-dual basis is defined by `tr(e_i e_j) = delta_ij`
  (`:1391-1399`). For `q=2`, odd positive `k` is the condition in the paper.
* Lemma `lem:efficient_basis` states existence of a deterministic algorithm
  producing a self-dual normal basis and multiplication tables for odd
  `k > 0` (`:1599-1623`). This is an algorithmic existence claim, not a
  caller-supplied basis assumption.

Mathlib's direct carrier is `GaloisField 2 k`, from
`.workflow-runtime/worktrees/qpbt-004/.lake/packages/mathlib/Mathlib/FieldTheory/Finite/GaloisField.lean:8-11,65-74`.
It derives `Field`, `CharP`, `Algebra (ZMod 2)`, `Finite`, and
`FiniteDimensional`; `Fintype` must be installed locally with
`Fintype.ofFinite`, and `DecidableEq` then comes from the finite instance.
`GaloisField.finrank` (`:78-82`) and `GaloisField.card` (`:131-135`) require
`k != 0`, discharged from `Odd k` and positivity. `Fact (2:Nat).Prime` is the
only prime field fact.

Recommended declarations (the constructor must prove the fields; it must not
take a basis or arbitrary hypothesis as an argument):

```lean
namespace MIPStarRE.QPBT
abbrev QPBTField (k : Nat) := GaloisField 2 k

noncomputable def fieldTrace {k : Nat} :=
  Algebra.trace (ZMod 2) (QPBTField k)

structure FieldData (k : Nat) (hk : Odd k) where
  basis : Module.Basis (Fin k) (ZMod 2) (QPBTField k)
  selfDual : forall i j, Algebra.trace (ZMod 2) (QPBTField k)
      (basis i * basis j) = if i = j then 1 else 0
  normal : ... -- Frobenius orbit condition, source-faithful

noncomputable def fieldDataOfOddExponent {k : Nat} (hk : Odd k) :
    FieldData k hk := by
  -- tracked proof obligation until Lemma `lem:efficient_basis` is formalized
  sorry
end MIPStarRE.QPBT
```

The `fieldTrace` sketch intentionally marks the result type for correction:
the actual callable value should be the coercion of
`Algebra.trace (ZMod 2) (GaloisField 2 k)`, a linear map
`LinearMap (ZMod 2) (GaloisField 2 k) (ZMod 2)` (the elaborated Lean linear-map
notation), rather
than a ring hom. Mathlib confirms the map and its finite-field formula in
`Mathlib/FieldTheory/Finite/Trace.lean:36-56`; the LDT precedent is
`MIPStarRE/LDT/Preliminaries/FiniteFields.lean`'s `ffTrace` abbreviation.

Negative search over the pinned Mathlib tree found no self-dual-normal-basis
theorem or declaration (`selfDual`, `SelfDual`, `selfDualNormalBasis`), only
`IsGalois.normalBasis` and `normalBasis_apply` in
`Mathlib/FieldTheory/Galois/NormalBasis.lean:108-129`. Thus `normalBasis` is
usable, but it does not discharge `selfDual`. Discharge options are: (1)
formalize the Wang/Shoup/Lenstra algorithmic existence argument cited by the
paper; or (2) add a separately sourced, reviewed internal theorem with a
paper-gap note. Until then, keep the source-faithful `fieldDataOfOddExponent`
visible with tracked proof debt and do not expose `basis`, `Hypotheses`, or a
bridge assumption as caller input.

## F03-MEASUREMENT: exact source and callable boundary

Blueprint anchor is `blueprint/metadata/nodes.json:70-85`, source label
`def:bracket`, original lines 1888-1903. The surrounding paper contract is
`compression_arXiv_v3.tex:1854-1872`: a POVM is a finite positive family with
sum equal to identity; projective means each effect satisfies `M_a^2=M_a`;
an observable is unitary. Bracket/postprocessing is the fiber sum
`M_[f(.)=b] = sum_{a : f a = b} M_a` (`:1887-1900`).

The callable project API is qualified `MIPStarRE.Quantum.Measurement`:
`Measurement (Outcome) (Coord)` requires
`[Fintype Outcome] [Fintype Coord] [DecidableEq Coord]` and stores
`effect : Outcome -> Op Coord`, with `Op Coord = Matrix Coord Coord Complex`
(`MIPStarRE/Quantum/Measurement.lean:30-48`, `Quantum/FiniteMatrix/Basic.lean:79`).
`Measurement.postprocess` is at `:127-140` and additionally requires
`DecidableEq` for source and target outcomes.

Recommended boundary (question index need not be finite until a distribution
is introduced):

```lean
abbrev MeasurementFamily (Question Outcome Coord : Type*)
    [Fintype Outcome] [DecidableEq Outcome]
    [Fintype Coord] [DecidableEq Coord] :=
  Question -> MIPStarRE.Quantum.Measurement Outcome Coord

def ProjectiveMeasurementFamily (M : MeasurementFamily Question Outcome Coord) : Prop :=
  forall q a, (M q).effect a * (M q).effect a = (M q).effect a

def observableOfMeasurement (M : MIPStarRE.Quantum.Measurement Bool Coord) :
    MIPStarRE.Quantum.Op Coord :=
  (M.effect true) - (M.effect false)
```

The last definition is the paper's binary-observable convention, but its
exact public generalization (binary-only versus a supplied outcome encoding)
must be frozen by QPBT-023; do not silently invent a generic observable map.
Do not import or inherit the LDT measurement hierarchy.

## F04-DISTANCE: exact source and callable boundary

Blueprint anchor is `blueprint/metadata/nodes.json:88-103`, source label
`def:state-distance`, original lines 3097-3288. Paper definitions are:

* Tensor-product strategy is a unit vector in a finite-dimensional complex
  bipartite Hilbert space plus Alice/Bob POVM families
  (`compression_arXiv_v3.tex:2887-2915`).
* State distance is squared vector norm, asymptotically `O(delta)`
  (`:3096-3107`).
* POVM state-dependent distance is
  `E_x sum_a ||(M_a^x-N_a^x) psi||^2 <= O(delta)`
  (`:3135-3148`). Strategy distance also compares states and both players'
  measurement families (`:3150-3165`).

The blueprint requires finite EuclideanSpace Complex carriers, bundled norm-one
state, explicit adapters to matrices/`Module.End`/`WithLp 2`, and a transparent
pair of local linear isometries. A safe contract shape is therefore:

```lean
structure PureStrategy (QuestionA QuestionB OutcomeA OutcomeB Alice Bob : Type*)
    [Fintype OutcomeA] [DecidableEq OutcomeA] [Fintype OutcomeB] [DecidableEq OutcomeB]
    [Fintype Alice] [DecidableEq Alice] [Fintype Bob] [DecidableEq Bob] where
  state : EuclideanSpace Complex (Alice x Bob)
  normalized : norm state = 1
  alice : QuestionA -> MIPStarRE.Quantum.Measurement OutcomeA Alice
  bob : QuestionB -> MIPStarRE.Quantum.Measurement OutcomeB Bob

structure BipartiteIsometry (Alice Bob AuxAlice AuxBob : Type*) ... where
  alice : LinearIsometry (RingHom.id Complex) (EuclideanSpace Complex Alice)
      (EuclideanSpace Complex AuxAlice)
  bob : LinearIsometry (RingHom.id Complex) (EuclideanSpace Complex Bob)
      (EuclideanSpace Complex AuxBob)
```

The tensor-state carrier and whether strategy questions/outcomes are bundled
inside `PureStrategy` remain an interface decision: the paper has a game-indexed
tuple, whereas the node only says "normalized finite bipartite pure strategies."
`BipartiteIsometry.conjugate` must be implemented through the explicit local
`V * A * V.adjoint` action required by the node, not an implicit coercion.

The source-faithful distance formulas should be exposed with concrete finite
families and `MIPStarRE.LDT.Error = Real` (the existing alias is at
`LDT/Basic/ParametersBase.lean:18-20`), for example
`stateDependentDistance (psi : PureStrategy ...) (mu : Distribution Question)
 (M N : Question -> Outcome -> Op Coord) : Real`; `familyApprox` should be the
corresponding inequality predicate. Every `Real.rpow` bound needs an explicit
nonnegativity proof. The exact distribution type and tensor adapter must be
frozen before implementation; do not hide them behind a generic assumptions
parameter.

## Dependency and dispatch implications

`workflow/state/issues.json:398-429` shows QPBT-013 owns only
`MIPStarRE/QPBT/Basic/Field.lean` and `Basic/Approximation.lean`; its dependency
edges are QPBT-004 and QPBT-023. QPBT-014 is strictly downstream
(`:434-467`). QPBT-023 is blocked on QPBT-003 and explicitly requires exact
F01/F03/F04 signatures, a paper-gap/discharge plan, independent immutable
review, and blueprint source/graph/declaration checks
(`:735-766`). Therefore QPBT-013 cannot be safely dispatched until QPBT-023
freezes the unresolved `observableOfMeasurement`, distribution/tensor carriers,
and self-dual-basis obligation. F01 independently blocks F02/F05 and later
field-dependent nodes; F04 depends on F03. No disjoint implementation lane can
repair these contracts without overlapping QPBT-013 ownership.

## Required next validation

After source materialization and contract freeze, run (in this order):

```text
python3 blueprint/check.py --check
python3 blueprint/check.py --check --source-root references/2001.04383v3
python3 -m unittest discover -s blueprint/tests -p 'test_*.py'
lake env lean MIPStarRE/QPBT/Basic/Field.lean
lake env lean MIPStarRE/QPBT/Basic/Approximation.lean
python3 blueprint/check.py --check --source-root references/2001.04383v3
lake build
```

The first source-root check is expected to fail closed while
`references/2001.04383v3/sections/` is absent. Do not mark QPBT-023 or QPBT-013
ready until the immutable review and all gates pass.
