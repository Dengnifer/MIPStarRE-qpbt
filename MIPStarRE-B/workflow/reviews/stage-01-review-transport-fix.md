# Stage 1 Reviewer Transport Fix

## Acceptance blocker

The reviewer retained `--ignore-user-config` for instruction/config isolation,
but that flag also removed the custom provider configuration from
`config.toml`. The health probe, which loaded user configuration, therefore did
not exercise the same transport path as the isolated full review.

The coordinator confirmed the missing configuration experimentally. Explicit
provider, endpoint, Responses-wire, and `requires_openai_auth=true` overrides
under `--ignore-user-config` reached the authorized `/responses` transport and
the empty-repository canary returned `{"isolated_provider":"ok"}` in 15.787
seconds. Exposed usage was 15,166 input, 11 output, 15,177 total, with 3,840
cached input tokens.

## Smallest sufficient change

`scripts/local_agent.py` now accepts an optional all-or-none non-secret review
transport profile. It validates a safe provider config key, non-empty provider
name, HTTPS endpoint without userinfo, credentials, query, or fragment, exact
`responses` wire API, and an explicit boolean `requires_openai_auth`. The five
values are emitted as top-level `-c` overrides before `exec`, while
`--ignore-user-config`, `--ignore-rules`, read-only sandboxing, and the isolated
harness remain in force. Dry-run and result envelopes record only this
non-secret profile; the wrapper has no credential input and does not read or
record authentication values.

The review CLI exposes the corresponding profile flags, including explicit
positive and negative forms for the authentication-mode boolean. The review
protocol documents the isolation and disclosure boundary.

## Validation

- `python3 tests/test_local_agent.py`: 26 tests passed.
- `python3 scripts/check_workflow.py`: 78 tests passed.
- `python3 -m py_compile scripts/local_agent.py tests/test_local_agent.py`: passed.
- `git diff --check -- scripts/local_agent.py tests/test_local_agent.py protocols/review.md`: passed.
- `python3 scripts/local_agent.py review --help`: all five transport flags present.

One exploratory package-style unittest command failed because `tests/` is not a
Python package; the direct focused command above is the repository-valid gate
and passed.

A fresh read-only child reviewer returned `approve` with no findings after
checking validation, TOML encoding and argv order in both execution modes,
isolation retention, envelopes, CLI wiring, and the gates above. Residual risk:
the subprocess tests use fake runners, so live routing rests on the successful
isolated-provider canary rather than a second external model session.
