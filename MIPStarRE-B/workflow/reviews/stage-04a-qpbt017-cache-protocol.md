# QPBT-017 cache-protocol readiness audit

Audit target: canonical main `8bf8ee89d24d833c28ecce6ce7e08c42e28b614f`
(`65315213d047d9181804ad74d573f533c904ef4f` parent). This was a read-only
audit: no files other than this worker-owned report were edited; no network,
Lean, Lake, hot-main warm/seed, or build commands were run. Elapsed time was
approximately 5 minutes. Token usage is unavailable from the collaboration
backend.

## Findings

QPBT-017 is still `planned`, has dependency `QPBT-004`, and names four gates
(`workflow/state/issues.json:542-566`): enumerate all identity inputs/recipe
commands/archive prerequisites, add a focused omission regression, record the
sync in the changelog, and obtain a fresh local review. INC-033 records the
same documentation drift (`research/metrics/incidents.jsonl:33`).

The canonical recipe is materially richer than the operator text:

- `BuildRecipe` identity payload includes schema version, recipe id, version,
  dependency/build/materialize/package-materialize/package-verify argv,
  additional identity files, and `test_only`
  (`scripts/hot_main_cache.py:75-115`).
- The canonical recipe is `qpbt-hot-main`, version `4`; dependency argv is
  `lake --packages=.lake/package-overrides.json exe cache get`; build argv is
  `lake --packages=.lake/package-overrides.json build`; foundation materialize
  argv is `python3 scripts/materialize_mipstarre.py materialize --archive-env
  MIPSTARRE_ARCHIVE`; package materialize argv is `python3
  scripts/materialize_lake_packages.py materialize --archive-directory-env
  LAKE_PACKAGE_ARCHIVES`; package verify argv is `python3
  scripts/materialize_lake_packages.py verify`
  (`scripts/hot_main_cache.py:145-168`).
- In addition to `lean-toolchain`, `lakefile.toml`, and `lake-manifest.json`,
  the identity hashes these five committed files:
  `references/mipstarre-upstream.json`,
  `scripts/materialize_mipstarre.py`, `references/lake-packages.json`,
  `references/mathlib-lake-manifest.json`, and
  `scripts/materialize_lake_packages.py`
  (`scripts/hot_main_cache.py:382-393,418-433`).
- The key payload also binds the exact source contract, and readiness requires
  matching source contract/evidence and recipe fields
  (`scripts/hot_main_cache.py:614-655,835-869`). The source-contract fields are
  schema version, pin SHA-256, source commit, inventory SHA-256, file/byte
  counts, and authored-QPBT file/byte/SHA-256 facts
  (`scripts/hot_main_cache.py:256-287,347-379`).
- Archive variables are hard prerequisites, not descriptive labels:
  `MIPSTARRE_ARCHIVE` must be nonempty for foundation materialization
  (`scripts/materialize_mipstarre.py:906-931`), and `LAKE_PACKAGE_ARCHIVES`
  must be nonempty for package materialization
  (`scripts/materialize_lake_packages.py:2031-2073`).

`protocols/local-development.md:29-36` currently documents only main SHA,
the three core pin hashes, and the dependency/build recipe id/version/argv.
It has no occurrences of `additional_identity_files`, either archive variable,
the materialization/package commands, or source-contract/evidence fields. Its
warm description (`:38-63`) also does not state these prerequisite commands.

Existing cache tests validate implementation behavior, but not synchronization
of the operator document. `tests/test_hot_main_cache.py:274-347` checks test
materialization/package ordering and identity files, and `:374-408` checks
Lake override/update rejection; `:580-600` checks recipe-bound readiness.
`tests/test_focused_command.py:23-39` only checks the focused workflow command
and package-style invocation. A repository-wide search found no test that
requires the protocol to contain every canonical recipe field/command/archive
variable.

## Smallest compliant patch

1. Extend the hot-main section of `protocols/local-development.md` with a
   machine-checkable canonical inventory: recipe id/version and all five argv
   arrays; all three core and five additional identity files; the source
   contract/evidence field names; and the required `MIPSTARRE_ARCHIVE` and
   `LAKE_PACKAGE_ARCHIVES` environment variables (including that they must be
   nonempty local archive paths). Keep the existing singleton lock/seed rules.
2. Add an isolated focused test (prefer a new
   `tests/test_cache_protocol.py`, avoiding ownership overlap with the already
   large hot-cache suite) that imports `scripts.hot_main_cache` and asserts
   every canonical value above appears in `protocols/local-development.md`.
   The test must mutate an in-memory protocol string or fixture and assert the
   omission fails, so deleting any field/command/prerequisite cannot silently
   pass. Do not change `scripts/hot_main_cache.py`.
3. Add a changelog entry under the next candidate revision in
   `protocols/CHANGELOG.md`, naming INC-033, the canonical SHA, the docs/test
   paths, and the exact focused command/result. The current ledger still marks
   `workflow/state/protocols.json:3` active revision `0.1.4`; the entry must not
   silently rewrite that canonical state. Root should reconcile the revision
   record through the normal state protocol if the PR is accepted.

## Gates and ordering

For the worker PR: run the exact focused test path (for example,
`python3 tests/test_cache_protocol.py`), `python3 -m py_compile` on the new
test, `python3 scripts/check_workflow.py`/the registered workflow checker as
applicable, and `git diff --check`. Since this is docs/test-only and does not
change cache implementation, no hot-main warm or Lean/Lake build is required
by the patch itself; record that the cache gate remains a separate QPBT-004
acceptance prerequisite. Before approval, run the issue's full recorded
checks, `python3 scripts/workflow.py validate`, and obtain a fresh read-only
reviewer on an immutable base/head pair. The reviewer must verify source
fidelity, exact command spellings, all identity fields, archive prerequisites,
and absence of implementation changes or untracked state.

The patch is technically independent of QPBT-004 (it only documents and tests
the already committed recipe), but it is not dispatchable under the current
issue DAG: `QPBT-017` explicitly depends on `QPBT-004`, which remains planned
and has an unresolved cache-gate unblock condition (`workflow/state/issues.json:
163` and QPBT-004 record). Do not bypass that edge. After QPBT-004 is completed
and its fresh singleton cache gate is recorded, QPBT-017 can be issued as an
independent docs/test lane, subject to checking no active candidate owns the
same protocol files.

## Negative searches and constraints

- No `MIPSTARRE_ARCHIVE` or `LAKE_PACKAGE_ARCHIVES` mention exists in
  `protocols/local-development.md` or `protocols/CHANGELOG.md`.
- No protocol-sync regression exists in the focused tests; current matches are
  implementation fixtures/assertions only.
- No source, blueprint, issue/PR/session ledger, cache artifact, or generated
  file was changed by this audit.
