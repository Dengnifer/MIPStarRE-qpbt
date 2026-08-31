# QPBT-023 self-dual-normal-basis search (i000-scout-a48-qpbt023-self-dual-search)

## Scope and source state

This was a read-only search on canonical main
`7526e58663f4a93c6643d936cb6cedb8df6e090b`. The requested materialized source
tree `references/2001.04383v3/sections/` is absent, and
`blueprint/metadata/edges.json` is absent. The authoritative source map is
`references/2001.04383v3/QPBT_SOURCE_MAP.md:93-101`; the pinned paper archive
is available at `/tmp/qpbt-010-acquisition.FJmb6mA8/2001.04383v3-source.tar`,
member `compression_arXiv_v3.tex`.

No canonical file, ledger, metric, build output, or cache was touched. No
network, Lean, Lake, build, cache warm/seed, or nested-agent command was run.
Elapsed wall time was not instrumented; exposed token usage is unavailable
(`null`, not estimated).

## Exact paper obligation

The archive gives the source-faithful anchors:

* Trace over the extension is an `F_q`-linear map and is independent of the
  basis (`compression_arXiv_v3.tex:1378-1389`). A dual basis satisfies
  `tr(e_i * e'_j) = delta_ij`, and self-dual means equal to its dual
  (`:1391-1399`).
* Lemma `lem:efficient_basis` states that a deterministic algorithm, given odd
  `k > 0`, outputs a self-dual normal basis of `F_(2^k)` over `F_2` and its
  multiplication tables in polynomial time (`:1599-1623`). The proof invokes
  Shoup, Lenstra, and Wang; it does not give a Lean-level construction.
* The QPBT source map explicitly places finite-field data in Section 3.3,
  original lines 1317-1728 (`QPBT_SOURCE_MAP.md:95`), and identifies the
  external QPBT ancestor and other theorem boundaries (`:105-113`).

Thus the self-dual-normal-basis result is a paper theorem/algorithmic fact,
not a parameter that a caller may provide. The source's use of an algorithm
also means that a bare existential `sorry` is proof debt, not a faithful final
implementation.

## Pinned Mathlib search and positive APIs

The local pinned source is `/tmp/qpbt018-mathlib-source.t8E8oS/mathlib`:

```text
HEAD  81a5d257c8e410db227a6665ed08f64fea08e997
tree  5ea66b811b8461daae82f14d356fed2a287d7c40
status clean (detached shallow checkout)
archive /tmp/mathlib-81a5d257-shallow-repo.tar.gz
archive bytes 51938317
archive sha256 c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7
```

Search commands covered all of the pinned `Mathlib/FieldTheory` and
`Mathlib/LinearAlgebra` trees, then all repository Mathlib/QPBT/LDT sources:

```text
rg -n -i 'self.?dual|selfdual|dual.?normal|normal.?basis|orthonormal.?basis|trace.*basis' mathlib/Mathlib/FieldTheory mathlib/Mathlib/LinearAlgebra
rg -n -i 'self.?dual|normal.?basis|efficient_basis|Wang|Shoup|Lenstra' MIPStarRE .workflow-runtime/worktrees/qpbt-004/MIPStarRE
rg -n -i 'normalBasis|traceForm|dualBasis|selfdual|self-dual' mathlib/Mathlib
```

No self-dual-normal-basis theorem, odd-degree criterion, Wang construction,
or declaration named `selfDual`, `SelfDual`, or
`selfDualNormalBasis` was found. The positive, but insufficient, APIs are:

* `GaloisField 2 k` derives `Field`, `CharP`, `Algebra (ZMod 2)`, `Finite`,
  and `FiniteDimensional` (`Mathlib/FieldTheory/Finite/GaloisField.lean:65-74`).
  `GaloisField.finrank` and `.card` provide dimension/cardinality after
  discharging `k != 0` (`:78-82,131-135`).
* `FiniteField.trace_to_zmod_nondegenerate` and the trace power-sum formula
  are available (`Mathlib/FieldTheory/Finite/Trace.lean:36-56`).
* `IsGalois.normalBasis` and `normalBasis_apply` construct an orbit basis for
  a finite Galois extension (`Mathlib/FieldTheory/Galois/NormalBasis.lean:108-129`).
* The trace form is nondegenerate and every chosen basis has a computable
  dual `Module.Basis.traceDual`; `trace_traceDual_mul`,
  `trace_mul_traceDual`, and `traceDual_eq_iff` are at
  `Mathlib/RingTheory/Trace/Basic.lean:501-505,547-604`.

`traceDual` proves duality for an arbitrary basis. It does not prove that the
chosen normal basis is fixed by `traceDual`, and none of the searched files
proves that such a fixed normal basis exists in characteristic two.
Generic orthogonal/orthonormal-basis APIs are not a substitute: the required
field has characteristic two and the normal-orbit constraint is additional.

## Reconciled F01/F03/F04 boundary

The blueprint nodes are `blueprint/metadata/nodes.json:34-49` (F01),
`:70-85` (F03), and `:88-103` (F04); the foundation chapter reiterates the
direct `GaloisField 2 k` policy at `blueprint/src/chapter/02-foundations.tex:8-14`.

F01 should use the concrete carrier `GaloisField 2 k`, local
`Fintype.ofFinite`/`DecidableEq`, and the callable trace
`Algebra.trace (ZMod 2) (GaloisField 2 k)` (a `LinearMap`), with no abstract
carrier wrapper. A `FieldData k hk` may package a basis and its self-dual and
normal proofs, but `fieldDataOfOddExponent hk` must construct it. It must not
accept `basis`, `Hypotheses`, a bridge, or an arbitrary existence proposition
from the caller.

F03 should remain the qualified `MIPStarRE.Quantum.Measurement` family with
explicit finite/decidable outcome and coordinate instances; projectivity is a
separate predicate. The paper bracket is the finite fiber sum at source
`:1887-1900`; the exact public binary `observableOfMeasurement` signature
still needs freezing because the node does not state whether outcomes are
`Bool` or carry an encoding.

F04 should bundle a norm-one finite bipartite state and Alice/Bob POVM families
using explicit Euclidean-space/tensor adapters. State-dependent distance is
the squared vector norm and POVM family sum from source `:3096-3148`; strategy
distance compares state and both measurement families (`:3150-3165`). The
question index, distribution type, tensor carrier, and `Real` return/error
domain remain to be made explicit before QPBT-013; no generic assumptions
parameter should conceal them.

## Concrete QPBT-023 discharge plan

1. Materialize the pinned paper sections from the authenticated archive and
   pass the source-root/declaration checks. This is prerequisite evidence,
   not a replacement for the theorem proof.
2. Freeze F01 declarations around `GaloisField 2 k` and define an internal
   `SelfDualNormalBasis` proposition using `Algebra.trace` and the Frobenius
   orbit. Expose `FieldData` and `fieldDataOfOddExponent` with the paper's odd
   positive `k` condition; do not add a public basis input.
3. Use Mathlib's `IsGalois.normalBasis` plus `Module.Basis.traceDual` for the
   ordinary normal/dual lemmas. Add a separately tracked proof issue for the
   missing implication that an odd-degree characteristic-two extension has a
   self-dual normal basis.
4. Discharge that issue in one of two faithful ways: formalize the cited
   Shoup/Lenstra/Wang construction (including the polynomial-time data needed
   by the later complexity node), or pin and independently review a source
   theorem that supplies exactly the odd-`k`, `F_(2^k)/F_2` result. Until one
   path is complete, keep a source-faithful theorem visible with tracked
   proof debt and, if needed, a private helper named
   `..._ofObligations`; never mark the paper theorem complete through that
   helper.
5. Freeze the remaining F03/F04 signatures and obtain the independent
   immutable contract review required by QPBT-023. Only then may QPBT-013's
   two owned Lean files be dispatched.

Recommended validation after the source and blueprint changes (not run here):

```text
python3 blueprint/check.py --check --source-root references/2001.04383v3
python3 -m unittest discover -s blueprint/tests -p 'test_*.py'
python3 scripts/workflow.py validate
lake env lean MIPStarRE/QPBT/Basic/Field.lean
lake env lean MIPStarRE/QPBT/Basic/Approximation.lean
```

The current missing `sections/` directory makes the source-root gate fail
closed. QPBT-023 remains blocked until this materialization, contract freeze,
paper-gap/discharge record, and independent review are all complete.
