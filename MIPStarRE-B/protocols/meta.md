# Meta-Protocol

## Authorities

The root coordinator owns scheduling and canonical state. An issue orchestrator
owns delivery for one issue. A role agent owns only the explicitly delegated
surface. A reviewer owns findings but never the implementation. Deterministic
tools own mechanical validation and state invariants.

Authority is narrow:

- The paper owns mathematical claims.
- The blueprint owns the planned declaration and dependency graph.
- Lean owns what has actually type-checked.
- The issue tree owns work status and dependency readiness.
- The PR list owns integration and review status.
- Session records own execution evidence; plan rows do not prove execution.

Only the root coordinator edits canonical state and aggregate metrics. Agents
write result envelopes and logs beneath `.workflow-runtime/runs/`; the
coordinator inspects and imports them. This prevents concurrent JSON updates and
keeps raw prompts or transcripts out of version control.

## Required invariants

1. Every non-tracking issue has one acceptance-gate list and an unambiguous
   deliverable.
2. Parent edges describe grouping; dependency edges describe order. Neither may
   contain a cycle.
3. Every issued implementation session names one issue, role, attempt, parent,
   base revision, owned paths, and validation command.
4. At most one writable owner exists for a path at a time.
5. A local PR has immutable reviewed base/head SHAs. A head change invalidates
   approval and requires a new review round.
6. Validation precedes model review. The implementer cannot self-approve.
7. Main cache publication is atomic and has one elected builder per key.
8. A source-labelled theorem is never made easier by smuggling proof debt into
   its assumptions.
9. Metrics distinguish unavailable data from zero.
10. A completed or archived label is applied only after artifacts and outcome
    are inspected.

Run `python3 scripts/workflow.py validate` after every canonical state change.
Validation failure freezes dispatch and integration until repaired.

## Stage closure discipline

Once a stage reaches its acceptance-gate pass, change its delivered surface
only when an acceptance test requires the change, a concrete safety issue
requires it, or the user directly requires it. Defer every other improvement to
a numbered issue in a later stage. Do not keep an accepted stage open for
speculative hardening, cleanup, or convenience work.

## Unborn-repository bootstrap review

The first commit has no base SHA and cannot satisfy the ordinary immutable
base/head review contract. This is the only exception:

1. Finish all intended stage-one files and deterministic checks.
2. Run `python3 scripts/bootstrap_manifest.py freeze` to generate
   `workflow/reviews/bootstrap-stage-01.manifest.json` with the sorted reviewed
   path list, SHA-256 for every file, aggregate snapshot digest, fixed check
   commands/results, and creation time.
3. Stop all writers to reviewed paths. The coordinator may update only the
   manifest's enumerated terminal-evidence files after review; any core edit or
   added core file invalidates the review.
4. Give a fresh read-only reviewer the manifest and require it to recompute all
   file hashes before review. Its report names the manifest digest.
5. Import the result, finish lifecycle evidence, and run
   `bootstrap_manifest.py seal` with the reviewer session, report, and named
   digest. Sealing requires an explicit `approve` verdict and binds the final
   terminal files. Run `bootstrap_manifest.py verify --sealed` immediately
   before the first commit; any mismatch requires a new freeze and review.

After the first commit, all reviews use immutable Git base/head SHAs. This
bootstrap exception cannot be reused.

## Evolution loop

The protocol is expected to evolve, but only from evidence:

1. Record an incident or repeated pattern with stage, issue, session, command,
   outcome, and current protocol revision.
2. On the third occurrence in one failure class, open a workflow issue. Earlier
   intervention is allowed for soundness, data loss, or severe cost.
3. Identify the smallest rule, check, or tool change that addresses the root
   cause. Avoid a second mechanism beside an existing authority.
4. Add or update a durable boundary test when the change is mechanical.
5. Run an adversarial read-only review against the motivating incidents and
   likely counterexamples.
6. Update `protocols/CHANGELOG.md` and the protocol-change metric with before and
   after revisions, evidence, expected effect, and retirement condition.
7. Re-evaluate after three uses. Remove machinery that creates more follow-up
   work than it retires.

Recurring proof or tactic shapes use the same third-occurrence trigger: extract
the lowest sufficient helper only after the pattern is real, then rewrite the
motivating sites and record the new project-native vocabulary.

## Stop conditions

Pause new implementation dispatch when any of the following is true:

- canonical state is invalid or two sessions claim the same writable surface;
- the reference statement/version is unresolved;
- a reviewed theorem has source-statement drift;
- the hot-main cache has a failed or unverified publication;
- a workflow bug causes unbounded retries, duplicate compilations, or duplicate
  session fan-out;
- active machinery opens more follow-up issues than it closes.

The coordinator resolves the authority problem first, records the incident,
and resumes only with an explicit next action.
