# Stage 04A cache and parallelism audit

Date: 2026-08-31 (Asia/Shanghai)
Snapshot: `e2446272a3cc904a612d7e0e5003074ef4a680ad`

Scope was read-only inspection of `scripts/hot_main_cache.py`,
`tests/test_hot_main_cache.py`, the local-development/orchestration protocol,
workflow state, and existing runtime metrics. No source/state edits, network,
Lean/Lake invocation, or build was performed. The only generated artifact is
this evidence report.

## Verdict

The singleton and parallel-copy design is structurally sound, but the current
main snapshot is not cache-ready in this environment. Two existing issues are
justified and remain the smallest sufficient work: QPBT-018/LPR-007 for the
cross-device detached-clone fallback, and QPBT-017 for protocol identity
synchronization. QPBT-021 remains the separate measured mathlib transport
blocker. No additional cache or parallelism issue is warranted by this audit.

## Findings

### HIGH: current main warm cannot cross the repository/cache mount boundary

`HotMainCache._detached_clone` invokes `git clone --local` unconditionally
(`scripts/hot_main_cache.py:920-930`). The live runtime has reproduced this
operation failing with `Invalid cross-device link` while creating a pack index;
there is no fallback in the current `e244627` source. A failed warm retains a
failure record and does not publish `READY`, which is correctly fail-closed, but
it prevents the singleton cache from ever becoming available on this mount.

Evidence: `.workflow-runtime/metrics/hot-main.jsonl` records clone failures in
0.027289 s and 0.095936 s; the retained log at
`.workflow-runtime/cache/failures/45ecc.../build.log` contains `fatal: failed to
create link ... Invalid cross-device link`. QPBT-018 (`workflow/state/issues.json`
around lines 572-610) and draft LPR-007 already require an EXDEV-only bounded
`--no-local` object-copy retry, exact detached identity rechecks, and a
no-`READY` regression. Do not create a duplicate issue. LPR-007 is not approved:
its authenticated singleton warm gate is explicitly unexecuted.

### MEDIUM: operator cache protocol is incomplete relative to the canonical recipe

The implementation identity binds the recipe schema, exact materialization and
package commands, five additional identity files, and source-contract evidence
(`scripts/hot_main_cache.py:103-168`, `:622-655`).
`protocols/local-development.md:29-36` documents only the main SHA, three core
pin hashes, and dependency/build recipe argv; it omits source-contract fields,
package materialization/verification commands, archive environment prerequisites,
and the additional identity files. This can lead an operator to compute or
review the wrong cache identity even though code readiness checks remain strict.

This is the recorded INC-033 drift and planned QPBT-017
(`workflow/state/issues.json:542-569`). Its acceptance gates already specify a
focused omission regression, changelog entry, and fresh documentation review;
no new issue is needed.

### HIGH (environmental blocker, existing): pinned mathlib retrieval dominates warm time

The prior authenticated candidate warm passed source/package gates and then
spent `1009.436415` seconds in `lake ... exe cache get` before failing on a
GitHub clone (`.workflow-runtime/metrics/hot-main.jsonl`, failure retained at
`.workflow-runtime/cache/failures/45ecc...-20260831T104453-2/build.log`). No
`READY` snapshot was published. This is not a safe parallelism opportunity:
duplicating cache-get/build work would violate the singleton rule and amplify
network contention. QPBT-021 is the existing blocked issue requiring an exact
local pinned mathlib source or archive and a no-network regression. Until it is
resolved, the cache gate must remain blocked/fail-closed.

## Singleton and parallel behavior

`CacheIdentity.create` hashes the exact main commit, all recipe-selected input
blobs, recipe payload, and source contract (`scripts/hot_main_cache.py:622-655`).
The lock path includes the resulting key (`:825-833`), so concurrent warm calls
for one identity elect one builder; calls for different immutable keys may run
independently in separate staging directories. `warm` checks readiness before
and after acquiring `ExclusiveLock` (`:982-1043`), builds in a detached clone,
verifies HEAD/input/source identity after compilation, computes a full artifact
inventory, makes the staging tree read-only, and publishes via one directory
rename (`:1045-1171`). Failed staging is retained and never published
(`:1186-1220`). Metrics use a separate short-held append lock
(`:885-902`), so metrics cannot serialize the build itself.

`seed` first joins the cache election, then takes a per-target lock
(`scripts/hot_main_cache.py:1323-1339`). It copies the cache with reflinks or
byte-copy fallback, never hardlinks (`:667-726`), makes the destination writable,
and validates a deep inventory before completing. A private backup and rollback
cover replacement failures (`:1283-1397`). This supports parallel seeding to
different worktrees while preventing two writers to the same target. The
hot-main builder remains singleton per cache key; dispatch capacity must not be
used to start competing builders or share writable `.lake/build` trees.

## Measured bottlenecks and safe options

* Current `status` and `warm --dry-run` both complete in about 0.14 s and report
  a cache miss for the current head/key `79f72a...`; these are cheap identity
  probes and do not build.
* Actual warm cost is dominated by detached clone portability and, after the
  fallback candidate, pinned mathlib network retrieval (~1009 s). Parallel
  Lean/Lake builds are not a remedy.
* Safe parallel work consists of read-only analysis/review with disjoint owned
  paths, or seeding distinct issue worktrees after one verified cache exists.
  One elected builder warms a key; waiters consume its immutable publication.
  Explicit runtime directories intentionally create isolated cache domains and
  must not be mistaken for shared singleton capacity.
* The existing QPBT-019 capacity-aware dispatcher should gate agent admission;
  its aggregate capacity does not relax this cache singleton. A future
  read-only status/metrics view may help operators choose parallel waves, but a
  guessed default or automatic competing warm would be unsafe.

## Acceptance checks run

* `/usr/bin/time -f 'ELAPSED %e s' python3 -m unittest discover -s tests -p
  'test_hot_main_cache.py' -v`: **28 tests, OK**, test body 3.584 s, wall
  3.72 s. This covers exact identity, recipe command restrictions, source and
  package post-build checks, no-READY failure retention, linked-worktree shared
  runtime, two-process singleton election, private writable seeding, symlink
  rejection, deep inventory, and rollback.
* `python3 scripts/hot_main_cache.py --repo-root . status`: exit 0, current key
  `79f72a...`, status `miss`, elapsed 0.14 s.
* `python3 scripts/hot_main_cache.py --repo-root . warm --dry-run`: exit 0,
  `would_build: true`, same key, elapsed 0.14 s.
* Read-only inspection of the retained metrics/logs confirmed the EXDEV and
  1009-second mathlib failures above.

No compileall, checker, workflow mutation, Lean/Lake, network, or cache warm was
run for this audit.

## Residual risk

The cache implementation's filesystem checks and atomic publication assume the
runtime root itself is trusted; explicit runtime directories can intentionally
isolate cache domains. Provider/network availability and mount topology remain
external facts. Until QPBT-018's fallback and QPBT-021's local mathlib source
are accepted, the correct operational result is a blocked cache gate, not
parallel duplicate builds.
