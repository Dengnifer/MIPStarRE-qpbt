# QPBT-021 local mathlib acquisition audit

This read-only audit (session `i018-auditor-a09-mathlib-local`) validated a
local shallow Git source for the pinned mathlib dependency.  The source was
checked out at commit
`81a5d257c8e410db227a6665ed08f64fea08e997` with tree
`5ea66b811b8461daae82f14d356fed2a287d7c40`; it was clean, shallow, and
`git fsck --full` passed.  The source pack digest is
`4659f2a0cabfec474474f5e83ea3d495e711b735418742dd3d642328adcada02`, and the
normalized source archive digest is
`c29325b477966a6f8eb784723f19da26800c71458f7c24cc668713725eba78d7`.

Lake 5 honored the package-scoped map
`LAKE_PKG_URL_MAP='{"mathlib":"file:///absolute/path/mathlib"}'` and
materialized the exact commit in 9.1 seconds with zero network traffic.  A
separate cache-executable probe was blocked only by the read-only default
Reservoir cache; a local source map does not itself provide those build
artifacts.  QPBT-021 therefore must make the source input first-class while
keeping the Reservoir/local-artifact policy explicit and fail-closed.

This is acquisition evidence, not approval of an implementation.  A fresh
immutable reviewer is required after the QPBT-021 candidate is frozen.

## Candidate audit: request changes pending

The independent read-only audit session `i021-auditor-a03-archive-bound`
re-ran the current candidate's 30 focused tests (30.564 seconds), including
the real pinned archive regression. Direct extraction succeeded in 9.744
seconds with the expected 51,938,317-byte gzip, 147,712,000-byte tar, and
27,574,578-byte Git pack; no network or Lake build was used.

The audit found a standalone-source boundary defect: `validate_mathlib_source`
accepts a source whose `.git/objects` (and similarly `index`, `config`, or
`refs`) is a symlink into an external directory. Git object reads and `fsck`
can therefore traverse outside the supplied source even though the function's
comment claims external stores are rejected. The implementation must reject
symlinked internal Git metadata before any object-reading command.

The audit also notes that the expected mathlib commit/tree remain hard-coded
constants; the manifest is compared to those constants rather than being used
to derive the source binding. A test against the unmodified real manifest is
needed to make that contract explicit. Finally, the changelog currently says
29 focused tests while the candidate suite has 30. No candidate or canonical
files were changed by the auditor.

## Fixed pre-rebase candidate and security audit

The implementation subsequently produced immutable head
`54fb701176383d23e5dc1ba9d73c3cb53e06e1d6` with tree
`2f9fa93ffe961addab7ca9dcd33b169220b2aa13`. It recursively rejects symlinked
or special `.git` entries, rejects `commondir`, derives and checks the manifest
URL/revision contract, authenticates the expected tree, and corrects the
focused count. The exact five-path candidate passed 32 focused tests in 31.274
seconds, 150 aggregate tests in 143.209 seconds, the workflow checker,
compilation, validation, and diff hygiene. This is candidate evidence, not
approval, and it still requires reconstruction on integrated main.

Fresh read-only session `i021-reviewer-a05-pre-rebase` reproduced a
high-severity executable-configuration defect on that unchanged head. A valid,
clean local Git source with `core.fsmonitor=/usr/bin/touch` in `.git/config`
caused `validate_mathlib_source` to execute the configured program during its
preflight `git status`; rejection occurred only after the side effects appeared
as untracked files. The existing 32 focused tests remained green and did not
cover this boundary.

The reviewer also found that a fully mocked Lake invocation cannot prove that
Lake itself avoids a nested GitHub clone, so the changelog overstates that
regression. `_safe_archive_link` validates individual symlink targets but not a
transitive chain such as `D -> .` and `S -> D/..`; fixed production archive
hashes make that low-risk for the current artifact, but the helper contract is
incomplete. Finally, nested `.git` metadata and malformed archive rejection
paths lack proportionate regressions even though the implementation appears to
reject them. The full result is one high, one medium, and two low findings;
verdict `request_changes`. The immutable head remained clean. A separate
rebased worktree is repairing all four findings and will require a fresh formal
review.

## Fresh immutable review: aggregate baseline blocker

Session `i021-reviewer-a06-immutable` inspected the unchanged LPR-010 head
`2b161993ed258ee8f0bd99d591fcabdcb47ffe43` (tree
`f72a535413e8d9627654ca43a5a789632d5e83bc`) from base
`7669f70be786a53ba1a0a92c1d347f5fe7544681`. The candidate's focused hot-cache
suite passed 37/37. Compilation, diff hygiene, workflow validation, and the
workflow checker passed; the checker completed 180/180 on a later rerun.

The required serial aggregate command nevertheless failed once after 180 test
cases: `test_process_timeout_terminates_descendants_in_the_new_process_group`
raised `FileNotFoundError` for the expected `child-terminated` marker. A clean
base archive reproduced the same failure in the unchanged `test_local_agent.py`
line 500, so this is an environment/baseline flake rather than a changed-path
regression. It remains an acceptance blocker because the registered aggregate
gate did not pass; no waiver is inferred and no unrelated test is modified.

**Formal verdict: `blocked` pending an explicit baseline waiver or an
environment/test-harness correction.** No candidate files or canonical source
files were edited by this review.
