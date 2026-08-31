# QPBT-002 Reference Source Split Delivery

## Scope and provenance

- Logical session: `i002-orchestrator-a01-reference-split`
- Issue / local PR: `QPBT-002` / `LPR-002`
- Worktree: `.workflow-runtime/worktrees/qpbt-002`
- Immutable speculative base: `cf43b33b5cd77cb005b90b02b6d369cfbd86d316`
- Protocol revision: 0.1.4
- Commit created: none; the coordinator must inspect and freeze the issue head.
- Network activity: none. Materialization used the previously authenticated local
  archive `/tmp/2001.04383v3-source.tar`.
- Token usage: unavailable; the collaboration backend exposes no per-session
  token accounting.

The committed pin authenticates arXiv:2001.04383v3 at 233,859 bytes and SHA-256
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`.
It pins the exact TeX member at 896,289 bytes, 14,935 CRLF lines, SHA-256
`38b3e662bb85bb902fcd056436fe9ecbe9e68d1990a074d0c0c12b39d5972ea9`,
and the BBL member at 16,898 bytes, 418 CRLF lines, SHA-256
`da0894e1c6f13e437e0d7f9d65ea3bf49615790c80d4e754696e6f1517ad71a0`.

## Delivered behavior

`scripts/reference_source.py` loads duplicate-key-rejecting closed JSON
contracts. When no archive is supplied, it delegates the pathname-based
`reference_transport` acquisition only into a private transport-owned temporary
directory outside the selected runtime. It verifies the exact archive size and
checksum there, then creates, copies, fsyncs, identity/size/checksum checks, and
atomically publishes the cache using only operations relative to the already
bound runtime descriptor. A supplied archive is rejected before reading unless
its complete parent chain is real, its leaf is a regular non-symlink file, and
its size and checksum are the exact pin.

Extraction verifies the archive before gzip processing, caps decompressed
bytes, parses tar headers without `extract` or `extractall`, and admits exactly
the two fixed explicit regular members. It rejects extra, missing, duplicate,
path-bearing, linked, device, sparse, PAX, and GNU-override entries; base-256
fields; invalid checksums/padding/trailers; and non-CRLF member data. Members and
all fragments are checked by exact size, line count, and SHA-256.

The manifest defines 15 exact top-level fragments, three exact QPBT-main
fragments, seven exact Appendix A fragments, and nine dependencies that exactly
cover five declared sparse scopes. It binds all 34 safe output paths to audited
headings and QPBT relevance. The generated 124,826-byte `labels.json` contains
646 ordered occurrences / 645 names, one-based line and byte columns, half-open
absolute byte ranges, per-name ordinals, and every containing output path. Its
SHA-256 is pinned as
`4da8ef3d95525e4c88ccafda3ff088aed5edd1b3ded97357024342d54f857cc7`.

Materialization binds the exact repository-local ignored
`.workflow-runtime/reference-source` directory before acquiring its
destination-keyed lock relative to that descriptor. Contracts are revalidated
after lock acquisition, and every transaction, staging, backup, fsync,
publication, rollback, and cleanup operation remains relative to the selected
runtime, transaction, and child descriptors even if the visible runtime path is
renamed or replaced. The runtime and reference roots must share a filesystem.
Publication installs source and sections and writes `READY` last as the
acceptance commit marker.
Inventory bytes bind both committed contracts and every generated file. An
exact existing generation is a no-write cache hit. Invalid existing output is
preserved by default; explicit replacement first backs up both trees and
restores both on any publication or verification failure. Author-owned source
and generated fragments remain ignored under the policy in `RIGHTS.md`.
Every recursive transaction deletion is preceded by an atomic rename to a
deterministic `.cleanup` tombstone and a runtime-parent fsync. Startup finishes
partial tombstone deletion without requiring `transaction.json`. New
transactions are assembled under that same recognizable preparation state and
atomically promoted, so every crash-visible directory is either an authoritative
live transaction or a safely disposable cleanup state.

## Real archive evidence

The first real materialization command was:

```text
/usr/bin/time -f 'WALL_SECONDS=%e' python3 scripts/reference_source.py materialize --archive /tmp/2001.04383v3-source.tar
```

It published 39 inventory-bound files, 646 labels, and exact archive SHA-256 in
0.413671 seconds internal / 0.59 seconds wall time. After strengthening the
manifest contract, the explicit transactional replacement command completed in
0.552917 seconds internal / 0.68 seconds wall time:

```text
/usr/bin/time -f 'WALL_SECONDS=%e' python3 scripts/reference_source.py materialize --archive /tmp/2001.04383v3-source.tar --replace-existing
```

The final generated inventory SHA-256 is
`04548808c30c476e9b2b7cb2f728a6d0c348a6706a8ed1bc9fb9945f20a124f4`;
the `READY` file SHA-256 is
`4d6a33759051b17428b3928d529d18e10da82e3bc09c75fbe429df324612b360`.
An independent `verify` completed in 0.24 seconds wall time and reported all 39
files and 646 labels valid. `inspect-archive` independently reported 233,859
archive bytes, two exact members, 34 slices, and 646 labels.

## Child topology and review disposition

The orchestrator was the sole writer. Two requested logical read-only auditors
ran concurrently through recycled physical collaboration nodes because the
backend retains completed nodes and provides no archive/delete primitive:

- `i002-auditor-a01-source-security`, physical
  `/root/i010_orchestrator_a01_reference_transport/i010_scout_a01_transport_boundaries`,
  UTC 2026-08-30 18:45:14 to 18:47:39. Its initial-snapshot materialization
  blocker became stale as implementation continued. Its actionable findings
  were accepted: bound archive reads, canonical collection descriptors, exact
  sparse scopes, heading/relevance metadata, a pinned generated label index,
  contract revalidation inside the lock, and additional rollback/adversarial
  tests.
- `i002-auditor-a02-manifest-fidelity`, physical `/root/stage2_split_a02`, UTC
  2026-08-30 18:45:16 to 18:54:29. It approved with no findings after
  independently recomputing both member pins, all 34 ranges/hashes/counts, full
  and QPBT reconstructions, all label records and mappings, metadata coverage,
  ignored-source policy, and final inventory.

The fidelity auditor additionally confirmed that all 646 labels map to exactly
one top-level output, 190 also map to a QPBT excerpt, 155 also map to a
dependency excerpt, and only `eq:farith` duplicates (ordinals 334/384 at lines
8928/10391).

## Validation

- `python3 -m unittest discover -s tests -p 'test_reference_source.py'`:
  46/46 passed in 9.222 seconds (9.44 seconds wall time).
- `python3 scripts/check_workflow.py`: 167/167 passed in 27.205 seconds
  (27.63 seconds wall time).
- `python3 -m compileall -q scripts tests`: passed.
- `git diff --check`: passed.
- `python3 scripts/reference_source.py verify`: passed, 39 files / 646 labels.
- `python3 scripts/reference_source.py inspect-archive --archive /tmp/2001.04383v3-source.tar`:
  passed, two members / 34 slices / 646 labels.

## Residual risk

Generic CI may not possess the ignored copyrighted archive, so the real archive
test is skip-capable there. Closure evidence above used an explicit local
integration command that fails when the pinned artifact is absent. Publication
uses two directory renames because `source/` and `sections/` are separate
required paths; consumers must require the inventory-bound `READY` marker,
which is installed only after both directories are durable. The implementation
uses POSIX `flock`, matching the repository's Linux workflow environment.

### Targeted security re-review

`i002-auditor-a03-source-security-fixes` ran read-only from UTC 2026-08-30
18:52:19 to 18:55:45. It verified the initial findings above, then found two
crash-safety blockers: author bytes in unignored transient paths and deletion of
backups after a rollback restoration failure. It also requested descriptor-bound
existing-output reads. The implementation moved all transactions into the exact
ignored runtime, added authoritative startup recovery, attempted both restores,
retained and reported incomplete transactions, and used `O_NOFOLLOW | O_NONBLOCK`
descriptor reads with pre/post `fstat` and exact byte bounds.

`i002-auditor-a04-publication-recovery` ran read-only from UTC 2026-08-30
19:00:01 to 19:01:54. It verified those fixes and found one remaining high
durability ordering issue: restored directory entries were not fsynced before
transaction deletion. The fix now performs both restores, fsyncs the reference
root, removes the transaction, and fsyncs the ignored runtime parent in that
order. A pre-delete fsync failure retains and reports the recoverable transaction.

`i002-auditor-a05-publication-durability` ran read-only from UTC 2026-08-30
19:04:04 to 19:04:22. It approved the exact final snapshot with no findings,
confirmed the explicit ordering and injected-failure tests, and reconfirmed all
earlier security dispositions. No reviewer edited the worktree or accessed the
network.

`i002-reviewer-a06-root-acceptance-preflight` ran read-only from UTC 2026-08-30
19:13:31 to 19:15:02. It found one medium crash-liveness gap: recursive cleanup
could remove `transaction.json` before removing the transaction directory, and
startup would reject that markerless remainder before recognizing a valid
publication. `i002-fixer-a01-transaction-tombstone` replaced every direct
transaction deletion with the atomic cleanup state described above. Four new
regressions interrupt cleanup after successful publication, stale valid
transaction recovery, rollback, and transaction initialization; every case
restarts from the markerless tombstone without manual repair.

The optional `i002-reviewer-a07-transaction-tombstone` began a read-only review
at UTC 2026-08-30 19:19:58 but was reassigned by the root coordinator before it
could return a verdict. Its partial audit found the tombstone state transitions
code-correct and identified one test-strengthening opportunity: exercise
rollback recovery through real `materialize` startup. The rollback regression
now deletes the marker, leaves the tombstone, and proves a real restart publishes
successfully. This interrupted attempt is not represented as an approval.

`i002-reviewer-a08-transaction-tombstone` ran an independent logical read-only
review on a reused physical node from UTC 2026-08-30 19:40:23 to 19:43:30. It
requested changes for two concrete findings. First, rollback validated the live
transaction root but could follow a symlinked `backup` component or accept an
unsafe saved tree before `os.replace`; a temporary reproduction moved an
external directory entry into the reference root. Second, initialization wrapped
a post-delete parent-fsync failure as preserved cleanup state even though neither
the transaction nor tombstone remained.

`i002-fixer-a02-backup-boundary-reporting` bound the runtime, transaction,
backup, and reference directories with no-follow descriptors, validated every
present saved tree as a directory before the first rollback mutation, and used
dirfd-relative renames. Backup-component symlink, saved-tree symlink, and
saved-tree non-directory regressions prove that live destinations and external
sentinels remain unchanged while recovery state is retained. Initialization now
reports the transaction/tombstone paths actually present and otherwise reports
removal-durability uncertainty. A real materialization regression deletes the
tombstone, injects the following parent-fsync failure, checks that retention is
not claimed, and then restarts successfully. This fixer disposition is not an
approval and requires a fresh read-only review.

`i002-reviewer-a09-backup-boundary` ran a fresh read-only review from UTC
2026-08-30 19:58:06 to 20:02:52 and requested changes after three deterministic
reproductions. Rollback closed its bound directory descriptors before fsync and
cleanup, so a runtime-path replacement redirected tombstone deletion into an
external directory. A saved tree could also be replaced after its no-follow
validation but before rename, replacing the live destination and discarding the
real transaction. Finally, a marker claiming an original tree with neither a
saved nor current copy was accepted as successful rollback.

`i002-fixer-a03-rollback-fd-races` ran from UTC 2026-08-30 20:04:21 to
20:12:15 (474 seconds). It keeps runtime, transaction, backup, saved-tree,
current-tree, and reference descriptors open through restoration, reference
fsync, descriptor-relative tombstoning, recursive no-follow cleanup, and runtime
fsync. Saved trees first move to deterministic `restore-*` candidates and must
retain the inode identity of their held descriptors before any current tree is
touched. Post-move checks restore descriptor-bound `incomplete-*` current trees
on a missing, symlinked, non-directory, or raced candidate. Marker, backup, and
current presence must now form an exact recoverable state. Five new regressions
cover both A09 reproductions, missing and unexpected saved state, candidate
disappearance, and post-delete descriptor-fsync reporting. The focused and
aggregate counts above include these tests. This fixer disposition is not an
approval and still requires a fresh independent review.

`i002-reviewer-a10-rollback-fd-races` ran read-only from UTC 2026-08-30
20:16:02 to 20:19:28 (206 seconds). It independently confirmed that all four
A09 rollback reproductions now fail closed or complete safely, but found the
same runtime-redirection class in the older pathname-based cleanup helpers used
by successful publication, valid stale recovery, markerless startup cleanup,
and initialization failure. Its reproduction redirected deletion into an
external transaction, removed its sentinel, reported success, and stranded the
real transaction.

`i002-fixer-a04-global-descriptor-cleanup` ran from UTC 2026-08-30 20:20:17 to
20:27:50 (453 seconds) and removed both pathname-authority helpers.
Materialization now holds one no-follow runtime descriptor throughout
the locked critical section. Startup binds `transaction.json` to a held
transaction inode; rollback and success cleanup reuse that same authority.
Transaction-to-tombstone rename, pre-delete fsync, recursive no-follow cleanup,
tombstone removal, and post-delete fsync are all relative to the held runtime
descriptor. Initialization cleanup uses the same path, and retained recovery is
distinguished from post-delete durability uncertainty using entries observed
through that descriptor. New normal-publication and markerless-startup runtime
swap regressions preserve external sentinels, clean only the bound object, and
fail closed if the runtime pathname no longer names the held directory. This
fixer disposition is not an approval and requires fresh independent review.

`i002-fixer-a06-atomic-runtime-staging` ran from UTC 2026-08-30 20:51:33 to
21:01:06 (573 seconds). It moved lock creation and acquisition
under the already bound runtime descriptor and made transaction initialization,
staged file creation, recursive staging fsync, backup moves, publication,
rollback, tombstoning, and cleanup use held descriptors without reopening the
mutable runtime pathname. Obsolete pathname-based write, directory-fsync, and
transaction-cleanup helpers were removed. Three new deterministic regressions
replace the runtime path with a real directory or symlink immediately before the
first staged write, and replace its incarnation between selection and lock
acquisition. They prove the selected inode receives the sole lock and all
transaction writes while replacement trees and sentinels remain untouched.

The first focused run after the authority rewrite ran 42 tests with six failures:
five failure-injection hooks still intercepted the removed pathname APIs and one
test expected the now-obsolete fail-on-runtime-rename behavior. After converting
those hooks to descriptor identities and adding the three concurrency tests, the
focused 45/45, aggregate 166/166, compileall, workflow validation, diff check,
archive inspection, and exact 39-file / 646-label verification gates all passed.
This fixer disposition is not an approval and requires fresh independent review.

`i002-fixer-a07-bound-default-acquisition` ran from UTC 2026-08-30 21:06:45 to
21:15:15 (510 seconds). It resolved the A12 high finding by removing the last
post-bind reconstruction of a runtime archive pathname. Default acquisition now
uses a private transport temporary directory, verifies the complete archive
contract before copying, and publishes the cache relative to `runtime_fd` with
no-follow regular-file checks, held-inode identity checks, exact size and SHA-256
readback, file and directory fsyncs, atomic replacement, and identity-bound
partial cleanup. A deterministic no-network regression omits `archive_path`,
renames and replaces the runtime between descriptor binding and lock acquisition,
and proves that only the selected locked inode receives the exact cache while
the replacement directory remains byte-for-byte unchanged.

The first targeted command used a dotted unittest module name and failed before
test discovery because `tests/` is not a Python package. The corrected discovery
filter passed 1/1. The final focused 46/46, aggregate 167/167, compileall,
workflow validation, diff check, archive inspection (233,859 bytes, two members,
34 slices, 646 labels), and exact verification (39 files, 646 labels) gates all
passed. This fixer disposition is not an approval and requires fresh independent
review.

`i002-fixer-a08-single-link-cache-publication` ran from UTC 2026-08-30 21:27:37
to 21:34:48 (431 seconds). It resolves the A14 file-identity finding in the
bound default-cache publication path while preserving A07's descriptor-relative
acquisition.
Every partial and final archive check now requires the held descriptor and the
runtime-directory entry to be the same regular inode with exactly one directory
link. The invariant is checked at initial binding, after writing, after file
fsync, across hashing, immediately before replacement, after replacement, after
runtime-directory fsync, and after final pinned-archive readback. A failed
post-replacement check removes only the same bound inode from the selected
runtime directory; cleanup never follows or removes an external alias.

A deterministic no-network regression creates a hard-link alias from the bound
partial during its write/fsync hook. Publication fails on the single-link
invariant, removes the runtime-owned partial, leaves no published cache or
unintended replacement, preserves the external alias and unrelated sentinel,
and publishes no source tree. The targeted regression passed 1/1, the focused
source suite passed 47/47, and the aggregate suite passed 168/168. Workflow
validation, compileall, exact materialization and verification (39 files, 646
labels), archive inspection (233,859 bytes, two regular members, 34 slices),
and candidate diff/whitespace checks passed with no intermediate failure. The
session used zero subagents; token usage is unavailable because the runtime does
not expose it. This fixer disposition is not an approval and requires fresh
independent review.

## Clean-base replay provenance

`i002-reviewer-a15-single-link-candidate` independently approved the exact
seven-path candidate from UTC 2026-08-30 21:38:49 to 21:42:44. The approved
candidate digest was
`5d08b189dc075e551870ddd9fc236b54a986cabaafc0378918447e2a65bce40a`
over lexically sorted `path NUL decimal-bytes NUL file-sha256 LF` records. It was
committed without content changes on the speculative base as
`e291ab635015f4d7afc0174ce6fad6b631b0102c`.

`i002-integrator-a09-clean-base-replay` created branch
`issue/qpbt-002-clean-base-a09` and worktree
`.workflow-runtime/worktrees/qpbt-002-clean-base-a09` directly from the approved
transport repair `e93d949d06af2a7f4407d198a37aad315deac6aa`, then cherry-picked the
approved candidate without conflict as
`dc7f52d78184974bb322839e5ef64fd9fff52cf7`. This provenance paragraph is an
uncommitted post-replay review-packet update. Clean-base validation passed the
49-test transport suite, 47-test source suite, 179-test aggregate and workflow
suites, compileall, contract and archive inspection, and isolated exact
materialization and verification. This paragraph does not alter the reviewed
seven-path replay commit and is not an integration approval.

`i002-fixer-a11-reference-root-descriptor-rollback` ran from UTC 2026-08-30
22:00:04 to 22:09:35 and resolves A16's reference-root pathname escape. Contract
loading, existing and final materialization verification, inventory binding,
stale recovery, rollback setup, backup restoration, transaction cleanup, and
all reference-directory fsyncs now reuse the no-follow reference descriptor
selected before the lock-protected operation. Rollback requires independently
bound runtime and reference descriptors; no recovery or rollback call site can
reopen `reference_root`. Descriptor-native verification recursively binds every
directory, bounded-reads every regular file, rechecks the captured contracts,
and requires the verified source and sections inodes to remain at their bound
names before success.

A deterministic regression replaces `reference_root` with another real
directory immediately before injected final-verification failure. Rollback
restores the original source and sections only in the descriptor-selected tree,
removes the selected transaction, and preserves all replacement-root sentinels
byte-exact. The first 48-test focused run had one failure because the new bounded
reader's generic oversized-file diagnostic no longer matched the established
exact-size error contract; restoring explicit exact-size semantics resolved it.
The final source suite passed 48/48, transport passed 49/49, and aggregate and
workflow suites passed 180/180. Compileall, both workflow validators, contract
validation, archive inspection, and isolated exact 39-file / 646-label
materialization and verification also passed. This fixer disposition is not an
approval and requires fresh independent review.

The immutable A18 review found that restart recovery still authenticated only
the textual `reference_root`, allowing a replacement directory at the same path
to receive rollback mutations or authorize transaction cleanup. The recovery
marker now also persists the selected reference directory's stable device and
inode identity. Startup validates that closed-schema identity against the held
no-follow reference descriptor before materialized-output verification,
rollback, or successful-transaction cleanup. A mismatch fails closed and
retains the live `.transaction` byte-for-byte. The deterministic artifact policy
is that a pre-existing `.cleanup` tombstone is always completed first using only
the bound runtime descriptor, while a live transaction whose reference identity
does not match is never renamed or deleted; neither policy touches any reference
directory content.

`i002-fixer-a13-reference-recovery-identity` ran from UTC 2026-08-30 22:32:18
to 22:38:03 (345 seconds). Its deterministic no-network restart regression
constructs a coherent saved-tree transaction, replaces the selected reference
directory at the same textual path, and proves that recovery retains every
transaction payload byte, leaves every replacement-root byte unchanged, creates
no cleanup tombstone, and refuses the unreadable archive path before acquisition.
The final source and transport suites passed 49/49 each. The aggregate suite and
`scripts/check_workflow.py` passed 181/181 each; `scripts/workflow.py validate`,
compileall, and the candidate whitespace check passed. Isolated contract and
archive validation plus exact materialization and verification passed with the
pinned 233,859-byte archive, 34 slices, 39 materialized files, and 646 labels.
The session used zero subagents and zero network or external-endpoint calls; it
did not run Lake or Lean. Token usage is `null` because this runtime does not
expose per-session token accounting. Model attestation: Codex based on GPT-5,
with no more specific backend model identifier exposed. This fixer disposition
is not an approval and requires fresh independent review.
