# Stage 04A CLI Capacity Audit

Logical session: `i000-auditor-a35-cli-capacity`  
Audit date: 2026-08-31 (Asia/Shanghai)  
Scope: read-only local collaboration/Codex CLI capacity and nested-session transport.

## Snapshot and hygiene

The audited main snapshot is:

```
HEAD e2446272a3cc904a612d7e0e5003074ef4a680ad
tree 4bfdd120bda296691569fc2743a94454eca9b723
parent 6506703b5dcf2abd20b00cd7bd454a6b79ec0534
```

The initial `git status --short --branch` was:

```
## main
 M workflow/events.jsonl
 M workflow/state/sessions.json
 M workflow/state/stages.json
?? workflow/reviews/stage-04a-postmerge-frontier.md
```

Those pre-existing user/coordinator changes were preserved. No source or
canonical state file was edited by this audit. `python3 scripts/workflow.py
validate` returned `{"valid": true, "counts": {"issues": 23,
"pull_requests": 11, "planned_sessions": 0, "issued_sessions": 236,
"stages": 7}}`.

## Measured limits

`collaboration.list_agents` returned four live nodes: `/root` and three
collaboration workers (`/root/qpbt020_review_a27`, `/root/qpbt021_scout_a29`,
and this session). This is the directly measured current topology, not a
portable service guarantee.

The current session ledger contained 236 issued rows: 232 archived and four
running (one coordinator plus three collaboration workers). The 29 historical
`sessions.dispatched` events used aggregate capacities 4 (28 events) or 3 (one
event), never a per-backend multiplier. The largest admitted batch was three;
the largest recorded `active_non_coordinator` value was three. One event had a
queued candidate at capacity four. Stage metrics report `max_concurrency` 4
for STAGE-01, STAGE-02, and STAGE-04A, and 2 for STAGE-03; the orchestration
protocol explicitly defines these as observations rather than admission
limits.

The independent transport metric for `i000-scout-a31-session-transport` records
`codex-cli 0.151.0`, four observed collaboration nodes, four observed active
non-coordinator workers, 37 unique physical identities, 101 recycled records,
and `transport_change_recommended: false`. The differing coordinator-counting
convention is why this report treats four as the observed environment ceiling,
not as a new protocol constant.

There is a second, independent limit: `INC-041` records that completed
collaboration threads remain retained by the service and can exhaust its hard
thread limit even when a logical worker slot is idle. The incident has no
portable numeric limit. Its prescribed mitigation is to record the failed
pre-launch attempt and recycle an explicitly completed thread under a fresh
governed logical session ID, while keeping dispatch capacity separate from
thread-retention capacity.

Host resource probes (`nproc`: 128; `ulimit -u`: 2060932; `ulimit -n`:
1048576) are not Codex transport measurements and do not justify increasing
the collaboration ceiling.

## Launcher and CLI behavior

`scripts/local_agent.py` has no worker pool, semaphore, or backend fan-out. A
governed `run`/`review` claims one issued lease, revalidates the worktree, and
starts one `codex` child. Bounded execution defaults to 1,800 seconds
(`DEFAULT_CODEX_TIMEOUT_SECONDS`, line 36); `_subprocess_run` uses `Popen` with
`start_new_session=True`, and timeout/interruption cleanup terminates the
complete process group (lines 1366-1439). Review performs an optional
persistence/capability preflight and then one bounded review child (lines
2556-2824), writing a terminal envelope even on timeout (lines 2825-2915).
There is therefore no hidden child multiplier that could safely be added to
the dispatcher capacity.

The installed CLI is `codex-cli 0.151.0`. `codex agents --help` describes
browsing sessions on the local app-server and exposes no concurrency option;
`codex exec --help` exposes `resume`, `fork`, and `review` but no local worker
limit; `codex review --help` likewise exposes selectors and review options but
no concurrency control. These help probes did not start a model request.

## Safe fan-out assessment

Independent read-only scouts, blueprint mappings, and fresh reviewers may be
admitted only with an explicit measured aggregate capacity. On this host that
means at most the observed four collaboration nodes, with the coordinator and
backend-counting convention made explicit in the dispatch evidence. Do not
interpret `--capacity 4` as four slots per backend, and do not infer a larger
limit from CPU or file-descriptor headroom.

Fan-out remains unsafe when tasks share writable paths, when a child depends on
a prior mathematical result, or when two candidates would materialize the same
worktree/cache output. The dispatcher’s lock, dependency checks, ownership
checks, atomic admitted prefix, and queued-row revalidation address those
boundaries. Lean/Lake work remains serialized behind the one hot-main cache
builder for a cache key; increasing session fan-out cannot change that.

When retained collaboration threads are exhausted, do not issue duplicate
logical work or silently relaunch an old identity. Reconcile the failed
pre-launch attempt, recycle a completed physical thread only with a new
governed logical lease, and preserve the external identity mapping.

## Decision

**Verdict: no protocol or source change justified.** The existing rules in
`protocols/orchestration.md:30-58` already require explicit aggregate capacity,
fail closed on unknown capacity, distinguish observed stage metrics, preserve
the singleton cache builder, and warn that four slots are an environment fact.
The existing `INC-041` mitigation supplies the smallest justified operational
handling for retained-thread exhaustion. A new numeric default or backend
multiplier would be unsound without a service-level measurement that is not
available here.

Audit accounting: edits 0 (apart from this requested report), new workflow
issues 0, subagents dispatched 0, Lean/Lake/build invocations 0, network
requests 0, elapsed time approximately 0.1 minutes for local probes; token
usage is unavailable for this collaboration session.
