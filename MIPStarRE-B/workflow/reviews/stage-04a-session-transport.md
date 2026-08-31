# Stage 04A session transport scout

Date: 2026-08-31 (Asia/Shanghai)

Scope: read-only inspection of `scripts/local_agent.py`, `scripts/workflow.py`,
`protocols/orchestration.md`, `workflow/README.md`, the workflow tests, the live
Codex CLI help/config, and the session ledger. No network, Lean/Lake, or build
was used. This report is evidence for transport/scheduling decisions; it does
not change canonical state or implementation files.

## Result

There is no transport defect requiring a code change. The smallest sufficient
speedup is operational: measure the active backend ceiling, pass that value to
the existing capacity-aware dispatcher, and issue only independent work. Do
not infer capacity from historical stage metrics or multiply one limit by the
number of backends.

## How a session launches another session

1. **Collaboration transport (the current parent/child mechanism).** The
   collaboration service creates a child logical session and records a parent
   relationship, role, issue, worktree, and owned paths. `spawn_agent`/the
   collaboration layer is the launch operation; `list_agents` observes the
   live physical tree. These logical leases are not the same thing as a new
   OS/backend worker. The service recycles retained workers, and there is no
   completed-node deletion primitive. Child prompts are self-contained and
   child reports are evidence; the orchestrator must inspect the result/diff.
   Protocol ownership and fresh-review checks remain authoritative.

2. **Local CLI transport (`scripts/local_agent.py`).** `run_exec` constructs a
   direct argv invocation of `codex --ask-for-approval <policy> exec --json
   --color never --sandbox <mode> --cd <cwd> -` (current source around
   `scripts/local_agent.py:1758-1868`) and supplies the prompt on stdin.
   `_subprocess_run` uses `shell=False`; bounded calls create a process group
   and terminate it on timeout (`scripts/local_agent.py:985-1058`). JSONL
   stdout, stderr, prompt, and a result envelope are written under the runtime
   run directory. This wrapper is a standalone CLI subprocess and, on current
   main, is not itself a WorkflowStore lease admission mechanism.

   `run_review` first probes persistence and then prepares an isolated review
   harness, validates the target/base/head, and invokes native `codex exec
   review` when the installed capability supports its selector; otherwise it
   uses generic exec over frozen evidence (`scripts/local_agent.py:1871-2109`).
   This protects review evidence but does not create a collaboration child.

3. **Native CLI session controls.** `codex exec --help` (version
   `codex-cli 0.151.0`) exposes stdin prompt `-`, `--json`, `--ephemeral`,
   `--output-last-message`, `--sandbox`, `--cd`, `--ignore-user-config`, and
   subcommands `resume`, `fork`, and `review`. `codex exec review --help`
   supports `--uncommitted`, `--base`, `--commit`, custom prompt, and JSON
   output. `codex queue --thread <UUID-or-exact-name> --message <TEXT>` queues
   work to an existing session; `codex fork [SESSION_ID] [PROMPT]` forks a
   retained interactive session; `codex archive <UUID-or-name>` archives it.
   `codex agents` only browses sessions. None of these help pages states a
   numeric thread quota, so an unmeasured CLI quota must be treated as
   unknown/fail-closed by the workflow.

## Measured logical and physical limits

The following was captured from the live local environment during this scout;
other sessions can change the ledger concurrently.

* `workflow/state/sessions.json`: 233 issued attempts; 228 archived, 4
  running, and 1 issued. Active non-coordinator count is 4. At the observation
  point, the active rows were one `codex-cli` reviewer (issued), three
  `codex-collaboration` scouts/auditor (running), and one coordinator (running;
  excluded from the capacity count). Backends across all attempts were 211
  `codex-collaboration`, 15 `codex-cli`, 4 `root-coordinator`, and 3
  `codex-root`.
* There are 37 unique historical `physical_agent` identities across records
  carrying that field and 101 records marked
  `recycled_physical_session=true`. This is direct evidence that many logical
  leases have been served by retained/reused physical workers.
* `collaboration.list_agents` showed four live physical nodes at the first
  measurement (the root plus three children). This is the currently observed
  collaboration pool, not a guaranteed service-wide limit. The CLI help and
  local config expose no backend thread ceiling. `/home/drx/.codex/config.toml`
  selects `gpt-5.6-sol`, stores no response transcripts, and configures an
  OpenAI-compatible provider; no credentials were copied into this report.
* Stage `max_concurrency` values (STAGE-01 4, STAGE-02 4, STAGE-03 2,
  STAGE-04A 4) are historical observations only. They are not an admission
  authority and must not be used as a current worker limit.

Thus, at the measurement point, the safe additional non-coordinator dispatch
count was zero if the aggregate ceiling is four. A slot becomes available only
after a session reaches a terminal state and is reconciled. Logical session
issuance can continue over time through worker recycling, but it must still be
bounded by the measured aggregate active count.

## Safe bounded parallelism

Use `python3 scripts/workflow.py ready` for readiness, then
`python3 scripts/workflow.py dispatch --capacity N` (or the legacy
`issue-session --capacity N` wrapper). `plan_dispatch` validates the issue DAG,
stage membership, active non-coordinator sessions across **all** backends, and
writable path ownership while the workflow lock is held. Candidate IDs are
sorted. Capacity exhaustion is `queued`; dependency/ownership failures are
`blocked`; a capacity-only wave atomically issues the sorted available prefix,
and a blocked batch remains untouched. Unknown or invalid capacity is rejected
fail-closed after deterministic dependency/ownership diagnostics.

Parallelize only independent read-only scouts/reviewers with disjoint owned
paths. Keep one orchestrator per implementation issue and never issue a
second planned/active orchestrator. Keep dependent proof work sequential.
Lean/Lake compilation still has a singleton hot-main cache builder: one worker
warms a cache key, while others wait and seed private issue-worktree caches.
Dispatch capacity does not relax that singleton or permit shared writable
`.lake/build` output.

The current protocol expressly says `backend_scope: all` is one local-service
ceiling, not one quota per backend (`protocols/orchestration.md:30-58`). This
preserves reviewer independence and writable ownership while allowing safe
read-only fan-out whenever measured capacity permits it.

## Acceptance evidence and smallest-sufficient change

No implementation change is recommended. The existing tests are the
acceptance-tested transport/scheduling change:

* `python3 -m unittest discover -s tests -p 'test_workflow.py'` -> **59 tests,
  OK**.
* Relevant tests include
  `test_active_non_coordinator_count_excludes_coordinator_and_terminal_sessions`,
  `test_active_count_is_conservative_across_backends`,
  `test_dispatch_requires_explicit_capacity_and_rejects_invalid_values`,
  `test_dispatch_plan_reports_sorted_queue_and_dependency_block`,
  `test_dispatch_plan_reports_writable_ownership_conflict`,
  duplicate-orchestrator and cross-candidate ownership tests, atomic batch and
  dry-run tests, and the `issue-session` capacity-wrapper tests
  (`tests/test_workflow.py:343-421, 449-605, 961-1271`).
* `python3 scripts/workflow.py validate` -> **valid** (23 issues, 11 PRs, 0
  planned, 233 issued sessions, 7 stages).
* `codex --version` -> `codex-cli 0.151.0`; all help commands listed above
  exited successfully. Codex emitted only the expected read-only warning that
  it could not create PATH aliases.

If a future operator needs automation beyond this, the smallest justified
addition would be a read-only capacity probe that reports the measured backend
limit and feeds it to `dispatch`; it should not invent a default or alter
lease/ownership semantics. Existing acceptance tests should be extended only
if that probe is implemented.

## Residual risk

The collaboration service's physical pool and any provider-side CLI quota are
external runtime facts and can change without a repository diff. There is no
CLI help/API evidence of a numeric provider thread limit. Therefore operators
must record the measurement, use an explicit aggregate capacity, and fail
closed when it is unavailable. Recycled physical workers do not weaken logical
lease identity, parentage, fresh-review, or path-ownership rules, but a caller
that bypasses `workflow.py dispatch` could still create untracked CLI work.
