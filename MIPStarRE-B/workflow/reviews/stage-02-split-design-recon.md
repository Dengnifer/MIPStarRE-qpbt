# Stage 2 Split Design Reconnaissance

- Session: `i002-scout-a01-split-design`
- Issue: `QPBT-002`
- Backend: Codex collaboration, read-only
- Workspace edits: none

The scout recommends a pinned, manifest-driven byte slicer rather than a
general TeX parser. It must verify the arXiv archive before extraction, admit
only the expected regular `.tex` and `.bbl` members, preserve CRLF and trailing
bytes, slice audited inclusive line ranges, verify output hashes, and publish
under a lock through a staging directory. The full-document partition and the
QPBT/dependency excerpt partition are both gap-checked by tests.

The source archive is 233,859 bytes with SHA-256
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`.
Important hazards are archive traversal and links, text-mode newline changes,
indented appendix headings, inline labels, fragments that are not standalone
documents, the missing `.bib`, and the nondeterministic `\today` date.

Recommended issue order: finish `QPBT-010` acquisition/cache resilience, then
implement and review `QPBT-002`. External reviewers must not receive ignored
author source without a separately expanded disclosure authorization.

Exact elapsed time and token usage were not exposed by the collaboration
backend; the canonical session records the coordinator-observed time window.

## Exact follow-up audit

Session `i002-scout-a02-split-manifest-audit` independently verified the local
archive at 233,859 bytes with SHA-256
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`.
Its TeX member is 896,289 bytes, has 14,935 CRLF-terminated lines, and hashes to
`38b3e662bb85bb902fcd056436fe9ecbe9e68d1990a074d0c0c12b39d5972ea9`;
the 16,898-byte BBL hashes to
`da0894e1c6f13e437e0d7f9d65ea3bf49615790c80d4e754696e6f1517ad71a0`.

The full reconstruction partition is: `1-488`, `489-759`, `760-897`,
`898-2162`, `2163-2877`, `2878-3566`, `3567-4148`, `4149-5766`,
`5767-8355`, `8356-8762`, `8763-11765`, `11766-12102`, `12103-13031`,
`13032-14930`, and `14931-14935`. The QPBT main exact-cover leaves are
`5028-5046`, `5047-5639`, and `5640-5766`; the appendix leaves are
`13032-13085`, `13086-13195`, `13196-13402`, `13403-13718`,
`13719-14006`, `14007-14453`, and `14454-14930`. The `\appendix` command
at line 13032 belongs to the first appendix leaf even though the QPBT section
starts at line 13040.

Dependency excerpts are intentionally sparse, not a global partition. The
manifest must store label occurrences by line, column, and ordinal: it has 646
occurrences, including duplicate `eq:farith` entries at lines 8928 and 10391.
Only the full top-level collection and the two QPBT leaf collections have
exact-cover reconstruction invariants.

## Parallel implementation preflight

Logical sessions `i002-scout-a03-secure-source-split` and
`i002-scout-a04-split-manifest-tests` ran concurrently for 314 and 294 seconds,
respectively. Both were read-only recycled collaboration nodes; their physical
identities and timings are retained in the canonical session ledger.

The security scout requires whole-archive validation before any write, an exact
two-member regular-file allowlist, rejection of path/link/device/sparse and
PAX/GNU override cases, streamed per-member and aggregate bounds, and fixed
output names rather than raw tar paths. It also requires CRLF-only byte slicing,
destination-keyed locking, same-filesystem staging, READY-bound inventories,
deep cache-hit verification, and preserve-or-rollback publication semantics.

The manifest scout specifies canonical sorted JSON with source/member pins,
inclusive line and half-open byte ranges, per-output hashes, collection
invariants, and an ordered occurrence table for all 646 labels. Its acceptance
matrix covers hostile tar variants, exact reconstruction, QPBT boundaries,
duplicate-label identity, injected publication failures, cache-hit immutability,
two-process writer election, tamper detection, ignored generated files, and
timezone-independent deterministic reruns.

## Immutable completion

The restart-recovery directory-identity repair was frozen at
`63037ddceada7a88436f9afa9ed1ef4d74319098` after the approved three-path
candidate review. Exact-head checks were recorded before formal review: 49/49
transport, 49/49 source, 181/181 aggregate, clean seven-path scope, and isolated
39-file/646-label materialization. Session
`i002-reviewer-a20-reference-recovery-immutable` independently reproduced the
range and gates in 381 seconds and approved with no findings. The local source
split PR is approved; only its QPBT-010 endpoint-review dependency remains.
