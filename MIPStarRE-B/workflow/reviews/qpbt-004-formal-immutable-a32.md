# QPBT-004 Formal Immutable Review Follow-up

Session `i004-fixer-a33-package-postbuild-lock` addressed the two blockers
reported by immutable review `i004-reviewer-a32-package-full-immutable`.

## Findings addressed

- The hot-cache builder now invokes the identity-bound Lake package verifier
  after dependency/build commands and before moving `.lake` into the staged
  cache. Verification time is accumulated in `package_verify_seconds`.
- Package materialization now serializes on the bound runtime directory
  descriptor and validates the selected lock path as one regular inode after
  acquisition. Replacing the pathname cannot create a concurrent election.

## Regression coverage

- `HotMainCacheTests.test_warm_rejects_post_build_package_drift`: mutates a
  package after the build; no `READY` snapshot is published and failure
  evidence is retained.
- `LakePackageMaterializationTests.test_replaced_lock_path_cannot_admit_concurrent_materializer`:
  replaces the lock pathname while held and proves a contender remains blocked
  until release.

Validation on 2026-08-31 UTC: hot-cache tests 23/23, package materialization
tests 25/25, `python3 -m compileall -q scripts tests`, and `git diff --check`.
The tests use isolated fake callbacks only; no Lake/Lean build, network access,
canonical hot-cache warm, Git administration, or canonical workflow/metrics
edits were used.
