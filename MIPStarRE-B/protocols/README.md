# Local Workflow Protocols

These protocols translate the current `LionSR/MIPStarRE` and TeXRA workflows
from GitHub automation into local, versioned operations.

| Concern | Local authority |
| --- | --- |
| Issues and sub-issues | `workflow/state/issues.json` |
| Pull requests and review threads | `workflow/state/prs.json` and review artifacts |
| Agent execution | named Codex sessions recorded in `workflow/state/sessions.json` |
| CI | scoped local checks followed by a full integration gate |
| Latest-main build artifact | locked hot-main cache under `.workflow-runtime/cache/` |
| Review bots | fresh read-only Codex reviewer sessions |
| Workflow telemetry | `research/metrics/` |

Read the protocols in this order:

1. [meta.md](meta.md): authority, invariants, and evidence-driven evolution.
2. [orchestration.md](orchestration.md): issues, PRs, agents, and session lifecycle.
3. [local-development.md](local-development.md): worktrees, builds, cache, and gates.
4. [formalization.md](formalization.md): paper, blueprint, Lean, and proof debt.
5. [review.md](review.md): independent review and finding disposition.

`AGENTS.md` is the concise executable constitution. These files provide the
operational detail. If they disagree, stop, open a workflow issue, and resolve
the conflict before implementation continues.
