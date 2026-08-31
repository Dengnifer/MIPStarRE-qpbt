# Protocol Changelog

## 0.1.6 candidate (QPBT-022) - 2026-08-31

The hot-main cache now derives its omitted runtime root from the primary
non-bare Git worktree. Linked issue worktrees consequently contend on one
filesystem lock and cannot duplicate a build for the same cache key. An
explicit `--runtime-dir` retains its prior absolute/relative path semantics;
the default skips prunable/unresolvable worktree records and fails closed with
an explicit override when the repository root or primary cannot be resolved. A
two-process linked-worktree regression exercises the election and records one
build with one waiter, while CLI regressions cover missing roots and resolution
failures. Canonical revision state and independent review remain with QPBT-022
integration.

## 0.1.5 - 2026-08-31

QPBT-019 adds a locked, capacity-aware dispatch boundary for local session
creation. The explicit `dispatch --capacity N` limit is compared with active
non-coordinator `issued`/`running` sessions; planned IDs are sorted and
reported across all backends in the selected local scope as dispatchable,
queued, or blocked after dependency, stage, and writable-path
checks. Capacity-only queueing issues the sorted available prefix atomically and
leaves the remainder planned; any blocked selected member leaves the requested
batch unchanged. Cross-candidate materialization checks apply to the admitted
prefix; queued rows are revalidated on a later attempt, while ownership checks
remain conservative across the selected set. `--dry-run` has no state effect.
The `backend_scope: all` value denotes one local-service ceiling: active counts
are summed across every backend and the explicit capacity is never multiplied
into per-backend quotas.
Unknown capacity now defers its rejection until dependency and writable-path
checks have produced deterministic diagnostics; the operation still fails closed
without changing state or events.
The stage `max_concurrency` counter remains an observed metric. Capacity does
not permit parallel Lean/Lake builds: callers still wait for the singleton
hot-main cache builder. The four-slot collaboration ceiling is recorded only as
the current environment observation, never as a hard-coded default.

Focused dispatch regressions cover explicit/unknown capacity, coordinator
exclusion, deterministic queue and block reasons, cross-candidate validation,
ownership conflicts, dry-run behavior, and atomic event/state updates.
The legacy `issue-session` command now routes through the same planner and
requires an explicit capacity, so authority-changing additions cannot bypass
dependency, ownership, or admission checks; successful calls retain the
historical issued-record JSON shape while queued/blocked calls return the
planner envelope. Admission reserves one orchestrator slot per issue (planned
or active duplicates are blocked), and mixed single-record/keyed override
objects are rejected.
The writer snapshots the sessions bytes and event offset and rolls both back
when an event append or post-append audit fails; crash-recovery journaling is
deferred to QPBT-020.

## 0.1.4 - 2026-08-31

The first full-tree staging attempt after A14's approval failed
`git diff --cached --check`: fourteen new files ended with an extra blank line.
The frozen `git diff --check` result was truthful but incomplete because an
unborn repository exposes no unstaged diff for untracked files.

Bootstrap core text hygiene now rejects a final empty logical line and records
`blank_line_at_eof_paths` alongside the existing trailing-whitespace and ASCII
checks. A focused regression covers `text\n\n`; the fourteen reported files
were changed by exactly one final LF each. An independent reviewer verified
those byte deltas against the prior frozen hashes and found no terminal-evidence
or unrelated edits. Focused tests pass 9/9, the aggregate gate passes 83/83,
and a disposable full-tree index passes `git diff --cached --check` while the
real bootstrap index remains empty.

## 0.1.3 - 2026-08-31

A12 proved that the nested Codex session and custom-provider boundary now work:
the isolated reviewer completed in 80.313 seconds and returned valid structured
evidence. It nevertheless blocked because its launch snapshot necessarily showed
its own session as nonterminal and the bootstrap seal as null. Both fields can
only be completed after the reviewer returns, so asking for them beforehand made
the acceptance gate circular.

Bootstrap reviews now pass an exact frozen-core digest through a dedicated,
validated phase contract. Fixed trusted text distinguishes review of that core
from the narrow lifecycle/report/seal evidence populated after return. The
launcher accepts this mode only for an unborn uncommitted repository, verifies
the unsealed Stage 1 manifest and exact terminal allowlist, rejects noncanonical
trusted phase fields, and never imports manifest prose as authority.

Independent review then found and closed two further safety defects: helper-level
callers could add keys to the trusted phase mapping, and source contents could
change between initial verification and evidence capture. The final launcher
canonicalizes the phase record and, after capture, reverifies the freeze,
byte-matches the copied manifest, and binds every captured core path and hash to
the frozen manifest before prompt construction or model dispatch. Focused tests
pass 30/30, the aggregate gate passes 82/82, and fresh re-review approved with no
findings.

## 0.1.2 - 2026-08-31

Compact A10 ruled out request-envelope size as the root transport cause. The
installed CLI documents that `--ignore-user-config` disables the entire user
configuration, not only instructions. That erased the custom provider URL,
Responses wire setting, and `requires_openai_auth` mapping used by the
successful health probe.

Nested reviewers now keep `--ignore-user-config`, `--ignore-rules`, read-only
sandboxing, and the isolated evidence harness, while receiving an explicit
all-or-none non-secret transport profile before `exec`. The wrapper validates
the provider config key, display name, HTTPS base URL, exact `responses` API,
and auth-mode boolean. URLs with credentials, userinfo, queries, fragments, or
non-HTTPS schemes fail closed. Authentication values remain in Codex's auth
store and are never accepted, read, copied, or recorded by the wrapper.

An empty-repository control first reached the authorized endpoint and returned
the expected 401 without the auth mapping. Adding only
`requires_openai_auth=true` then returned the exact requested response in
15.787 seconds. Focused tests pass 26/26, the aggregate gate passes 78/78, and a
fresh read-only child reviewer approved with no findings.

## 0.1.1 - 2026-08-30

Two full frozen-review attempts reached their wall-clock bounds without model
work even though the exact endpoint and model completed a tiny health probe.
The second failed packet was 36,041 bytes and redundantly inlined every
untracked manifest entry. Frozen prompts now carry only a fixed-shape target
summary, the exact manifest-file digest, and its logical digest. The full
manifest remains in the isolated harness and result envelope and is reverified
immediately before dispatch. Prompt byte length is recorded, and regression
tests require prompt growth to be independent of manifest cardinality.

Endpoint liveness and local packet-size construction are separate gates. Files
already present in frozen evidence are inspected there rather than copied into
caller context. The current packet is about 4,136 bytes before task-specific
text, down from 36,041 bytes for A08.

The user also closed the Stage 1 scope: after an acceptance gate passes, only a
failed acceptance test, concrete safety issue, or direct user requirement may
change that stage. Every other improvement is deferred to a numbered issue.

## 0.1.0 - 2026-08-30

Initial local-first protocol, derived from:

- `LionSR/MIPStarRE` at `507e81220d95266ff3d589d125b2f87c7300a9fb`;
- `LionSR/TeXRA` at `039757e8b076ac6bf43c5b7623b61cd8543d7b64`;
- the initial QPBT source audit of arXiv:2001.04383v3.

It replaces GitHub state with versioned issue/PR/session records, GitHub Actions
artifacts with a locked atomic hot-main cache, and mention-triggered review bots
with fresh read-only local Codex reviewers. It adds explicit session lineage,
honest token-availability fields, cache timing, incident classes, and the
third-occurrence evolution trigger that the source workflows lacked as a single
research ledger.

Adversarial bootstrap review hardened the initial revision before its first
commit. The cache now binds its canonical recipe, rechecks source state, and
deeply verifies artifact inventories before seeding. Review targets and trusted
authority are isolated and content-addressed. State transitions enforce
immutable session authority, SHA-bound PR evidence, independent reviewers,
fresh finding resolution, worktree-aware ownership, and formalization
orchestrators. Canonical events are chronological and reconciled with session
lifecycle, and the aggregate gate reconciles incidents, protocol changes, and
terminal-session metrics. `protocols.json` itself now participates in canonical
state validation. A failed real-review preflight further separated host-level
Codex session persistence from the reviewer model sandbox: the host wrapper may
need approved filesystem access, while the nested reviewer remains read-only in
an isolated evidence repository. A subsequent host-enabled review stalled for
more than 21 minutes without exposing intermediate events, which added a
bounded, interrupt-safe reviewer timeout and structured partial-result evidence
to the bootstrap hardening scope. The same boundary was applied to execution,
archive, and capability probes. A later 503 during an agent's final report was
recovered by a no-edit report-only retry under the same session identity.
The first subsequent external reviewer launch was rejected before execution,
which made disclosure consent an explicit precondition: sending a frozen local
repository snapshot to the Codex service requires separate user authorization,
and a rejected launch receives a terminal alias rather than a workaround.
The user subsequently authorized `gpt-5.6-sol` at
`https://api.finite-dimensional.space`; the non-secret endpoint/model/wire
profile and evidence scope are now bound into the review record.
The first authorized attempt then exposed endpoint transport failure rather
than a review finding: WebSocket and HTTPS requests both failed for 900 seconds.
The protocol now requires a minimal successful endpoint/model health prompt
before another full frozen-evidence attempt.
The first such probe selected plain `/tmp` and was rejected locally by Codex's
Git trust check. Repository-free health probes now use a disposable empty Git
repository rather than disabling that check.
The corrected empty-repository probe returned the exact requested response in
15.196 seconds with complete usage evidence and archived successfully, clearing
the endpoint-health gate for the next frozen review.

Revision 0.1.0 is re-evaluated after three completed issue workflows and must be
superseded if it permits duplicate main builds, overlapping writable ownership,
or review state that cannot be tied to an immutable SHA or bootstrap manifest.
## 2026-08-31

- Added issued-session launch leases with locked authority checks, exactly-once
  terminal envelope imports, and explicit idempotent interruption recovery.
- Remediated the initial candidate after pre-review: governed exec and review
  now bind complete authority, all post-claim failures terminate the lease,
  imports and recovery are byte-idempotent under the real WorkflowStore, and
  archive retries cannot silently invoke Codex again.
- Hardened the lease boundary after independent review: claims now verify the
  live clean Git `HEAD` and tree against the issued base, lifecycle rollback
  covers interrupts, terminal paths are normalized and bound to the issued
  result envelope, and recovery emits archiveable evidence with exact-once
  reuse.
- Hardened runtime publication after LPR-009: Git claim/status probes isolate
  inherited configuration and disable repository hooks/fsmonitor; governed
  terminal imports transactionally publish or roll back their result artifact;
  archive aliases use no-follow runtime confinement, strict envelope reuse,
  atomic directory publication, interruption cleanup, and same-alias locking.
- Closed the remaining launch/archive race window after immutable review:
  governed exec/review repeat canonical worktree identity checks immediately
  before child spawn, and archive retries verify stdout/stderr byte counts and
  SHA-256 digests against the recorded log files before reusing an envelope.
