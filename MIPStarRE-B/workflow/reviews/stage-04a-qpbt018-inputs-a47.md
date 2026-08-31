# QPBT-018 input and singleton-gate audit (i000-scout-a47-qpbt018-inputs)

## Immutable snapshot

Canonical main is `7526e58663f4a93c6643d936cb6cedb8df6e090b`, parent
`5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6`, subject
`chore(workflow): record frontier gate audit`. The canonical worktree has
unrelated dirty coordinator files: `research/metrics/sessions.jsonl`,
`workflow/events.jsonl`, and files under `workflow/state/`. No files were
changed by this audit.

LPR-007/QPBT-018 remains recorded as `draft`/`review` with old base
`687e182c7ad41520c226a59160c084ab53ad6f38` and head
`e21c9cda11803f7564a500c005fd55882530538d`; its changed paths are exactly
`scripts/hot_main_cache.py` and `tests/test_hot_main_cache.py`.
Those candidate objects are not reachable from canonical Git refs (the
canonical `git cat-file`/revision-range checks fail), although the preserved
temporary clone `/tmp/qpbt018-review-clone` has head `e21c9cda` and parent
`1273f1dc9fed33b6a5eafd5e25e6081c8b32ceb7`.

The rebased QPBT-021/LPR-010 candidate is preserved separately at
`/tmp/qpbt-021-repair-a02`, branch `repair/qpbt-021-a02`, head
`63d1e9e9807412008f7174199fdcd1ca11787890`, parent exactly
`7526e58663f4a93c6643d936cb6cedb8df6e090b`, tree
`204ca4af35939f989c85828da97012cea8879fb9`. It is clean and its diff from
current main is five paths:

```text
protocols/CHANGELOG.md
protocols/orchestration.md
scripts/hot_main_cache.py
tests/test_hot_main_cache.py
workflow/README.md
```

The PR ledger currently records this head but still labels LPR-010
`changes_requested` and leaves findings `F-LPR010-A06-001` (aggregate baseline
failure at `tests/test_local_agent.py:500`) and `F-LPR010-A06-002` (a malformed
historical diff-check command) open. No fresh immutable approval is recorded
for `63d1e9e`; old review evidence is for `2b161993` or older bases. The
candidate's two-dot `git diff --check 7526e586..63d1e9e` exits 0.

Commands run (read-only):

```text
git rev-parse HEAD; git show -s --format=... HEAD
git -C /tmp/qpbt-021-repair-a02 show -s --format=... HEAD
git -C /tmp/qpbt-021-repair-a02 status --short --untracked-files=no
git -C /tmp/qpbt-021-repair-a02 diff --name-status 7526e586..HEAD
git -C /tmp/qpbt-021-repair-a02 diff --check 7526e586..HEAD
```

## Cache identity and current status

`python3 scripts/hot_main_cache.py status` on current main returned:

```text
cache_key 25e3ba6d0270bd5154c58ddc2105246b6a80e65bc9e540b20f2a20d066d8d6be
main_commit 7526e58663f4a93c6643d936cb6cedb8df6e090b
recipe qpbt-hot-main version 4
status miss
```

The current-main script contains no `MATHLIB_SOURCE` or `MATHLIB_ARCHIVE`
handling; only the package archive environment is present in its materialize
command. Local Mathlib support is implemented only by the unapproved LPR-010
candidate (`scripts/hot_main_cache.py:1008-1221,1636-1774` in the temporary
candidate). Therefore invoking warm from current main cannot satisfy the
offline pinned-Mathlib gate and must not be used as QPBT-018 evidence.

No current-key READY directory was found. Three old lock files exist under
`.workflow-runtime/locks/` for other cache keys; there is no lock file for the
current key. They do not establish a running or published current warm.

## Authenticated local inputs

The exact pinned Mathlib source is available and independently checked:

```text
/tmp/qpbt018-mathlib-source.t8E8oS/mathlib
  HEAD 81a5d257c8e410db227a6665ed08f64fea08e997
  tree 5ea66b811b8461daae82f14d356fed2a287d7c40
  clean detached shallow source; fsck --full passed in prior local check
/tmp/mathlib-81a5d257-shallow-repo.tar.gz
  51,938,317 bytes; sha256 c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7
/tmp/mathlib-81a5d257c8e410db227a6665ed08f64fea08e997.bundle
  sha256 a0cf67420c92a39a29fc785ad4014c5db9aa12baaf372598cb12414c7a671ffc
```

The authenticated MIPStarRE archive is present:

```text
/tmp/qpbt-010-acquisition.FJmb6mA8/MIPStarRE-verified.tar.gz
  1,989,153 bytes; sha256 656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc
  matches references/mipstarre-upstream.json (commit 507e81220d95266ff3d589d125b2f87c7300a9fb)
```

All eight pinned Lake package archives are present under
`.workflow-runtime/acquisitions/lake-packages-20260830/` (Cli,
LeanSearchClient, Qq, aesop, batteries, importGraph, plausible, and
proofwidgets), with filenames carrying the revisions from
`references/lake-packages.json`. The current shell has all four required
environment variables unset: `MATHLIB_SOURCE`, `MATHLIB_ARCHIVE`,
`MIPSTARRE_ARCHIVE`, and `LAKE_PACKAGE_ARCHIVES`.

## Go/no-go and smallest next action

**Singleton warm: no-go at this snapshot.** A warm must run the reviewed
LPR-010 candidate (or its integrated successor), with exactly one authenticated
Mathlib input and both `MIPSTARRE_ARCHIVE` and `LAKE_PACKAGE_ARCHIVES` set. The
candidate must first receive a fresh immutable review at its current parent
and head; the stale open findings must be reconciled, and the malformed ledger
check must not remain a passed gate. QPBT-018 cannot warm concurrently because
LPR-007 owns the same two cache/test paths and its head is stale/unreachable.

Smallest bounded action: perform a fresh read-only immutable review of
`/tmp/qpbt-021-repair-a02` at `63d1e9e` against `7526e586`, then bind that exact
head in the PR ledger. If approved, run one elected warm from that exact
candidate with absolute local inputs, record the cache identity/lock/build
result, and only then rebase QPBT-018 onto the integrated main for its own
fresh review. Do not run a warm from current main or from the stale LPR-007
clone.

Accounting: elapsed time was not instrumented; exposed token usage is
unavailable (`null`, not estimated). Network requests, Lean/Lake invocations,
builds, cache warm/seed operations, and nested agents: 0 each.
