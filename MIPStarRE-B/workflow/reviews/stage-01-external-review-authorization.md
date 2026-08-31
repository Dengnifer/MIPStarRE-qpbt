# Stage 1 External Review Authorization

- Authorized at: `2026-08-30T22:28:18+08:00`
- User statement: `use the gpt 5.6 sol provided by endpoint https://api.finite-dimensional.space`
- Endpoint origin: `https://api.finite-dimensional.space`
- Model: `gpt-5.6-sol`
- Wire protocol: Responses API
- Local provider label: `OpenAI`
- Credential recording: prohibited; no API key is stored here

This authorization permits the local Codex CLI reviewer to send the frozen
Stage 1 evidence it reads to the named endpoint for model inference. The
isolated reviewer remains locally read-only. Ignored author-source payloads,
runtime files, and credentials are outside the frozen evidence and must not be
transmitted by the review harness.

The authorization does not retroactively approve A06, which never launched.
The corrected core must be frozen again and reviewed under a fresh alias with
the endpoint and model recorded in its terminal evidence.
