# LPR-007 / QPBT-018 immutable review (i018-reviewer-a03-clone-fallback)

## Verdict

**Approve.** The exact candidate has the requested two-path scope, passes all
registered Python gates, and implements a bounded EXDEV fallback that preserves
the exact detached commit and never publishes a snapshot after fallback
checkout failure. No finding remains.

## Immutable identity and scope

Review worktree: `/tmp/qpbt018-review-clone` (clean after validation).

```text
base  687e182c7ad41520c226a59160c084ab53ad6f38
head  e21c9cda11803f7564a500c005fd55882530538d
tree  a64c98c23f34416f60cf9c9127655ed108f3e64e
head parent 1273f1dc9fed33b6a5eafd5e25e6081c8b32ceb7
ancestry: base is an ancestor of head (exit 0)
```

The diff is exactly:

```text
M scripts/hot_main_cache.py
M tests/test_hot_main_cache.py
```

It contains 38 additions/8 deletions in the cache script and 60 additions in
the test file. No other path is changed.

## Review findings

None.

The changed `_detached_clone` implementation retains the initial log offset,
detects only explicit `cross-device`/`exdev` diagnostics, removes the failed
checkout, appends an auditable marker, and retries exactly once with
`git clone --no-local`. It then performs the existing detached checkout at
`self.identity.main_commit`; any nonzero retry or checkout status raises
`CacheError`. The surrounding warm flow rechecks detached input identity and
commit after all build steps, rejects source changes, and publishes atomically
only after artifact validation. The new regression exercises fallback checkout
failure, confirms the original and retry commands plus detached checkout order,
retains all diagnostics, and proves neither `READY` nor the snapshot directory
is published.

This is source-faithful to the issue's bounded portability requirement. The
fallback does not broaden clone behavior for unrelated failures, silently
accept a wrong revision, or alter cache identity. The test also checks that a
failed fallback cannot leave a misleading ready artifact.

## Validation commands and results

Commands were run from `/tmp/qpbt018-review-clone` against the immutable head;
no network, Lean, Lake, build, warm, or seed command was used.

```text
python3 -m unittest discover -s tests -p test_hot_main_cache.py -v
  PASS: Ran 25 tests in 2.759s

python3 scripts/check_workflow.py
  PASS: workflow state valid; underlying suite Ran 143 tests in 52.431s

python3 -m compileall -q scripts tests
  PASS (exit 0)

python3 scripts/workflow.py validate
  PASS: valid=true; issues 12, pull_requests 0, planned_sessions 0,
        issued_sessions 38, stages 7

git diff --check 687e182c7ad41520c226a59160c084ab53ad6f38..e21c9cda11803f7564a500c005fd55882530538d
  PASS (exit 0)
```

The worktree was rechecked clean after tests and compilation. No cache
artifact or shared writable `.lake/build` was created by this review.

## Accounting

Approximate wall-clock elapsed time: 65 seconds (test runtime dominates).
Exposed token usage is unavailable (`null`, not estimated). Subagents
dispatched: 0. Network requests, Lean/Lake invocations, builds, cache warms,
and seeds: 0 each.
