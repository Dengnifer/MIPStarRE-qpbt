# QPBT source materialization audit

Session: `i000-scout-a50-source-materialization`
Snapshot audited: main `7526e58663f4a93c6643d936cb6cedb8df6e090b`, tree
`e45a463ae0a58f8faf4c3d10329a6f68b08b19e2`
Verdict: materialization is procedurally ready from the local pinned archive,
but QPBT-003 and QPBT-004 remain blocked by workflow admission gates.
Elapsed: approximately 6 minutes. Token usage: unavailable (not exposed).

This was a read-only audit. No canonical repository file, source tree, workflow
state, metric, worktree, cache, or runtime file was changed. No network, source
materialization, Lean/Lake build, or cache warm was run. The only output is this
report under `/tmp`.

## Pin and local archive evidence

`references/2001.04383v3/source-pin.json:1-23` is a closed schema for source
identity `arxiv-2001.04383v3`, URL `https://arxiv.org/src/2001.04383v3`, and the
allowlist `arxiv.org`/`export.arxiv.org`. It pins a 233859-byte archive with
SHA-256
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174` and exactly
two regular members:

* `compression_arXiv_v3.tex`: 896289 bytes, SHA-256
  `38b3e662bb85bb902fcd056436fe9ecbe9e68d1990a074d0c0c12b39d5972ea9`, 14935
  CRLF lines;
* `compression_arXiv_v3.bbl`: 16898 bytes, SHA-256
  `da0894e1c6f13e437e0d7f9d65ea3bf49615790c80d4e754696e6f1517ad71a0`, 418
  CRLF lines.

The available `/tmp/2001.04383v3-source.tar` is exactly 233859 bytes and its
`sha256sum` is the pinned archive digest above. It is a regular local file. The
same archive was also present in prior temporary acquisition directories; those
paths are ephemeral and are not canonical provenance.

`references/2001.04383v3/split-manifest.json:1-74` cross-binds the TeX member,
its size/digest/14935-line count, output template
`{output_directory}/{id}.tex`, four ordered collections, 34 slices, and exact
or sparse source ranges. Lines 112-122 bind the UTF-8 label contract: 646
occurrences, 645 unique names, duplicate `eq:farith` at source lines 8928 and
10391, generated `sections/labels.json`, and its SHA-256
`4da8ef3d95525e4c88ccafda3ff088aed5edd1b3ded97357024342d54f857cc7`.

`references/2001.04383v3/RIGHTS.md:1-24` explains that author-owned TeX/BBL
bytes and all generated slices remain ignored because redistribution permission
is not established. It explicitly documents the materialize and verify commands
and permits an already acquired archive via `--archive PATH`.

## Exact offline command and semantics

The minimal offline path, using the already verified local archive, is:

```text
python3 scripts/reference_source.py validate-contracts
python3 scripts/reference_source.py inspect-archive --archive /tmp/2001.04383v3-source.tar
python3 scripts/reference_source.py materialize --archive /tmp/2001.04383v3-source.tar
python3 scripts/reference_source.py verify
```

The first two commands were run read-only and returned:

```text
{"command":"validate-contracts","status":"ok"}
{"archive_bytes":233859,"command":"inspect-archive","labels":646,"members":["compression_arXiv_v3.bbl","compression_arXiv_v3.tex"],"slices":34,"status":"ok"}
```

The `materialize` and `verify` commands were not run because they write or
inspect the ignored generated tree. With default roots, the script resolves the
reference root to `references/2001.04383v3` and requires the runtime root to be
exactly `.workflow-runtime/reference-source` on the same filesystem
(`scripts/reference_source.py:1614-1637`). A non-default runtime root is
rejected, so this is not a safe disposable read-only invocation.

`validate_source_pin` and `validate_manifest` enforce exact keys, identities,
sizes, digests, collection ordering, contiguous exact covers, sparse scopes,
label cardinalities, and output paths (`scripts/reference_source.py:91-246`).
Archive extraction then enforces the archive digest and size, gzip/tar bounds,
ASCII non-path member names, regular-file-only members, member size/digest/CRLF
checks, and a zero-block trailer (`scripts/reference_source.py:290-335`).

Materialization stages `source/` and `sections/` under a locked transaction,
writes `sections/inventory.json`, computes the READY payload as the ASCII
SHA-256 of that inventory plus a newline, atomically publishes `sections/READY`,
and verifies before returning (`scripts/reference_source.py:1686-1690`,
`1780-1843`). Existing invalid output is preserved unless the explicit
`--replace-existing` flag is supplied (`scripts/reference_source.py:1652-1678`).
The verifier re-reads the contracts, checks every expected file byte-for-byte,
rejects extra/missing/symlinked entries, and requires the bound source/sections
directory identities (`scripts/reference_source.py:614-729`). A `READY` marker
without the matching inventory and contract bytes is therefore unusable.

## Current absence and workflow blockers

`test -d references/2001.04383v3/sections` and
`test -e references/2001.04383v3/sections/READY` both report absent. The source
map (`references/2001.04383v3/QPBT_SOURCE_MAP.md:21-44`) states that a tree
without matching `READY` is not usable and that dependency excerpts are sparse,
not a source reconstruction. This explains why a local archive alone cannot
authorize source-faithful formalization.

* **QPBT-002** is `blocked` (`workflow/state/issues.json:75-104`). Its source
  pin/split acceptance gates are satisfied in the recorded candidate, but the
  endpoint-specific QPBT-010 dependency still awaits an authorized review or
  explicit disposition.
* **QPBT-003** is `blocked` (`workflow/state/issues.json:107-135`). Its
  acceptance requires source anchors, dependency graphs, independent review,
  and a second Git commit. The unblock condition is integration of the approved
  transport, source split, blueprint, and parameter ranges followed by the
  combined gates and that second main commit.
* **QPBT-004** is `planned` and depends on QPBT-003
  (`workflow/state/issues.json:138-163`). Its gates require Lean/Mathlib pins,
  reusable foundation provenance, and the empty project build/cache gate. The
  current blocked reason records unresolved package/cache findings on the prior
  candidate; it explicitly requires a new fixed head, fresh immutable review,
  then exactly one singleton hot-main cache-get and Lake build.

The repository's own frontier report confirms that the current main checkout
still lacks materialized source and QPBT/Quantum/LDT trees and that QPBT-004 must
wait for the second main commit and fresh hot-main cache acceptance
(`workflow/reviews/stage-04a-postmerge-frontier.md:10-17`, `48-82`).

## Concrete next-step checklist

1. Resolve the QPBT-010 endpoint gate and integrate the approved transport range.
2. Integrate the approved QPBT-002 source-split range, then the approved
   QPBT-003/009 blueprint range and ancestral QPBT-012 in the rehearsed order.
3. On the resulting main checkout, rerun source `validate-contracts` and
   `inspect-archive` against a locally acquired archive whose bytes/digest match
   `source-pin.json`.
4. With coordinator authorization, run the exact offline materialize command
   above. Capture its JSON result, `source/` and `sections/` inventories, and
   `READY` digest; immediately run `verify`.
5. Run the required source-split tests, aggregate workflow tests, compileall,
   `workflow.py validate`, and `git diff --check`; create the required second
   main commit. Do not commit author-owned source bytes.
6. For QPBT-004, create a fresh current-main candidate, use the singleton
   hot-main `warm` with authenticated local Mathlib/Lake archives, then private
   `seed`. Never share a writable `.lake/build` across worktrees.

## Checks performed

* `git rev-parse HEAD` -> `7526e58663f4a93c6643d936cb6cedb8df6e090b`.
* `git rev-parse HEAD^{tree}` -> `e45a463ae0a58f8faf4c3d10329a6f68b08b19e2`.
* `python3 scripts/reference_source.py validate-contracts` -> pass.
* `python3 scripts/reference_source.py inspect-archive --archive /tmp/2001.04383v3-source.tar` -> pass; 233859 bytes, 2 members, 34 slices, 646 labels.
* `sha256sum /tmp/2001.04383v3-source.tar` -> pinned digest.
* `python3 scripts/workflow.py validate` and blueprint checks were not needed
  for this source-only audit and no state was changed; no build or compile was
  run.

No source materialization, network, Lean/Lake/build, cache warm/seed, or file
mutation was performed. Token usage is unavailable.
