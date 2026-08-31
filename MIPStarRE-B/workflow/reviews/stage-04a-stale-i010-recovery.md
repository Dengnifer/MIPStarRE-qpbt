# Stage 04A stale-session recovery

## Evidence

- Logical session: `i010-reviewer-a02-reference-transport`
- Issue/PR: `QPBT-010` / `LPR-001`
- Recorded status before recovery: `issued`
- Recorded external identity: `null`
- Recorded start time: `null`
- Worktree: `.workflow-runtime/worktrees/qpbt-010`
- Observed worktree HEAD: `e93d949d06af2a7f4407d198a37aad315deac6aa`
- Observed worktree status: clean
- Process check at `2026-08-31T08:50:09Z`: no `codex` or `local_agent`
  child process was present; only the coordinator's sandbox wrapper matched.

The lease has no result envelope, output path, or persistent external session
identity. The clean worktree and process absence establish that it is an
orphaned pre-launch record rather than a live reviewer. No files were changed,
and no network, Lean, Lake, or build command was run.

## Recovery

Following the orchestration recovery rule, the coordinator transitions the
attempt to `failed` with this evidence, then archives it. The failed attempt is
retained as provenance and is not silently relaunched. Any future review gets a
new stable attempt ID and a fresh immutable target.

## Throughput effect

Before recovery, the explicit aggregate capacity-four planner counted this
issued lease as active even though no worker existed. Archiving it releases one
logical admission slot for an independently owned session. This does not raise
the measured service ceiling; it removes stale accounting that hid available
capacity.
