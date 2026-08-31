# Stage 04A LPR-001 integration audit

Date: 2026-08-31 (Asia/Shanghai)
Current main: `920e53e8bf978951fff631cc9b3c228d05bc1312`
LPR-001 base: `77aa1a4ac947c1632ea57262d29d2753ba163c8a`
LPR-001 head: `e93d949d06af2a7f4407d198a37aad315deac6aa`
LPR-001 head tree: `b518e346719a7d208604ba4c0b2db2b215fb77a2`

This was a read-only integration audit. No canonical/source files were edited,
no network or build was used, and all replay work was confined to disposable
`/tmp` clones.

## Verdict

**Approve the complete LPR-001 range for integration, with the sequencing below.**
There is no source-code finding. The head commit must not be cherry-picked by
itself: it depends on the preceding feature commit that creates the three
paths. Applying the complete base-to-head range to current main is clean.

## Identity and ancestry

The old PR base is an ancestor of current main (`git merge-base --is-ancestor`
exit 0). Current main is not an ancestor of the PR head, as expected for a
branch that predates the later workflow/cache integrations (reverse ancestry
probe exit 1). The base and head are not directly ancestor-related; their merge
base is the old base `77aa1a4...`.

The immutable base-to-head diff contains exactly three added paths and no
deletions or modifications:

```
A  scripts/reference_transport.py
A  tests/test_reference_transport.py
A  workflow/reviews/qpbt-010-reference-transport.md
```

The first feature commit is `cf43b33b5cd77cb005b90b02b6d369cfbd86d316`
(parent `77aa1a4...`); `e93d949` is its repair commit (parent `cf43b33`).
The PR record in `workflow/state/prs.json` correctly names the three changed
paths, immutable base/head SHAs, and the candidate focused/aggregate/checker/
compile/diff/validation gates.

## Replay results

1. `git archive 920e53e...` into a disposable directory followed by
   `git diff 77aa1a4... e93d949... | git apply --check` exited **0**. The
   patch-level base-to-head addition applies without context conflicts.
2. A disposable `git clone --no-local` of current main followed by
   `git cherry-pick e93d949...` alone exited **1** with three expected
   modify/delete conflicts:
   `scripts/reference_transport.py`, `tests/test_reference_transport.py`, and
   `workflow/reviews/qpbt-010-reference-transport.md`. Current main lacks these
   paths while the selected commit's parent (`cf43b33`) contains them.
3. A fresh disposable clone followed by
   `git cherry-pick cf43b33... e93d949...` exited **0**. The resulting history
   has both commits, exactly the three paths added, and `git diff --check`
   exited **0**. This is the required integration strategy.
4. On that fully replayed temporary tree,
   `python3 -m unittest discover -s tests -p 'test_reference_transport.py' -q`
   passed **49/49** in 2.587 s (wall 2.79 s). Tests use fakes/disposable local
   subprocesses; no network transport was exercised.

The initial single-commit probe failed only because the commit was selected
without its path-creating parent; it did not modify the shared worktree. The
corrected range replay is the acceptance result.

## Source/path review

`scripts/reference_transport.py` is self-contained and imports only Python
standard-library modules. Its direct-download and GitHub archive pins validate
HTTPS/host/revision/checksum constraints; subprocess and HTTP workers are
bounded, use argv/no shell, capture bounded diagnostics with raw byte counts
and digests, and publish through temporary files with inode/path checks. The
repair commit binds REST fallback identity and retains bounded output behavior.
The added tests contain no `sorry`, `axiom`, `admit`, or `constant` tokens.
No current-main file is deleted by the complete base-to-head patch.

## Required gates before canonical integration

The PR’s registered gates remain mandatory on the exact integrated head:

* focused reference-transport unittest discovery;
* aggregate `python3 -m unittest discover -s tests`;
* `python3 -m compileall -q scripts tests`;
* `python3 scripts/workflow.py validate`;
* `git diff --check` against the integrated base; and
* the three checksum-pinned acquisition probes recorded in
  `workflow/reviews/qpbt-010-reference-transport.md`, subject to the existing
  external-disclosure authorization policy.

Those gates were recorded as passed for the immutable candidate (`e93d949`) in
the PR ledger, but this audit did not rerun network acquisitions, compileall,
or the aggregate suite on current main. A fresh immutable reviewer should
rerun the exact registered non-network gates after the two-commit replay and
retain the candidate’s source review. Current main’s read-only
`python3 scripts/workflow.py validate` passed (23 issues, 11 PRs, 0 planned,
239 issued sessions, 7 stages) in 0.15 s.

## Residual risk

The only integration hazard found is procedural: cherry-picking `e93d949` alone
produces modify/delete conflicts and can tempt an incorrect manual resolution.
Use the immutable range from `77aa1a4...` through `e93d949`, or cherry-pick
`cf43b33` followed by `e93d949`, then rerun the integrated gates. External
acquisition remains governed by the recorded authorization and checksum
requirements; no network approval is inferred by this audit.
