# QPBT-012 Nested Codex and Lifecycle Hardening

- Logical session: `i012-orchestrator-a01-nested-codex-hardening`
- Immutable base: `77aa1a4ac947c1632ea57262d29d2753ba163c8a`
- Scope: `scripts/local_agent.py`, `scripts/workflow.py`,
  `scripts/check_workflow.py`, `tests/test_local_agent.py`,
  `tests/test_workflow.py`, and this review note
- Incident inputs: `INC-010`, `INC-021`

## Architecture

Reviewer launch now probes the actual Codex persistence root before reading task
or context files at the CLI boundary. The CLI enters a private post-success
review helper without probing again. Public `run_review` callers independently
perform exactly one probe before resolving the source repository or constructing
an evidence harness. The probe creates a random private directory and exclusive
mode-0600 file, writes and fsyncs a fixed non-secret payload, removes both, and
fsyncs the persistence root. It never enumerates or reads persistent state,
credentials, headers, or user configuration.

A failed probe creates only the ignored local result directory. Its envelope
classifies `outer-host-codex-persistence-unwritable`, records fixed-shape error
type/errno and cleanup evidence, and states that repository evidence was neither
prepared nor transmitted. It does not write the prompt, construct a harness,
run a capability subprocess, or invoke Codex. Dry runs explicitly skip the
probe because they do not launch Codex.

The host persistence capability remains separate from model authority. Every
real reviewer command still carries nested `--sandbox read-only`, disables
automatic project instructions, and operates only in the ephemeral immutable
evidence harness. Provider routing remains an independently validated,
non-secret argv profile.

All completed subprocess envelopes now contain exact UTF-8 stdout/stderr byte
counts and SHA-256 digests. These constant-size fields cover ordinary non-timeout
failures as well as timeouts, while existing timeout-only partial byte fields
retain their original meaning.

New `session.issued` and issued-session `record.transitioned` events emit
`payload.session_id`. Event replay retains only the narrow schema-v1
`session.issued` `payload.id` fallback required by immutable historical rows.
Regression coverage drives one session through running, finished, and archived,
and a second through failed and archived, then performs full event reconciliation.

Research-ledger validation now binds every session metric to its issued
session's exact issue and unique stage, rejects duplicate issue-to-stage
mappings and unknown stages, and derives each stage's issued-subagent total from
stage issue membership. The root `coordinator` role is deliberately excluded;
all other issued roles count as subagents.

## Acceptance Evidence

- A forced persistence permission failure returns locally before packet/context
  loading, runner invocation, prompt publication, harness creation, or thread
  creation; the injected diagnostic text is absent from the result envelope.
- The successful CLI path consumes exactly one probe result in strict
  `probe -> packet -> post-success helper` order. A queued second failure remains
  unused, proving the helper cannot silently repeat the probe after evidence load.
- An ordinary return-code failure binds both output streams by exact byte count
  and digest while leaving timeout partial counts at zero.
- Existing transport tests confirm provider overrides still precede `exec`,
  `--sandbox read-only` remains present, instruction loading remains disabled,
  and environment secrets do not enter the dry-run envelope.
- Lifecycle regressions validate canonical issuance plus running, finished,
  failed, and archived transitions end to end.
- Reconciliation regressions cover exact success, metric issue mismatch,
  unknown metric stage, duplicate issue mapping, and stale stage totals.

## Review Finding And Disposition

Fresh pre-freeze reviewer `i012-reviewer-a01-nested-codex-hardening` requested
changes because the initial CLI performed one probe before packet loading and
then called `run_review`, which probed a second time. A transient second failure
could therefore produce a preflight-failure envelope after task/context evidence
had already been loaded.

`i012-fixer-a01-single-persistence-probe` resolved the finding by moving the
unchanged review execution into a private post-success helper. The production
CLI validates and probes once before packet loading, then calls that helper;
the public direct-call API validates and probes once before calling the same
helper. No public parameter accepts a caller-supplied success mapping. The new
ordering regression simulates a first success followed by a possible second
failure and proves only the first result is consumed.

## Validation

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p
  'test_local_agent.py'`: 34/34 passed in 3.249 seconds.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p
  'test_workflow.py'`: 34/34 passed in 0.375 seconds.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/check_workflow.py`: workflow
  state valid and 93/93 aggregate tests passed in 6.130 seconds (6.38 seconds
  wall).
- `PYTHONPYCACHEPREFIX=/tmp/i012-fixer-a01-pycache python3 -m compileall -q
  scripts tests`: passed without writing bytecode into the worktree.
- `git diff --check`: passed.

An initial non-gate `python3 -m unittest tests.test_local_agent
tests.test_workflow` invocation failed immediately with two import errors because
`tests/` is not a Python package. The canonical discovery commands above were
then run exactly and passed; no implementation failure or test retry was hidden.
The first post-review focused run also exposed one stale CLI wiring mock that
still intercepted public `run_review`; it was updated to intercept the new
private post-success helper, after which the exact focused and aggregate gates
above passed.

## Review Status

This is orchestrator-authored implementation evidence, not an approval. The
finished head still requires the acceptance gate's fresh, independent local
reviewer; that reviewer must not be this implementer or the issue orchestrator.
