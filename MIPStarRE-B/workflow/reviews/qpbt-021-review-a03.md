# LPR-010 / QPBT-021 Immutable Review A03

Logical session: `i021-reviewer-a03-cache-repair`

Verdict: `approve`

This independent review examined the clean owned worktree
`/tmp/qpbt-021-repair-a02`. No source, PR, workflow state, metrics, or other
canonical files were edited. The only write was this report. No network, Lean,
Lake, hot-main warm, or cache build was run.

## Immutable identity and scope

```
base commit  7526e58663f4a93c6643d936cb6cedb8df6e090b
base tree    e45a463ae0a58f8faf4c3d10329a6f68b08b19e2
head commit  63d1e9e9807412008f7174199fdcd1ca11787890
head tree    204ca4af35939f989c85828da97012cea8879fb9
parent       7526e58663f4a93c6643d936cb6cedb8df6e090b
```

`git status --short --branch` reports only the clean branch
`repair/qpbt-021-a02`. The exact base-to-head diff is five paths:

```
protocols/CHANGELOG.md
protocols/orchestration.md
scripts/hot_main_cache.py
tests/test_hot_main_cache.py
workflow/README.md
```

No unintended files or whitespace errors were found. The requested source
handoff path `workflow/reviews/qpbt-021-repair-a02.md` is absent; the available
handoff `/tmp/qpbt-021-repair-a02-report.md` was inspected instead.

## Findings and prior dispositions

No new finding was established.

F-LPR010-A06-001 (prior blocker) is addressed by a new exact serial aggregate
run on this frozen rebased head. The previously failing
`test_process_timeout_terminates_descendants_in_the_new_process_group` passed
within the 299-test run. The prior canonical finding/evidence remains history
for the coordinator to reconcile against this new head; it was not edited here.

F-LPR010-A06-002 (prior medium ledger evidence issue) is addressed for new
evidence by the exact two-dot command below. The malformed historical command
must remain recorded and receive an explicit coordinator disposition; it was
not silently removed.

```
git diff --check 7526e58663f4a93c6643d936cb6cedb8df6e090b..63d1e9e9807412008f7174199fdcd1ca11787890
exit 0
```

## Source fidelity and cache behavior

The candidate binds the project root Lake manifest to the exact pinned Mathlib
URL and revision (`scripts/hot_main_cache.py:1638-1679`) and the audited tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`. Local source validation at
`:963-1106` rejects symlinked/special Git metadata, external common directories,
alternates, replacement refs, hidden index flags, unsafe local config, and
dirty repositories before object reads. Archive validation and extraction at
`:1109-1344` enforce the exact compressed/tar sizes and digests, safe member
paths, symlink graph, Git metadata, and post-extraction commit/tree checks.

The warm path requires exactly one local source/archive input before cache-hit
or build decisions (`:1749-1769`), constructs a sorted `LAKE_PKG_URL_MAP` while
preserving unrelated package entries (`:1603-1635`), and rechecks source
identity before publication (`:2138-2143`). The archive extraction is cleaned
before `.lake` publication. Source paths remain runtime inputs rather than
cache identity inputs, and no untrusted Git configuration is inherited.

The current LPR-011 shared-runtime behavior remains intact at
`:620-662` and `:2438-2474`; focused tests include omitted-runtime linked
worktree election and explicit runtime override coverage. No changed code adds
an arbitrary assumption, external proof debt, or a public bypass of the
authenticated Mathlib contract.

Local contract evidence inspected:

```
root lake-manifest.json mathlib revision:
  81a5d257c8e410db227a6665ed08f64fea08e997
audited source tree:
  5ea66b811b8461daae82f14d356fed2a287d7c40
archive SHA-256:
  c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7
archive bytes: 51938317
git bundle verify: is okay; ref 81a5d257... HEAD
```

## Exact checks

Fresh focused command with bytecode redirected outside the clone:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/qpbt021-review-a03-pyc \
python3 -m unittest discover -s tests -p 'test_hot_main_cache.py' -v
Ran 42 tests in 9.225s
OK
```

Fresh exact registered serial aggregate:

```
python3 -m unittest discover -s tests -v
Ran 299 tests in 80.454s
OK
```

Additional read-only gates:

```
python3 -m compileall -q scripts tests
exit 0

python3 scripts/workflow.py validate
{"valid": true, "counts": {"issues": 24, "pull_requests": 11,
 "planned_sessions": 0, "issued_sessions": 245, "stages": 7}}

git diff --check 7526e58663f4a93c6643d936cb6cedb8df6e090b..63d1e9e9807412008f7174199fdcd1ca11787890
exit 0
```

The worktree remained clean after all checks. The singleton cache gate was not
run and no cache artifact is claimed; authenticated runtime environment inputs
must still be provisioned separately before warm.

## Recommendation and accounting

The candidate is approved for coordinator integration/reconciliation as the
unchanged immutable head `63d1e9e`. A subsequent cache gate remains a distinct
operation: provision exactly one authenticated local Mathlib source/archive,
the MIPStarRE archive, and package archives; then elect exactly one shared
hot-main warm and record its lock/build evidence. Do not run a second builder or
share writable `.lake/build` output.

Elapsed time: approximately 12 minutes including the focused and aggregate
runs. Subagents: 0. Lean/Lake/build invocations: 0. Network requests: 0. Cache
warms: 0. Collaboration token usage is unavailable (`null`) and was not
estimated.
