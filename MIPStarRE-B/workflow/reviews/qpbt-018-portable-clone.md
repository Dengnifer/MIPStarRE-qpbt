# QPBT-018 Portable Detached Clone Evidence

## Frozen candidate

- Base: `687e182c7ad41520c226a59160c084ab53ad6f38`
- Head: `e21c9cda11803f7564a500c005fd55882530538d`
- Tree: `a64c98c23f34416f60cf9c9127655ed108f3e64e`
- Changed paths: `scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`
- Candidate worktree: `/tmp/qpbt018-review-clone`

## Deterministic checks

- Focused cache tests: 25/25 passed
- Aggregate workflow checks: 143/143 passed
- Python compile check: passed
- Diff hygiene: passed
- EXDEV regression: local clone -> bounded `--no-local` retry -> exact detached checkout
- Invalid fallback checkout regression: no `READY` or snapshot is published and failure evidence is retained

## Singleton warm evidence

The first attempt used the base checkout script by operator mistake and failed at
the local clone with `Invalid cross-device link`; it published no artifact
(INC-035, session `i018-auditor-a07-warm-script-path-mismatch`).

The changed-hypothesis attempt used the absolute candidate script and exact local
source/package archive inputs. It successfully retried with `--no-local`,
materialized and verified the source plus all eight package archives, and checked
out the exact candidate head. Lake then failed while cloning pinned mathlib from
GitHub (`curl 56 GnuTLS recv error`, early EOF), so no `READY` file or snapshot
was published (INC-036, session `i018-builder-a08-mathlib-fetch-failure`).

The authenticated singleton cache gate therefore remains blocked until a local,
verified pinned mathlib source is supplied. No further warm is authorized under
this candidate without a changed acquisition hypothesis.

## Review disposition

Fresh immutable reviews A01 and A02 found no code findings but were blocked by
candidate transport and the failed/unexecuted warm gate. A new immutable review
is required after the local mathlib acquisition gate is satisfied.
