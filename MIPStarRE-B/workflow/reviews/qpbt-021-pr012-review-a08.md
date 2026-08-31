# LPR-012 / QPBT-021 Immutable Review (a08)

Verdict: changes requested

## Findings

P1. `protocols/CHANGELOG.md:22-24` claims that the focused hot-cache suite
passes 37/37 tests. At the reviewed head, `tests/test_hot_main_cache.py`
defines 42 test methods and the registered focused command ran all 42
successfully. The evidence count is therefore false. Update the changelog to
the exact 42/42 result (or document a separately scoped 37-test command and
run that command) before approval. This is a review-evidence/provenance issue,
not a test failure.

No other findings were identified after inspecting all five changed paths.

## Immutable identity

- Worktree: `/tmp/qpbt-021-repair-a03`
- `HEAD`: `c37431ec44c3d1f281a31c1a2125ace3ca590716`
- Reviewed base: `7669f70be786a53ba1a0a92c1d347f5fe7544681`
- `HEAD` parent: `7669f70be786a53ba1a0a92c1d347f5fe7544681`
- `HEAD` tree: `1d51c83e63835bffd7d885988c392ba37a291d05`
- Merge-base check: base is an ancestor of `HEAD` (exit 0).
- Worktree status: clean before and after checks.
- Exact two-dot changed paths (five):
  `protocols/CHANGELOG.md`, `protocols/orchestration.md`,
  `scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`,
  `workflow/README.md`.
- `git diff --check 7669f70be786a53ba1a0a92c1d347f5fe7544681..c37431ec44c3d1f281a31c1a2125ace3ca590716`: pass.

## Scope and behavior checks

The implementation authenticates exactly one local Mathlib source/archive
input, validates the pinned commit
`81a5d257c8e410db227a6665ed08f64fea08e997` and tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`, constructs a sorted
`LAKE_PKG_URL_MAP`, rechecks the source before publication, and removes an
archive extraction before publishing `.lake` (`scripts/hot_main_cache.py:1681-1791`,
`1990-2184`). The independently inspected local source is clean at the exact
commit/tree; the audited archive is present at
`/tmp/mathlib-81a5d257-shallow-repo.tar.gz`, compressed SHA-256
`c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`,
51,938,317 bytes, decompressed tar SHA-256
`ad9a60b01736070112fbc1008ea98c67e68fa045c5b69e66873e0b9444ddd3ba`,
147,712,000 bytes. The single-pack source evidence was also checked against
the pinned local acquisition.

LPR-011 shared-runtime behavior remains present: omitted runtime resolution
uses the primary non-bare worktree and linked worktrees share the singleton
runtime/lock (`scripts/hot_main_cache.py:620-662`; regression
`tests/test_hot_main_cache.py:1412-1470`). No Lean declarations, axioms,
unintended assumptions, or files outside the five-path candidate were added.

## Commands and results

All commands were executed in `/tmp/qpbt-021-repair-a03` without network,
Lean/Lake, hot-cache warm, or cache seed operations.

1. `python3 -m unittest discover -s tests -p test_hot_main_cache.py -v`:
   pass, 42 tests in 10.341 s.
2. `python3 -m unittest discover -s tests -v` (exact serial aggregate):
   pass, 185 tests in 58.704 s.
3. `python3 scripts/check_workflow.py`: pass; its registered 185-test suite
   also completed successfully.
4. `python3 -m compileall -q scripts tests`: pass.
5. `python3 scripts/workflow.py validate`: pass (`valid: true`).
6. `git diff --check 7669f70be786a53ba1a0a92c1d347f5fe7544681..c37431ec44c3d1f281a31c1a2125ace3ca590716`: pass.
7. `git status --short --untracked-files=all`: clean after all checks.

Review elapsed wall time was approximately four minutes including immutable
identity inspection and the two test suites. Exposed token usage is
unavailable (`null`); it was not estimated. Network calls: 0. Lean/Lake/build
attempts: 0. Hot-cache warm/seed attempts: 0.
