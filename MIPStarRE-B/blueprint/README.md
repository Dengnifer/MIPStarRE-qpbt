# QPBT Lean Blueprint

This is the speculative, source-faithful blueprint for the quantum Pauli basis
test in arXiv:2001.04383v3. It remains provisional until `QPBT-002` and
`QPBT-009` are accepted. The blueprint contains no copied author TeX and makes
no claim that a planned Lean declaration exists.

`metadata/nodes.json` is the canonical declaration and dependency graph.
`metadata/gaps.json` records every source-facing repair, and
`metadata/external-sources.json` records exact external trust boundaries. Run:

```sh
python3 blueprint/check.py --check
# Integration gate: run from the immutable combined Stage-2/3 tree.
python3 blueprint/check.py --check \
  --source-root references/2001.04383v3
python3 -m unittest discover -s blueprint/tests -p 'test_*.py'
make -C blueprint pdf
```

For every node, `transitive_definitions` is the sorted set of definition-kind
nodes in its strict prerequisite closure. The checker derives this closure and
rejects missing, extra, or theorem-valued entries. Every declared target has a
source-controlled required spine, and the checker rejects missing targets,
detached dependencies, and unresolved external theorem pins on any target's
dependency path. `EXT-TENSOR` records
the official arXiv metadata contract for `2111.08131v3` (published version,
last revised 2022-12-06); this pins the source boundary but does not claim its
theorem has been proved in Lean.

The source-root gate verifies each generated-file anchor and its corresponding
original `compression_arXiv_v3.tex` line using the split manifest. The
standalone Stage-3 branch intentionally lacks that source payload, so it cannot
pass the exact gate; integration must rerun it against the immutable combined
Stage-2/3 tree. A missing source root fails closed and is not evidence that the
anchors were checked. `--write` regenerates `generated/graph.json`,
`generated/graph.dot`, and the TeX entry fragments. `--check` fails if any
generated output is stale.

The Lean-facing metadata is also an API compatibility contract. It fixes the
concrete `GaloisField 2 k` model and exact odd-exponent admissibility, qualified
arbitrary POVMs, bundled normalization, sigma codecs into uniform outcome
alphabets, Euclidean/`WithLp`/operator adapters, transparent bipartite
isometries, separate `SquaredRealizes` and public `Realizes` certificates, and
`Real.rpow`. Carrier universes and required finite/decidable instances are
explicit. The minimal-skeleton stage plan has exactly one `sorry`, at
`MIPStarRE.QPBT.pauliSoundness`; the complete-skeleton stage may expose the
additional tracked proof debt needed for all blueprint declarations. No
conditional helper moves public proof debt into an assumption.

The PDF is written to `blueprint/build/main.pdf`. Build products and the
Graphviz SVG are ignored. The PDF target verifies that all planned Lean
identifiers remain extractable, that at least one physical page exists, and
that every extracted word has positive area, stays within its page, and does
not overlap another extracted word. The tracked DOT and JSON are deterministic
review artifacts.
