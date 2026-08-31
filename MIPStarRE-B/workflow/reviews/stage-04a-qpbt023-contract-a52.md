# QPBT-023 contract scout (i000-scout-a52-qpbt023)

## Immutable scope and checks

The clean detached clone is `/tmp/qpbt-scout-a52-qpbt023`.

- `HEAD`: `7526e58663f4a93c6643d936cb6cedb8df6e090b`
- `HEAD` tree: `e45a463ae0a58f8faf4c3d10329a6f68b08b19e2`
- `HEAD` parent: `5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6`
- Worktree status: clean; `git diff --check`: pass.
- `git merge-base --is-ancestor 7526e58663f4a93c6643d936cb6cedb8df6e090b HEAD`: pass.
- `python3 blueprint/check.py --check`: pass (48 nodes, 12 chapters, acyclic,
  deterministic outputs).
- `python3 blueprint/check.py --check --source-root references/2001.04383v3/sections`:
  fails closed because this exact clone has no materialized source split and
  therefore no `sections/split-manifest.json`.
- No Lean, Lake, build, network, hot-cache warm, or cache seed command was run.

The requested paths
`references/2001.04383v3/sections/07-03-pauli-basis-test.tex` and
`references/2001.04383v3/sections/a-analysis-pauli-basis-test.tex` are absent
from the exact clone. The committed `split-manifest.json` instead names
`sections/qpbt/qpbt-game-and-soundness.tex` and
`sections/top-level/appendix-qpbt.tex`; the dependency excerpts are under
`sections/dependencies/`. For source inspection only, I used the already
materialized, READY-marked local source at
`/home/drx/MIPStarRE-auto/.workflow-runtime/worktrees/qpbt-002/references/2001.04383v3/`.
Its `source/compression_arXiv_v3.tex` has the pinned member SHA-256
`38b3e662bb85bb902fcd056436fe9ecbe9e68d1990a074d0c0c12b39d5972ea9`, matching
`source-pin.json`; no source was copied or modified.

## Source anchors

The paper's actual finite-field dependency says that a self-dual basis is a
basis equal to its trace-dual, and that a normal basis is a Frobenius orbit
(`sections/dependencies/finite-fields.tex:62-83`). The admissible QPBT field is
`F_(2^k)` with odd `k` (`:243-248`). Lemma `lem:efficient_basis` claims a
deterministic polynomial-time algorithm returning a self-dual normal basis and
multiplication tables for every odd positive `k` (`:283-307`). The follow-on
`lem:one` uses that basis (`:309-347`), and `lem:efficient_arithmetic` assumes
the algorithm-returned basis (`:350-400`).

The measurement source defines a POVM as PSD effects indexed by a finite outcome
set summing to identity, projectivity as effect idempotence, and an observable
as a unitary matrix (`sections/dependencies/measurements.tex:3-19`). A family is
indexed by a finite question set; postprocessing is fiberwise summation under
an arbitrary function (`:21-47`). The same section's Naimark boundary starts
from finite local submeasurements and a bipartite state and returns auxiliary
spaces, a product auxiliary state, and projective measurements preserving all
correlations (`:49-78`).

The strategy source defines a game
`(X,Y,A,B,mu,D)` with finite question/answer alphabets, a probability
distribution `mu` on `X x Y`, and a Boolean decision predicate
(`sections/dependencies/strategies-distance.tex:4-18`). A tensor strategy is a
unit vector in a finite-dimensional complex tensor Hilbert space plus POVM
families (`:20-32`). State-dependent distance uses finite question sets and a
distribution, with an average squared norm of `(M_a-N_a) psi`
(`:252-265`); consistency uses an average off-diagonal probability
(`:226-242`); strategy distance additionally quantifies same-space states and
both player families (`:267-282`).

The QPBT game source fixes admissible `(q,m,d)` with `q=2^k`, odd `k`, and
`m | q` (`sections/qpbt/qpbt-game-and-soundness.tex:60-63`), question types
`({Point,ALine,DLine,Pauli,Pair} x {X,Z}) union type_MS union {Pair}`
(`:66-76`), and a finite question carrier
`type^pauli x V^pauli x type^pauli x V^pauli`, where
`V^pauli = (F_q^m)^2 x F_q x F_q^m x (F_q)^2` and sampling is uniform over
graph edges and `V^pauli` (`:175-222`).

## Frozen blueprint facts

`blueprint/metadata/nodes.json:34-49` (generated mirror
`blueprint/src/generated/chapter-02-entries.tex:2-12`) names F01 as module
`MIPStarRE.QPBT.Basic.Field` with public names `FieldData`,
`fieldDataOfOddExponent`, and `fieldTrace`. It requires direct
`GaloisField 2 k`, vectors `Fin n -> GaloisField 2 k`, and derived Field,
Fintype, DecidableEq, CharP, cardinality, finite-dimensional Algebra, trace,
and self-dual-basis data. Caller-supplied duplicate field/cardinality/
characteristic/algebra instances are forbidden.

`nodes.json:70-85` (generated `chapter-02-entries.tex:26-36`) names F03 as
`MeasurementFamily`, `ProjectiveMeasurementFamily`, and
`observableOfMeasurement` in `MIPStarRE.QPBT.Basic.Approximation`, using the
qualified `MIPStarRE.Quantum.Measurement` API. It specifies outcome and
coordinate universes and finite/decidable instances, but omits the question
index universe, its finiteness, and the exact observable input/output.

`nodes.json:88-103` (generated `chapter-02-entries.tex:38-48`) names F04 as
`PureStrategy`, `BipartiteIsometry`,
`BipartiteIsometry.conjugate`, `stateDependentDistance`, and `familyApprox` in
the same module. It specifies Alice/Bob/auxiliary universes and finite/
decidable instances, EuclideanSpace Complex carriers, a bundled norm-one
state, explicit WithLp/matrix/Module.End/operator adapters, and explicit
conjugation, but omits exact question/outcome domains, distribution type,
state carrier shape, and distance/error return type.

## Callable contract proposal

The following should be recorded as the exact contract (with names/imports
fixed) before QPBT-013 writer dispatch. These are proposed declarations, not a
claim that the current snapshot type-checks them.

F01, direct carrier and no public basis assumption:

```lean
structure SelfDualNormalBasis (k : Nat) where
  basis : Basis (Fin k) (ZMod 2) (GaloisField 2 k)
  normal : IsNormalBasis (ZMod 2) (GaloisField 2 k) basis
  self_dual : forall i j,
    Algebra.trace (ZMod 2) (GaloisField 2 k) (basis i * basis j) =
      if i = j then 1 else 0

structure FieldData (k : Nat) where
  basis : SelfDualNormalBasis k
  basis_card : Fintype.card (GaloisField 2 k) = 2 ^ k

noncomputable def fieldDataOfOddExponent
    (k : Nat) (hk : Odd k) : FieldData k

def fieldTrace (k : Nat) :
    GaloisField 2 k ->+ ZMod 2
```

`IsNormalBasis` above is a placeholder for the exact chosen predicate; the
writer must bind it to a concrete orbit-basis statement because the pinned
Mathlib API exposes `IsGalois.normalBasis` (normal basis only), not a
self-dual-normal-basis theorem. `fieldTrace` should use Mathlib's
`Algebra.trace (ZMod 2) (GaloisField 2 k)` as a linear map rather than an
untyped function. The basis existence proof belongs in the body/theorem debt,
not in `FieldData` constructor arguments supplied by callers.

F03, with the omitted finite question index made explicit:

```lean
abbrev MeasurementFamily
    (Question Outcome Coord : Type*)
    [Fintype Question] [Fintype Outcome] [DecidableEq Outcome]
    [Fintype Coord] [DecidableEq Coord] :=
  Question -> MIPStarRE.Quantum.Measurement Outcome Coord

def ProjectiveMeasurementFamily
    (Question Outcome Coord : Type*) ...
    (M : MeasurementFamily Question Outcome Coord) : Prop :=
  forall q a, (M q).effect a * (M q).effect a = (M q).effect a

def observableOfMeasurement
    (Coord : Type*) [Fintype Coord] [DecidableEq Coord]
    (M : MIPStarRE.Quantum.Measurement Bool Coord) :
    MIPStarRE.Quantum.Op Coord
```

The final observable declaration needs an explicit binary encoding (for
example `Bool` effects mapped to `effect true - effect false`) and a separate
projectivity premise if the result is required to be a unitary/binary
observable. The paper does not define a canonical unitary for an arbitrary
multi-outcome POVM; silently accepting arbitrary `Outcome` would be
source-inaccurate.

F04, with all finite domains and a concrete finite distribution:

```lean
structure PureStrategy
    (QuestionA QuestionB OutcomeA OutcomeB Alice Bob : Type*)
    [Fintype QuestionA] [Fintype QuestionB]
    [Fintype OutcomeA] [Fintype OutcomeB]
    [Fintype Alice] [DecidableEq Alice]
    [Fintype Bob] [DecidableEq Bob] where
  state : EuclideanSpace Complex (Alice x Bob)
  alice : MeasurementFamily QuestionA OutcomeA Alice
  bob : MeasurementFamily QuestionB OutcomeB Bob
  unit : norm state = 1

def stateDependentDistance
    (Question Outcome Coord : Type*) [Fintype Question]
    [Fintype Outcome] [DecidableEq Outcome]
    [Fintype Coord] [DecidableEq Coord]
    (mu : PMF Question) (psi : EuclideanSpace Complex Coord)
    (M N : MeasurementFamily Question Outcome Coord) : Real :=
  sum q, mu q * sum a, norm ((M q).effect a - (N q).effect a) psi ^ 2

def familyApprox ... (delta : Real) : Prop :=
  0 <= delta /\ stateDependentDistance ... <= delta
```

The exact tensor carrier and existing project PMF name must be checked when
QPBT-004 materializes the imported foundations; the important contract points
are finite Question/Outcome/Coord domains, a normalized pure state, and an
explicit real-valued finite average. `BipartiteIsometry` must expose local
linear isometries for Alice/Bob and `.conjugate` must state the exact side's
`V * A * V.adjoint` operator action. Do not reuse the incompatible
`MIPStarRE.LDT.Measurement` hierarchy.

## Self-dual obligation and dependency decision

The pinned Mathlib source at `/tmp/qpbt018-mathlib-source.t8E8oS/mathlib`
contains `GaloisField` with Field, CharP, Finite, and FiniteDimensional
instances (`Mathlib/FieldTheory/Finite/GaloisField.lean:67-83`), cardinality
theorems (`:131-160`), and the generic normal-basis theorem
`IsGalois.normalBasis` (`Mathlib/FieldTheory/Galois/NormalBasis.lean:89-123`).
It has trace forms and `Basis.traceDual`, but a negative search over the pinned
Mathlib tree found no self-dual-normal-basis theorem or odd-degree criterion.
The paper's Lemma `lem:efficient_basis` is an external deterministic algorithm
(Lenstra plus Wang), not a Mathlib declaration. Therefore the obligation must
be tracked as an internal proof/dependency issue with a discharge plan (formal
finite-field construction, or a separately authenticated imported algorithm
boundary). A conditional helper may end in `_ofObligations`, while the
paper-facing F01 theorem remains visible with tracked proof debt; do not add a
public `Hypotheses`, bridge, witness, or basis argument.

QPBT-023 is blocked on QPBT-003 (`workflow/state/issues.json:735-766`), whose
unblock condition is integration of the approved source/blueprint ranges and
the second main commit. QPBT-013 depends on both QPBT-004 and QPBT-023
(`issues.json:398-428`), so neither the F01/F03/F04 writer nor downstream QPBT
lanes are dependency-ready. QPBT-004 itself remains blocked on its package/cache
repair and independent review. Recommended next action is to materialize the
source split and second commit, amend the F01/F03/F04 signature contract and
paper-gap record, then obtain an immutable blueprint review before dispatch.

Elapsed wall time: approximately 12 minutes including clone creation, source
inspection, metadata/API searches, and report preparation. Exposed token usage
is unavailable (`null`); it was not estimated. Nested agents: 0.
