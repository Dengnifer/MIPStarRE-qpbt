# Stage 1 Protocol Review, Round 1

- Session: `i001-reviewer-a01-protocol-state`
- Backend: Codex collaboration agent
- Duration: 311 seconds
- Subagents: 0
- Tokens: unavailable from the collaboration backend
- Verdict: blocked

This review covered the policy/state surface before tooling completion. The
repository had no `HEAD`, reviewed files were untracked, and state changed while
review was running. It therefore could not grant durable approval.

## Findings

1. **Blocker:** define a one-time bootstrap review based on a frozen path/hash
   manifest, recompute it before commit, and re-review that exact snapshot.
2. **High:** active writable sessions must record base revision or null reason,
   worktree, owned paths, validation command, and result-envelope path.
3. **High:** ignore fetched and split author TeX by default; commit only
   fetch/verify/split tooling, manifests, source maps, and rights metadata until
   compatible redistribution permission is recorded.
4. **High:** persist the QPBT dependency/discrepancy audit rather than relying on
   `/tmp`, and attach a concrete issue for source-facing decisions.
5. **Medium:** the fourth Git-transport hang crossed the third-occurrence trigger;
   open a workflow issue and give protocol revision 0.1.0 a reevaluation or
   retirement criterion.
6. **Medium:** record the early QPBT source scout as stage-one preflight rather
   than dispatching the dependency-blocked stage-two issue.
7. **Medium:** emit `session.finished` or `session.failed` before archive events.

All seven findings must be addressed before the frozen-snapshot review.
