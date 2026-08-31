# Paper, Blueprint, and Lean Protocol

## Pinned source

The QPBT source is arXiv:2001.04383v3, revised 2022-11-04. The v1 formulation is
not interchangeable: it uses a materially different parameterization. Pin the
download URL, version, source checksum, extraction checksum, and split manifest.
Do not silently update the paper version.

The core route includes Section 7.3 (game, completeness, soundness, canonical
parameters) and Appendix A (soundness analysis). The dependency map must also
identify required material from preliminaries, conditionally linear games, the
classical low individual-degree test, and the Magic Square game. A citation is
not a dependency proof: every imported prerequisite must have an explicit
formalization boundary.

The arXiv source is copyright material distributed under arXiv's terms. Keep a
provenance and rights notice. Local splitting is for this formalization; do not
claim that the repository grants a license to redistribute the paper text.

## Source split

The canonical downloaded source remains immutable and local. A deterministic
script creates one ignored TeX file per top-level chapter/appendix and one per
included section, without rewriting mathematical content. The committed split
manifest records source line ranges, headings, labels, expected output
checksums, and QPBT relevance. Re-running the splitter must reproduce the same
local outputs byte-for-byte.

By default, commit only the fetch/verify/split tooling, manifests,
project-authored source maps, and rights notice. `references/2001.04383v3/source/`
and `references/2001.04383v3/sections/` are ignored. Vendoring the author TeX
requires a recorded compatible license or permission and an explicit protocol
review.

## Blueprint gates

The blueprint is organized by proof dependency and theorem ownership, not raw
paper order. Every entry has:

- a paper source path, label, and precise informal statement;
- intended Lean declaration and module;
- definitions used transitively;
- prerequisites and downstream consumers;
- encoding choices and boundary hypotheses;
- status (`not-started`, `statement`, `proved`, or `paper-gap`); and
- `\lean{...}` only when the declaration exists, with `\leanok` only when its
  transitive axiom closure is free of `sorryAx`.

Before the blueprint commit, independently audit coverage, dependency acyclicity,
source fidelity, naming, and main-theorem reachability.

## Skeleton stages

The minimal skeleton contains a structured file tree, the source-faithful main
QPBT theorem with a tracked `sorry`, and every definition used transitively in
its type. It need not yet expose all intermediate theorem statements.

The complete skeleton contains every definition and theorem statement in the
approved blueprint. Proofs may be tracked `sorry`; forbidden ambient assumptions
may not replace them. Each statement must type-check and carry its source label.

The proof stage follows the dependency graph. A theorem is complete only when
its body is proved, its source-integrity audit passes, and downstream declarations
type-check. The final gate scans all QPBT modules and blueprint-linked axiom
closures for unintended proof debt.

## Paper gaps

If the source omits a needed step, appears false, or differs from the intended
Lean domain, create a self-contained note under `docs/paper-gaps/` and a linked
issue. State the paper claim, exact formal obstruction, smallest faithful
restricted result if any, and discharge/repair plan. A paper-gap note documents
debt; it does not authorize advertising a conditional helper as the paper result.
