# Research Record

This directory stores data suitable for a technical report on agent-assisted
formalization and workflow self-evolution.

Tracked metrics are compact summaries. Raw Codex events, full prompts, and build
logs stay under ignored `.workflow-runtime/` and are referenced by digest/path
when useful. Never store secrets or claim unavailable token data as zero.

- `metrics/sessions.jsonl`: one inspected record per issued agent attempt.
- `metrics/incidents.jsonl`: recurring failure classes and mitigations.
- `metrics/protocol_changes.jsonl`: evidence-to-protocol revision history.
- `report.md`: cumulative human-readable findings and stage table.

Canonical stage status remains in `workflow/state/stages.json`; the report
summarizes it without becoming a second mutable authority.
