# QPBT-004 formal immutable review

## Verdict

`request_changes` for the exact range
`77aa1a4ac947c1632ea57262d29d2753ba163c8a..b92935e98b1d631b88065c2b6887451c6ae416d4`.

Reviewer session: `i004-reviewer-a32-package-full-immutable`
UTC interval: `2026-08-30T23:48:10Z` to `2026-08-31T00:01:21Z` (approximately
791 seconds; the collaboration backend did not expose token or exact runtime
model telemetry). The reviewed head tree is
`a0380cceca1d5dd43d08a67483724188b566dadb`; the 15-path patch is 290,137
bytes with SHA-256
`a85a3a67b9616403bb089d3eb83a01907eb36380e8ceb29aa291280c489669d8`; the
framed manifest is 1,491 bytes with SHA-256
`0b37ad6aff8681fdd2f613cd5541fd68d52b04c9d8cf46d4f9372bbe22a6cd37`.

## Findings

1. **High, F-LPR005-001**: `scripts/hot_main_cache.py:1048-1118` verifies the
   package tree before dependency caching and compilation, but the post-build
   path only checks Git/source identity before publishing `.lake`. Because
   `.lake/packages` is ignored and `artifact_inventory` records whatever is
   present, a build-time package mutation can enter a READY cache. Add an
   identity-bound post-build package verification and a regression test before
   the publish rename.

2. **High, F-LPR005-002**: `scripts/materialize_lake_packages.py:1073-1088`
   locks a pathname without binding its inode/incarnation after acquisition.
   A replacement of the lock entry can allow a second materializer to acquire
   a different lock while the first still runs. Bind the lock file identity (or
   a stable runtime descriptor) and add a deterministic replacement race test.

## Checks

The reviewer independently reproduced package tests `24/24`, hot-cache tests
`22/22`, aggregate checks `127/127`, workflow validation, compileall, and diff
hygiene. The review used no network, Lake/Lean/cache materialization, build,
Git administration, edits, or subagents. The worktree remained clean.
