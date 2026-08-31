# LPR-012 Candidate Binding Handoff

Logical session: `i021-orchestrator-a04-pr012-bind`

The approved exact-base replay was materialized in the isolated clone
`/tmp/qpbt-021-pr012-bind` from source worktree
`/tmp/qpbt-021-repair-a03`. No source bytes were edited, and no canonical
workflow/state/review/metrics files were changed. No nested agents were used.

## Immutable identities

```
base commit  7669f70be786a53ba1a0a92c1d347f5fe7544681
base tree    48f451bc82f2037abe09e9d97130fdb4d0cbdd53
head commit  c37431ec44c3d1f281a31c1a2125ace3ca590716
head tree    1d51c83e63835bffd7d885988c392ba37a291d05
head parent  7669f70be786a53ba1a0a92c1d347f5fe7544681
```

The source and binding clones report identical commit, parent, and tree:

```
git -C /tmp/qpbt-021-repair-a03 show -s --format='commit=%H parent=%P tree=%T' HEAD
commit=c37431ec44c3d1f281a31c1a2125ace3ca590716 parent=7669f70be786a53ba1a0a92c1d347f5fe7544681 tree=1d51c83e63835bffd7d885988c392ba37a291d05

git show -s --format='commit=%H parent=%P tree=%T' HEAD
commit=c37431ec44c3d1f281a31c1a2125ace3ca590716 parent=7669f70be786a53ba1a0a92c1d347f5fe7544681 tree=1d51c83e63835bffd7d885988c392ba37a291d05
```

## Materialization command

The target path did not exist. It was cloned locally and then checked out at
the immutable candidate; the first clone did not carry the detached candidate
object, so it was fetched directly from the local source worktree. No network
transport was used.

```
git clone --no-local /tmp/qpbt-021-repair-a03 /tmp/qpbt-021-pr012-bind
git fetch /tmp/qpbt-021-repair-a03 c37431ec44c3d1f281a31c1a2125ace3ca590716
git checkout --detach c37431ec44c3d1f281a31c1a2125ace3ca590716
```

The final binding clone reports `git status --short --branch` as:

```
## HEAD (no branch)
```

## Exact path scope

The immutable old-base range contains exactly the five owned paths:

```
git diff --name-status 7669f70be786a53ba1a0a92c1d347f5fe7544681..c37431ec44c3d1f281a31c1a2125ace3ca590716
M protocols/CHANGELOG.md
M protocols/orchestration.md
M scripts/hot_main_cache.py
M tests/test_hot_main_cache.py
M workflow/README.md
```

The range summary is `5 files changed, 2162 insertions(+), 14 deletions(-)`.
The SHA-bound whitespace gate passes:

```
git diff --check 7669f70be786a53ba1a0a92c1d347f5fe7544681..c37431ec44c3d1f281a31c1a2125ace3ca590716
diff_check_exit=0
```

## Validation boundary

This binding task performed identity, tree, scope, clean-status, and diff-check
validation only. Lean, Lake, full builds, tests, hot-main cache warm, and
network operations were explicitly not run. Those gates remain the
responsibility of the independent review and subsequent singleton cache gate.

Accounting: elapsed time approximately 2 minutes; subagents `0`; compile
attempts `0`; cache warms `0`; network requests `0`. Collaboration token usage
is unavailable (`null`) and was not estimated.
