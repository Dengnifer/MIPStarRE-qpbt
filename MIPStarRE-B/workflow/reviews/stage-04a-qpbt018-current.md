# QPBT-018 current-main provenance and cache audit

Audit target: supplied current main `5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6`,
tree `544aac816db08aea60ef231bbc951992bc86f9e5`, parent
`8bf8ee89d24d833c28ecce6ce7e08c42e28b614f`.

Candidate LPR-007 is recorded as draft with base
`687e182c7ad41520c226a59160c084ab53ad6f38d` and head
`e21c9cda11803f7564a500c005fd55882530538d`; its tree is
`a64c98c23f34416f60cf9c9127655ed108f3e64e`. The candidate ancestry is
`687e182 -> 1273f1dc9fed33b6a5eafd5e25e6081c8b32ceb7 -> e21c9cda` (two
commits after the old base), and its changed paths are exactly
`scripts/hot_main_cache.py` and `tests/test_hot_main_cache.py`.

This was a read-only audit. The canonical worktree was already dirty in
`workflow/events.jsonl` and `workflow/state/sessions.json`; those changes were
preserved. No source/state/ledger files were changed by the audit, and no
network, Lean, Lake, build, hot-main warm, or seed command was run. Elapsed
time was approximately 8 minutes; collaboration token usage is unavailable.

## Findings (ordered by severity)

### Blocker: candidate is not reviewable against current main

The canonical repository cannot resolve `e21c9cda11803f7564a500c005fd55882530538d`
(`git cat-file -t` fails), nor the old base `687e182c...`. The exact objects do
exist in `/tmp/qpbt018-review-clone`, whose detached/branch head is
`e21c9cda...` with tree `a64c98...`; that clone is clean and records
`e21c9cda` parent `1273f1d...`, parent `687e182...`. The candidate therefore
cannot be rebased, reviewed, or integrated from canonical main until its
objects are transported into a controlled temporary/worktree repository and a
new immutable head is produced. The existing two formal reviews were both
blocked for this provenance/warm reason (`workflow/reviews/qpbt-018-review-a01-
blocked.md`, `qpbt-018-review-a02-blocked.md`).

Even if the candidate object is provisioned, its base is stale: current main
`5d36cdf...` contains later runtime/source/blueprint integration commits. A
fresh candidate must be rebased onto current main (or onto the exact main that
will be integrated), then all checks and review must bind the new base/head/tree.

### Blocker: required singleton warm has no accepted READY artifact

The read-only status command

`python3 scripts/hot_main_cache.py --repo-root /home/drx/MIPStarRE-auto --project-dir . --runtime-dir /home/drx/MIPStarRE-auto/.workflow-runtime --main-commit 5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6 status`

reports cache key
`808d09441cd2f4c44c49597304d458ab2a78b6e4dcf6970f98603260281f69e6`, main
commit `5d36cdf...`, and `status: miss`; its snapshot/`.lake/build` path has
no published READY marker. Historical candidate warm metrics show the only
changed-hypothesis run reached source and package materialization, then failed
at Lake dependency retrieval with `curl 56 GnuTLS recv error (-54); early EOF`
(`research/metrics/incidents.jsonl:36`, failure record under
`.workflow-runtime/cache/failures/45ecc...-20260831T104453-2`). No candidate
snapshot was published.

The exact EXDEV finding is still open (`INC-032`): the initial
`git clone --local --no-checkout` failed with `Invalid cross-device link`; no
READY artifact was published. Candidate `1273f1d` adds one bounded retry with
`--no-local`, and `e21c9cda` adds a warm-level invalid-checkout/no-READY test.
The candidate tests and prior A02 review report no code findings on the frozen
old base, but that evidence is not approval for a rebased head.

### Blocker: local mathlib input is available as evidence but not consumed by this recipe

The eight exact Lake package archives are present under
`.workflow-runtime/acquisitions/lake-packages-20260830/`; their names and
digests match `references/lake-packages.json`. The authenticated MIPStarRE
archive exists at `/tmp/qpbt-010-acquisition.FJmb6mA8/MIPStarRE-verified.tar.gz`
with SHA-256
`656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc`.
The local shallow mathlib source is
`/tmp/qpbt018-mathlib-source.t8E8oS/mathlib`, commit
`81a5d257c8e410db227a6665ed08f64fea08e997`, tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`, with pack digest
`4659f2a0cabfec474474f5e83ea3d495e711b735418742dd3d642328adcada02`; its
normalized archive `/tmp/mathlib-81a5d257-shallow-repo.tar.gz` has digest
`c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`.

However, canonical `5d36cdf` and LPR-007 still invoke the pinned mathlib URL
through Lake and have no `MATHLIB_SOURCE`, `MATHLIB_ARCHIVE`, or
`LAKE_PKG_URL_MAP` handling (`rg` over `scripts/hot_main_cache.py` and
`protocols/orchestration.md` found none). The shell has neither archive
environment variable exported. LPR-010/QPBT-021 is the implementation that
introduces deterministic local mathlib consumption, but it is `changes_requested`
with open findings and changes the same cache/test paths. Do not try another
QPBT-018 warm until QPBT-021 is repaired, reviewed, and integrated or its
equivalent is present in the rebased QPBT-018 head.

## Candidate implementation audit

In `/tmp/qpbt018-review-clone`, the two-file diff from old base is 30 added/8
removed lines in `scripts/hot_main_cache.py` and 60 added lines in
`tests/test_hot_main_cache.py`. `_detached_clone` retries exactly once with
`--no-local` only when the newly appended clone log contains `cross-device` or
`exdev`; it removes a partial checkout, records an explicit retry marker, then
performs the exact detached checkout. Existing warm code rechecks HEAD,
identity inputs, source changes, source evidence, and real `.lake/build` before
publication (`scripts/hot_main_cache.py:1067-1135` on the candidate). The new
tests cover retry ordering and that a failed detached checkout retains failure
evidence without creating a snapshot or READY (`tests/test_hot_main_cache.py`
candidate additions around `test_detached_clone_retries_without_local...` and
`test_warm_exdev_fallback_checkout_failure...`). No standalone code finding was
established from this old-base inspection; current-main review remains
mandatory because QPBT-022 and QPBT-021 touch the same file.

## Safe lane and exact next gates

There is no safe concurrent writable repair lane for QPBT-018 while LPR-010 is
active: both own `scripts/hot_main_cache.py` and `tests/test_hot_main_cache.py`.
QPBT-021 additionally owns `protocols/CHANGELOG.md`,
`protocols/orchestration.md`, and `workflow/README.md`; do not cherry-pick or
edit overlapping files in parallel. The safe sequence is:

1. Preserve `/tmp/qpbt018-review-clone` as immutable evidence and provision its
   exact objects into a controlled temporary clone. Rebase a new QPBT-018
   worktree onto current main `5d36cdf...` after resolving any QPBT-021 cache
   changes; record new base/head/tree SHAs.
2. Complete QPBT-021's local pinned-mathlib repair and fresh review first (its
   current aggregate baseline blocker is recorded in
   `workflow/reviews/qpbt-021-local-mathlib.md`). This is necessary to make the
   QPBT-018 singleton warm offline and avoids competing writers/builds.
3. On the rebased QPBT-018 head run the registered exact checks:
   `python3 -m unittest discover -s tests -p test_hot_main_cache.py -v`,
   `python3 scripts/check_workflow.py`,
   `python3 -m compileall -q scripts tests`,
   `python3 scripts/workflow.py validate`, and a correctly SHA-bound
   `git diff --check BASE..HEAD`. Then run one singleton warm using absolute
   candidate script and authenticated `MIPSTARRE_ARCHIVE`,
   `LAKE_PACKAGE_ARCHIVES`, and local pinned mathlib input. Record lock wait,
   build, cache key, source/package verification, and READY evidence.
4. Only after the warm publishes a verified snapshot, dispatch a fresh
   independent immutable reviewer against the new base/head/tree. The reviewer
   must inspect the EXDEV-only boundary, exact detached identity, no-READY
   failure path, cache provenance, and absence of shared writable `.lake/build`.

## Verdict

**GO only for read-only preparation; NO-GO for rebase, approval, integration, or
another warm now.** The candidate's EXDEV implementation is plausible and its
old-base checks passed, but candidate object transport, stale ancestry, shared
cache-path ownership with QPBT-021, and the missing local-mathlib-backed READY
artifact are all unresolved acceptance blockers. Do not alter issue/PR status or
waive the singleton warm gate based on the historical failed run.

