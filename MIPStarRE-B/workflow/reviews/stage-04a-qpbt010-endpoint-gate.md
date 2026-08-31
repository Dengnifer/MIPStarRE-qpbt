# QPBT-010 Endpoint Gate Audit

Session `i000-reviewer-a42-qpbt010-gate` performed a fresh read-only
provenance audit from main SHA `5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6`
(tree `544aac816db08aea60ef231bbc951992bc86f9e5`), with no source, blueprint,
state, PR, metrics, build, or network changes. Elapsed time was approximately
5 minutes including bounded inspection and CLI probes. Token usage is
unavailable from the collaboration backend.

## Verdict and recommendation

**No-go for treating current main as the approved immutable LPR-005 review
target.** A fresh endpoint-backed review is legitimate in principle, but it
must run against a clean checkout whose `HEAD` is exactly the recorded LPR-005
head `4de452495228aad3debe05f166097e746b97b2e5`, with base
`77aa1a4ac947c1632ea57262d29d2753ba163c8a`. Current main contains the recorded
integration `687e182c7ad41520c226a59160c084ab53ad6f38` and later commits, but
does not contain the recorded approved head. Therefore no endpoint review
result obtained from current main could be imported as evidence for the
immutable LPR-005 head without first reconciling PR metadata or provisioning
the exact head worktree.

The configured endpoint itself passes the authorization and health gates. The
remaining QPBT-010 gate is a real full frozen-evidence review, not another
health canary; none was launched by this audit.

## Findings

1. **High: LPR-005 head is not current-main content.** The PR record says
   `status: merged`, `base_sha: 77aa1a4...`, `head_sha: 4de4524...`, and
   `integration_sha: 687e182...` (`workflow/state/prs.json:1383-1392,1556-1575`).
   Git proves `687e182...` is an ancestor of current `5d36cdf...`, but
   `4de4524...` is not (`git merge-base --is-ancestor 4de4524... 5d36cdf...`
   exits 1; merge base is `77aa1a4...`). The trees are distinct:
   `4de4524...^{tree}=8b8e6db14eca531f6319012dbd145c02252da1fa` and current
   `544aac816db08aea60ef231bbc951992bc86f9e5`. The recorded integration tree
   is `5b43ca5c46120ebc1de3e005af3ea11cd439f4cf`; current foundation paths
   match that integration, but `scripts/hot_main_cache.py` differs between
   integration and approved head. The PR metadata therefore cannot be used to
   claim that current main bytes are the approved LPR-005 bytes.

2. **Medium: endpoint health is not full-review evidence.** The explicit user
   authorization records model `gpt-5.6-sol`, endpoint
   `https://api.finite-dimensional.space`, Responses API, and no credential
   recording (`workflow/reviews/stage-01-external-review-authorization.md:3-15`).
   Health probe A02 used an empty disposable Git repository and returned the
   exact `{"endpoint":"ok","model":"gpt-5.6-sol"}` response in 15.196164s,
   with complete thread/final/usage evidence (`workflow/reviews/stage-01-endpoint-health-a02.md:3-20`).
   This proves transport availability only. The review protocol explicitly
   requires a fresh immutable review after the canary and says a canary does
   not validate the larger prompt (`protocols/review.md:33-78`). QPBT-010's
   endpoint-specific gate consequently remains unsatisfied until a full review
   terminal envelope contains an actual verdict tied to the frozen SHA.

3. **Low: native review selector is unavailable; generic frozen-evidence exec
   is the tested fallback.** `codex --version` reports `codex-cli 0.151.0`.
   `codex exec review --help` supports `--commit`, `--base`, `--json`, `-m`,
   `--ignore-user-config`, `--ignore-rules`, and stdin prompt, but the launcher
   capability probe reports `selector_with_prompt_supported: false`, parser
   return code 2, and reason `installed parser rejects selector plus custom
   prompt` (probe hash `ddb22fbb9010d50b55b43615cf34b5deeec9444884d8143d9002c34c74231ace`).
   `scripts/local_agent.py:1829-1915` therefore selects
   `generic-exec-frozen-evidence`; this is a supported fail-closed mode, not an
   endpoint authorization failure.

## Exact authorized transport

The launcher validates an all-or-none non-secret profile
(`scripts/local_agent.py:480-547`) and emits top-level config overrides before
`exec` (`:550-568`). The profile used by the authorized Stage 1 evidence is:

```text
--model gpt-5.6-sol
--model-provider OpenAI
--provider-name OpenAI
--provider-base-url https://api.finite-dimensional.space
--wire-api responses
--provider-requires-openai-auth
```

The resulting overrides are:

```text
-c model_provider="OpenAI"
-c model_providers.OpenAI.name="OpenAI"
-c model_providers.OpenAI.base_url="https://api.finite-dimensional.space"
-c model_providers.OpenAI.wire_api="responses"
-c model_providers.OpenAI.requires_openai_auth=true
```

No API key is accepted or recorded. The endpoint URL must be HTTPS and have no
userinfo, credentials, query, or fragment. The profile validation accepted the
exact values above; it rejected HTTP and incomplete all-or-none profiles.

## Required full-review command shape

After provisioning a disposable clean checkout at `HEAD=4de4524...` (and
verifying its first parent is `77aa1a4...`), the governed command must use the
registered session lease and exact immutable SHA fields. Its shape is:

```text
python3 scripts/local_agent.py review \
  --issue QPBT-004 --attempt <attempt> --slug qpbt010-endpoint-gate \
  --task-file <frozen-review-task> --cwd <clean-head-worktree> \
  --base main --base-sha 77aa1a4ac947c1632ea57262d29d2753ba163c8a \
  --head-sha 4de452495228aad3debe05f166097e746b97b2e5 \
  --model gpt-5.6-sol --model-provider OpenAI --provider-name OpenAI \
  --provider-base-url https://api.finite-dimensional.space \
  --wire-api responses --provider-requires-openai-auth \
  --session-id <issued-session-id> --parent-session-id <coordinator-session-id>
```

The wrapper's `base` target requires source `HEAD` to equal the declared head,
a clean source worktree, and base ancestry
(`scripts/local_agent.py:2584-2601`). It then captures an isolated harness and
revalidates the target before constructing the prompt (`:2682-2733`). The
child is read-only and uses `--ignore-user-config`, `--ignore-rules`, and the
validated profile before generic `codex exec` (`:2735-2773`). A legitimate gate
result must include the terminal result envelope, external thread ID, model,
transport profile, reviewed base/head/tree and evidence digests, prompt byte
count, final structured review JSON, usage fields when exposed, and archival or
retirement evidence. A health response alone is insufficient.

## Checks performed

- `git rev-parse HEAD HEAD^{tree}`: exact current SHA/tree above.
- `git cat-file -t` for current, approved head, integration, and base: all
  returned `commit`.
- `git merge-base --is-ancestor 4de4524... 5d36cdf...`: exit 1.
- `git merge-base --is-ancestor 687e182... 5d36cdf...`: exit 0.
- `git diff --quiet 687e182... 5d36cdf... --` foundation paths (`MIPStarRE.lean`,
  manifests, materializers): exit 0; cache path differs.
- `python3 scripts/local_agent.py review --help`: exit 0, elapsed 0.09s.
- `PYTHONPATH=scripts python3` capability probe: exit 0, elapsed 0.29s;
  Codex 0.151.0, native selector rejected, generic fallback selected.
- `PYTHONPATH=scripts python3` transport profile validation and argument
  construction: exit 0, elapsed 0.07s; exact non-secret overrides above.
- `python3 scripts/workflow.py validate`: pass, 24 issues, 11 PRs, 245 issued
  sessions, 7 stages; elapsed 0.14s.
- `git diff --check` against current HEAD: pass.
- No full endpoint request, source acquisition, build, Lean/Lake command, or
  workflow/PR/state mutation was performed by this audit.

## Go/no-go

**Go** to schedule the endpoint-backed immutable review only after creating a
clean worktree at the exact LPR-005 head and issuing a governed reviewer lease
with the transport profile above. **No-go** to review current main as if it
were that head, and **no-go** to close QPBT-010 from the A02 canary alone.
