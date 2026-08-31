# Source Rights and Local Materialization

The pinned source is Ji, Natarajan, Vidick, Wright, and Yuen, *MIP* = RE*,
arXiv:2001.04383v3. The arXiv source page records arXiv's non-exclusive
distribution license. It does not identify a Creative Commons license granting
this repository downstream redistribution rights.

Accordingly, the repository commits only project-authored provenance, split
metadata, source maps, and deterministic tooling. The fetched
`compression_arXiv_v3.tex` and `compression_arXiv_v3.bbl` files and all byte
slices generated from them remain ignored. A compatible redistribution grant
must be recorded before any of those author-owned bytes are committed.

This file documents the project's conservative handling decision and is not
legal advice. The authoritative source endpoints are:

- Abstract: <https://arxiv.org/abs/2001.04383v3>
- Pinned source: <https://arxiv.org/src/2001.04383v3>

Exact archive and member checksums are in `source-pin.json`. Run
`python3 scripts/reference_source.py materialize` to acquire and build the
ignored local tree, or pass an already acquired pinned archive with
`--archive PATH`. Run `python3 scripts/reference_source.py verify` before using
the generated sections as a formalization source.
