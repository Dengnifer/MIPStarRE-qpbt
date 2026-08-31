# Local Development and Cache

## Worktree isolation

Each writable implementation issue uses a dedicated branch and worktree. The
issue orchestrator is its only integration owner. Read-only scouts may inspect
any tree. A prover may edit only delegated paths. Reviewers never edit.

Before dispatch, record the exact base SHA and confirm a clean worktree. After
delivery, inspect `git diff --check`, changed paths, scoped type-checks, and the
result envelope. Do not let agents commit canonical workflow state or raw run
logs.

## Hot-main cache

The GitHub "latest successful main artifact" is replaced by a content-addressed
local cache under `.workflow-runtime/cache/main/`.

When `--runtime-dir` is omitted, the cache command derives this runtime root
from the primary non-bare Git worktree (`.workflow-runtime` beneath the root
reported by `git worktree list --porcelain`). Linked issue worktrees therefore
share one lock and one published snapshot for a cache key. Prunable or
unresolvable registered entries are ignored; if the repository root or primary
worktree cannot be resolved, the command fails closed and asks for an explicit
runtime directory. An explicit `--runtime-dir` keeps its existing semantics:
absolute paths remain absolute and relative paths resolve beneath the supplied
`--repo-root`.

The cache key contains:

- the local `main` commit SHA;
- SHA-256 of `lean-toolchain`;
- SHA-256 of `lakefile.toml`; and
- SHA-256 of `lake-manifest.json`; and
- the identifier, version, and exact argv of the canonical dependency and
  build recipe.

`python3 scripts/hot_main_cache.py warm` takes an exclusive `flock`. The elected
owner builds a detached local clone in a key-specific staging directory, runs
Mathlib cache retrieval when needed, and runs the full build. It writes the
manifest and metrics only after success, then atomically renames staging to the
published key. Waiters re-check the manifest after the lock is released and
report a cache hit instead of compiling.

Publication also records a content-addressed inventory of the entire `.lake`
tree. The `READY` marker binds the manifest bytes. Cheap status and warm-hit
checks use that marker; `seed` performs deep source and destination inventory
verification so corruption cannot enter an issue worktree unnoticed.

Failed staging output is retained or logged as diagnostic state but is never
published as successful. A new main SHA or input hash produces a new key; it
does not mutate an older cache.

`python3 scripts/hot_main_cache.py seed --worktree PATH` waits for a published
key, verifies that the target is a live compatible registered Git worktree, and
copies `.lake` with copy-on-write reflinks when available. Every issue worktree
receives a private writable copy. Hard-linked or directly shared `.lake/build`
trees are forbidden because Lean processes can update artifacts. Replacement
uses a private backup and rolls back if publication or validation fails.

The cache record includes key, source SHA, elected owner, hit/miss, lock wait,
dependency-cache duration, build duration, total duration, exit status, and log
path. Cache cleanup is explicit and outside ordinary agent runs.

## Validation ladder

The canonical focused Python validation command is:

```text
python3 tests/test_check_workflow.py
```

Run that exact argv when validating workflow-ledger changes. The `tests/`
directory is intentionally not imported as a package; use a direct test path
or unittest discovery rather than a `tests.test_*` module name.

During proof work:

1. Search source and Mathlib.
2. Run `lake env lean path/to/changed.lean`.
3. Scan owned files for unexpected `sorry`, `admit`, `axiom`, and `constant`.
4. Run affected Lake targets and workflow unit tests.
5. Run blueprint declaration and source-integrity checks.

Before review:

1. verify the local PR base/head and clean generated state;
2. run all scoped checks recorded by the issue;
3. run `lake build` using the issue worktree's private cache;
4. build/lint the blueprint when it changed;
5. validate local issue/PR/session state; and
6. save command, exit status, duration, and log paths in the PR record.

A registered validation command is evidence only after that exact command has
run successfully. A similar-looking command or an agent-reported paraphrase is
not interchangeable.

After integration, warm the new main cache once. Main cache builds are never
cancelled merely because another agent is waiting. Issue-level builds may be
cancelled and retried when their head changes.

## Fixed-point bounds

Automated fix/review loops are serialized per PR and stop after five consecutive
agent-authored fix attempts. A repeated identical failure is not retried without
a changed hypothesis, source, or protocol. On the third recurrence, record a
workflow incident and evaluate a root-cause protocol change.
