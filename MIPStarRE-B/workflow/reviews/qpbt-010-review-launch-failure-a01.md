# QPBT-010 reviewer launch failure A01

- Session: `i010-reviewer-a01-reference-transport`
- Requested model: `gpt-5.6-sol`
- Endpoint origin: `https://api.finite-dimensional.space`
- Immutable base: `77aa1a4ac947c1632ea57262d29d2753ba163c8a`
- Immutable head: `cf43b33b5cd77cb005b90b02b6d369cfbd86d316`
- Started: `2026-08-30T18:20:21.442702Z`
- Ended: `2026-08-30T18:20:31.753190Z`
- Elapsed: 10.31035 seconds
- Outcome: failed before thread creation; no review verdict

The isolated review harness was created and its immutable target was resolved,
but Codex CLI 0.151.0 exited before opening a persistent thread or emitting a
JSONL event. Its only diagnostic was that the in-process app-server client
could not initialize on the read-only outer Codex home. The stderr digest is
`8e3330eeb312ddb37b9da73c3ece4a8aa7e2ade4b7bb255573aa487bc89f0f58`.
This is a byte-for-byte recurrence of `INC-010`; provider routing and
authentication were never reached.

This attempt confers no review evidence and has no external thread to archive.
The bounded retry uses approved host-level persistence for the wrapper while
retaining the nested Codex read-only sandbox, explicit provider routing,
ignored user configuration and repository rules, and immutable review target.
