# Stage 04A Lean/API reconnaissance

Session: `i000-scout-a24-lean-api`
Base: `7669f70be786a53ba1a0a92c1d347f5fe7544681`
Mode: read-only; no files, network calls, Lake builds, or cache writes.

## Findings

- Mathlib exposes finite-field `finrank`, cardinality, and `Algebra.trace`,
  while `NormalBasis` and generic `Basis.dualBasis` do not provide the QPBT
  odd-characteristic self-dual basis theorem. The F01 boundary therefore needs
  an explicit theorem/assumption rather than an `infer_instance` claim.
- The existing `LDT.Basic.ParametersBase.FieldModel` over `Fin q` is not the
  blueprint's direct `GaloisField 2 k` contract. Public signatures should not
  silently substitute it.
- `MIPStarRE.Quantum.Measurement` (`Submeasurement`, `Measurement.ofSumEqOne`)
  and the LDT measurement hierarchy are distinct. F03 must choose an adapter
  boundary instead of leaking one namespace into the other.
- `PureState` and density/tensor APIs exist in LDT, but F04 still needs explicit
  `EuclideanSpace`/`WithLp`/matrix and conjugation (`V * A * V.adjoint`)
  adapters, including a `LinearIsometry` contract.
- MvPolynomial degree/evaluation patterns can support F02; PMF averages require
  explicit normalization. Dependent Sigma fibers/codecs need explicit
  `Fintype`/`DecidableEq` instances.
- The Pauli source uses the phase-sensitive identity
  `X(a)Z(b) = omega^(-tr(ab)) Z(b)X(a)`. Characteristic-2 commutation is only
  available when the phase vanishes; no blanket commute lemma should be added.
- S01/A15 retain split squared/unsquared obligations and the source's
  `Real.rpow` argument order `(epsilon, m, d, q)`.

## Dispatch guidance

Prepare separate read-only F01 self-dual-basis and F03/F04 adapter scouts before
issuing a writer for QPBT-013. Keep all Lean/Lake builds behind the singleton
hot-main cache; use scoped checks in issue worktrees and a full build only at
review. The local Codex launch protocol remains the governed route for nested
sessions. The installed `codex-cli 0.151.0` exposes `codex exec review` and
`codex exec fork/resume`; `scripts/local_agent.py` bounds version/help probing
and runs its selector/prompt parser probe under an isolated temporary
`CODEX_HOME`, failing closed to generic `exec` when the review surface is not
available. Current evidence is mocked parser coverage only: no model or
network child was launched by this scout, so a live endpoint-specific parser
confirmation remains an explicit gap.
