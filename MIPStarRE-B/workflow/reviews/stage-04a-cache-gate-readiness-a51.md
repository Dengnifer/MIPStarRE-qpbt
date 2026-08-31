# Cache gate readiness handoff

Session: `i000-scout-a51-cache-gate-readiness`
Audit clone: `/tmp/qpbt-scout-a51-cache-gate`
Audited commit: `7526e58663f4a93c6643d936cb6cedb8df6e090b`
Audited tree: `e45a463ae0a58f8faf4c3d10329a6f68b08b19e2`
Verdict: **no-go for warm/seed now; read-only preparation is complete**.
Elapsed: approximately 12 minutes, including the 285-test aggregate run.
Token usage: unavailable and not estimated.

The clone was created without network from the repository and checked out
detached at the exact SHA. Its status is clean. No canonical repository,
workflow state, source tree, worktree, cache, or runtime file was edited. No
network request, Lean/Lake build, hot-cache warm, or cache seed was run.

## Current ledger and ownership

* QPBT-004 is `planned`, depends on QPBT-003, and requires pinned Lean/Mathlib,
  reusable-foundation provenance, and an empty-project build/cache gate
  (`workflow/state/issues.json:138-163`). Its unblock condition still requires
  a new fixed LPR-005 head, fresh immutable approval, and exactly one singleton
  hot-main cache-get/Lake build.
* QPBT-003 is `blocked` on QPBT-002 and QPBT-009 and requires integration of
  approved ranges, combined source/blueprint checks, and a second main commit
  (`workflow/state/issues.json:107-135`).
* QPBT-018 is in `review`; LPR-007 is a `draft` at old base
  `687e182c7ad41520c226a59160c084ab53ad6f38`, head
  `e21c9cda11803f7564a500c005fd55882530538d` (`workflow/state/prs.json:1945-2034`).
  Its two changed paths are `scripts/hot_main_cache.py` and
  `tests/test_hot_main_cache.py`. Reviews A01 and A02 are blocked because the
  required singleton warm was not accepted (`workflow/state/prs.json:2001-2024`);
  the EXDEV fallback candidate is not a current-main approval.
* QPBT-021 is `blocked`; LPR-010 is `changes_requested` at old base
  `7669f70be786a53ba1a0a92c1d347f5fe7544681`, head
  `2b161993ed258ee8f0bd99d591fcabdcb47ffe43`
  (`workflow/state/prs.json:2753-2762`). Open blocker
  `F-LPR010-A06-001` is the serial aggregate failure at
  `tests/test_local_agent.py:500`; medium `F-LPR010-A06-002` records a malformed
  diff-check command even though the corrected command passes
  (`workflow/state/prs.json:2838-2867`). LPR-010 owns
  `scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`,
  `protocols/CHANGELOG.md`, `protocols/orchestration.md`, and `workflow/README.md`.
  It cannot be approved or integrated from this stale head without a rebase and
  fresh checks/review.

LPR-007 and LPR-010 overlap both implementation/test paths. They therefore have
no concurrent writable lane. Rebase/repair QPBT-021 first, obtain a fresh review,
then rebase QPBT-018 onto the resulting main and obtain its fresh review. Do not
cherry-pick either old candidate directly onto current main.

## Cache identity and recipe

The canonical recipe is `qpbt-hot-main`, version 4
(`scripts/hot_main_cache.py:145-168`):

```text
lake --packages=.lake/package-overrides.json exe cache get
lake --packages=.lake/package-overrides.json build
python3 scripts/materialize_mipstarre.py materialize --archive-env MIPSTARRE_ARCHIVE
python3 scripts/materialize_lake_packages.py materialize --archive-directory-env LAKE_PACKAGE_ARCHIVES
python3 scripts/materialize_lake_packages.py verify
```

The cache identity hashes `lean-toolchain`, `lakefile.toml`,
`lake-manifest.json`, the five additional materializer/provenance files, the
exact recipe argv, and the selected main commit
(`scripts/hot_main_cache.py:382-433`, `145-168`). Read-only status on the audit
clone, using an isolated runtime directory, returned:

```text
cache_key 25e3ba6d0270bd5154c58ddc2105246b6a80e65bc9e540b20f2a20d066d8d6be
main_commit 7526e58663f4a93c6643d936cb6cedb8df6e090b
status miss
recipe qpbt-hot-main version 4
```

No READY snapshot exists for this key. Omitted `--runtime-dir` derives the
shared `.workflow-runtime` from the primary Git worktree; an explicit runtime
directory is allowed for status but must not be used to create a competing
builder cache (`scripts/hot_main_cache.py:521-563`, `1405-1464`). Warm elects
one owner under the per-key `flock`, builds in a detached clone, verifies source,
packages, commit/input identity, and artifact inventory, then atomically publishes
`manifest.json` and `READY` (`scripts/hot_main_cache.py:982-1185`). Seed waits on
the same cache lock, validates a registered non-main worktree, copies to a
private writable `.lake`, and deeply verifies the destination
(`scripts/hot_main_cache.py:1222-1397`).

The current main source contains no `MATHLIB_SOURCE`, `MATHLIB_ARCHIVE`, or
`LAKE_PKG_URL_MAP` handling (`rg` over `scripts/hot_main_cache.py`,
`protocols/orchestration.md`, and `protocols/local-development.md` returned no
matches). Thus setting a local Mathlib variable cannot make this exact snapshot
offline; the LPR-010 implementation must first be repaired, rebased, reviewed,
and integrated. The archive variables are mandatory recipe inputs, not labels:
`MIPSTARRE_ARCHIVE` is consumed by foundation materialization and
`LAKE_PACKAGE_ARCHIVES` by package materialization (documented in
`workflow/reviews/stage-04a-qpbt017-cache-protocol.md:20-50`).

## Authenticated local inputs

The following inputs are available as read-only evidence on this machine:

* MIPStarRE archive:
  `/tmp/qpbt-010-acquisition.FJmb6mA8/MIPStarRE-verified.tar.gz`, 1,989,153
  bytes, SHA-256
  `656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc`, matching
  `references/mipstarre-upstream.json`.
* Eight Lake package archives under
  `/home/drx/MIPStarRE-auto/.workflow-runtime/acquisitions/lake-packages-20260830/`.
  Their names and SHA-256 values match all eight entries in
  `references/lake-packages.json` (plausible, LeanSearchClient, importGraph,
  proofwidgets, aesop, Qq, batteries, and Cli). The read-only hash command
  matched the committed package digests; no package archive was modified.
* Pinned Mathlib source:
  `/tmp/qpbt018-mathlib-source.t8E8oS/mathlib`, clean shallow Git repository,
  commit `81a5d257c8e410db227a6665ed08f64fea08e997`, tree
  `5ea66b811b8461daae82f14d356fed2a287d7c40`, `git fsck --full` passed. Its
  source pack digest is
  `4659f2a0cabfec474474f5e83ea3d495e711b735418742dd3d642328adcada02`.
  Normalized archive `/tmp/mathlib-81a5d257-shallow-repo.tar.gz` is 51,938,317
  bytes with SHA-256
  `c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`.

These paths are temporary or ignored acquisition evidence, not current-main
canonical inputs. The audit environment had all four variables unset:
`MIPSTARRE_ARCHIVE`, `LAKE_PACKAGE_ARCHIVES`, `MATHLIB_SOURCE`, and
`MATHLIB_ARCHIVE`. The Mathlib source must be admitted through the repaired
QPBT-021 contract; do not rely on an ephemeral path after review.

## Exact next cache gates

Do not run these commands until QPBT-021 and QPBT-018 have been rebased onto the
current integrated main as needed, their exact scoped/aggregate/checker/
compileall/validation/diff gates pass, and fresh independent immutable reviews
approve the new heads.

1. Rebase QPBT-021 onto current main; repair the open aggregate baseline gate or
   obtain an explicit protocol-approved waiver. Reconcile the malformed
   historical diff check in the PR ledger. Then run the registered QPBT-021
   focused, serial aggregate, checker, compileall, workflow validation, and
   corrected `git diff --check BASE..HEAD` commands on the frozen new SHA.
2. Rebase QPBT-018 onto that resulting main (the paths overlap), run its scoped
   checks and fresh immutable review, and preserve the EXDEV retry evidence.
3. After both reviews and QPBT-003 integration/second-commit admission, run one
   elected warm with exactly one local Mathlib selector plus both archive inputs.
   The command template is:

```text
MATHLIB_SOURCE=/tmp/qpbt018-mathlib-source.t8E8oS/mathlib \
MIPSTARRE_ARCHIVE=/tmp/qpbt-010-acquisition.FJmb6mA8/MIPStarRE-verified.tar.gz \
LAKE_PACKAGE_ARCHIVES=/home/drx/MIPStarRE-auto/.workflow-runtime/acquisitions/lake-packages-20260830 \
python3 scripts/hot_main_cache.py \
  --repo-root /home/drx/MIPStarRE-auto \
  --project-dir . \
  --main-commit <NEW_INTEGRATED_MAIN_SHA> \
  warm
```

   `MATHLIB_ARCHIVE` may replace `MATHLIB_SOURCE`, but both must not be set.
   Use the shared default runtime under the primary worktree for the real
   election; do not pass the isolated audit runtime. Capture JSON cache key,
   elected owner, lock wait, materialization/package verification, build
   duration, source evidence, artifact inventory, log path, and `READY` digest.
4. Only after a verified READY snapshot is published, seed a newly registered
   private issue worktree once:

```text
python3 scripts/hot_main_cache.py \
  --repo-root /home/drx/MIPStarRE-auto \
  --project-dir . \
  --main-commit <NEW_INTEGRATED_MAIN_SHA> \
  seed --worktree /home/drx/MIPStarRE-auto/.workflow-runtime/worktrees/<fresh-issue>
```

   The target must be a live non-main Git worktree with matching cache-key
   inputs. Never share a writable `.lake/build` tree or run a second builder.

## Checks run on the clean detached clone

* Clone and identity: exact detached `HEAD=7526e586...`, tree
  `e45a463a...`, clean status.
* `python3 scripts/workflow.py validate`: valid; 24 issues, 11 pull requests,
  0 planned sessions, 245 issued sessions, 7 stages.
* `python3 blueprint/check.py --check`: `OK: 48 nodes, 12 chapters, acyclic
  graph, deterministic outputs`.
* `python3 -m unittest discover -s tests -p 'test_hot_main_cache.py' -q`:
  28 tests passed in 3.530 seconds.
* `python3 scripts/check_workflow.py`: 285 aggregate tests passed in 78.473
  seconds.
* `python3 hot_main_cache.py ... status` with isolated `/tmp` runtime: cache
  miss and key shown above; no runtime files were created.
* `sha256sum` of Mathlib, MIPStarRE, and all eight Lake archives matched the
  committed evidence. `git diff --check` passed on the clean clone.

No warm, seed, source materialization, network, Lean/Lake build, canonical
state edit, or cache mutation was performed. Token usage is unavailable.
