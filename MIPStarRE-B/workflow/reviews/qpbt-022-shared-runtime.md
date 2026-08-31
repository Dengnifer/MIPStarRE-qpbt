# QPBT-022 shared hot-main runtime review

## Candidate provenance

Implementation session `i022-orchestrator-a01-shared-runtime` froze head
`08befbfedd7e1d956b77c6827aecc6f9997b1c10` (tree
`9f169c7413f40c83c5a8dada857ff87ed458dfce`) on base
`7669f70be786a53ba1a0a92c1d347f5fe7544681`. The exact changed paths are
`scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`,
`protocols/local-development.md`, and `protocols/CHANGELOG.md`. Its focused
25-test suite, aggregate 168-test suite, checker, compilation, validation, and
diff hygiene all passed before review.

## Fresh immutable review: fail-closed exception boundary

Session `i022-reviewer-a03-immutable` inspected the unchanged head. Focused
tests passed 25/25 in 14.286 seconds; the aggregate suite passed 168 tests in
100.254 seconds; the workflow checker passed 3/3; compilation, validation, and
diff hygiene passed. Normal linked-worktree contention and explicit
`--runtime-dir` cases were reproduced.

Finding `F-LPR011-001` is open at `scripts/hot_main_cache.py:533-557`:
`default_runtime_dir` catches only `FileNotFoundError`. A prunable linked
worktree replaced by a self-symlink causes `Path.resolve(strict=True)` to raise
`RuntimeError`, and an inaccessible record raises `PermissionError`; both leak
through the CLI as tracebacks despite the documented fail-closed contract.
The same boundary is observable for a missing or symlinked repo root. The
bounded repair is to skip prunable records, catch the expected
`OSError`/`RuntimeError` family, normalize the selected root, and add a real CLI
regression.

**Formal verdict: `request_changes`.** No candidate, canonical source, Git
ref, network, Lake/Lean build, or ledger file was changed by the reviewer.

## Fresh immutable review of repaired head

Session `i022-reviewer-a04-immutable` independently checked base
`7669f70be786a53ba1a0a92c1d347f5fe7544681` and head
`d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1d` (tree
`860c40b9c184ee30af4f3daa999c7be2c8cbeae1`). The four changed paths and
worktree are exact and clean. The registered focused suite passed 28/28 in
3.491 seconds; aggregate tests passed 171/171 in 52.059 seconds; checker,
compileall, workflow validation, and diff hygiene all passed. Linked
worktrees resolve to one primary runtime root, and a contention probe observed
one builder and one waiter sharing one cache identity. No network, Lake, or
Lean build was run.

**Formal verdict: `approve`.** `F-LPR011-001` is fixed: default repository and
record resolution catches `OSError`/`RuntimeError`, skips prunable entries,
and missing/self-loop default roots return concise `rc=2` errors. An explicit
self-symlink `--runtime-dir` can still raise a `RuntimeError` at
`scripts/hot_main_cache.py:813` (`rc=1`); the reviewer classified this as
pre-existing and outside the repaired default-runtime scope. Valid explicit
relative and absolute overrides remain unchanged and pass.

## Integrated-main gate

The approved head was fast-forwarded into `main` from the local candidate
clone. On the integrated tree, the focused cache suite passed 28/28, the
aggregate suite passed 171/171, the workflow checker passed 3/3, compileall,
workflow validation, and `git diff --check` passed. These post-merge results
are recorded here as integration evidence rather than appended to the
immutable review's pre-review check set.
