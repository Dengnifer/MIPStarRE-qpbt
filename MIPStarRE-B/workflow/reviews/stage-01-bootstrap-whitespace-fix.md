# Stage 1 Bootstrap Whitespace Fix

## Trigger And Scope

The first full-tree staging attempt failed `git diff --cached --check` because
fourteen untracked bootstrap files ended with a blank line. Ordinary unstaged
diff checks could not see this first-commit condition. This acceptance failure
authorized a narrow change to bootstrap text hygiene and removal of one final
newline from only the reported files.

`scripts/bootstrap_manifest.py` now rejects a final empty logical line and
records `blank_line_at_eof_paths` in its hygiene result. The focused regression
places `review me\n\n` in a core file and proves freeze fails with that field.

The first focused run exposed an incorrectly placed block in the test edit: the
second half of the existing core-mutation test had been nested under the new
test. The placement was corrected without changing product code; the rerun
passed.

## Validation

- `python3 -m unittest discover -s tests -p 'test_bootstrap_manifest.py'`:
  9 passed.
- `python3 scripts/check_workflow.py`: 83 passed.
- `python3 -m compileall -q scripts tests`: passed.
- `git diff --check`: passed.
- Disposable staging used bare Git directory
  `/tmp/qpbt-staged-check.NQzPAf/git` with this repository only as its worktree;
  `git add -A` followed by `git diff --cached --check` passed.
- `git diff --cached --name-only` in the real repository remained empty.

## Independent Review

- Session: `i001-reviewer-a15-bootstrap-whitespace`.
- Verdict: approve.
- Findings: none.

The reviewer reproduced all gates and proved that each of the fourteen named
files is exactly one byte shorter than its prior frozen entry, with
`sha256(current_bytes + b"\n")` equal to the recorded hash. No terminal
evidence or unrelated file was changed. Because the repository is unborn, the
prior bootstrap manifest is the available byte-level baseline rather than Git
history.
