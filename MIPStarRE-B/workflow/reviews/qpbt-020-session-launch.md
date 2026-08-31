# QPBT-020 Nested Session Launch Preflight

Read-only preflight evidence for the dependent local Codex launch issue.

- Audited base: `687e182c7ad41520c226a59160c084ab53ad6f38`
- Auditor session: `i020-auditor-a01-launch-preflight`
- Physical worker: `/root/qpbt020_launch_scout_a14`
- Network calls: 0
- Lean/Lake builds: 0

## Observed gap

`scripts/local_agent.py:1758-1868` (`run_exec`) creates a runtime output
directory, invokes `codex exec`, and writes an envelope, but accepts no issued
session identifier and performs no WorkflowStore authority check. The direct
`cwd` is not compared with a recorded worktree, base SHA, or writable-path
claim. The canonical session therefore remains `issued` while a child is
running, allowing duplicate launches.

`run_review` and the CLI packet path (`scripts/local_agent.py:1871-2037,
2520-2598`) similarly validate Git evidence without binding a reviewer lease.
There is no atomic import API that sets the external ID, result path,
timestamps, elapsed duration, token fields, and terminal status exactly once.

Timeout handling terminates process groups, but an interrupted or killed parent
can leave an issued session and partial files. `run_archive` creates a new
suffix for an existing output directory rather than importing an existing
result idempotently, and no recovery command records an explicit interrupted
state or prevents an unreviewed silent rerun.

## Measured checks

- `python3 -m unittest discover -s tests -p 'test_local_agent.py'`: 34/34 in
  9.228 seconds.
- `python3 -m unittest discover -s tests -p 'test_workflow.py'`: 34/34 in
  0.446 seconds.
- `python3 -m compileall -q scripts/local_agent.py scripts/workflow.py tests`:
  passed.
- `git diff --check`: passed.
- `python3 scripts/workflow.py validate --json`: valid (22 issues, 8 PRs,
  195 issued sessions at audit time).

The package-style forms `python3 -m unittest tests.test_local_agent` and
`python3 -m unittest tests.test_workflow` fail because `tests/` is not a Python
package; discovery commands are the canonical reproducible forms.

## Required implementation tests

1. Reject unknown, non-issued, wrong-parent, wrong-base, wrong-worktree,
   ownership-mismatched, and role/read-only-incompatible launch requests under
   the WorkflowStore lock.
2. Prove the `issued -> running` state/event precedes the first child process
   invocation and that a concurrent duplicate claim admits only one launcher.
3. Import a fake Codex envelope atomically, setting external ID, result/outcome
   path, exact lifecycle/timing/token fields, and terminal status. Repeating an
   identical import must be byte/idempotent; conflicting data must fail.
4. Inject interruption, process-group failure, and parent-crash recovery. The
   restart path must record an explicit failed/unknown-interrupted marker,
   emit one terminal/archive sequence, and never silently rerun the child.
5. Run a fresh independent immutable review against the changed head and
   integrate only after all current-base checks pass.

## First candidate and pre-rebase audit

Session `i020-orchestrator-a01-session-launch` committed speculative head
`aaa80ec48fd24024ac838e4810988456073c1fa8` with tree
`133b0fbe8451f1a011b130f8616e484dd0eae197` on the pre-QPBT-019 base. Its five
changed paths are `scripts/local_agent.py`, `tests/test_local_agent.py`,
`protocols/orchestration.md`, `protocols/CHANGELOG.md`, and
`workflow/README.md`. The candidate passed 36 focused local-agent tests and its
aggregate/checker/compile/validation/diff gates, but those tests were primarily
mock-store happy paths. This head was never promoted to formal review.

Independent auditor `i020-auditor-a02-candidate-preflight` reproduced the
following defects with real temporary `WorkflowStore` ledgers:

1. Output-directory preparation and generic runner exceptions after claim can
   strand a canonical session in `running` without a result.
2. Claim authority omits name, role, issue, and parent checks; `run` hard-codes
   writable mode, while `review` advertises but ignores `--session-id`.
3. Import accepts an unclaimed `issued` session and overwrites canonical
   `started_at` provenance.
4. Identical import retries append duplicate events; the digest omits the
   outcome path and therefore accepts conflicting provenance.
5. `session.result_imported` is not a terminal event recognized by canonical
   validation, so an imported session cannot subsequently archive.
6. Recovery retries append duplicate events and accept a conflicting reason.
7. Missing token usage, null external IDs, and non-finite elapsed time pass the
   candidate's field checks.
8. Coverage lacks real-ledger failure, concurrency, event-order, recovery,
   malformed-field, and review-wiring regressions.

The audit's 36 local-agent and 34 workflow tests still passed; compilation,
validation, and diff hygiene also passed. A two-process diagnostic admitted
exactly one claim, which preserves that narrow positive result. The verdict is
`request_changes`, and no approval is implied. QPBT-019 is now integrated, so
retry lease `i020-orchestrator-a02-session-launch-fix` is rebasing and repairing
all eight findings before a local PR or immutable review is created.

## Remediated immutable candidate

The retry preserved the original head and reconstructed its provenance on
integrated main. LPR-009 binds base
`7669f70be786a53ba1a0a92c1d347f5fe7544681`, provenance commit
`c4c83ac58a9e7a43bcaba74eb305e118d1d13803`, head
`038b8a6f4240417de0deaa2b7c395f8d5d8e88a8`, and tree
`9dc4e6438c3c4a92a35e44c4c2aa75378462ed01`. The exact five-path scope is
unchanged.

The candidate adds transaction rollback for state/event writes, complete
lease authority checks, governed exec and review wiring, post-claim failure
recovery, running-only terminal import with preserved start provenance, strict
terminal field checks, provenance-complete result digests, byte/event no-op
retries, conflict rejection, validator-compatible terminal events, and
idempotent archive-envelope reuse. Real-store and two-process regressions cover
the failure, ordering, import, recovery, and concurrency paths. Omitting a
session ID remains explicitly ungoverned compatibility and never mutates
workflow state; the formal reviewer must decide whether that boundary satisfies
the issue contract.

Exact-head gates passed before review: 39 local-agent tests in 9.665 seconds
(9.049-second final rerun), 59 workflow tests in 0.725 seconds, 171 aggregate
tests in 133.940 seconds, three checker tests in 0.010 seconds, compilation,
workflow validation, and diff hygiene. Binder session
`i020-integrator-a03-pr-bind` independently confirmed the clean head, tree,
merge base, changed paths, and LPR-009 check binding. Fresh reviewer session
`i020-reviewer-a04-immutable` inspected the unchanged head and returned
`request_changes`. Its four real-store blockers were:

1. `claim_issued_session` compares a caller-supplied base SHA but does not
   verify the actual Git HEAD/tree of the claimed worktree, so a stale worktree
   can be launched under an old authority record.
2. `_session_transaction` catches `Exception` rather than `BaseException`; an
   injected `KeyboardInterrupt` during append leaves the on-disk lease
   `running` without a matching event or recovery.
3. `import_session_result` accepts an arbitrary outcome path outside the
   issued session's registered `result_envelope_path`; including that path in
   the digest does not make the path authorized.
4. `recover_interrupted_session` records a failed session with `outcome_path`
   null, after which canonical archive transition fails the validator's
   required-outcome rule.

The exact candidate remains immutable and clean; LPR-009 is not approved.
Retry session `i020-orchestrator-a03-session-launch-fix2` is repairing these
findings with real-store regressions before a new immutable review round.

## Parallel audit of repaired head

Session `i020-auditor-a06-realstore` independently exercised frozen head
`b6b19362369d683c4de784910825df78526d790b` in 1.447755 seconds. It made no
edits, network calls, Lake/Lean builds, or child sessions. Recovery
transactions passed byte-idempotence, digest-tamper detection,
malformed-artifact preservation, and issued-result symlink rejection controls.

Four additional defects remain open:

1. **High:** repository `core.fsmonitor` and inherited `GIT_CONFIG_*` values can
   execute during `_validate_claim_worktree` before a lease is accepted
   (`scripts/local_agent.py:1494-1656`).
2. **High:** symlinked archive alias directories, the archives root, or
   `result.json` redirect archive reads/writes outside the runtime root
   (`scripts/local_agent.py:2877-2888`).
3. **Medium:** a prior archive envelope is trusted on matching `external_id`
   alone; a JSON-list envelope raises an uncaught `AttributeError`.
4. **Medium:** interruption can leave an empty archive directory that blocks
   retry, and concurrent same-alias calls race.

These are evidence for the queued hardening attempt, not an approval and not a
request to widen QPBT-020 ownership beyond its five declared paths.

## Interruption recovery

The coordinator turn was interrupted after issuing QPBT-020 reviewer
`i020-reviewer-a05-immutable` and fixer `i020-fixer-a07-runtime-hardening`.
The collaboration tree then contained no live worker and `ps` showed no
`codex`/`local_agent` process. Both assigned worktrees were clean at their
frozen bases (`b6b19362369d683c4de784910825df78526d790b` for the reviewer and
the same base for the fixer), with no unimported candidate edits. The attempts
are therefore recovered as failed provenance and will be reissued with new
attempt IDs; the old leases are never silently relaunched.

## Fresh immutable review of b6b1936

Reviewer session `i020-reviewer-a06-immutable` checked LPR-009 at base
`7669f70be786a53ba1a0a92c1d347f5fe7544681` and head
`b6b19362369d683c4de784910825df78526d790b` (tree
`a94b791cbf49f827686a756c70e13b300ab73365`). The five changed paths are
unchanged. The focused local-agent discovery passed 43/43 tests and
`git diff --check` passed; no network, Lake, or Lean command was run. Verdict:
`request_changes`.

The fresh review confirms that prior findings F-LPR009-001 through 004 are
addressed, but records these findings for the exact head:

1. **High** (`scripts/local_agent.py:1494-1505`): `_git_environment` copies
   inherited `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_*`, `GIT_CONFIG_VALUE_*`,
   `GIT_CONFIG_PARAMETERS`, and `GIT_CONFIG_SYSTEM`. A bounded probe kept an
   injected `core.hooksPath` effective despite `GIT_CONFIG_NOSYSTEM=1` and a
   null global config, so claim-time Git commands can still execute attacker
   configuration.
2. **Blocker** (`scripts/local_agent.py:2323-2367,
   2435-2486`): bound execution/review writes `result.json` before the
   terminal import transaction. If import or its append is interrupted,
   recovery encounters the existing finished artifact and leaves the canonical
   session `running`. The importer also does not verify artifact bytes as part
   of the terminal transition.
3. **High** (`scripts/local_agent.py:2851-2939`): archive retries accept a
   matching `external_id` from a symlinked alias or a weak JSON object without
   complete envelope and log-path validation. A symlinked alias containing
   `{"external_id":"x"}` was accepted without invoking the runner. No-follow
   directory creation, confined atomic publication, complete validation, and
   interruption/race cleanup are required.

Related medium boundary notes are retained in the auditor evidence: terminal
elapsed time is not checked against its timestamps, and claim-time Git identity
is not held through child launch. These are not approval conditions to waive;
the hardening fixer owns the five declared paths and must add regressions.

## Runtime-hardening candidate

Fixer session `i020-fixer-a08-runtime-hardening` produced immutable commit
`8417f6a97b37131f58c95645ace69caa95d78e75` (tree
`15ffab237211e302b8007df6a3e7ddde178fa79d`) on base
`b6b19362369d683c4de784910825df78526d790b`. The changed-path set remains
exactly `scripts/local_agent.py`, `tests/test_local_agent.py`,
`protocols/orchestration.md`, `protocols/CHANGELOG.md`, and `workflow/README.md`.

The candidate isolates inherited Git configuration and disables repository
hooks/fsmonitor for identity probes; moves terminal result publication into the
state/event rollback transaction; and confines archive roots and aliases with
no-follow checks, complete envelope validation, atomic rename, interruption
cleanup, and per-alias locking. Four focused regressions cover those edges.
The fixer reports 47/47 local-agent tests, 179 checker tests, compileall,
workflow validation, and diff hygiene passing, with a clean worktree and no
network/Lake/Lean activity. The candidate is frozen pending a fresh independent
immutable review; no approval is implied by the fixer checks.

## Fresh immutable review A07: launch and archive integrity

Reviewer session `i020-reviewer-a07-immutable` inspected the exact frozen
candidate from base `7669f70be786a53ba1a0a92c1d347f5fe7544681`, head
`8417f6a97b37131f58c95645ace69caa95d78e75`, and tree
`15ffab237211e302b8007df6a3e7ddde178fa79d`. The focused local-agent suite
passed 47/47, the workflow suite 59/59, the serial aggregate suite 179/179,
the checker 3/3, compilation, workflow validation, and diff hygiene all
passed. No network, Lake, or Lean build was used. Verdict: `request_changes`.

Two findings remain:

1. **High:** `scripts/local_agent.py:2391-2398,2509-2515` validates the
   registered worktree while claiming the lease, releases the lock, and then
   launches the child without a second identity check. A concurrent actor can
   dirty or switch the worktree after validation; a controlled probe patched
   `_validate_claim_worktree` to create an untracked file immediately after it
   returned, and the claim proceeded while `_working_tree_status` was dirty.
   Revalidate immediately before `_run_exec_unbound`/
   `_run_review_unbound`, or hold an equivalent lease/descriptor through spawn.

2. **Medium:** `scripts/local_agent.py:2963-2970` checks that archived stdout and
   stderr log paths exist and are not symlinks, but does not read them and
   compare their byte counts and SHA-256 digests to the envelope. A retry after
   editing `stdout.log` was accepted without rerunning Codex and returned a
   digest different from the actual log.

The earlier four launch findings and the Git-config isolation finding were
verified fixed. The launch TOCTOU and archive evidence-integrity boundaries
remain open pending a new candidate head and independent review.

## Runtime-race remediation candidate

Fixer session `i020-fixer-a09-launch-race` produced immutable commit
`e0bab14a1489e1b7344dfef63061f515ca0db0b2` (tree
`7fb95fca94ba555b1f4fd804ce5c6298d9b5a800`) on parent
`8417f6a97b37131f58c95645ace69caa95d78e75`. The exact five-path scope is
unchanged: `scripts/local_agent.py`, `tests/test_local_agent.py`,
`protocols/orchestration.md`, `protocols/CHANGELOG.md`, and
`workflow/README.md`.

The candidate revalidates the claimed worktree HEAD/tree immediately before
both governed child-spawn paths and adds deterministic real-store replacement
race regressions. Archive retry now reads both logs and requires exact recorded
byte counts and SHA-256 digests before reusing an envelope, with a tamper
regression. The fixer reports 50/50 local-agent tests, 59/59 workflow tests,
182/182 aggregate tests, checker, compileall, workflow validation, and diff
hygiene passing. The worktree is clean; no network, Lake, or Lean build was
used. This candidate is frozen pending a fresh independent immutable review.

## Fresh immutable review A08

Reviewer session `i020-reviewer-a08-immutable` independently inspected the
exact candidate base `7669f70be786a53ba1a0a92c1d347f5fe7544681`, head
`e0bab14a1489e1b7344dfef63061f515ca0db0b2`, and tree
`7fb95fca94ba555b1f4fd804ce5c6298d9b5a800`. The five changed paths matched
the PR exactly. The reviewer verified both governed launch race regressions
and archive tamper handling, then ran 50/50 local-agent tests, 59/59 workflow
tests, 182/182 aggregate tests, checker 3/3, compileall, workflow validation,
and diff hygiene. No network, Lake, or Lean build was used. Verdict:
`approve`; no new findings were introduced.

The reviewer resolved the recorded findings as follows: Git environment and
hooks/fsmonitor isolation, transaction rollback, terminal path/timing/digest
binding, runtime/archive confinement, strict archive reuse, and claim-to-launch
worktree revalidation are all covered by the frozen implementation and focused
regressions. Residual risk is limited to an unavoidable filesystem-component
replacement between checks and subsequent OS operations; the governed boundary
fails closed when that replacement is observable.

## Post-merge integration gate

The coordinator integrated the complete candidate history in a clean temporary
worktree rooted at the canonical checkpoint. The resulting merge commit is
`4bfdd120bda296691569fc2743a94454eca9b723` (tree
`baf5e879cc24a20b29617f8b5f862a06ecc55889`), with candidate head
`e0bab14a1489e1b7344dfef63061f515ca0db0b2` as the second parent. The merge
preserved all five candidate paths and did not cherry-pick a partial fixer
range.

Post-merge gates in that worktree passed: 50/50 local-agent tests, 59/59
workflow tests, 187/187 aggregate tests, `scripts/check_workflow.py
--skip-tests`, `compileall`, `workflow.py validate`, and `git diff --check`.
No Lean/Lake build was run for this Python-only change. The hot-main cache
probe for the new main SHA reported `miss`; a singleton warm/build is deferred
until the next canonical snapshot so that state reconciliation does not create
duplicate compilation.
