# Stage 1 Review Payload Fix

- Fixer: `i001-fixer-a05-review-payload`
- Independent reviewer: `i001-reviewer-a09-compact-prompt`
- Issue: `QPBT-001`
- Trigger: `INC-016`
- Backend: Codex collaboration sessions

The frozen review prompt now replaces the redundant inline per-file manifest
with a fixed-shape reference containing the manifest path, exact file-byte
SHA-256, logical canonical SHA-256, selectors, revisions, status binding, and
entry counters. The full manifest remains in `evidence/manifest.json` and in
the result envelope. Immediately before dispatch, the wrapper re-reads the
manifest and verifies its exact bytes, parsed value, and logical digest.

For the current Stage 1 snapshot, a dry run reduced the trusted prompt from
36,041 to 4,136 UTF-8 bytes while retaining the full 12,341-byte, 58-entry
manifest outside the prompt. The result envelope now records `prompt_bytes`.

The reviewer requested exact on-disk binding, unambiguous digest semantics,
fixed counters, strict manifest kinds, and recorded prompt bytes; all were
accepted. Exhaustive validation of every generated field and an arbitrary
global prompt-size cap were deferred because they are not required to close the
Stage 1 acceptance failure. The final review reported no remaining blocker.

Validation:

- focused local-agent tests: 23/23 passed;
- aggregate tooling tests: 75/75 passed;
- Python compilation: passed;
- whitespace check: passed.

The collaboration backend did not expose per-session token usage. One child
reviewer was used. Exact elapsed time was not exposed, so the session ledger
records the coordinator-observed parent window.
