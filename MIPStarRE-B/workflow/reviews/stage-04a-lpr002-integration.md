# LPR-002 Integration Audit

Read-only auditor session: `i000-auditor-a37-lpr002-integration`.
Current main base: `920e53e8bf978951fff631cc9b3c228d05bc1312`, tree
`1225068284e7f5cee0a6ebbbba67e9cc9bb470dd`, parent
`e2446272a3cc904a612d7e0e5003074ef4a680ad`.

## Candidate identity

LPR-002 (`QPBT-002`) is approved at immutable head
`63037ddceada7a88436f9afa9ed1ef4d74319098`, tree
`2a357e125aaab5b078b5ffd77bf0b1e395f8f1a4`, parent
`7f4a65e03d0386df28c320f0c5235de21efb5f31`. Its declared base is the
approved LPR-001 head `e93d949d06af2a7f4407d198a37aad315deac6aa`; therefore it
must be replayed only after LPR-001 is integrated or otherwise materialized at
that exact content. LPR-002 is not an ancestor of current main.

Changed paths are exactly:

```text
references/2001.04383v3/QPBT_SOURCE_MAP.md
references/2001.04383v3/RIGHTS.md
references/2001.04383v3/source-pin.json
references/2001.04383v3/split-manifest.json
scripts/reference_source.py
tests/test_reference_source.py
workflow/reviews/qpbt-002-reference-split.md
```

The current main already contains the first-commit stub
`references/2001.04383v3/QPBT_SOURCE_MAP.md`; its current blob is identical to
the `77aa1a4...` base blob. The candidate changes that file by adding the local
source layout and exact collection contracts. `git merge-tree` with base
`77aa1a4...`, current `920e53e...`, and candidate `63037dd...` reports
`merged`, with no conflict markers. The remaining six paths are additions and
are absent from current main (`scripts/reference_source.py`, its tests,
`RIGHTS.md`, `source-pin.json`, `split-manifest.json`, and the review record).

## Safe replay

1. Integrate LPR-001 head `e93d949...` first, preserving current main's
   workflow/parallelism commits.
2. Replay LPR-002 head `63037dd...` on that resulting tree. Keep the candidate
   `QPBT_SOURCE_MAP.md` blob, since the only current-main overlap is the
   unchanged first-commit stub and the three-way merge is clean.
3. Inspect the seven-path result, verify no generated author-owned source bytes
   are tracked, and freeze the resulting SHA before review/ledger transition.
4. Apply the approved blueprint head LPR-004 (`3f4d4b3...`) afterward; its
   `blueprint/` path set is disjoint from LPR-002. This completes the source +
   blueprint portion of the required second-main-commit milestone.

No temporary replay worktree was created, so no writable state was changed.
The read-only three-way merge simulation is sufficient to establish zero
conflicts; the coordinator should still perform the actual replay in a fresh
owned integration worktree and inspect its diff before fast-forwarding main.

## Exact acceptance gates

The candidate's immutable checks, all passed at the frozen head, are:

- `python3 -m unittest discover -s tests -p 'test_reference_transport.py' -v`
- `python3 -m unittest discover -s tests -p 'test_reference_source.py' -v`
- `python3 scripts/check_workflow.py`
- exact archive inspection and isolated materialization of the 233,859-byte
  pinned archive, yielding 39 inventory files, 646 labels, and inventory
  SHA-256 `04548808c30c476e9b2b7cb2f728a6d0c348a6706a8ed1bc9fb9945f20a124f4`
- candidate manifest/diff binding and `git diff --check`

The isolated source input is `/tmp/2001.04383v3-source.tar` with archive SHA
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`;
the pinned TeX and BBL member hashes are recorded in
`references/2001.04383v3/source-pin.json`. After replay, rerun the exact
transport/source suites, aggregate workflow gate, compileall, workflow
validation, and diff hygiene against the new current-main base. Then rerun
the blueprint source-root check against the same generated inventory before
integrating LPR-004. The source archive and generated sections remain ignored
under `RIGHTS.md`; only manifests, checksums, maps, and tooling are tracked.

## Dependencies and residual blockers

`QPBT-010`/LPR-001 is currently `ready` rather than integrated, so QPBT-002's
issue status remains `blocked` despite LPR-002's approval. QPBT-003 remains
blocked until LPR-001, LPR-002, QPBT-012's existing ancestor, and LPR-004 are
reconciled and the second-main-commit combined source/blueprint/PDF/workflow
gates pass. QPBT-004 and all Lean implementation lanes remain non-dispatchable
until that milestone and its fresh cache acceptance complete.

No source/state edits, build, Lean, Lake, network, or cache command occurred.
Audit elapsed approximately 5 minutes (`2026-08-31T09:31Z` to
`09:36Z`); subagents 0; token usage unavailable and not estimated.
