# Stage 1 Isolated Provider Probes

Both probes used an empty disposable Git repository, `gpt-5.6-sol`, a read-only
sandbox, `--ignore-user-config`, `--ignore-rules`, and explicit non-secret
provider routing. They transmitted no QPBT repository contents and used
`--ephemeral`, so no persistent CLI session remained to archive.

## A03: routing without auth mapping

- Session: `i001-scout-a03-isolated-provider`
- External ephemeral thread: `01a0536d-93dc-7801-99d2-707089431a7f`
- Measured command time: 8.200177849 seconds
- Outcome: expected diagnostic failure

Explicit provider name, base URL, and Responses wire API reached
`https://api.finite-dimensional.space/responses` immediately. The endpoint
returned `401 API_KEY_REQUIRED`. No credential was read or recorded. This
showed that `--ignore-user-config` also removed the non-secret
`requires_openai_auth` provider mapping needed to load existing Codex auth.

## A04: complete non-secret transport profile

- Session: `i001-scout-a04-isolated-provider`
- External ephemeral thread: `01a0536e-7396-7cb0-afe9-1100813f8a61`
- Measured command time: 15.787069467 seconds
- Usage: 15,166 input, 11 output, 15,177 total, 3,840 cached input
- Outcome: passed

Adding only `requires_openai_auth=true` returned exactly:

```json
{"isolated_provider":"ok"}
```

The successful control proves that instruction/config isolation and the custom
authorized provider can coexist. Authentication values stayed implicit in
Codex's auth store and did not enter argv, prompts, output, or committed state.
