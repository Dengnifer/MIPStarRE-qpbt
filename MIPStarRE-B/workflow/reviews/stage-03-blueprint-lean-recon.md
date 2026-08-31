# Stage 3 Blueprint and Lean Reconnaissance

- Sessions: `i003-scout-a01-blueprint-recon`, `i003-scout-a02-lean-reuse`
- Issue: `QPBT-003`
- Backend: Codex collaboration, read-only
- Workspace edits: none

The source scout mapped Section 7.3 and Appendix A into a public QPBT surface,
an explicit proof dependency graph, 19 proposed blueprint chapters, and named
internal error terms. The Lean scout audited the upstream project at Lean and
Mathlib 4.32.0, identified reusable field, measurement, state-distance,
Naimark, orthonormalization, and LDT APIs, and proposed minimal and full QPBT
file trees under `MIPStarRE/QPBT/`.

The reconnaissance identified three additional statement-integrity boundaries:

1. the paper says `ind_m(u) = 0` iff `u = 0`, although the indicator vector is
   never zero;
2. the claimed cross-basis commutation for arbitrary vectors is false without
   the generalized Pauli phase;
3. Appendix A invokes classical LDT in dimension `2m+2`, while its earlier CL
   encoding assumes the dimension divides `q`, which QPBT admissibility does
   not provide.

These are inputs to `QPBT-009`, not silent extra hypotheses. The recommended
formalization boundary uses finite coordinate Hilbert spaces, explicit
POVM/PVM postprocessing, heterogeneous questions via dependent sums, and a
public soundness theorem with no bridge or extraction assumptions.

Exact elapsed times and token usage were not exposed by the collaboration
backend; the canonical sessions record the coordinator-observed time window.

## Follow-up preflight

Sessions `i003-scout-a03-upstream-api-map`,
`i003-scout-a04-source-dependency-graph`, and
`i003-scout-a05-blueprint-toolchain` refined the implementation boundary. The
minimal QPBT package should separate parameters, generalized Pauli operators,
the typed game, pure strategies, local extraction, the classical LDT adapter,
and public soundness. Existing LDT measurement and distance APIs are reusable
only after heterogeneous carriers are explicitly transported; `Test.mainFormal`
does not supply the QPBT isometries or generalized Pauli rigidity conclusion.

The source proof graph has no mathematical cycle. Lean should topologically
move the helper `lem:qld-constructing-the-paulis-helper` before its consumer and
keep the quantum-linearity theorem as an explicit external boundary. The main
soundness theorem is blocked by six source-facing nodes: the false indicator
claim, omitted win-implication cases/indices, the average-to-fixed-fiber
linearity jump, malformed restricted-line references, missing LDT divisibility
and proof content, and the final squared-norm-to-norm/suffix bridge.
Completeness remains independently reachable.

The local blueprint should use twelve dependency-oriented chapters, one
canonical `\uses` edge list, source/status/Lean-plan metadata, and visible
statement-integrity tables. A standard-library checker can validate coverage,
acyclicity, reachability, paper-gap links, and deterministic JSON/DOT output.
The installed XeLaTeX/latexmk and Graphviz tools support the mandatory local
PDF/static gates. Web output remains unavailable until exact leanblueprint,
plasTeX, and TexRA artifacts are pinned; the absent tools must not be installed
implicitly during a build.

## QPBT-009 disposition audit

Session `i009-scout-a01-gap-dispositions` used the generated, checksum-bound
QPBT fragments to expand the six blocking groups into thirteen issue-ready
dispositions. Bracketed numbers below are original source lines.

| ID | Generated anchor | Required disposition | Public effect |
| --- | --- | --- | --- |
| G01 | `appendix-preliminaries.tex:34` [13119] | Replace the false `ind_m(u)=0 iff u=0` step by the partition-of-unity identity `sum_y ind_{m,y}(u)=1`, then derive the advertised probability bounds. | Proof repair only. |
| G02 | `appendix-strategies.tex:42-104,130` [13237-13300,13325], `appendix-combine-xz.tex:32` [13750] | Use indicator indices in Magic-Square conditioning, quantify `u in F_q^m`, change the second point basis from `X` to `Z`, and enumerate all seven decider edges and orientations. | Intended tests restored. |
| G03 | `appendix-strategies.tex:92-97` [13287-13297] | Give internal A.7 hypothesis `6*m*d <= q`; split the public proof and discharge the complementary branch by a large universal robustness coefficient, without circularly citing the result. | Public theorem unchanged. |
| G04 | `qpbt-game-and-soundness.tex:533-591` [5579-5635] | Normalize `phi_alice,phi_bob`, one robustness argument order, and the probability-error domain `0 <= eps <= 1`. | Typo repair plus intended domain. |
| G05 | `appendix-separate-xz-conclude.tex:256-369,450-462` [14709-14915] | Add a named squared-distance-to-norm robustness bridge, including the invalid `||(H-I)psi||^2 <= delta` substitution and small/large-error cases. | Reparameterizes polynomial constants/exponent only. |
| G06 | `appendix-strategies.tex:112` [13307] | Preserve malformed source label provenance but expose normalized alias `lem:qld-win-implications-obs`. | Metadata only. |
| G07 | `appendix-strategies.tex:8-16` [13203-13211] | Prove one simultaneous local Naimark dilation for all finite POVM families, correlation preservation, and composition with extracted isometries. | Removes an implicit proof boundary. |
| G08 | `appendix-combine-xz.tex:117-153` [13835-13871] | Replace the average-to-fixed-fiber jump by a good/bad fiber argument with threshold `eta`, yielding `O(delta/eta+eta)`. | Internal exponent loss only. |
| G09 | `appendix-separate-xz-conclude.tex:37-43` [14490-14496] | State the generalized phase `(-1)^(Tr(e_j*e_j'*(u dot v)))`; do not claim cross-basis commutation without proving its phase vanishes. | False intermediate weakened; downstream use retained. |
| G10 | `dependencies/classical-ldt.tex:399-443` [4561-4605] | State admissible field/dimension hypotheses, correct the Reed-Solomon tuple, and formalize the tensor-code/simultaneous-coordinate reduction. | Literal internal theorem narrowed to its defined game. |
| G11 | `appendix-apply-classical-ldt.tex:300-321` [14306-14327] | Avoid the unjustified `(2m+2) | q` invocation by proving a direct `Fin n`-axis LDT and equivalence when divisibility happens to hold. | Preserves QPBT assumptions. |
| G12 | `appendix-apply-classical-ldt.tex:71-275` [14077-14281] | Repair restricted-line punctuation, basis/point indices, missing Property 3 and expectations, complement estimate, and malformed duplicate reference; formalize mixture weights. | Proof repair only. |
| G13 | `appendix-apply-classical-ldt.tex:432` [14438] | Replace the `similar calculation` placeholder by a named triple-product consistency bound, then handle the `alpha=0` mass separately. | Fills real proof debt. |

Recommended order is: public statement table; G01/G09 field and Pauli algebra;
G10 then G11 classical LDT; G07 Naimark; G02/G03 finite-case extraction;
G08 fiberwise linearity; G12 restricted lines; G13 separability; and finally
G05 public robustness. G06 lands before blueprint cross-links.

External boundaries requiring exact version pins are `arXiv:1904.05870v3`
(QPBT ancestor and quantum-measurement infrastructure), `arXiv:2111.08131`
(version still unresolved; tensor-code soundness), `arXiv:2009.12982v1`
(Naimark/orthonormalization), `arXiv:1610.03574v1` (quantum linearity),
`arXiv:1709.09267v2` (Magic Square rigidity), and optionally
`arXiv:1012.4728v2` for historical orthonormalization provenance.
`arXiv:1801.03821v2` is gap-bearing and may be recorded only as excluded
provenance, not trusted as a theorem boundary.

## Dependency-oriented implementation plan

Session `i009-scout-a02-blueprint-dependency-plan` (UTC 2026-08-30 19:13:36
to 19:17:27, 231 seconds) checked the materialized fragments against the gap
matrix and produced an acyclic implementation order:

```text
field/code + quantum API
  -> generalized Pauli algebra
  -> typed seven-check QPBT game
  -> simultaneous Naimark + strategy consequences
  -> expanded observables + fiberwise joint measurements
  -> restricted lines + direct-axis classical LDT
  -> global polynomial-pair measurement
  -> exact Pauli representation
  -> squared extraction + proved norm robustness
  -> public soundness -> binary corollary -> canonical parameters
```

Completeness branches after the typed game and is independent of the
soundness chain. The proposed Lean package separates `Basic`, `Game`, and
`Analysis` modules, followed by public `Soundness`, `Binary`, and
`CanonicalParameters` modules. The thirteen recommended work packages cover
blueprint metadata/gap links, foundations, game/completeness, Naimark,
strategy consequences, fiber linearity, direct-axis LDT, restricted lines,
global measurement, exact Pauli, extraction/robustness, public
soundness/binary, and complexity. G01-G13 remain separately named proof
obligations, and no external pin authorizes a Lean axiom.

## Decimal freeze and fidelity follow-up

The five-path exact-Decimal PDF candidate passed independent A11 review and was
frozen at `38e199c89140e2b188c7464f76e5fff4c0d0e1c1`. Before any formal reviewer
dispatch, the root recorded 20/20 tests, the 46-node/12-chapter graph, combined
exact source anchors, compile and diff hygiene, a forced 43-page PDF with 107
identifiers, the 324,172-byte base patch, and the 4,263-byte 39-path manifest.

A parallel read-only pre-review then found six fidelity/checker gaps: the F10
Pauli-binary and A04 reverse-order source repairs were not declared; K03/K04
overstated their source anchors and omitted proof dependencies; only the
soundness target was validated; the one-hole wording did not say minimal
skeleton; and empty PDF geometry did not fail closed. This scout is explicitly
not a formal disposition. A bounded repair is active, and the next formal
review will bind a new immutable head after fresh combined checks.

Session `i003-fixer-a25-blueprint-fidelity` completed the bounded 13-path
candidate in 433 seconds. It records the F10 and A04 source corrections, adds
the missing canonical-complexity dependencies, validates all targets and the
minimal one-hole contract, and rejects empty PDF geometry. The candidate passes
26/26 tests, a 48-node graph, exact combined source anchors, compile and diff
hygiene, and a fresh 45-page/109-identifier PDF. Its 69,043-byte patch hashes to
`fa2716e1427efeaa769e0c94bd7b5e2661a53ad5b463178dcf5a6068c731cb96`;
the 1,349-byte framed manifest hashes to
`a290d85c6856d2f1bca738635e13cba9e21ad7d38d821903c8ee7c0c346a91d3`.
Independent candidate review is active before any new freeze.

## Full approval and integration rehearsal

The source-fidelity candidate was frozen at
`3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd`. Formal session
`i003-reviewer-a30-full-blueprint-immutable` reviewed the complete range from
the first commit and approved it with zero findings after 26 tests, the
48-node graph, exact 39-file/646-label source validation, and a forced
45-page/109-identifier PDF gate.

Session `i003-scout-a31-second-commit-rehearsal` then applied the exact
QPBT-010, QPBT-002, QPBT-012, and blueprint ranges in a disposable tree. The
55-path composition had zero conflicts and zero overlaps and passed 191
aggregate tests plus all source, blueprint, graph, PDF, workflow, compile, and
hygiene gates. The real worktree and Git refs were unchanged; QPBT-004 was
explicitly excluded from this rehearsal.
