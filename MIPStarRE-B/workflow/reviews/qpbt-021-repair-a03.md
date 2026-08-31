# QPBT-021 Exact-Base Replay Handoff

Logical session: `i021-orchestrator-a03-rebase-pr-base`

This bounded implementation was performed in the isolated clone
`/tmp/qpbt-021-repair-a03`. The canonical repository, workflow state, events,
PR ledgers, research metrics, and other worktrees were not edited. No nested
agents were used.

## Immutable identities

Requested exact base:

```
base commit  7669f70be786a53ba1a0a92c1d347f5fe7544681
base tree    48f451bc82f2037abe09e9d97130fdb4d0cbdd53
```

Source candidate inspected in `/tmp/qpbt-021-repair-a02`:

```
old head     63d1e9e9807412008f7174199fdcd1ca11787890
old parent   7526e58663f4a93c6643d936cb6cedb8df6e090b
old tree     204ca4af35939f989c85828da97012cea8879fb9
```

Final exact-base replay:

```
head         c37431ec44c3d1f281a31c1a2125ace3ca590716
head tree    1d51c83e63835bffd7d885988c392ba37a291d05
parent       7669f70be786a53ba1a0a92c1d347f5fe7544681
subject      feat(workflow): support local pinned mathlib cache input
```

The clone is detached at the final commit and clean (`git status --short
--branch` reports `## HEAD (no branch)`).

## Replay and conflict resolution

The initial attempt applied only the parent-relative patch
`63d1e9e^..63d1e9e`. That produced commit `01b376a52788d178228d5beeb36922146e3af339`
but would have omitted LPR-011 runtime changes already present in the
candidate's newer parent. It was discarded in the isolated clone before any
handoff.

The final replay reset the clone to the requested base and applied the complete
candidate-head diff restricted to the five owned paths:

```
git diff --binary 7669f70be786a53ba1a0a92c1d347f5fe7544681..63d1e9e9807412008f7174199fdcd1ca11787890 -- \
  protocols/CHANGELOG.md protocols/orchestration.md scripts/hot_main_cache.py \
  tests/test_hot_main_cache.py workflow/README.md > /tmp/qpbt-021-a03-full-five.patch
git apply --check /tmp/qpbt-021-a03-full-five.patch
apply_check_exit=0
git apply /tmp/qpbt-021-a03-full-five.patch
git commit -m "feat(workflow): support local pinned mathlib cache input"
```

The three-way application had one changelog conflict because the candidate's
newer parent supplied the intervening QPBT-022 `0.1.6` entry. Resolution
retained the exact-base `0.1.5` history and added the candidate's QPBT-021
`0.1.7 candidate` entry; the parent-only `0.1.6` text was not imported as an
unowned historical change. The complete five-path patch applies directly to
the exact base without conflict after this resolution.

## Scope and runtime preservation

The exact old-base range contains only:

```
protocols/CHANGELOG.md
protocols/orchestration.md
scripts/hot_main_cache.py
tests/test_hot_main_cache.py
workflow/README.md
```

The range summary is `5 files changed, 2162 insertions(+), 14 deletions(-)`.
The final script contains the LPR-011 shared-runtime implementation, including
`default_runtime_dir` and explicit `--runtime-dir` handling at
`scripts/hot_main_cache.py:620-662` and `:2438-2474`, in addition to the local
pinned Mathlib source/archive contract. The candidate's source-authentication,
archive validation, URL-map preservation, and pre-publication recheck changes
are present in the same owned file.

## Validation evidence

All bytecode was redirected to `/tmp/qpbt-021-a03-pyc2` and test logs to
`/tmp/qpbt-021-a03-*.log`.

Focused cache tests:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/qpbt-021-a03-pyc2 \
python3 -m unittest discover -s tests -p 'test_hot_main_cache.py' -v
Ran 42 tests in 9.849s
OK
focused_exit=0
```

Exact serial aggregate:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/qpbt-021-a03-pyc2 \
python3 -m unittest discover -s tests -v
Ran 185 tests in 58.363s
OK
aggregate_exit=0
```

Workflow checker:

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/qpbt-021-a03-pyc2 \
python3 scripts/check_workflow.py
Ran 185 tests in 58.862s
OK
check_workflow_exit=0
```

Additional gates:

```
python3 -m compileall -q scripts tests
compileall_exit=0

python3 scripts/workflow.py validate
{"valid": true, "counts": {"issues": 12, "pull_requests": 0,
 "planned_sessions": 0, "issued_sessions": 38, "stages": 7}}
validate_exit=0

git diff --check 7669f70be786a53ba1a0a92c1d347f5fe7544681..c37431ec44c3d1f281a31c1a2125ace3ca590716
diff_check_exit=0
```

The final worktree remained clean after all gates. No Lean, Lake, full build,
hot-main warm, cache publication, or network command was run; no cache
artifact is claimed. The source/archive provisioning and singleton cache gate
remain separate post-review operations.

## Handoff

The exact-base candidate is available for an independent immutable review at
base `7669f70be786a53ba1a0a92c1d347f5fe7544681`, head
`c37431ec44c3d1f281a31c1a2125ace3ca590716`, tree
`1d51c83e63835bffd7d885988c392ba37a291d05`. A reviewer should verify the five
paths, source/mathlib contract, and retained LPR-011 runtime behavior before
any cache warm or integration decision.

Accounting: one isolated clone creation, one discarded parent-relative replay,
one final exact-base replay, subagents `0`, Lean/Lake/build invocations `0`,
network requests `0`, cache warms `0`. Elapsed time was approximately 8
minutes. Collaboration token usage is unavailable (`null`) and was not
estimated.
