# Workflow State

This directory replaces GitHub issues, pull requests, review threads, and agent
run status with local versioned records.

## Canonical files

- `state/issues.json`: issue hierarchy, dependencies, acceptance gates, owners.
- `state/prs.json`: local PR base/head revisions, checks, reviews, findings.
- `state/sessions.json`: planned roles and actual issued attempts.
- `state/stages.json`: top-level project stage measurements and outputs.
- `state/protocols.json`: active protocol revision and evolution history.
- `events.jsonl`: append-only canonical lifecycle events.
- `prompts/`: trusted role contracts passed to fresh Codex sessions.

Raw Codex JSONL, prompts assembled for a specific issue, build logs, cache data,
and result envelopes live under ignored `.workflow-runtime/`. Only the root
coordinator imports compact, inspected evidence into canonical files.

Launches of issued sessions are lease-bound: authority is checked under the
WorkflowStore lock, the session is marked running before child invocation, and
terminal evidence is imported exactly once. Interrupted sessions are explicitly
failed and are never silently relaunched.
The `run` and `review` commands accept `--session-id` to select this governed
path. Calls without it are explicitly ungoverned compatibility operations and
cannot update canonical session state.

## Commands

```bash
python3 scripts/workflow.py validate
python3 scripts/workflow.py ready
python3 scripts/workflow.py show --help
python3 scripts/workflow.py add --help
python3 scripts/workflow.py update --help
python3 scripts/workflow.py transition --help
python3 scripts/workflow.py issue-session --help
python3 scripts/workflow.py dispatch --help
python3 scripts/hot_main_cache.py status
python3 scripts/local_agent.py --help
python3 scripts/bootstrap_manifest.py --help
```

Run validation before dispatch, after any state edit, before review, and after
integration. The aggregate gate also reconciles canonical event lifecycles,
incident references, protocol-change evidence, and terminal-session metrics.
State writes are locked and atomically renamed. Do not hand-edit canonical JSON
while another coordinator command is active.

Terminal artifact publication and lifecycle import are one rollback-safe
transaction. Archive directories are confined beneath `.workflow-runtime`,
published by atomic alias rename, and reused only after strict envelope and log
validation. Git claim/status probes run with isolated configuration and disabled
repository hooks/fsmonitor callbacks.

`dispatch` is the capacity-aware batch entry point. The legacy `issue-session`
command is a single-session wrapper around the same planner and also requires
an explicit capacity. On success it preserves its historical JSON shape by
returning the issued session record; queued or blocked attempts return the
planner envelope with a status and reason. Dispatch requires an explicit
non-negative `--capacity`; an omitted or unknown limit fails closed. The command
counts active `issued`/`running` sessions other than `coordinator` across all
backends (the explicit limit is an aggregate local ceiling), scoped
to `--stage` when requested, and sorts planned session IDs before classifying
them as `dispatchable`, `queued`, or `blocked`. Capacity-only queueing issues the
available prefix atomically and leaves the remainder planned; a batch containing
any blocked candidate is left unchanged. Cross-candidate materialization
conflicts are checked for the admitted prefix; queued rows are revalidated when
they are admitted. Ownership conflicts are checked across the whole selected
set. `backend_scope: all` is one local-service ceiling: counts are summed across
backends and `--capacity N` is never multiplied into per-backend quotas. The
result's `request_atomic` and `blocked_batch_unchanged` fields make the
transaction and rollback semantics explicit. Use `--dry-run` to inspect that plan.
When capacity is unknown, dependency and ownership analysis still runs and its
deterministic diagnostics are included in the fail-closed error; no state or
event is written.
Stage `max_concurrency` remains historical observation data and is not an
admission limit.

An issued launch lease also binds the live worktree: the launcher must observe
a clean Git repository at the registered root with the exact issued `HEAD` and
tree (or an unborn repository when the base is null), and repeats that identity
check immediately before spawning the child. Terminal imports must use
the normalized, in-root `result_envelope_path` from the issued row. An
interrupted lease writes a deterministic failed recovery envelope at that path;
the recovery and its subsequent archive transition are retried only by
reusing the recorded evidence.

The planner reserves one orchestrator slot per issue: a second planned or
active orchestrator is blocked at admission, including for a still-planned
issue. Terminal attempts remain provenance for a later retry. Dispatch override
objects must use one shape (single record, keyed map, or ID-bearing list); a
single record mixed with keyed entries is rejected.
