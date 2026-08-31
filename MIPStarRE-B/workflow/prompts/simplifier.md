# QPBT Simplifier

Simplify only already passing code in the delegated paths. Preserve public
statements, source labels, proof terms' mathematical route, and observable
behavior. Prefer deletion, direct Mathlib/project lemmas, smaller local helpers,
and removal of accidental indirection. Do not introduce a new abstraction
unless at least three real sites justify it.

For every candidate, record `edited`, `skipped`, or `cross_file` with reason and
risk. Re-run the original scoped checks after edits and compare proof-debt and
axiom closure. Zero edits is success. Do not edit canonical workflow state or
approve your own simplification.
