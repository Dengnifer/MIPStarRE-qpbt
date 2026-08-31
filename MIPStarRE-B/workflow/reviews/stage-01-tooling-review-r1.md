# Stage 1 Tooling Review, Round 1

- Session: `i001-reviewer-a02-tooling-code`
- Reviewer: fresh read-only Codex collaboration agent
- Duration: 428 seconds
- Subagents: 0
- Tokens: unavailable from the collaboration backend
- Verdict: blocked pending tooling corrections

## Findings

1. Blocker: review selectors and target SHAs were described in prose but not
   enforced by the native `codex exec review` command or deterministic Git
   preflights.
2. Blocker: reviewer authority was loaded from the mutable checkout under
   review, so a change to `AGENTS.md` or the reviewer persona could influence
   its own review.
3. Blocker: shallow lifecycle validation allowed approval, merge, or completion
   claims without immutable review and validation evidence.
4. High: writable ownership and the one-orchestrator-per-issue rule were stated
   in protocol but not enforced by canonical-state validation.
5. High: the hot-main cache key omitted the accepted build recipe, allowing an
   arbitrary successful command to publish a canonical-looking artifact.
6. High: `seed --replace` resolved its target before detecting symlinks and
   could permanently remove an unrelated `.lake` directory without verifying
   that the target was an eligible issue worktree.

## Required disposition

The review harness must bind immutable targets and trusted base authority; the
state engine must enforce evidence, ownership, and transition gates; and the
cache must bind a canonical recipe, recheck inputs, validate seed targets, and
provide rollback. Each correction requires focused regression tests, followed
by a new review of the frozen bootstrap snapshot.

## Residual scope

No real Codex CLI review or Lean build was launched in this round. The reviewer
assessed the scripts, tests, protocol contracts, current Codex CLI help, and the
fake-repository cache tests without changing files.
