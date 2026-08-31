# Stage 04A LPR-004 Integration Compatibility Audit

Logical session: `i000-auditor-a38-lpr004-integration`
Audited main: `920e53e8bf978951fff631cc9b3c228d05bc1312`
Candidate: LPR-004, base `77aa1a4ac947c1632ea57262d29d2753ba163c8a`, head
`3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd`.

## Identity and working-tree evidence

The exact object evidence is:

```
main       920e53e8bf978951fff631cc9b3c228d05bc1312
main tree  1225068284e7f5cee0a6ebbbba67e9cc9bb470dd
candidate  3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd
candidate tree b5083f00006af56cef4c617c10ce1b085185a3f2
base       77aa1a4ac947c1632ea57262d29d2753ba163c8a
base tree  8d2400f86347395a80388a9600db4cc72a878ebb
merge-base(main,candidate) 77aa1a4ac947c1632ea57262d29d2753ba163c8a
```

`base` is an ancestor of `candidate` (exit 0); `candidate` is not an
ancestor of current main (exit 1). Current main was dirty before the audit:

```
 M workflow/events.jsonl
 M workflow/state/sessions.json
 M workflow/state/stages.json
```

These coordinator changes were preserved. `python3 scripts/workflow.py validate`
passed with 23 issues, 11 PRs, 239 issued sessions, and 7 stages.

## Changed paths and replay

The candidate changes exactly 39 paths: `blueprint/.gitignore`, `Makefile`,
`README.md`, `check.py`, `check_pdf.py`, generated graph DOT/JSON, three
metadata files, twelve chapter TeX files, generated chapter/external/gap TeX,
macros/main TeX, and `blueprint/tests/test_check.py`. The candidate diff is
6,113 insertions and 4 deletions.

The current-main delta from the common base is 59 paths. The sorted path
intersection between `diff base..main` and `diff base..candidate` is empty
(0 paths). A three-tree read-only merge check:

```
git merge-tree 8d2400f86347395a80388a9600db4cc72a878ebb \
  1225068284e7f5cee0a6ebbbba67e9cc9bb470dd \
  b5083f00006af56cef4c617c10ce1b085185a3f2
```

returned exit 0 and no `CONFLICT`, `both modified`, `both added`, or
`changed in both` records. A clean temporary replay of the blueprint range
onto current main is therefore technically admissible. It must be performed
in a disposable worktree from the verified main SHA, never in the dirty main
worktree; preserve the coordinator state files and import only the resulting
immutable integration evidence.

The safe project-level order is still source first, then blueprint:

1. approved LPR-001 (`e93d949d06af2a7f4407d198a37aad315deac6aa`);
2. approved LPR-002 (`63037ddceada7a88436f9afa9ed1ef4d74319098`), which adds
   `source-pin.json`, `split-manifest.json`, `RIGHTS.md`, source tooling, and
   the corrected `QPBT_SOURCE_MAP.md`;
3. LPR-004 head `3f4d4b302b96b74dffaf595c11ff01db4e6c7fbd`.

LPR-002 is currently `approved` but QPBT-002 remains blocked pending its
endpoint-specific QPBT-010 gate. Thus LPR-004 can be merged without a path
conflict, but it cannot be acceptance-closed or source-gate-validated on the
current main tree alone. The candidate README explicitly states that the
standalone Stage-3 branch lacks the source payload and that the exact
`--source-root references/2001.04383v3` check must run on the combined
Stage-2/3 tree (README lines 31-35).

## Source and blueprint fidelity gates

The pinned map records arXiv:2001.04383v3 and the primary regions at
`references/2001.04383v3/QPBT_SOURCE_MAP.md:21-44`: Section 7.3/game setup
(original lines 5028-5377), Theorem 7.14 soundness (5576-5594), qubit
conversion (5595-5639), canonical complexity (5640-5766), and Appendix A
(13032-14930). The split source anchors used by the candidate include:

- `sec:qld-game`, `def:admissible`, `lem:pauli-completeness`, `thm:pauli`, and
  `cor:pauli-binary` in `sections/qpbt/qpbt-game-and-soundness.tex` lines 2,
  60, 334, 534, and 572;
- `sec:qld-analysis`/`thm:pauli-appendix` in
  `sections/qpbt/appendix-statement-roadmap.tex` lines 10 and 15;
- the Appendix proof spine `sec:qld-prelim`, `sec:commutation`,
  `sec:expanding`, `sec:combining`, `sec:apply-ldt`, and `sec:separating`;
- dependency anchors `sec:finite-fields`, `sec:ld-encoding`, `def:bracket`,
  `def:state-distance`, `sec:generalized-pauli`, `sec:linear`, and `sec:types`.

The immutable candidate records 48 nodes (13 definitions, 21 lemmas, 4
external-theorem boundaries, 6 internal lemmas, 3 theorems, 1 corollary), 15
explicit paper gaps (`G01`-`G15`), and exactly one minimal-skeleton `sorry` at
`MIPStarRE.QPBT.pauliSoundness`. Its metadata is marked `speculative: true` and
`blocked_by: [QPBT-002, QPBT-009]`; 20 nodes remain `paper-gap` and 28 are
`not-started`.

The exact recorded candidate gates are:

```
26 blueprint tests; deterministic check 48 nodes/12 chapters; graph SVG;
Python compileall
materialize exact QPBT-002 head 63037dd ... verify 39 files/646 labels/
inventory 04548808c30c476e9b2b7cb2f728a6d0c348a6706a8ed1bc9fb9945f20a124f4;
run blueprint source-root gate
force clean/rebuild PDF; validate 45 pages, 109 identifiers, positive-area
words and exact Decimal collision threshold
verify 346808-byte patch ae487f890e0b3decf5d9e7b997c0cc8880d494ec2d3903ba8ae39fef906bdba4;
4264-byte manifest 7a115499b38a591f722750c28fed34fe181631ae43b2929ef819395b827e9551;
clean worktree; git diff --check
```

The candidate README names the reproducible commands as
`python3 blueprint/check.py --check`, the combined source-root form with
`--source-root references/2001.04383v3`,
`python3 -m unittest discover -s blueprint/tests -p 'test_*.py'`, and
`make -C blueprint pdf`. No command was rerun in this audit because builds and
network access are prohibited.

For issue acceptance, QPBT-003 additionally requires every declaration/theorem
to have a paper anchor, explicit transitive definition/proof graphs, reachability
of the main theorem from leaves, independent blueprint approval, and the second
Git commit. QPBT-009 requires explicit disposition of every source discrepancy,
separation of mathematical repairs from typographical normalization, a named
norm/squared-norm bridge, pinned external dependency boundaries, and independent
review of source-facing choices. The candidate metadata exposes the relevant
gaps rather than silently changing these theorem contracts.

## Compatibility decision

**Verdict: technically replayable, but integration/acceptance blocked pending
the approved source ranges and QPBT-009/combined-tree gates.** There is no
changed-path conflict with current main, and a temporary worktree merge is the
safe mechanism. Do not cherry-pick the six candidate commits into dirty main,
do not run the standalone source-root gate (the source sections are absent
there), and do not mark QPBT-003 done until the ordered combined replay passes
all recorded source, graph, PDF, declaration, independent-review, and
second-commit gates.

Audit accounting: source/state edits 0 (this report only), builds 0, Lean/Lake
0, network 0, dispatched subagents 0; token usage unavailable for this
collaboration session.
