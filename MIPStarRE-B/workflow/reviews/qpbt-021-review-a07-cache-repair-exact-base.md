# LPR-010 / QPBT-021 Immutable Review A07

Logical session: `i021-reviewer-a07-cache-repair-exact-base`

Verdict: `request_changes`

This is a fresh read-only review of `/tmp/qpbt-021-repair-a02`. The declared
PR base is `7669f70be786a53ba1a0a92c1d347f5fe7544681`; the candidate head is
`63d1e9e9807412008f7174199fdcd1ca11787890`, tree
`204ca4af35939f989c85828da97012cea8879fb9`. No canonical files, workflow
state, PR ledgers, metrics, or other worktrees were edited. No network, Lean,
Lake, hot-main warm, or cache build was run.

## Findings

### Blocker: immutable declared-base range is not a five-path LPR-010 diff

The candidate's actual parent is `7526e58663f4a93c6643d936cb6cedb8df6e090b`,
not the declared base. `git merge-base 7669f70... 63d1e9e...` is the declared
base, so ancestry is present, but the exact declared-base range contains 98
paths and 35,477 insertions/189 deletions. It includes blueprint, references,
workflow state/events, metrics, and unrelated review files in addition to the
five owned paths. Therefore the required exact-base review cannot establish a
scoped LPR-010 candidate or approve this immutable head.

Evidence:

```
HEAD  63d1e9e9807412008f7174199fdcd1ca11787890
tree  204ca4af35939f989c85828da97012cea8879fb9
parent 7526e58663f4a93c6643d936cb6cedb8df6e090b
merge-base(7669f70,63d1e9e) 7669f70be786a53ba1a0a92c1d347f5fe7544681
git diff --name-status 7669f70...63d1e9e | wc -l  98
git diff --stat 7669f70...63d1e9e  98 files changed, 35477 insertions(+), 189 deletions(-)
```

The parent-scoped diagnostic range `7526e586...63d1e9e` has exactly these five
paths, but that does not satisfy the explicitly requested declared-base check:

```
protocols/CHANGELOG.md
protocols/orchestration.md
scripts/hot_main_cache.py
tests/test_hot_main_cache.py
workflow/README.md
```

The coordinator should issue/rebase a candidate whose immutable PR base and
review base are the same current base (or otherwise reconcile the PR metadata)
before another approval round. Treating the 98-path old-base range as the
five-path change would be unsafe.

### Blocker: exact declared-base diff hygiene is red

The required command exits 2:

```
git diff --check 7669f70be786a53ba1a0a92c1d347f5fe7544681..63d1e9e9807412008f7174199fdcd1ca11787890
workflow/reviews/stage-04a-cli-capacity.md:3: trailing whitespace.
workflow/reviews/stage-04a-cli-capacity.md:4: trailing whitespace.
workflow/reviews/stage-04a-qpbt018-current.md:145: new blank line at EOF.
```

These errors are in unrelated files introduced in the broad old-base range,
but the gate is SHA-bound and cannot be waived for this review. The corrected
parent-scoped check was clean only as a diagnostic:
`git diff --check 7526e58663f4a93c6643d936cb6cedb8df6e090b..63d1e9e9807412008f7174199fdcd1ca11787890` exits 0.

### Prior finding F-LPR010-A06-001

Fixed on this immutable head: the exact serial aggregate passed, including the
previously failing process-group timeout test. The historical finding/evidence
must still receive an explicit coordinator disposition; it was not deleted.

### Prior finding F-LPR010-A06-002

The malformed historical diff command remains untrusted historical evidence and
was not edited. New evidence must use a valid two-dot command bound to the exact
review base and head. Under the explicitly declared old base, that valid check
is the failing broad-range check above; the clean parent-scoped command cannot
close the finding for the old-base record.

## Candidate implementation and contract checks

The parent-scoped candidate diff changes only the five paths listed above. The
implementation retains LPR-011 shared-runtime behavior in
`scripts/hot_main_cache.py:620-662` and `:2438-2474`, including linked-worktree
default runtime resolution and explicit `--runtime-dir` override.

The Mathlib contract is source-authenticated and locally pinned. The project
manifest records URL `https://github.com/leanprover-community/mathlib4`, commit
`81a5d257c8e410db227a6665ed08f64fea08e997`, and input revision `v4.32.0`.
The candidate constants at `scripts/hot_main_cache.py:63-75` bind that commit,
tree `5ea66b811b8461daae82f14d356fed2a287d7c40`, archive size 51,938,317, and
archive SHA-256
`c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`.
Local source/archive evidence was available and matched those values.

Relevant fail-closed paths inspected:

* source Git metadata, alternates, replacement refs, dirty state, index flags,
  and commit/tree are checked before object reads (`:963-1106`);
* archive member paths and symlink graph are bounded and authenticated
  (`:1109-1344`);
* the real manifest pin and exactly-one source/archive preflight are enforced
  (`:1638-1679`, `:1749-1769`);
* source identity is rechecked before publication (`:2138-2143`);
* existing `LAKE_PKG_URL_MAP` entries are preserved while mathlib is bound
  (`:1603-1635`).

Focused tests cover symlinked Git internals, archive link chains, dirty and
mismatched sources, linked worktrees, explicit runtime overrides, and
two-process builder election. No unintended proof assumptions or source
fidelity changes were found in the parent-scoped implementation.

## Exact checks

```
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/qpbt021-review-a07-pyc \
python3 -m unittest discover -s tests -p 'test_hot_main_cache.py' -v
Ran 42 tests in 9.781s
OK

python3 -m unittest discover -s tests -v
Ran 299 tests in 71.239s
OK

python3 -m compileall -q scripts tests
compileall_exit=0

python3 scripts/workflow.py validate
{"valid": true, "counts": {"issues": 24, "pull_requests": 11,
 "planned_sessions": 0, "issued_sessions": 245, "stages": 7}}
validate_exit=0

git status --short --branch
## repair/qpbt-021-a02
```

The singleton hot-main cache gate remains unexecuted, so no cache artifact or
warm approval is claimed. Provisioning of authenticated inputs and one elected
builder is a separate post-review gate.

## Recommendation and accounting

Do not approve or integrate this head under declared base `7669f70`. Reconcile
the immutable PR base/head evidence and obtain a clean exact-base diff before a
fresh review. The implementation itself is plausibly sound on the
parent-scoped range, but the current immutable review contract is not met.

Elapsed time: approximately 3 minutes for this review and checks. Subagents: 0.
Lean/Lake/build invocations: 0. Network requests: 0. Cache warms: 0.
Collaboration token usage is unavailable (`null`) and was not estimated.
