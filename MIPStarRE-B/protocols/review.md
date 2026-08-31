# Local Review Protocol

## Gate order

Model review starts only after deterministic validation succeeds. Code review
and blueprint/prose review are separate fresh sessions because their failure
modes differ. A completion auditor checks the assembled outcome after both.

Reviewer sessions run read-only and receive a trusted prompt from the reviewed
base plus an untrusted diff/context artifact. The wrapper loads and hashes base
authority with `git show`, constructs an isolated evidence repository, disables
project/user instruction loading there, and records the installed Codex version
and review-help hash. It uses a native selector only when a parser probe proves
that selector and trusted prompt coexist; otherwise it uses generic read-only
`codex exec` over the same frozen evidence. They may inspect paper sources,
blueprint entries, definitions, callers, and build logs. They may not edit,
commit, launch fix agents, change state, or approve their own work.

## Execution bounds

Every local Codex run has an explicit wall-clock bound. The default is 1,800
seconds; a stage may choose a smaller positive value and records it in the run
envelope. On timeout, the wrapper terminates the complete Codex process group,
escalates to a forced kill after a short grace period, and preserves any partial
stdout and stderr. It writes a failed result envelope even when no thread ID,
usage event, final message, or verdict was exposed.

A timeout is terminal evidence for that attempt, not a review verdict. The
session is archived or retired according to the exposed thread evidence, the
incident is recorded, and any retry receives a new stable alias. A timed-out
attempt never confers approval and cannot be resumed as the approving reviewer.

## External disclosure preflight

Before an external model-backed reviewer starts, record the exact endpoint
origin, model identifier, wire protocol, evidence scope, and explicit user
authorization. Never record an API key or authentication token. Changing the
endpoint, model, or evidence scope invalidates the authorization binding and
requires a new preflight decision. A rejected launch is terminal and cannot be
routed through a different persistence or network path.

Custom reviewer transport is an explicit, non-secret all-or-none profile: the
model-provider key, provider display name, HTTPS base URL, `responses` wire API,
and the provider's `requires_openai_auth` boolean. The wrapper keeps
`--ignore-user-config` and injects the validated profile as top-level CLI
configuration overrides before `exec`; authentication still comes from the
Codex credential store and is never read or recorded by the wrapper. Provider
keys must be safe dotted-config components, and endpoint URLs with userinfo,
credentials, queries, fragments, or non-HTTPS schemes fail before evidence
dispatch.

For the Stage 1 bootstrap review, the authorized profile is
`gpt-5.6-sol` over the Responses protocol at
`https://api.finite-dimensional.space`. The disclosure scope is the frozen
Stage 1 repository evidence read by the reviewer; ignored paper payloads,
runtime files, and credentials are excluded.

Before spending a frozen full-evidence attempt, a minimal read-only prompt must
receive a complete response through that exact endpoint/model profile within
the configured health window. The probe gets its own stable session and metric,
contains no repository contents, and is archived. A connection, fallback, or
reconnect-only stream fails closed and blocks the large review until a later
probe succeeds. Use a disposable empty Git repository for the probe so Codex's
trusted-repository preflight remains enabled without exposing project files.

The health canary proves transport availability only; prompt construction has
an independent bounded-payload gate. A frozen prompt includes trusted authority,
selectors, revisions, status hashes and counts, the evidence digest, and a
fixed-shape manifest summary whose numeric counters grow only logarithmically.
It references `evidence/manifest.json` inside
the isolated harness rather than duplicating its per-file entries. The wrapper
verifies both the exact file-byte digest and the parsed manifest's logical
digest immediately before launch, while the full manifest remains in the
harness and result envelope. Tests must demonstrate that manifest cardinality
does not make the prompt grow linearly. Record exact UTF-8 prompt bytes for each
attempt; if this gate fails, fix the packet before spending a full reviewer
session rather than treating a tiny successful canary as evidence that a large
prompt will complete.

The unborn Stage 1 review passes `--bootstrap-snapshot-digest` with the exact
digest printed by the freeze tool. The launcher accepts this phase contract
only with `--uncommitted` while `HEAD` is unborn. It independently runs the
bootstrap verifier, matches the digest, requires an unsealed Stage 1 manifest,
and compares the manifest's terminal-evidence contract with the tool's fixed
allowlist and rule. After evidence capture it repeats verification, byte-matches
the copied freeze manifest, and binds every captured core path and hash to the
verified freeze before dispatch. The trusted phase record has an exact key set
and constant values; extra, missing, or changed fields fail before prompt
serialization. Only then does built-in trusted prompt text explain the
unavoidable ordering: the current reviewer's terminal lifecycle fields, final
report, and seal are completed after an approving reviewer returns, so their
pre-return state is not a finding by itself. Manifest prose remains evidence
and is never interpolated into reviewer authority.

## Code and mathematical review

Review only the local PR delta, but inspect enough surrounding code to verify it.
Priorities are:

1. mathematical truth and exact paper-statement fidelity;
2. soundness, forbidden assumptions, proof holes, and quantifier/domain drift;
3. Lean type/API correctness and downstream behavior;
4. reproducible source/build behavior and cache isolation;
5. maintainability issues that materially affect future proofs.

For every changed source-labelled theorem, compare paper and Lean assumptions,
conclusion, quantifier order, parameter bounds, normalizations, and error terms.
Boundary hypotheses must be justified. A load-bearing proof-obligation input is
a blocker even if the declaration compiles.

Findings are ordered by severity and cite `path:line`. Each states the concrete
failure, evidence, impact, and smallest reasonable fix. Do not manufacture
comments, repeat an existing unresolved finding, or lead with style nits.

## Blueprint/prose review

Check source citations, exact definitions, dependency edges, notation,
cross-references, declared encoding choices, and `\leanok` truthfulness. Verify
the blueprint explains every mathematically load-bearing boundary introduced by
the formal encoding. A readable but inaccurate blueprint fails review.

## Findings ledger

Each review round is tied to one head SHA. Findings have stable IDs, severity,
path/line when available, body, status, and disposition. The implementer may
mark `fixed` or `rejected` with evidence; only a fresh reviewer confirms
`resolved`. A changed head invalidates approval.

Verdicts are `approve`, `request_changes`, or `blocked`. Any blocker or
unresolved correctness finding yields `request_changes`. Reviewer failure,
timeout, or unavailable evidence yields `blocked`, never implicit approval.

## Completion audit

A fresh read-only auditor inspects the issue gates, child reports, diff, git
state, builds, reviews, source links, remaining TODO/proof debt, metrics, and
protocol incidents. It returns one of: stop; one concrete next action; at most
five bounded options; or a necessary user question. Its report does not mutate
state.
