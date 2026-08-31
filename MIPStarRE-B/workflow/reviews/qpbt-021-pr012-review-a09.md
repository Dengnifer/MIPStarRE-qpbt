# LPR-012 / QPBT-021 Immutable Review (a09)

Verdict: approve

No new findings. The prior finding `F-LPR012-A08-001` is resolved by the
repaired head: `protocols/CHANGELOG.md:23` now reports the registered focused
suite as 42/42, matching the 42 discovered tests and this review's run.

## Immutable identity and scope

- Review clone: `/tmp/qpbt-021-review-a09` (detached, clean).
- Base: `7669f70be786a53ba1a0a92c1d347f5fe7544681`.
- Head: `6303aab63eeed144fe176969ca7c87f5a852b967`.
- Head tree: `def685a69b3aee904b6ef6c2d711d63c75211efe`.
- Head first parent: `c37431ec44c3d1f281a31c1a2125ace3ca590716`.
- `c37431e^1` is the exact declared base (`7669f70...`); the base is an
  ancestor of the head (merge-base exit 0).
- Exact old-base changed paths (and only these five):
  `protocols/CHANGELOG.md`, `protocols/orchestration.md`,
  `scripts/hot_main_cache.py`, `tests/test_hot_main_cache.py`,
  `workflow/README.md`.
- Range stat: 5 files, 2162 insertions, 14 deletions.

The repair commit from `c37431e` to `6303aab` changes only the focused count
in the changelog (`37/37` to `42/42`). No source, Lean, blueprint, workflow
state, PR, or metrics files are part of this candidate range.

## Source and runtime review

The changed implementation authenticates exactly one local Mathlib source or
the pinned shallow archive. Git commands use an isolated environment that
removes inherited `GIT_*` configuration and disables global/system config,
hooks, fsmonitor, credential helpers, replacement objects, and prompts
(`scripts/hot_main_cache.py:350-383`). Source validation checks standalone
metadata, no symlink/special Git internals, no alternates/replacement refs,
clean status, submodule absence, index visibility flags, local fsck, and exact
commit/tree (`scripts/hot_main_cache.py:901-1106`). Archive validation checks
bounded gzip/tar bytes, exact member prefix, duplicate/path/link-graph safety,
special-file rejection, extraction confinement, and repeats source
authentication (`scripts/hot_main_cache.py:1107-1344`).

The local authenticated source independently returned:

```
commit 81a5d257c8e410db227a6665ed08f64fea08e997
tree   5ea66b811b8461daae82f14d356fed2a287d7c40
pack   4659f2a0cabfec474474f5e83ea3d495e711b735418742dd3d642328adcada02
bytes  27574578
```

The local archive independently matched 51,938,317 bytes and compressed
SHA-256 `c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`,
and decompressed tar 147,712,000 bytes with SHA-256
`ad9a60b01736070112fbc1008ea98c67e68fa045c5b69e66873e0b9444ddd3ba`.
The detached project manifest pin is parsed and checked against the same
authenticated URL/revision/tree (`scripts/hot_main_cache.py:1638-1679`).
Source paths remain outside cache identity; the builder derives a sorted local
`LAKE_PKG_URL_MAP`, rechecks the source before publication, and removes an
archive extraction before publishing `.lake` (`scripts/hot_main_cache.py:1624-1635,
1681-1791, 1988-2184`).

LPR-011 runtime behavior is retained: `scripts/local_agent.py` and
`tests/test_local_agent.py` are unchanged in the exact old-base range. The
candidate therefore retains the previously reviewed clean-head/base checks,
runtime confinement, alias/archive handling, and interruption behavior. No
unintended `axiom`, `sorry`, `admit`, or generic proof-assumption text was
introduced in the five changed paths.

## Checks

All commands ran in the detached clone. No network, Lean/Lake invocation,
full build, hot-cache warm, or cache seed was attempted.

1. `python3 -m unittest discover -s tests -p 'test_hot_main_cache.py' -v`:
   pass, 42/42; unittest duration 10.788 s, shell wall 10.93 s.
2. `python3 -m unittest discover -s tests -v`: pass, 185/185; unittest
   duration 60.503 s.
3. `python3 scripts/check_workflow.py`: pass, its registered 185/185 suite;
   shell wall 90.57 s.
4. `python3 -m compileall -q scripts tests`: pass; shell wall 0.03 s.
5. `python3 scripts/workflow.py validate`: pass, `{"valid": true}` with
   counts issues 12, pull_requests 0, planned_sessions 0, issued_sessions 38,
   stages 7; shell wall 0.07 s.
6. `git diff --check
   7669f70be786a53ba1a0a92c1d347f5fe7544681..6303aab63eeed144fe176969ca7c87f5a852b967`:
   pass; shell wall 0.00 s.
7. `git status --short --untracked-files=all`: clean after checks.

Review elapsed wall time was approximately four minutes including identity,
source authentication, and the suites. Exposed token usage is unavailable
(`null`) and was not estimated. Subagents: 0. Repository/canonical state was
not edited; only this report was written under `/tmp`.
