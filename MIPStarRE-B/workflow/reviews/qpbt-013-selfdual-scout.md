# QPBT-013 F01 self-dual-basis reconnaissance

Session `i013-scout-a25-selfdual` ran read-only on base
`7669f70be786a53ba1a0a92c1d347f5fe7544681`; duration 30.514 seconds; edits,
network calls, Lean/Lake builds, and child sessions: zero.

The paper's F01 contract (finite-fields.tex:62-83, 283-317) requires a
self-dual **normal** basis for `GaloisField 2 k` with odd `k`. The pinned
Mathlib sources provide `GaloisField` instances/cardinality/finrank,
trace-form nondegeneracy, `traceDual`, and ordinary normal-basis APIs, but no
self-dual-normal existence theorem or odd-degree criterion. The available
`exists_orthogonal_basis` route requires invertible `2` and is unusable in
characteristic two. Repository search found no faithful theorem to import.

Do not assert the standard external criterion as a Lean fact without a source
proof. Split preparation into independent read-only carrier, trace-dual, and
normal-basis scouts, then issue a sequential faithful existence lane; if the
theorem is absent, record an explicit blocker or assumption boundary in the
blueprint rather than using `infer_instance`.

Nested Codex capability evidence: installed `codex-cli 0.151.0` exposes
`exec review` and `exec fork/resume`; an isolated strict-config parser probe
returns unsupported (code 2), so `scripts/local_agent.py` falls back to the
generic bounded `codex exec --json` harness. No live model/network child was
launched; parser evidence is mocked and endpoint-specific confirmation remains
open.
