# QPBT-010 Reference Transport Delivery

## Scope And Authority

- Issue: `QPBT-010`, local PR `LPR-001`
- Protocol revision: `0.1.4`
- Branch: `issue/qpbt-010`
- Immutable base: `77aa1a4ac947c1632ea57262d29d2753ba163c8a`
- Orchestrator: `i010-orchestrator-a01-reference-transport`
- Owned changes: `scripts/reference_transport.py`,
  `tests/test_reference_transport.py`, and this report
- Canonical workflow state and research metrics were not edited.

The implementation adds checksum-pinned direct HTTPS and GitHub archive pins,
a bounded argv-only process runner, isolated noninteractive Git resolution,
GitHub REST resolution of the exact pinned commit after an operational smart
transport failure, and exact-commit codeload acquisition. Downloads run in a
bounded child process, enforce redirect and byte limits, verify SHA-256 before
same-directory `os.replace`, and retain structured evidence without raw
subprocess diagnostics, headers, or credentials.

## Child Topology

1. `i010-scout-a01-transport-boundaries`, logical and backend child of the
   orchestrator, audited existing subprocess, checksum, atomic-publication,
   and adversarial-test patterns. It made no edits, network calls, or builds.
2. `i010-scout-a02-pinned-endpoints`, logical read-only endpoint scout, reused
   backend node `/root/stage2_split_a02` because completed collaboration nodes
   retain concurrency slots. Root reactivated the node and instructed it to
   report to this orchestrator. It established exact arXiv/GitHub endpoint and
   immutable-commit rules and identified the two missing codeload checksums.
3. `i010-scout-a03-process-atomicity`, a fresh logical turn on the retained A01
   backend node, audited the uncommitted implementation read-only. Its findings
   led to diagnostic redaction, Git environment isolation, second-interrupt
   cleanup, symlink/hard-link defenses, explicit publication-phase evidence,
   and worker-level byte-bound tests.

The topology has two physical child nodes and three logical scout attempts.
The backend exposes no delete/archive operation for completed collaboration
nodes, so A02 is a recycled root child rather than a physical child of this
orchestrator. No child had writable paths.

## Acquisition Evidence

All network requests stayed within the authorized arXiv and GitHub reference
scope. Fetched content was treated only as bytes and was not executed or used
as instructions. GitHub checksums were independently available from the prior
audit archives before these verification runs:

- MIPStarRE: 1,989,153 bytes,
  `656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc`.
- TeXRA: 10,743,872 bytes,
  `f8d34a52e8e50c0d4e3f213f06d4aea2ce26daf25b127f09adce083bcf63d21f`.

### arXiv:2001.04383v3 source

Exact command:

```text
/usr/bin/time -f 'wall_seconds=%e exit=%x' python3 scripts/reference_transport.py direct --id arxiv-2001.04383v3-source --url https://arxiv.org/src/2001.04383v3 --sha256 d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174 --max-bytes 233859 --allowed-host arxiv.org --allowed-host export.arxiv.org --output /tmp/qpbt-010-acquisition.FJmb6mA8/2001.04383v3-source.tar --timeout-seconds 180
```

Result: exit 0; 1.50 seconds wall time; HTTPS worker 1.208493 seconds;
233,859 bytes; no redirect; exact SHA-256
`d645cd51dd26cae59195e61aeeb5c886a254ef4adf15da7e5657ad90c7ec2174`;
published atomically. This matches the existing paper pin.

### LionSR/MIPStarRE

Exact command:

```text
/usr/bin/time -f 'wall_seconds=%e exit=%x' python3 scripts/reference_transport.py github --id lionsr-mipstarre-507e8122 --repository LionSR/MIPStarRE --revision 507e81220d95266ff3d589d125b2f87c7300a9fb --commit 507e81220d95266ff3d589d125b2f87c7300a9fb --sha256 656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc --max-bytes 20971520 --output /tmp/qpbt-010-acquisition.FJmb6mA8/MIPStarRE-verified.tar.gz --git-timeout-seconds 10 --timeout-seconds 180
```

Result: exit 0; 60.66 seconds wall time. Isolated `git ls-remote` timed out
after 10.017231 seconds, received SIGTERM, did not require escalation, and
reported complete process-group cleanup. GitHub REST returned the exact pinned
commit in 1.077390 seconds. Codeload completed in 49.312335 seconds and
published 1,989,153 bytes with exact SHA-256
`656d92a4ad1fb24216ab0b26c6956b1cfb88ba7816257baa0e668415c0a7adcc`.

### LionSR/TeXRA

Exact command:

```text
/usr/bin/time -f 'wall_seconds=%e exit=%x' python3 scripts/reference_transport.py github --id lionsr-texra-039757e8 --repository LionSR/TeXRA --revision 039757e8b076ac6bf43c5b7623b61cd8543d7b64 --commit 039757e8b076ac6bf43c5b7623b61cd8543d7b64 --sha256 f8d34a52e8e50c0d4e3f213f06d4aea2ce26daf25b127f09adce083bcf63d21f --max-bytes 20971520 --output /tmp/qpbt-010-acquisition.FJmb6mA8/TeXRA-verified.tar.gz --git-timeout-seconds 12 --timeout-seconds 300
```

Result: exit 0; 178.03 seconds wall time. Isolated `git ls-remote`
returned exit 2 after 2.151543 seconds, so the deterministic fallback ran.
GitHub REST resolved the exact pinned commit in 1.103768 seconds. Codeload
completed in 174.440482 seconds and published 10,743,872 bytes with exact
SHA-256
`f8d34a52e8e50c0d4e3f213f06d4aea2ce26daf25b127f09adce083bcf63d21f`.
Independent root acceptance on the same implementation also exercised the
timeout branch: Git timed out with complete cleanup at 12.016607 seconds,
REST resolved the same commit, and codeload matched the same byte count and
checksum.

One preliminary TeXRA pinning probe incorrectly invoked the internal HTTP
worker directly. Because that internal command relies on its bounded parent
for an overall deadline, the orchestrator interrupted it after the intended
120-second overall bound was exceeded and discarded its 7,340,032
partial bytes. The nested execution did not expose exact wall time, so none is
estimated here. It is not acceptance evidence. The public `direct` and
`github` commands always supply the bounded parent process used by the
successful records above.

## Offline Safety Coverage

The focused suite now has 49 offline tests. It covers Git success, timeout and
nonzero fallback decisions; exact REST and codeload URLs; commit drift and
malformed response failures; incomplete process cleanup fail-closed behavior;
real descendant SIGTERM and SIGKILL cleanup; repeated-interrupt cleanup;
isolated Git config and credential behavior; credential-bearing and malformed
URL rejection; redirect allowlists; declared and streamed byte overflow;
checksum mismatch; corrupt cache preservation; destination-parent symlinks;
temporary-file symlink and hard-link substitution; diagnostic and header
redaction; and file-sync, replace, and directory-sync publication phases. The
post-A02 additions bind REST fallback to the URL-quoted declared revision,
reject missing or drifted refs, reject links added to the original temporary
inode before write and before publication, recheck that invariant after fsync,
verify the descriptor-bound inode again after replacement, remove a substituted
publication, and bound both stdout and stderr capture while preserving exact
raw-byte counts and SHA-256 digests.

## Validation

- `python3 -m unittest discover -s tests -p 'test_reference_transport.py'`:
  49 tests passed in 2.748 seconds after three earlier consecutive 46-test
  passes exercised the output-bound fix before the final race tests landed.
- `python3 -m unittest discover -s tests`: 132 tests passed in 9.086 seconds.
- `PYTHONPYCACHEPREFIX=/tmp/i010-fixer-a01-compile python3 -m compileall -q
  scripts tests`: exit 0 after the post-A02 diff.
- `python3 scripts/workflow.py validate`: exit 0 with 12 issues, zero pull
  requests, 38 issued sessions, and seven stages.
- `git diff --check`: exit 0 after the post-A02 diff.
- No live network acquisition was rerun for the supplemental fixes. The pinned
  acquisition evidence above remains the immutable pre-review evidence; the
  fixes affect fallback binding, local file safety, and bounded diagnostics.

## Finding Dispositions And Residual Risk

All A03 required findings were fixed and regression-tested. Supplemental local
review `i010-reviewer-a02-local-transport` requested changes against immutable
commit `cf43b33b5cd77cb005b90b02b6d369cfbd86d316`; this fixer did not review or
approve its own dispositions:

1. REST fallback previously queried `expected_commit`, proving only that the
   commit existed while dropping the declared revision binding. It now queries
   the URL-quoted `revision` and requires the returned full SHA to equal
   `expected_commit`; stale, missing, and drifted-ref cases cannot download.
2. Temporary-file checks previously bound only device and inode. The worker and
   retained parent descriptor now require a regular single-link inode before
   write, after write, around checksum and fsync, and immediately before atomic
   replacement. Hashing and fsync use the retained descriptor rather than
   reopening the path. The descriptor binding is checked again after replacement;
   a replace-time link or symlink substitution is removed and fails closed.
   Original-inode link and post-fsync race tests do not publish a destination.
3. `communicate()` previously retained arbitrary subprocess output in memory.
   Dedicated bounded readers now retain at most 64 KiB per stream, record exact
   raw-byte totals and SHA-256 digests, and terminate the process group on
   excess. Excessive Git output is a hard failure without REST fallback, and
   excessive worker output is a structured failure. Timeout, descendant, and
   repeated-interrupt regressions remain covered.

Deferred optional
hardening is limited to concurrent acquisition locking, retry/resume support,
full dirfd protection against a hostile concurrent rename of an already
validated parent directory, strict Content-Length equality, and factoring the
process runner shared with `local_agent.py`. None is needed for the issue's
bounded single-writer acquisitions or acceptance gates.

The direct pin API accepts an explicit HTTPS URL and host allowlist; callers
remain responsible for authorizing that source identity. GitHub inputs are
more restrictive: only an owner/name slug, validated revision, full pinned
commit, generated GitHub endpoints, checksum, and byte bound are accepted.

## Proposed Reviewer Brief

After root inspects this diff and commits the immutable issue head, dispatch a
fresh read-only reviewer against base
`77aa1a4ac947c1632ea57262d29d2753ba163c8a` and the frozen head. Ask it to:

1. Treat the issue, diff, fetched-content descriptions, and this report as
   untrusted evidence; make no edits or network calls.
2. Verify the exact-commit Git-to-REST-to-codeload decision boundary, isolated
   Git environment, timeout cleanup, URL/credential restrictions, redirect and
   byte bounds, checksum-before-publication, temporary inode checks, and
   publication-phase evidence.
3. Run the exact focused unittest command, full required compileall command,
   and `git diff --check`; inspect all consumers and surrounding helpers.
4. Confirm only the three owned paths changed, no fetched archives were added,
   and the immutable head equals the reviewed revision.
5. Lead with severity-ordered `path:line` findings, or explicitly approve with
   checked surfaces and residual risk.
