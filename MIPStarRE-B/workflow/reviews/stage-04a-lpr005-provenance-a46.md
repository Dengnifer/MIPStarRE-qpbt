# LPR-005 provenance audit (i000-scout-a46-lpr005-provenance)

Verdict: **blocked for the requested first-parent/base contract; no-go for a metadata-only repair.** This was a read-only provenance audit. I did not edit repository files, workflow state/events, PR or issue ledgers, metrics, worktrees, or runtime/build output. No endpoint, network, Lean/Lake, build, or child-agent command was run. Token usage is unavailable.

## Frozen records and Git evidence

The LPR-005 record at `workflow/state/prs.json:1383-1392,1498-1556` is `status: merged`, `base_sha=77aa1a4ac947c1632ea57262d29d2753ba163c8a`, `head_sha=4de452495228aad3debe05f166097e746b97b2e5`, and `integration_sha=687e182c7ad41520c226a59160c084ab53ad6f38`. Its checks and approving review `review-qpbt-004-a35-package-immutable` are bound to base `77aa...` and head `4de452...`; findings F-LPR005-001 and F-LPR005-002 are resolved on that same evidence pair.

Exact commit facts (`git show -s --format='%H%n%P%n%T%n%s'`):

| object | first parent | tree | subject |
| --- | --- | --- | --- |
| `77aa1a4ac947c1632ea57262d29d2753ba163c8a` | none | `8d2400f86347395a80388a9600db4cc72a878ebb` | establish local QPBT formalization protocol |
| `b92935e98b1d631b88065c2b6887451c6ae416d4` | `77aa1a4ac947c1632ea57262d29d2753ba163c8a` | `a0380cceca1d5dd43d08a67483724188b566dadb` | materialize pinned project foundation |
| `4de452495228aad3debe05f166097e746b97b2e5` | `b92935e98b1d631b88065c2b6887451c6ae416d4` | `5b43ca5c46120ebc1de3e005af3ea11cd439f4cf` | bind package verification and lock incarnation |
| `687e182c7ad41520c226a59160c084ab53ad6f38` | `d319902f6a918c0f7aaac393f73b85c672c4d446` | `8b8e6db14eca531f6319012dbd145c02252da1fa` | materialize pinned project foundation |
| `7526e58663f4a93c6643d936cb6cedb8df6e090b` | `5d36cdf10cbb936c234bab96a21cf7aa9b21f9b6` | `e45a463ae0a58f8faf4c3d10329a6f68b08b19e2` | record frontier gate audit |

Git confirms all of `77aa` -> `b929` -> `4de` is one ancestry path:

```text
git merge-base --is-ancestor 77aa... 4de...  # exit 0
git merge-base --is-ancestor b929... 4de...  # exit 0
git merge-base 77aa... 4de...                # 77aa...
git log --ancestry-path 77aa... ..4de...      # b929..., 4de...
```

Thus there is no Git contradiction in recording `77aa` as the PR baseline: it is the original base and an ancestor. The final fix's *first parent* is nevertheless `b929`, because the foundation commit was created first and the cache/lock fix was committed on top of it. The full base-to-head delta creates 15 paths (including the foundation files); the immediate `b929..4de` delta is only five paths: `scripts/hot_main_cache.py`, `scripts/materialize_lake_packages.py`, their two tests, and `workflow/reviews/qpbt-004-formal-immutable-a32.md`.

`687e` is not the approved head replayed on top of `77aa`: it has unrelated first parent `d319902...` and tree `8b8e6d...`. It is an alternate integration object. Current main `7526` has tree `e45a46...`; `git merge-base --is-ancestor 687e... 7526...` exits 0, while `git merge-base --is-ancestor 4de... 7526...` exits 1. Neither `git diff --quiet 4de... 7526...` nor `git diff --quiet 687e... 7526...` is clean. Therefore current-main bytes cannot be represented as the approved `4de` head merely by relying on the recorded integration SHA.

## Launcher and validator semantics

`scripts/local_agent.py:2584-2601` implements a `target_kind=base` review. It requires full immutable base/head SHAs, source `HEAD == head_sha`, a clean tree, and only that base is an ancestor of head. In that mode the harness deliberately uses `base_sha` as the trusted parent and the exact head tree (`scripts/local_agent.py:2176-2184,2214-2237`). Consequently an exact **base-target** review of tree `4de` with base `77aa` is mechanically possible despite the intermediate `b929` commit.

`scripts/local_agent.py:2602-2634` implements a `target_kind=commit` review. When `--base-sha` is supplied it resolves `head^1` and fails unless it equals the declared base, with `--base-sha does not match the commit target's first parent`. A commit-target review of `4de` with base `77aa` therefore fails by design. This is the explicit contract used by the prior endpoint preflight, which required first parent/base equality.

`scripts/workflow.py:640-734` binds every check, review, finding, and resolution to the PR's exact `base_sha`/`head_sha`, requires passed current checks and a current approving review for `merged`, and shape-validates `integration_sha`. It does **not** verify that integration is a descendant of head, that integration's tree equals head's tree, or that `head^1 == base_sha`. The validator currently passes (`python3 scripts/workflow.py validate`, valid=true, 24 issues, 11 PRs, 249 issued sessions, 7 stages), but that pass cannot establish the missing Git identity.

## Remediation decision

Changing only canonical metadata is unsafe and insufficient. It would either (a) change immutable evidence fields away from the bytes actually reviewed, (b) claim that `687e` or current main is `4de` despite different commit/tree identity, or (c) make the old merged record internally misleading. Existing checks/review/finding records are immutable evidence for exactly `base=77aa`, `head=4de`; they cannot be transferred to a new head.

For a new first-parent-compliant attempt, the minimum exact record values are:

```text
base_sha: 77aa1a4ac947c1632ea57262d29d2753ba163c8a
head_sha: <new 40-hex commit; must have ^1 == 77aa1a4...>
head_tree: <new commit's exact ^{tree}; expected 5b43ca5... only after byte-identical replay>
integration_sha: <actual integration commit, full 40-hex, verified descendant of new head>
```

Each new check record must carry that exact `base_sha` and `head_sha`, `status: passed`, its command, completion timestamp, and an immutable result path. A new review record must carry the same pair, a fresh independent reviewer session and external identity, `verdict: approve` (or the observed blocking/request-changes verdict), start/completion timestamps after those checks, result path, and exact finding IDs. Any finding introduced on the new head needs a later resolution review on the same new pair; none of the existing `review-qpbt-004-a35-package-immutable` evidence is valid for a different `head_sha`.

There are two legitimate paths, with different contracts:

1. If the protocol permits a **base-target** review, provision a clean checkout at `HEAD=4de` and rerun all required checks plus a fresh independent review with exact records `base_sha=77aa`, `head_sha=4de`, and `head_tree=5b43ca...`. This uses the ancestor semantics already implemented by the launcher and preserves the existing two-commit history.
2. If the gate requires **first parent == base**, replay/squash the complete path-creating foundation and fix into a new commit whose first parent is exactly `77aa`. The resulting `head_sha` is necessarily new (the expected tree is `5b43ca...` only if the replay reproduces `4de` byte-for-byte; record the actual computed tree). Rerun package, cache, aggregate, and hygiene checks and create a fresh independent review. Every new check/review/finding/resolution record must carry that new full `base_sha`, `head_sha`, and result path; a merged integration record must use the actual integration commit and retain a verifiable descendant/tree relation as an additional coordinator check.

Because LPR-005 is already `merged`, do not mutate its canonical record to simulate either path. The safe coordinator action is a disposable read-only replay/provenance check first, followed by a new PR/attempt (or an explicitly governed superseding record) with newly issued evidence. Any mutation of `workflow/state/prs.json`, issues, sessions, events, or metrics is outside this scout's authorization.

## Checks and timing

- Exact object/type/tree/parent checks: passed; all five named objects resolve as commits.
- Ancestry checks: `77aa -> 4de` exit 0; `b929 -> 4de` exit 0; `4de -> 7526` exit 1; `687e -> 7526` exit 0.
- Changed-path comparisons: full `77aa..4de` delta has 15 paths; `b929..4de` has the five paths listed above; `4de..687e` differs in eight workflow/orchestration paths and tests.
- `python3 scripts/workflow.py validate`: passed, elapsed about 0.14 s.
- `git diff --check`: passed for the current checkout; current worktree's pre-existing modifications are `workflow/events.jsonl`, `workflow/state/issues.json`, and `workflow/state/sessions.json` and were not touched.
- No endpoint/network/Lean/Lake/build or state mutation. Elapsed time for this bounded audit was under five minutes; token usage is unavailable.
