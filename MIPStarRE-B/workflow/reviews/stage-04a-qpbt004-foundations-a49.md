# QPBT-004 foundation frontier scout

Session: `i000-scout-a49-qpbt004-foundations`
Role: read-only implementation-frontier scout
Snapshot: main `7526e58663f4a93c6643d936cb6cedb8df6e090b`
Snapshot tree: `e45a463ae0a58f8faf4c3d10329a6f68b08b19e2`
Verdict: **blocked** for implementation dispatch on this snapshot.
Elapsed: approximately 8 minutes (wall-clock; token usage is unavailable).

No repository, workflow state, metrics, source, worktree, cache, or runtime
files were edited. No network, Lean/Lake build, or cache warm was run. The only
output is this report under `/tmp`.

## Verified frontier

The generated blueprint is the authoritative interface map currently present.
`blueprint/src/chapter/02-foundations.tex:3-16` fixes the dependency scope:
finite fields, measurements, state-dependent distance, and Pauli algebra. The
generated entries and metadata provide the following source-faithful order.

* **F01-FIELD** (`blueprint/src/generated/chapter-02-entries.tex:2-12`,
  `blueprint/metadata/nodes.json:34-49`) cites the pinned finite-field source
  `dependencies/finite-fields.tex`, original lines 1317-1728, label
  `sec:finite-fields`. Its planned public names are
  `MIPStarRE.QPBT.FieldData`, `fieldDataOfOddExponent`, and `fieldTrace` in
  `MIPStarRE.QPBT.Basic.Field`. The contract is direct `GaloisField 2 k`, odd
  `k`, characteristic two, cardinality `q = 2^k`, finite-field trace, and the
  self-dual basis/algebra data. Instances are derived from `k`; callers must
  not provide duplicate field/cardinality/characteristic/algebra assumptions.
  It has no blueprint prerequisite and feeds F02, F05, F06, G01, and K03A.
  The paper's `lem:efficient_basis` (original lines 1603-1608) is an
  algorithmic self-dual-normal-basis obligation, not a safe new public
  assumption.

* **F03-MEASUREMENT** (`blueprint/src/generated/chapter-02-entries.tex:26-36`,
  `blueprint/metadata/nodes.json:70-85`) cites `measurements.tex`, original
  lines 1888-1903, label `def:bracket`. Planned names in
  `MIPStarRE.QPBT.Basic.Approximation` are `MeasurementFamily`,
  `ProjectiveMeasurementFamily`, and `observableOfMeasurement`. The boundary
  requires explicit `uOutcome`/`uCoord`, finite and decidable outcome/coordinate
  instances, and Complex finite-coordinate Hilbert spaces. Arbitrary POVMs use
  the qualified `MIPStarRE.Quantum.Measurement` API; projectivity is a separate
  predicate. The blueprint explicitly forbids opening or inheriting the
  incompatible LDT measurement hierarchy.

* **F04-DISTANCE** (`blueprint/src/generated/chapter-02-entries.tex:38-48`,
  `blueprint/metadata/nodes.json:88-103`) cites `strategies-distance.tex`,
  original lines 3097-3288, label `def:state-distance`, and depends on F03.
  Planned names are `PureStrategy`, `BipartiteIsometry`,
  `BipartiteIsometry.conjugate`, `stateDependentDistance`, and `familyApprox`.
  The contract calls for finite EuclideanSpace Complex carriers, explicit
  Alice/Bob/auxiliary universe and Fintype/DecidableEq parameters, a bundled
  norm-one state, transparent local isometries, and explicit adapters among
  EuclideanSpace/WithLp, matrices, `Module.End`, and operator actions. Every
  `Real.rpow` needs a proved nonnegativity fact.

The resulting implementation order is F01, independently F03, then F04 after
F03. F02 and G01 consume F01; F05 consumes F01 and F03. QPBT-013 owns exactly
`MIPStarRE/QPBT/Basic/Field.lean` and
`MIPStarRE/QPBT/Basic/Approximation.lean` (`workflow/state/issues.json:398-428`),
but its acceptance gate requires the frozen signatures and imports first.

## Source and repository blockers

1. **Blocker: canonical source fragments are not present.**
   `test -d references/2001.04383v3/sections` reports `absent`. The source map
   (`references/2001.04383v3/QPBT_SOURCE_MAP.md:21-44`) says that the exact
   source and split fragments are ignored, require
   `python3 scripts/reference_source.py materialize`, and are usable only with
   a matching `sections/READY` marker. `references/README.md:3-13` records the
   rights boundary. The pinned archive checksum is recorded in the map, but an
   external temporary archive is not a canonical source tree. No source-faithful
   implementation should proceed until the materialization/provenance gate is
   satisfied.

2. **Blocker: the tracked main tree has no Lean foundation modules.**
   `git ls-tree -r --name-only 7526... -- MIPStarRE/QPBT`,
   `-- MIPStarRE/Quantum`, and `-- MIPStarRE/LDT` each return zero paths, and
   `rg --files MIPStarRE` returns zero files. The only tracked Lean root,
   `MIPStarRE.lean:1-2`, imports `MIPStarRE.Quantum` and `MIPStarRE.LDT`, which
   are therefore not available in this canonical snapshot. Declarations seen
   in ignored materialized issue worktrees cannot establish current-main
   provenance or a valid import graph.

3. **Blocker: F01/F03/F04 callable contracts remain incomplete.**
   QPBT-023 is explicitly blocked (`workflow/state/issues.json:735-766`) because
   names and carrier policies are frozen but exact signatures, finite domains,
   distributions, state representation, return/error types, and imports are
   omitted. QPBT-013 depends on both QPBT-004 and QPBT-023 and requires those
   exact interfaces before dispatch (`workflow/state/issues.json:398-418`).

4. **High: self-dual basis proof/algorithm is an open paper gap.**
   The pinned paper requires the efficient basis construction (original
   `finite-fields.tex:1603-1608`). A Mathlib source search in the available
   package found normal-basis infrastructure but no self-dual-normal-basis
   theorem specialized to `GaloisField 2 k` with odd `k`. This cannot be hidden
   behind an arbitrary assumption or an untracked axiom; QPBT-023 must record a
   source-anchored internal obligation and a discharge plan while preserving the
   paper theorem's assumptions.

5. **High: namespace/type collision requires an adapter boundary.**
   Provisional ignored worktree files expose both `MIPStarRE.Quantum.Measurement`
   (POVM effects) and `MIPStarRE.LDT.Measurement` (the LDT hierarchy). They have
   different fields and semantics. F03 must qualify the Quantum type and add
   explicit adapters rather than aliasing or opening LDT names.

6. **Medium: F04 is not a direct alias of existing state code.**
   Provisional LDT `QuantumState` is a density-matrix/PSD representation,
   whereas the F04 boundary requires a normalized bipartite pure state and
   explicit local-isometry conjugation. Existing finite-Hilbert matrix helpers
   may be reused only after signatures and scalar/coercion obligations are
   frozen; silently coercing `WithLp`, matrices, and operators would violate
   the blueprint boundary.

## Smallest sufficient issue sequence

1. Unblock QPBT-003 source/integration gates and materialize the authenticated
   source tree with `READY` and manifest checks.
2. Complete QPBT-023: publish exact F01/F03/F04 declarations, imports,
   universes, finite/decidable instances, domains, distributions, state and
   distance return types; add the self-dual-basis paper-gap note and discharge
   plan; obtain an independent immutable contract review.
3. Dispatch QPBT-013 with ownership restricted to the two stated files. Validate
   each file, declaration integrity, no `sorry`/`axiom`, blueprint sync, scoped
   build, and the full build/cache gates only after source and project trees are
   canonical.
4. Keep F02/F05/G01 downstream until F01 is proven and its API is stable; do not
   introduce a generic carrier wrapper to bypass the direct `GaloisField 2 k`
   requirement.

## Read-only checks

* `git rev-parse HEAD` -> `7526e58663f4a93c6643d936cb6cedb8df6e090b`.
* `git rev-parse HEAD^{tree}` -> `e45a463ae0a58f8faf4c3d10329a6f68b08b19e2`.
* `python3 scripts/workflow.py validate` -> valid; counts were 24 issues,
  11 pull requests, 0 planned sessions, 256 issued sessions, 7 stages.
* `python3 blueprint/check.py --check` -> `OK: 48 nodes, 12 chapters, acyclic
  graph, deterministic outputs`.
* Negative tree checks: `sections/` absent; tracked `MIPStarRE/QPBT`,
  `MIPStarRE/Quantum`, and `MIPStarRE/LDT` each contain zero paths.

No build, compile, cache, network, endpoint, source materialization, or file
mutation was performed. Token usage was not exposed.
