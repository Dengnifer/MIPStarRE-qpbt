# Stage 1 Bootstrap Review Ordering Fix

## Scope

The A12 reviewer completed through the isolated nested-session transport but
blocked only because its own lifecycle record and the bootstrap seal necessarily
remain incomplete until that reviewer returns. The smallest fix adds an explicit
`--bootstrap-snapshot-digest` review phase contract.

The launcher accepts the contract only for an unborn `--uncommitted` target. It
runs the existing bootstrap verifier, matches the exact lowercase SHA-256,
requires the Stage 1 manifest to remain unsealed, and compares the complete
terminal-evidence contract against the freeze tool's fixed paths and rule. The
trusted prompt then explains the post-return lifecycle/seal ordering in built-in
text. No manifest prose is copied into authority.

Independent review initially requested two blocking changes. The final launcher
canonicalizes the trusted phase record and rejects extra, missing, or nonconstant
fields. It also reverifies after harness capture, byte-matches the copied freeze
manifest, and checks the captured core path set, sizes, and hashes against the
verified freeze before model dispatch. A mutation injected between initial
verification and capture now fails before the runner is called.

## Validation

- `python3 -m unittest discover -s tests -p 'test_local_agent.py'`: 30 passed.
- `python3 scripts/check_workflow.py`: 82 passed.
- `python3 -m compileall -q scripts tests`: passed.
- `git diff --check`: passed.

The package-style command `python3 -m unittest tests.test_local_agent` remains
unavailable because `tests/` is not a Python package; this is the existing
QPBT-011 discovery issue and is outside this Stage 1 acceptance fix.

## Independent Review

The first read-only review requested the canonicalization and post-capture
TOCTOU fixes described above. A fresh re-review of the revised four-file scope
returned `approve` with no findings. It checked the trusted/untrusted prompt
boundary, exact bootstrap preconditions, captured-evidence binding, CLI wiring,
isolation preservation, adversarial tests, and validation evidence.
