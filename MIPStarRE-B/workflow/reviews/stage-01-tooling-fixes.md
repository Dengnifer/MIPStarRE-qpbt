# Stage 1 Tooling Corrections

The blocked tooling review was split across three disjoint fixer sessions and
one nested state reviewer.

## Review harness

`i001-fixer-a01-review-harness` bound review targets to verified Git objects or
a frozen unborn-tree evidence repository. Reviewer authority comes from an
immutable base or a built-in bootstrap contract, never the reviewed head. The
wrapper records installed CLI capability and uses generic read-only `codex
exec` when selector plus trusted prompt is incompatible. Sixteen focused tests
and a live unborn-tree dry run passed.

## State invariants

`i001-fixer-a02-state-invariants` made status changes transition-only, issued
authority immutable, PR evidence append-only and SHA-bound, reviewer identity
independent, finding resolution fresh, ownership worktree-aware, timing
provenance enumerated, and formalization orchestrators mandatory. Its fresh
child reviewer reported eight findings; all were addressed. Twenty-five
focused tests passed after the final corrections.

## Hot-main cache

`i001-fixer-a03-hot-cache` bound the versioned canonical recipe into identity,
rechecked source and pins after builds, restricted seeding to compatible live
worktrees, and made replacement transactional. The coordinator then closed the
remaining artifact-integrity finding by binding manifest bytes to `READY` and
requiring deep source/destination inventories at seed time. Thirteen focused
tests passed, including two-process single-builder election and corruption,
symlink, wrong-target, and rollback cases.

The assembled repository remains subject to the frozen bootstrap review; this
delivery record is not approval.
