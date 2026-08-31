# QPBT-021 Rebase Repair Handoff

Logical session: `i021-orchestrator-a02-local-mathlib-rebase`

This handoff was produced in the owned clone `/tmp/qpbt-021-repair-a02` only.
No canonical repository files, workflow state/events, PR ledgers, metrics, or
other worktrees were edited. The historical malformed diff-check record was
not deleted or rewritten.

## Replay identity

The repair clone started clean at current main:

```
base commit 7526e58663f4a93c6643d936cb6cedb8df6e090b
base tree   e45a463ae0a58f8faf4c3d10329a6f68b08b19e2
base parent 5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6
```

The candidate was imported from the local candidate worktree object store:

```
old head   2b161993ed258ee8f0bd99d591fcabdcb47ffe43
old tree   f72a535413e8d9627654ca43a5a789632d5e83bc
old base   7669f70be786a53ba1a0a92c1d347f5fe7544681
```

`git rebase --onto 7526e58663f4a93c6643d936cb6cedb8df6e090b 7669f70be786a53ba1a0a92c1d347f5fe7544681 2b161993ed258ee8f0bd99d591fcabdcb47ffe43`
encountered one documentation conflict in `protocols/CHANGELOG.md`. The
resolution retained the current QPBT-022 shared-runtime entry and added the
QPBT-021 entry as `0.1.7 candidate`; the four code/document files auto-merged.

Rebased candidate:

```
head   63d1e9e9807412008f7174199fdcd1ca11787890
tree   204ca4af35939f989c85828da97012cea8879fb9
parent 7526e58663f4a93c6643d936cb6cedb8df6e090b
subject feat(workflow): support local pinned mathlib cache input
```

The exact changed paths remain the five owned paths:

```
protocols/CHANGELOG.md
protocols/orchestration.md
scripts/hot_main_cache.py
tests/test_hot_main_cache.py
workflow/README.md
```

`git status --short --branch` reports only the clean branch
`repair/qpbt-021-a02`; `git show --name-only HEAD` reports no other paths.
The current-main LPR-011 runtime behavior remains present at
`scripts/hot_main_cache.py:620-662` and `:2438-2474`.

## Findings and disposition

F-LPR010-A06-001 was not masked or repaired by changing
`tests/test_local_agent.py`. The exact serial aggregate on the frozen rebased
head passed, so the prior baseline timeout is cleared for this head. The
canonical PR finding and its prior failed evidence remain for the coordinator
to reconcile against this new immutable result.

F-LPR010-A06-002 was not silently removed. New diff evidence used the exact
two-dot SHA-bound command:

```
git diff --check 7526e58663f4a93c6643d936cb6cedb8df6e090b..63d1e9e9807412008f7174199fdcd1ca11787890
exact_sha_diff_check_exit=0
```

The malformed historical command remains canonical state and needs an explicit
coordinator disposition.

## Validation evidence

Focused command (with bytecode redirected to `/tmp/qpbt021-repair-a02-pyc`):

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/qpbt021-repair-a02-pyc \
python3 -m unittest discover -s tests -p 'test_hot_main_cache.py' -v
Ran 42 tests in 11.292s
OK
```

Exact required serial aggregate command:

```
python3 -m unittest discover -s tests -v
Ran 299 tests in 80.243s
OK
```

The aggregate included the previously failing
`test_process_timeout_terminates_descendants_in_the_new_process_group`, which
passed on this frozen head. The workflow checker independently completed all
299 tests and exited zero:

```
python3 scripts/check_workflow.py
Ran 299 tests in 83.523s
OK
exit 0
```

Additional gates:

```
python3 -m compileall -q scripts tests
compileall_exit=0

python3 scripts/workflow.py validate
{"valid": true, "counts": {"issues": 24, "pull_requests": 11,
 "planned_sessions": 0, "issued_sessions": 245, "stages": 7}}

git diff --check 7526e58663f4a93c6643d936cb6cedb8df6e090b..63d1e9e9807412008f7174199fdcd1ca11787890
exact_sha_diff_check_exit=0
```

No Lean, Lake, hot-main warm, or network command was run. No cache artifact is
claimed. Local Mathlib source/archive and package availability were inherited
from the audit: commit `81a5d257c8e410db227a6665ed08f64fea08e997`, tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`, archive SHA-256
`c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`, and the
eight pinned Lake package archives. Cache environment variables and the
MIPStarRE archive were not provisioned in this session, so the singleton cache
gate remains unexecuted.

## Handoff recommendation

The rebased implementation is ready for a fresh immutable reviewer to inspect
head `63d1e9e9807412008f7174199fdcd1ca11787890` against base
`7526e58663f4a93c6643d936cb6cedb8df6e090b`. The reviewer must verify the five
owned paths, current LPR-011 runtime behavior, local Mathlib authentication,
and the exact SHA-bound checks above. Approval is still distinct from the
singleton cache gate; after approval, the coordinator must provision the
authenticated inputs and elect exactly one warm.

Accounting: one nested rebase repair attempt, no subagents; Lean/Lake/build
invocations 0; network requests 0; cache warms 0; elapsed approximately 11
minutes for replay and validation; collaboration token usage unavailable and
not estimated.
