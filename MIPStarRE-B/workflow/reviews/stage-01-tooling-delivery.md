# Stage 1 Tooling Delivery

- Session: `i001-tooling-a01-local-clis`
- Duration: approximately 27 minutes
- Child sessions: 1 read-only design auditor
- Tokens: unavailable from the collaboration backend

## Delivered

- `scripts/workflow.py`: locked atomic issue/PR/session/stage validation and
  mutation, dependency readiness, and event logging.
- `scripts/hot_main_cache.py`: exact-main cache identity, one-builder lock,
  detached build tree, atomic publication, and private reflink seeding.
- `scripts/local_agent.py`: stable aliases, trusted prompt composition,
  persistent Codex run/review JSON capture, token extraction, result envelopes,
  and archive by external ID.
- `scripts/check_workflow.py`: aggregate local workflow gate.
- focused unit tests for all three tools.

## Delivery checks

- 23 of 23 unit tests passed.
- Live `workflow.py validate` passed.
- Python compilation and script/test diff checks passed.
- Run and review dry-runs passed.
- No real Codex session or Lean build was invoked.

## Residual review target

Reviewer trust depends on launching from a trusted base checkout. The wrapper
records immutable base/head SHAs but cannot independently prove that a supplied
checkout's instruction files came from the base. The full stage review must
inspect this boundary and require the coordinator to prepare reviewer context
from a trusted base snapshot.
