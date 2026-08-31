# Reference Workflow Provenance

Audited on 2026-08-30. Git smart transport hung in this environment; commit
metadata came from the GitHub REST API and source snapshots from codeload.

## LionSR/MIPStarRE

- Repository: https://github.com/LionSR/MIPStarRE
- Default branch: `main`
- Commit: `507e81220d95266ff3d589d125b2f87c7300a9fb`
- Commit date: 2026-08-25
- Local audit snapshot:
  `/tmp/mipstarre-audit.PFk6yl/MIPStarRE-507e81220d95266ff3d589d125b2f87c7300a9fb`

Highest-signal sources were `AGENTS.md`, `docs/CONTRIBUTING.md`,
`docs/{formalization-patterns,anti_patterns,proof_frontier_review,ci-automation,pr_review_management}.md`,
`docs/paper-gaps/`, `.githooks/`, `.github/prompts/`, and
`.github/workflows/{pr-ci,pr-review,issue-automation}.yml`.

Reused principles: paper-first statement integrity, explicit proof-debt policy,
dependency-ordered proof work, blueprint synchronization, local fast gates,
review after build, serialized fixed-point loops, and main-only build caching.

The machine-readable project pins at this snapshot are Lean and Mathlib 4.32.0.
The prose agent files still report 4.31.0, which is recorded as `INC-004`.

## LionSR/TeXRA

- Repository: https://github.com/LionSR/TeXRA
- Default branch: `main`
- Commit: `039757e8b076ac6bf43c5b7623b61cd8543d7b64`
- Commit timestamp: 2026-08-29T22:36:49Z
- Local audit snapshot:
  `/tmp/texra-audit.btCapR/TeXRA-039757e8b076ac6bf43c5b7623b61cd8543d7b64`

Highest-signal sources were `prompts/README.md`,
`prompts/agents/remote/Lean4/{leanOrchestrator,lean,leanSearch,leanBlueprint,leanSimplifier}.yaml`,
`prompts/agents/remote/progressCheck.yaml`,
`packages/extension/resources/tool_use_agents/{prover,codeReviewer,changeReviewer,codeSimplifier}.yaml`,
`.github/prompts/{issue-tree,issue-tracker,texra-code-review}.md`, and the local
review skill/checklist.

Reused principles: bounded self-contained delegation, deterministic fan-out
only for known-independent work, separate planned and issued attempts, stable
session lineage, fresh read-only completion audit, high-bar issue creation,
third-occurrence abstraction, adversarial simplification review, and explicit
concurrency/idempotence guards.

## Codex CLI command authority

- Installed runtime: `codex-cli 0.151.0`
- Official command reference:
  https://developers.openai.com/codex/cli/reference
- Local authorities inspected: `codex exec review --help` and
  `codex archive --help`

The official reference documents native review selectors and a custom prompt
as conflicting. The installed help lists those surfaces without stating the
conflict. This discrepancy is `INC-006`: review automation records the exact
runtime capability and uses an isolated generic review packet whenever native
target selection cannot coexist with external trusted reviewer instructions.

## QPBT source

- Paper: *MIP* = RE*, arXiv:2001.04383v3, revised 2022-11-04
- Abstract page: https://arxiv.org/abs/2001.04383v3
- Source archive acquired for local processing:
  `/tmp/2001.04383v3-source.tar`
- Archive SHA-256:
  `d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`
- Extracted primary TeX:
  `/tmp/2001.04383v3-source/compression_arXiv_v3.tex`

Section 7.3 defines the test and states completeness/soundness; Appendix A gives
the soundness analysis. The exact split manifest and dependency map are stage
two outputs. Version 3 is mandatory because version 1 has a materially obsolete
parameter tuple.
