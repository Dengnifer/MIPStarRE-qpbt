# QPBT-004 project materialization

## Status

Speculative implementation at immutable base
`77aa1a4ac947c1632ea57262d29d2753ba163c8a`. QPBT-004 still depends on
QPBT-003, so this work is not ready for approval or integration. A fresh,
read-only reviewer who is neither the implementer nor orchestrator is still
required after the dependency is accepted and a local PR head exists.

Logical session: `i004-orchestrator-a01-local-project`
Start UTC: `2026-08-30T19:35:31Z`
End UTC: `2026-08-30T19:57:03Z`
Elapsed: 1,292 seconds

## Rights and provenance boundary

The authenticated upstream snapshot at commit
`507e81220d95266ff3d589d125b2f87c7300a9fb` contains no license file.
Redistribution permission is therefore recorded as not established. No
upstream source byte is tracked: `.gitignore` excludes `MIPStarRE/*` and only
re-opens `MIPStarRE/QPBT/**` for future project-authored formalization files.

`references/mipstarre-upstream.json` binds the prior authenticated acquisition
evidence, archive and decompressed-tar sizes and SHA-256 values, exact archive
prefix, exact global PAX commit comment, complete output inventory, Lean
4.32.0, Mathlib `81a5d257c8e410db227a6665ed08f64fea08e997`, and the selected reusable
foundation modules. The local archive used for verification was:

- path: `/tmp/qpbt-010-acquisition.FJmb6mA8/MIPStarRE-verified.tar.gz`
- bytes: `1,989,153`
- SHA-256: `656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc`
- decompressed tar bytes: `10,752,000`
- decompressed tar SHA-256: `4e4850855ac74b63cb9ef292281462174da776628a6278006f3728c9458a1d39`

The delivery evidence above records the local acquisition path, but the path is
absent from the machine-reusable pin, cache identity, cache manifests, and build
commands.

## Architecture

`scripts/materialize_mipstarre.py` performs descriptor-bound reads without
following symlinks, applies compressed, decompressed, member-count,
per-member, and aggregate-byte ceilings, and parses the ustar blocks directly.
It admits one exact initial global PAX commit comment and otherwise only safe
directories and regular files beneath one exact prefix. It rejects duplicate
or non-canonical paths, raw traversal components, links, devices, local PAX,
and GNU extensions. Publication verifies the exact `MIPStarRE/` allowlist and
foundation hashes.

Publication is serialized under the repository-local ignored
`.workflow-runtime/mipstarre-materialization/` directory. Stage, backup, and
transaction state remain on the destination filesystem. Publication uses
fsynced files/directories and atomic renames; stale transactions either accept
an already-valid publication or restore the prior tree. Failed restoration
retains recovery authority. Existing project-authored `MIPStarRE/QPBT/` bytes
are descriptor-verified, copied, reverified, and preserved across replacement.

The canonical hot-main recipe materializes inside the elected builder's
detached clone before dependency caching and compilation. Its identity now
binds the materializer and provenance pin as well as the Lake pins. Before a
build starts, it derives the exact source commit, output inventory, file and
byte counts from the committed provenance pin and derives the complete
project-authored `MIPStarRE/QPBT/` file, byte, and content digest from Git
objects at the immutable main commit. These facts are part of the cache key.
Waiters reuse the published cache and do not materialize or compile again. The
archive is supplied through the `MIPSTARRE_ARCHIVE` environment variable, so
an ephemeral machine path does not affect canonical identity.

After compilation, the elected builder loads the identity-bound materializer
from the detached checkout and reruns its exact project-pin and materialized
tree verification before publishing any cache. The bounded result records the
source commit, provenance-pin SHA-256, foundation inventory SHA-256 and
file/byte counts, and the project-authored QPBT digest and counts in the cache
manifest. The verifier result must equal the committed source contract field
for field, not merely have valid-shaped values. The builder also rejects all
tracked changes and unexpected untracked project source after compilation;
authenticated materialized upstream paths remain excluded by the committed
ignore boundary. The READY digest covers this evidence; cache hits validate
its closed schema and exact semantic provenance binding, and seeding validates
it both before and after copying the cache.

## Review finding disposition

Read-only session `i004-reviewer-a01-local-project` requested changes because a
build could mutate ignored materialized source after initial verification and
still publish a READY cache. Writable fixer session
`i004-fixer-a01-cache-source-revalidation` addressed the finding by adding the
post-build exact verification and manifest/readiness contract above.

Fixer start UTC: `2026-08-30T20:07:49Z`
Fixer end UTC: `2026-08-30T20:15:05Z`
Fixer elapsed: 436 seconds

The regression mutates an ignored foundation file in the build callback and
confirms failure, no READY snapshot, and retained `build.log` plus
`failure.json`. Separate tests reject malformed source evidence and evidence
that changes between the initial deep cache check and seed publication. This
disposition is implementation evidence only; it is not self-approval, and a
fresh read-only review remains required.

Candidate-only read-only session `i004-reviewer-a02-cache-postbuild-candidate`
then requested two changes. First, the tracked-only post-build status check did
not reject a build-created, untracked `MIPStarRE/QPBT/*.lean` file. Second,
READY evidence with a different but syntactically valid source commit or
inventory could pass because fields were checked for shape rather than against
the identity-bound pin semantics.

Writable fixer session `i004-fixer-a02-authored-tree-provenance-binding`
addressed both findings. The cache identity now derives the committed authored
QPBT tree directly from Git blobs, and the post-build path combines a complete
tracked/untracked source status check with the exact materializer-authored-tree
comparison. Exact source facts are derived from the identity-bound committed
pin and compared field for field at verification and READY-read time. Tests
cover a build-created untracked Lean source, a committed authored-tree identity
change, and valid-shaped tampering of the source commit, inventory digest,
foundation counts, and authored-tree counts/digest.

Fixer start UTC: `2026-08-30T20:37:37Z`
Fixer end UTC: `2026-08-30T20:43:02Z`
Fixer elapsed: 325 seconds

The first focused run exposed an incomplete fake-repository ignore boundary:
the test fixture did not ignore generated `.lake/` output, so the new complete
status check correctly rejected it. The fixture was corrected to model the
canonical ignore contract, after which the focused and aggregate gates passed.
This disposition is implementation evidence only; it is not self-approval.

## Acceptance evidence

- Exact archive inspection passed with 839 filesystem members, 337 output
  files, 5,970,111 output bytes, and inventory SHA-256
  `d8d9e7632f5dcdb0cbe7bceeb55c71a0dbbcf6f901c6efd7f4c4814090d096db`.
- Local publication and verification passed; a deterministic rerun returned
  `cached` with the same inventory.
- `git ls-files MIPStarRE` returned no upstream path.
- `git check-ignore -q MIPStarRE/Quantum/Measurement.lean` returned 0;
  `git check-ignore -q MIPStarRE/QPBT/Future.lean` returned 1.
- Focused materialization tests: 11 passed.
- Focused hot-main cache tests: 20 passed, including two-process election with
  one materialization and one build.
- Aggregate Python tests: 101 passed.
- `python3 scripts/workflow.py validate`: passed with `valid: true`.
- `python3 -m compileall` for the changed Python files and tests: passed.
- `git diff --check`: passed.

## Residual gates and risks

No local Lean 4.32.0 toolchain or Mathlib package cache was available. Running
Lake would have attempted a network retrieval, which this session forbids, so
the empty-project Lean build and canonical cache warm remain unexecuted. This
acceptance gate must pass from the eventual committed head using an already
available dependency cache or an explicitly authorized acquisition. The
upstream no-license condition also remains unresolved; local materialization
does not imply permission to redistribute its source.

## Exact Lake package archive fallback

Writable fixer session `i004-fixer-a03-archive-package-materializer` added a
strict offline-capable fallback for the eight transitive packages pinned by the
root and Mathlib Lake manifests. `references/lake-packages.json` binds every
package name, scope, repository, exact Git revision, input revision,
configuration and manifest filename, inherited flags, codeload URL and prefix,
as well as the root and Mathlib manifest SHA-256 values. Acquisition-derived
archive, decompressed-tar, inventory, size/count and Git-tree fields are
explicitly `null` with a reason because this session had no authorized network
acquisition. Normal tool loading rejects any pending or partially populated
package; only schema inspection may opt into reading pending pins.

Fixer start UTC: `2026-08-30T21:04:20Z`
Fixer end UTC: `2026-08-30T21:18:42Z`
Fixer elapsed: 862 seconds

`scripts/materialize_lake_packages.py` admits already-downloaded archives or an
injected direct-argv transport template. The subprocess boundary uses
`shell=False`, a process-group timeout, discarded child output, a restricted
environment, exact URL/output placeholders and an argv credential scan. It
manually parses bounded gzip/ustar bytes, requires the exact global PAX commit
comment and archive prefix, and rejects traversal, duplicate paths, hardlinks,
unsafe symlinks, special files, local/GNU extensions, `.gitmodules`, missing or
non-directory parents and all count/byte excesses. Regular executable bits and
safe symlink text are preserved.

Every staged package is added through an isolated bare Git object database and
private work tree with system/global Git configuration disabled. Its computed
tree must equal the authenticated API tree SHA from the pin. Only after all
eight packages pass does one locked transaction replace their private
`.lake/packages/` directories and emit a complete Lake 1.2 path override.
Failure restores every displaced package and prior override; the original Git
manifests remain unchanged and continue to determine Mathlib cache hashes.

The first focused run found that rollback removed a prior override when package
publication failed before the override was displaced. Separate
`override_replaced` and `override_published` states fixed the error. The rerun
passed all 9 focused tests, including exact publication and verification,
semantic manifest rebinding, archive and tree mismatch, traversal, duplicates,
special files, gitlinks, oversize entries, symlink handling, complete rollback,
pending production pins, override completeness and direct argv/no-credential
transport. The aggregate suite passed all 110 tests. `compileall`,
`python3 scripts/workflow.py validate` (`valid: true`) and `git diff --check`
also passed. No network, Lake/Lean build, commit or canonical-state edit was
performed. These results are implementation evidence and not self-approval;
authenticated acquisition, complete production pin facts, the elected build
and fresh independent review remain required.

## Package cache recovery and no-update boundary

Writable session `i004-fixer-a04-package-cache-recovery-boundary` addressed
four accepted candidate-review findings and the subsequent frozen real-archive
format evidence. Its owned scope was extended to
`references/lake-packages.json` so the authenticated offline facts and closed
Gitlink contract could be recorded without embedding source facts in code.

Fixer start UTC: `2026-08-30T21:32:04Z`
Fixer end UTC: `2026-08-30T21:58:46Z`
Fixer elapsed: 1,602 seconds

The canonical hot-main recipe now binds both package pin and materializer into
its identity. The elected detached builder materializes and verifies all eight
packages before either permitted Lake command. Every Lake command contains the
exact `.lake/package-overrides.json` argument, and recipe construction rejects
missing or alternate overrides and all `update`/`--update` forms. The package
archive directory is supplied by the `LAKE_PACKAGE_ARCHIVES` environment
variable without placing a machine path in cache identity.

Publication now uses one deterministic, marker-backed transaction. Startup
disposes a committed cleanup tombstone or restores the complete prior set
before doing new work. Every cross-directory publication and recovery rename
fsyncs both parent directories. Successful publication moves transaction state
to a cleanup tombstone only after all eight packages and the override are
durable. Tests interrupt publication with `KeyboardInterrupt`, observe the
partial state, and prove that retry recovers and publishes one verified set.

Transport timeout handling polls the complete process group after the direct
child exits, sends SIGTERM, escalates remaining members to SIGKILL, and fails
closed if the group cannot be reaped. One real finite-descendant regression
proves bounded group waiting; a deterministic process-group regression proves
SIGKILL escalation.

Frozen offline inspection established the exact GitHub codeload modes:
directories `0775`, regular files `0664` or `0775`, and symlinks `0777`.
Regular modes normalize to Git modes `0644` and `0755`; directory modes are not
part of Git identity. The pin schema is version 2 and contains complete exact
archive/tar sizes and SHA-256 values, member/output facts, archive inventory,
raw archive tree, reconstructed API tree and an explicit Gitlink list for all
eight packages. Seven lists are empty. Aesop binds only
`lean_packages/std` as mode `160000`, type `commit`, SHA
`c2130e653bc1057f8f21196a9b89987d84fe247b`. The codeload placeholder must be
an empty directory; unpinned empty directories, missing or nonempty
placeholders, overlapping paths, alternate modes/types and malformed SHAs are
rejected. The isolated Git index injects only this pinned entry.

An independent frozen harness and a direct production `inspect_archive` run
matched all eight local archives. Seven archive and API trees coincide. Aesop
separately proves archive subset tree
`e26624e311c6cb94a40bd342de04630bb4b6c990` and reconstructed API tree
`942d19cef97fc177e3ddd90fc4d5ceaf0d4d8b31`. The tree helper has no default
Gitlink argument, preventing callers from silently reporting the subset tree
as the authenticated result.

The first focused command used dotted unittest names even though `tests/` is
not a Python package and failed discovery with two import errors; file-path and
aggregate discovery runs were used thereafter. A later structured pin rewrite
temporarily wrote `null` archive-tree fields; the production-pin regression
failed closed on the first package, the per-package mapping was corrected, and
both focused suites passed. Earlier frozen harness passes exposed the real
codeload modes and the Aesop Gitlink before the final eight-of-eight pass.

Final focused results are 14 package-materialization tests and 22 hot-cache
tests. The offline aggregate passed all 117 tests, and compileall passed for
the four changed Python implementation/test files. No network, archive
acquisition, Lake/Lean/cache build, commit, or canonical-state edit was
performed. These results are implementation evidence only; this fixer does not
approve its own work.

## Detached package bootstrap and path confinement

Writable session `i004-fixer-a05-detached-package-bootstrap-confinement`
addressed the four A06 candidate-review findings. Its owned scope added the
tracked `references/mathlib-lake-manifest.json` snapshot; no QPBT-002,
blueprint, canonical ledger or unrelated project path was edited.

Fixer start UTC: `2026-08-30T22:11:28Z`
Fixer end UTC: `2026-08-30T22:37:20Z`
Fixer elapsed: 1,552 seconds

The ignored Mathlib package directory is no longer a bootstrap prerequisite.
The new tracked snapshot is byte-for-byte equal to the exact ignored Mathlib
manifest used to derive the package pin: 2,811 bytes and SHA-256
`015c7e00ead0f05f2a72b32d9bdef782d4689d05a6297f0ceb0ab5d196c164bd`.
The package materializer authenticates and semantically reconciles this
snapshot with the root manifest and closed eight-package pin before creating
`.lake`. The canonical hot-cache recipe binds the snapshot into cache identity
and copies it into the detached clone before package materialization. A fake
detached-build regression proves that the snapshot exists while the ignored
`.lake/packages/mathlib/lake-manifest.json` does not, and that package
materialization and verification both precede the only two permitted Lake
commands.

Lake recipe validation now rejects `update`, every `--update` form, standalone
`-U`, and bundled short forms including `-qU` and `-Uq`. Every permitted Lake
command still contains exactly one canonical
`--packages=.lake/package-overrides.json` argument.

Package names and package-local config/manifest filenames now use a closed
ASCII path-component grammar: an alphanumeric first character followed only by
ASCII letters, digits, dash, underscore or dot, with a 128-byte character
bound. Traversal, absolute paths, separators, leading dots, spaces, shell
metacharacters and non-ASCII names are rejected before path construction.
Archive input/output, package, runtime, transaction, backup, stage and override
paths are constructed beneath held directory descriptors. The real transport
subprocess inherits only the exact bound archive-output descriptor it needs;
an actual no-network subprocess regression writes through that descriptor.

Repository, `.lake`, packages, runtime, transaction, backup and stage
directories are bound with `O_DIRECTORY|O_NOFOLLOW` and checked for stable
device/inode incarnation. Manifest, archive, lock and override file reads use
no-follow regular-file checks. Static regressions cover symlinked `.lake`,
packages, runtime, override, lock and transaction paths without changing an
external sentinel. Two injected publication races replace `.lake` and
`.lake/packages`; both are detected, rollback stays inside the held original
directories, and each replacement remains byte-for-byte sentinel-only.

Intermediate failures were confined to validation harnesses. The first focused
import exposed Python's `dataclass` dependency on an importlib module being in
`sys.modules`; the small descriptor records were changed to ordinary classes.
The next run exposed closed `/proc/self/fd` paths in Git subprocesses and two
rollback fixtures that had not created their package parent; descriptor
inheritance and fixture setup were corrected. The expanded symlink regression
then exposed an unnormalized `ELOOP` from the lock open and it was converted to
the materializer's fail-closed error. The first direct eight-archive inspection
command omitted its private per-package stage parents and failed before archive
inspection; the corrected command created those parents and matched all eight.

Final focused results are 18 package-materialization tests and 22 hot-cache
tests. The complete offline aggregate passed all 121 tests. `compileall`,
`python3 scripts/workflow.py validate` (`valid: true`) and `git diff --check`
passed. A direct production `inspect_archive` run matched all eight frozen local
archives. Seven raw and reconstructed tree SHAs coincide; Aesop again produced
raw archive tree `e26624e311c6cb94a40bd342de04630bb4b6c990` and authenticated
Gitlink-reconstructed tree `942d19cef97fc177e3ddd90fc4d5ceaf0d4d8b31`.
No network, archive acquisition, Lake/Lean/cache build, commit, canonical-state
edit or subagent was used. Model/runtime and token usage were not exposed. This
is fixer evidence only and is not self-approval.

## Selected package transaction rollback

Writable session `i004-fixer-a06-package-transaction-descriptors` addressed
the A07 candidate-review finding that same-process publication failure reopened
`runtime/transaction` by name even though publication still held authenticated
transaction, backup and stage descriptors.

Fixer start UTC: `2026-08-30T22:37:40Z`
Fixer end UTC: `2026-08-30T23:00:14Z`
Fixer elapsed: 1,354 seconds

Same-process rollback now receives the already-selected `BoundTransaction` and
restores packages and the override through its held root and backup descriptors
and the held project layout. It does not call pathname-opened restart recovery.
Disposal validates the selected transaction, backup and stage identities
relative to their held parent descriptors and removes the selected transaction
descriptor-relatively. If any ordinary directory instance was replaced, the
rollback clears only the held backup and stage instances and disarms only the
held marker; it neither opens nor removes the replacement instance.

Restart recovery remains a separate boundary. It opens the canonical
transaction, backup and stage once beneath held parent descriptors, loads and
validates the exact transaction marker through the selected root, rechecks all
directory identities and only then restores through the resulting descriptors.
There is no option to skip current-instance validation at this boundary.

Three deterministic regressions independently replace the transaction, backup
and stage with ordinary directories during publication. Every case proves that
all eight prior package directories and the prior override are restored from
the selected descriptors, while the replacement remains exactly one unchanged
sentinel file.

The final focused package suite passed 21 tests and the unchanged hot-cache
suite passed 22. The complete offline aggregate passed 124 tests. `compileall`,
`python3 scripts/workflow.py validate` (`valid: true`) and `git diff --check`
passed. Direct production inspection matched all eight frozen archives. Seven
raw and reconstructed Git trees coincide; Aesop again produced raw tree
`e26624e311c6cb94a40bd342de04630bb4b6c990` and Gitlink-reconstructed tree
`942d19cef97fc177e3ddd90fc4d5ceaf0d4d8b31`. The first inspection invocation
used the wrong local parent depth and failed before opening an archive; the
corrected offline invocation passed eight of eight.

No network, Lake, Lean, cache get/warm/build, acquisition, external endpoint,
commit, canonical-ledger edit or subagent was used. Model/runtime and token
usage were not exposed. This disposition is fixer evidence only and is not
self-approval.

## Selected package-child identity binding

Writable session `i004-fixer-a24-package-child-binding` addressed the A21
candidate-review findings that the injected publication operation could
substitute an existing package source, the existing override source, or a
staged package child while all three parent directories retained their bound
identities. The observed validation interval was
`2026-08-30T23:10:13Z` through `2026-08-30T23:19:39Z`; the coordinator owns
the complete issued-session interval.

Publication now binds every selected existing package directory, every staged
package directory, and the single-link regular override before the first
injected operation. It validates the selected source immediately before the
operation and the selected identity at the destination immediately afterward.
Regular-file binding additionally retains byte count, modification time and
link count. A final identity pass covers all eight published staged children
before transaction disposal.

Same-process rollback uses those retained child bindings. It searches only the
held package, backup, Lake and transaction descriptors for the selected
instances, moves them descriptor-relatively, and refuses to claim restoration
if an original cannot be found. Authenticated staged children are returned to
the selected stage for disposal. Substituted package, override and staged
children are moved unchanged beneath the held runtime descriptor under an
inode-qualified `rejected-*` name, outside both the published package set and
the disposable transaction.

Three deterministic regressions reproduce the A21 attacks. Package-source and
override-source substitution each strand the selected original under a sibling
name and move a sentinel replacement into the backup; a later injected failure
must restore the exact selected original and preserve the sentinel unchanged in
runtime quarantine. Staged-child substitution must fail, leave no package at
the canonical destination, and preserve its sentinel only in quarantine.

The final focused package suite passed 24 tests, the hot-cache suite passed 22,
and the complete offline aggregate passed all 127 tests. `compileall`,
`python3 scripts/workflow.py validate` (`valid: true`) and `git diff --check`
passed. Direct production inspection matched all eight frozen local archives,
including the authenticated Aesop tree
`942d19cef97fc177e3ddd90fc4d5ceaf0d4d8b31`. No network, acquisition,
Git administration, Lake, Lean, cache action, build, canonical-ledger edit,
external endpoint or subagent was used. The requested `gpt-5.6-sol` model was
not exposed by the runtime, and token usage was not exposed. This is fixer
evidence only and is not self-approval.
