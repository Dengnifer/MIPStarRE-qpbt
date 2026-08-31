# QPBT Source and Discrepancy Map

Project-authored map for the Lean formalization. It paraphrases structure and
does not reproduce the paper source.

## Pin

- Paper: Ji, Natarajan, Vidick, Wright, and Yuen, *MIP* = RE*.
- Version: arXiv:2001.04383v3, revised 2022-11-04.
- Abstract: https://arxiv.org/abs/2001.04383v3
- Source: https://arxiv.org/src/2001.04383v3
- Retrieved local archive SHA-256:
  `d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`.
- Retrieved local PDF SHA-256:
  `3310802ab185fb1c7051a274064ed16d5a8ce70444ab784d68f349de12777017`.

Version 3 is mandatory. Version 1 uses an obsolete seven-component parameter
tuple; versions 2 and 3 use `(q, m, d)` and the repaired low-individual-degree
soundness route.

## Local source layout

`source-pin.json` authenticates the archive and its two fixed regular members.
`split-manifest.json` gives the closed output-path convention, inclusive source
line range, byte count, SHA-256, and lexical label count for every generated
fragment. `RIGHTS.md` records why all author-owned source and derived fragments
remain ignored.

After `python3 scripts/reference_source.py materialize`, use:

- `source/compression_arXiv_v3.tex` as the exact CRLF-preserving primary source;
- `sections/top-level/` for the 15-fragment exact reconstruction;
- `sections/qpbt/` for the three Section 7.3 and seven Appendix A fragments;
- `sections/dependencies/` for the nine intentionally sparse dependency excerpts;
- `sections/labels.json` for all 646 ordered lexical label occurrences, including
  one-based line and byte-column positions, half-open absolute source byte
  ranges, and every containing split-file path; and
- `sections/inventory.json` plus `sections/READY` as the verified generation
  boundary. A tree without a matching `READY` marker is not usable source.

The QPBT main collection exactly covers lines 5028-5766 and the Appendix
collection exactly covers lines 13032-14930. The top-level collection exactly
reconstructs all 14,935 lines. Dependency excerpts are deliberately sparse and
must not be concatenated as a source reconstruction.

## Primary QPBT regions

Original source lines refer to `compression_arXiv_v3.tex` from the pinned
archive.

| Lines | Paper unit | Labels/content ownership |
| ---: | --- | --- |
| 5028-5046 | Section 7.3 introduction | `sec:pauli-verifier` |
| 5047-5104 | 7.3.1 game setup | `sec:qld-game` |
| 5106-5109 | admissible parameters | `def:admissible` |
| 5111-5220 | typed question distribution | `eq:pauli-type`, `fig:type-graph-pauli` |
| 5221-5294 | conditionally-linear functions | sampler functions |
| 5295-5377 | decision procedure | `eq:gamma-value`, seven checks |
| 5378-5568 | perfect-strategy completeness | `lem:pauli-completeness` |
| 5576-5594 | quantitative soundness | `thm:pauli` |
| 5595-5639 | qubit conversion | `cor:pauli-binary` |
| 5640-5766 | canonical parameters/complexity | `def:introparams`, `lem:delta-bound`, `lem:introparams-complexity`, `lem:qld-complexity` |
| 13032-13085 | Appendix A statement/roadmap | `sec:qld-analysis`, `thm:pauli-appendix` |
| 13086-13195 | A.1 preliminaries | `sec:qld-prelim` |
| 13196-13402 | A.2 strategies | `sec:commutation` |
| 13403-13718 | A.3 expanded observables | `sec:expanding` |
| 13719-14006 | A.4 combine X/Z | `sec:combining` |
| 14007-14453 | A.5 apply classical LDT | `sec:apply-ldt` |
| 14454-14930 | A.6 separate X/Z and conclude | `sec:separating` |

## Appendix proof spine

1. A.3-A.6 develop probability, state-dependent distance, Fourier-observable,
   and POVM-to-PVM tools.
2. A.7 extracts consequences of passing the seven QPBT checks.
3. A.8-A.10 derive point consistency, twisted commutation, and projective line
   measurements after an explicit Naimark/ancilla expansion.
4. A.11 uses orthonormalization and quantum linearity; A.12 is the imported
   quantum-linearity theorem.
5. A.13-A.15 paste X/Z data into a strategy for the classical simultaneous
   individual low-degree test.
6. A.16-A.20 define restricted-line couplings and prove the consistency bounds
   used by A.15.
7. A.21 applies classical LDT soundness to obtain a global polynomial-pair
   measurement.
8. A.22-A.24 construct exact generalized Pauli operators, prove consistency,
   and extract EPR pairs with local unitaries.
9. A.24 proves A.1/Theorem 7.14; Lemma 3.26 yields Corollary 7.15.

Completeness Lemma 7.13 is a separate branch using low-degree encoding,
generalized Pauli Fourier identities, and the perfect Magic Square construction.

## Same-paper dependencies

- Section 3.3, lines 1317-1728: finite fields, trace, self-dual bases, and
  admissible field sizes.
- Section 3.4, lines 1729-1822: individual-degree polynomials and low-degree
  encoding/decoding.
- Section 3.6, lines 1854-1948: measurements, observables, and postprocessing.
- Section 3.7, lines 1949-2162: generalized Pauli operators/projectors,
  Fourier transforms, twisted commutation, and qudit-to-qubit conversion.
- Section 4, lines 2163-2877: conditionally-linear maps and samplers.
- Sections 5.1-5.2, lines 2884-3417: strategies, state-dependent distances,
  commutation analysis, and pasting.
- Section 6, lines 3567-4148: typed samplers, deciders, and graph distributions.
- Section 7.1, lines 4163-4659: classical simultaneous individual LDT and
  Theorem 7.8.
- Section 7.2, lines 4660-5027: Magic Square game, rigidity, and perfect
  construction.

## External result boundaries

The blueprint must choose and pin exact versions before treating these as
formal dependencies:

- arXiv:1904.05870v3, Section 6/Theorem 6.4: direct QPBT ancestor.
- arXiv:2111.08131, Theorem 4.7: tensor-code soundness used for Theorem 7.8.
- arXiv:2009.12982v1: corrected individual-degree soundness and
  Naimark/orthonormalization machinery.
- arXiv:1610.03574v1: quantum linearity theorem used as A.12.
- arXiv:1709.09267v2, Theorem 6.9: Magic Square rigidity.
- arXiv:1012.4728v2: historical orthonormalization ancestor.

The total-degree soundness route in arXiv:1801.03821v2 is explicitly reported
as having a gap and is not an acceptable trusted soundness boundary.

## Discrepancy ledger

These require explicit blueprint decisions and issue `QPBT-009`; do not silently
normalize them.

1. Theorem 7.14/A.1 declares isometries with `alice`/`bob` suffixes but uses
   `A`/`B` suffixes in the conclusion.
2. Corollary 7.15 changes the displayed argument order of the robustness
   function between declaration and use.
3. Theorem A.24 proves a squared-norm estimate while Theorem 7.14/A.1 states a
   norm estimate. The square-root and universal-constant reparameterization
   must be a named Lean bridge.
4. A.8 has source label prefix `len:` rather than `lem:`.
5. A.7's Magic Square condition omits the individual-degree embedding on two
   vectors although the surrounding definitions require it.
6. A.7 implicitly reduces to `6*m*d <= q`; the complementary trivial-robustness
   case needs an explicit Lean case split.
7. Theorem 7.14 omits a nonnegative domain for epsilon although real powers
   occur. The Lean API should expose a faithful probability domain.
8. Theorem 7.8 omits admissible-field and divisibility hypotheses used
   immediately by its proof; QPBT supplies them but its formal interface must
   say so.
9. Theorem 7.8 contains stray code-distance notation in the Reed-Solomon
   parameter tuple.
10. Claim A.19 contains a capital measurement index where context requires the
    sampled point.
11. Theorem 7.14 starts from arbitrary POVMs while Appendix A works with a
    projective strategy only after an explicit Naimark dilation. Preserve that
    boundary in Lean.
12. Lines 13835-13870 establish approximate linearity only after averaging over
    both the fiber variables `(x,z)` and the linearity-test variables, while line
    13871 invokes quantum linearity separately for every fixed `(x,z)` with one
    error parameter. The proof needs an explicit bad-fiber, conditioning, or
    block-diagonal argument before this can become a Lean theorem boundary.

## Rights

The source page identifies arXiv's non-exclusive distribution license, not a
Creative Commons downstream reuse license. The repository commits this map,
checksums, manifests, and deterministic tooling. Fetched source and generated
split TeX remain ignored unless a compatible redistribution permission is
recorded. This is provenance guidance, not legal advice.
