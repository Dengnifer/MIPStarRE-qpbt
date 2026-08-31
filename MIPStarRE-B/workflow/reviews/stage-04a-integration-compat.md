# Stage 04A Integration Compatibility Audit

## Scope and evidence

- Logical session: `i000-auditor-a29-integration-compat`
- Role: read-only integration auditor
- Current main: `d9dd6f2d83d03ab6e2c4eb46b7016f15e358da1d`
- Current main tree: `860c40b9c184ee30af4f3daa999c7be2c8cbeae1`
- Approved LPR-009 head: `e0bab14a1489e1b7344dfef63061f515ca0db0b2`
- Approved candidate tree: `7fb95fca94ba555b1f4fd804ce5c6298d9b5a800`
- Candidate base: `7669f70be786a53ba1a0a92c1d347f5fe7544681`
- Candidate base tree: `48f451bc82f2037abe09e9d97130fdb4d0cbdd53`
- Read-only audit window: approximately 2026-08-31 08:36-08:44 UTC; token usage not exposed
- Lean/Lake/build/network operations: none

The candidate is present in `/tmp/qpbt020-fix-a06` and its worktree is at
`e0bab14` with tree `7fb95f...`. Its worktree has one untracked review file,
`workflow/reviews/qpbt-020-session-launch.md`; that file is not part of the
candidate tree and must not be copied as an integration input. Main is also
dirty; no working-tree mutation was attempted.

## Ancestry and changed paths

Main's chain is:

```text
7669f70 -> e6c3eca -> 687e182 -> d319902 -> 9755f17 -> 08befbf -> d9dd6f2
```

The candidate's chain is:

```text
7669f70 -> c4c83ac -> 038b8a6 -> b6b1936 -> 8417f6a -> e0bab14
```

The parent chains establish `7669f70be786a53ba1a0a92c1d347f5fe7544681` as
the merge base. A direct `git merge-base` from the main worktree could not run
because `e0bab14` is not yet in main's object database (`fatal: bad object`);
the candidate repository independently confirms the complete parent chain.

Candidate range `7669f70..e0bab14` changes exactly five tracked paths:

```text
M protocols/CHANGELOG.md
M protocols/orchestration.md
M scripts/local_agent.py
M tests/test_local_agent.py
M workflow/README.md
```

Main range `7669f70..d9dd6f2` changes exactly four different cache paths plus
the shared changelog:

```text
M protocols/CHANGELOG.md
M protocols/local-development.md
M scripts/hot_main_cache.py
M tests/test_hot_main_cache.py
```

The only path overlap is `protocols/CHANGELOG.md`. Main adds the QPBT-022
entry at lines 3-15; LPR-009 adds its dated launch/archive entries at the end
of the file (around lines 177-198 in the candidate). A temporary
`git merge-file -p` three-way simulation for all five paths, using main `d9`,
base `7669`, and candidate `e0`, returned `rc=0` for every path. No textual
conflict is predicted, and the QPBT-022 changelog entry is preserved.

## Canonical-state cleanliness

`git status --short --branch` on main reports branch `main` at `d9dd6f2` with
24 dirty paths: modified `research/metrics/{incidents,sessions}.jsonl`,
`research/report.md`, `workflow/events.jsonl`, and
`workflow/state/{issues,prs,sessions,stages}.json`, plus modified Stage-2/3
review documents and untracked review artifacts. The canonical state currently
contains LPR-009 as `approved` with immutable base `7669f70` and head `e0bab14`,
and LPR-011 as `merged` at `d9dd6f2`; `python3 scripts/workflow.py validate`
returns `valid: true` with 23 issues, 11 PRs, 232 issued sessions, and 7 stages.

This dirtiness is coordinator-owned evidence, not disposable noise. Direct
`git merge`, `git cherry-pick`, reset, checkout, or stash on main is therefore
not admissible for this audit. The candidate's untracked review artifact must
also remain outside any integration commit.

## Integration decision

The approved `e0bab14` commit is not directly cherry-pickable by itself onto
main: its parent is `8417f6a`, and all four earlier LPR-009 commits contain the
implementation that the final race-window commit expects. A clean integration
must import and merge the full candidate history (or apply the equivalent
`7669f70..e0bab14` patch), not just the final commit.

The admissible non-destructive rehearsal is a temporary clean worktree at main
`d9dd6f2`, after importing the candidate objects from the local candidate
repository, followed by a no-conflict merge of `e0bab14` (or an ordered replay
of `c4c83ac`, `038b8a6`, `b6b1936`, `8417f6a`, and `e0bab14`). The rehearsal
must inspect the resulting tree and retain only the five candidate paths plus
main's existing files. It must not import the candidate worktree's untracked
review file.

Do not perform that merge on the current main worktree until the coordinator
has reconciled and durably recorded its dirty canonical state. After the
rehearsal succeeds, integration requires a fresh immutable result tree and
canonical PR transition evidence; approval of `e0bab14` does not itself approve
the post-merge tree.

## Required post-merge gates

Run these exact gates from the clean merged worktree, recording the merged SHA,
base SHA, command, exit status, and logs:

```text
python3 -m unittest discover -s tests -p 'test_local_agent.py' -v
python3 -m unittest discover -s tests -p 'test_workflow.py' -v
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/test_check_workflow.py
python3 -m compileall -q scripts tests
python3 scripts/workflow.py validate
git diff --check <main-d9-sha>..<merged-sha>
```

The protocol also requires the full main build through the singleton hot-main
cache before integration is closed. This audit did not run it, and it must not
be run concurrently with another builder. Any source/blueprint changes later
added to the merged tree require their own declaration/source synchronization
gates.

## Risks and final status

- **High operational risk:** main's canonical files and events are dirty. A direct integration could overwrite or entangle coordinator evidence; preserve and reconcile it first.
- **Medium ancestry risk:** candidate base is `7669f70`, not current main `d9dd6f2`; integration must prove the clean merge result rather than treating the approved head as a fast-forward.
- **Low path-conflict risk:** only `protocols/CHANGELOG.md` overlaps, and the temporary three-way merge returned no conflicts.
- **Residual candidate-worktree risk:** one untracked review file exists; integrate commit/tree objects only.

Final disposition: **temporary-worktree merge/replay is admissible after local
object import and canonical-state reconciliation; direct cherry-pick/merge on
the current dirty main is not admissible.** No conflict, build, network, or
repository mutation was introduced by this audit.
