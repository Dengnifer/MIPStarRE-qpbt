# QPBT-010 endpoint review A06

Session: `i010-reviewer-a06-endpoint-transport`
Candidate: `/home/drx/MIPStarRE-auto/.workflow-runtime/worktrees/qpbt-010`
Requested target: base-target review, base `77aa1a4ac947c1632ea57262d29d2753ba163c8a`, head `e93d949d06af2a7f4407d198a37aad315deac6aa`
Verdict: **blocked**

The candidate preflight is valid, but the authorized endpoint-backed reviewer could not be launched. The first unbound invocation failed during the local host persistence probe before preparing repository evidence. A host-level retry was rejected by the execution policy because it would transmit repository evidence to an external destination. No endpoint request, external thread, model output, review verdict, findings JSON, or usage envelope exists for A06. This report records the failure rather than treating the local approval or health canary as endpoint-review evidence.

## Authorization and prior transport evidence

`workflow/reviews/stage-01-external-review-authorization.md:3-15` records explicit authorization for model `gpt-5.6-sol` at `https://api.finite-dimensional.space` over the Responses API, local provider label `OpenAI`, with credential recording prohibited. `workflow/reviews/stage-01-endpoint-health-a02.md:3-20` records a successful empty-repository health canary (external thread `01a05327-feb8-7a01-b2f7-b432151305f4`, 15.196164 seconds, usage exposed). That canary establishes transport availability only; it is not a review verdict.

The exact profile supplied to A06 was:

```text
--model gpt-5.6-sol
--model-provider OpenAI
--provider-name OpenAI
--provider-base-url https://api.finite-dimensional.space
--wire-api responses
--provider-requires-openai-auth
```

The assignment required a fresh read-only review of the exact base-to-head diff, including `scripts/reference_transport.py`, its tests, surrounding callers, source fidelity, revision binding, bounded capture, timeout/process-group cleanup, fallback selection, and publication confinement. It required the structured JSON contract in `workflow/prompts/reviewer.md`.

## Candidate identity

Read-only checks on the supplied worktree returned:

```text
HEAD       e93d949d06af2a7f4407d198a37aad315deac6aa
HEAD^1    cf43b33b5cd77cb005b90b02b6d369cfbd86d316
HEAD tree  b518e346719a7d208604ba4c0b2db2b215fb77a2
base -> head ancestor: exit 0
git status --short: empty
git diff --check: pass
```

The exact base-scoped delta has the three expected paths:

```text
A scripts/reference_transport.py
A tests/test_reference_transport.py
A workflow/reviews/qpbt-010-reference-transport.md
```

The LPR-001 record (`workflow/state/prs.json`, current record) binds local checks and independent local approval `review-qpbt-010-a04-immutable` to this exact base/head pair. Its prior local findings F-LPR001-001, F-LPR001-002, and F-LPR001-003 are recorded resolved on later head `e93d949...`. Those local records do not substitute for the requested external review.

## Launch evidence

The unbound command used the exact base-target form and all six transport fields:

```text
python3 scripts/local_agent.py --repo-root /home/drx/MIPStarRE-auto \
  --runtime-dir /tmp/qpbt010-endpoint-a06 review \
  --issue QPBT-010 --attempt 6 --slug endpoint-transport \
  --task-file /tmp/qpbt010-review-task-a06.md \
  --cwd /home/drx/MIPStarRE-auto/.workflow-runtime/worktrees/qpbt-010 \
  --base main \
  --base-sha 77aa1a4ac947c1632ea57262d29d2753ba163c8a \
  --head-sha e93d949d06af2a7f4407d198a37aad315deac6aa \
  --model gpt-5.6-sol --model-provider OpenAI --provider-name OpenAI \
  --provider-base-url https://api.finite-dimensional.space \
  --wire-api responses --provider-requires-openai-auth \
  --timeout-seconds 900
```

The complete failure envelope is preserved at `/tmp/qpbt010-endpoint-a06/runs/i010-reviewer-a06-endpoint-transport/result.json`:

```json
{
  "status": "failed",
  "failure_classification": "outer-host-codex-persistence-unwritable",
  "host_persistence_probe": {"status": "failed", "error_type": "OSError", "errno": 30, "cleanup_complete": true},
  "repository_evidence_prepared": false,
  "repository_evidence_transmitted": false,
  "external_id": null,
  "token_usage": {"input": null, "output": null, "total": null, "availability_reason": "Codex was not launched after local persistence preflight failure"},
  "read_only": true,
  "nested_sandbox": "read-only",
  "timed_out": false,
  "stdout_bytes": 0,
  "stderr_bytes": 0
}
```

The launcher returned process exit 0 because it emitted the failed envelope; the envelope's `returncode` is null and `command` is empty, confirming no Codex subprocess started. Wall time was 0.07 seconds; envelope elapsed time was 0.000378 seconds. A second identical invocation with `sandbox_permissions=require_escalated` was rejected before execution by the host policy as unacceptable external-evidence egress risk. It therefore produced no additional runtime or endpoint evidence.

## Checks and residual risk

- `python3 scripts/workflow.py validate`: passed (`valid=true`, 24 issues, 11 PRs, 252 issued sessions, 7 stages), approximately 0.14 seconds.
- Candidate `rev-parse`, clean-tree, ancestor, changed-path, and `git diff --check` probes: passed.
- `python3 scripts/local_agent.py review --help`: passed; base-target, immutable SHA, runtime, and all transport-profile flags are present.
- No candidate tests, compileall, Lean/Lake, build, cache, archive, or network command was run; running tests was unnecessary after preflight failure and could alter the candidate worktree.
- No canonical source, blueprint, workflow state, PR/issue record, metrics, candidate worktree, or runtime build output was modified. Only `/tmp/qpbt010-review-task-a06.md`, the `/tmp/qpbt010-endpoint-a06` failed envelope, and this report were created.
- Token usage: unavailable for A06; the failed envelope records null usage with its availability reason.
- Elapsed time: under two minutes including preflight, policy rejection, and report capture.

The residual risk is that no independent endpoint model inspected the diff. The prior local approval remains the only completed review for this head; QPBT-010's endpoint gate must remain open until a separately authorized host-capable run returns a complete terminal envelope and structured verdict tied to the exact base/head/tree.
