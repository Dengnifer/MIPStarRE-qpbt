# MIPStarRE QPBT

Lean 4 formalization of the quantum Pauli basis test (QPBT) used in
`MIP* = RE` (arXiv:2001.04383v3).

This repository follows the local analogue of the workflow evolved in
[LionSR/MIPStarRE](https://github.com/LionSR/MIPStarRE). The mathematical
source, blueprint, and Lean implementation have a strict source-of-truth order:

1. `references/` contains the pinned paper sources and provenance.
2. `blueprint/` contains the dependency-tracked formalization design.
3. `MIPStarRE/` contains the Lean declarations and proofs.

GitHub issues, pull requests, CI caches, and review bots are replaced by local,
versioned state and fresh Codex sessions. See [protocols/README.md](protocols/README.md)
and [workflow/README.md](workflow/README.md).

## Project stages

1. Establish the local workflow and research instrumentation.
2. Split the QPBT reference source into one TeX file per chapter or section.
3. Build a paper-traceable Lean blueprint.
4. Implement a minimal theorem skeleton, the complete declaration skeleton,
   and then all proofs through dependency-ordered local issues.

Every implementation issue has one orchestrator. Provers, scouts, reviewers,
and simplifiers are bounded child sessions. A fresh read-only reviewer must
approve a local PR after its validation gate passes.

## Current status

Canonical machine-readable status lives in `workflow/state/`; research
measurements live in `research/metrics/`. Stage boundaries and commits are
recorded there rather than duplicated in this overview.
