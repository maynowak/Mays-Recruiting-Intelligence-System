# RIS-JOBSEARCH-APPLICATION-ORCH-03C — Regression Triage

## Result: No RIS ApplicationV1 regression identified

The full repository suite ran with the isolated Python 3.14 environment:

```text
2300 passed, 27 failed, 56 skipped, 400 subtests passed
```

All 27 failures are outside ApplicationV1:

| Count | Group | Classification |
|---:|---|---|
| 3 | `test_composite_lifecycle.py` argument/output tests | Existing installer orchestration fixture does not reach the mocked child process; unrelated to RIS ApplicationV1 |
| 1 | composite AWS-context test | Missing local `mayaws` AWS profile; environment-dependent, no AWS access performed |
| 5 | credential symlink tests | Windows `WinError 1314`; symlink privilege unavailable |
| 14 | credential issue/revoke/list/CLI tests | Windows temp-directory permission precheck rejects the test fixture before the intended assertion |
| 2 | dependency-check CLI tests | Test invokes unavailable `python3` executable on Windows |

No ApplicationV1 test failed. No test was removed, disabled or reclassified as
PASS. Required reproductions are `python -m pytest tests/ -q` in a supported
POSIX/symlink-capable environment with the required AWS-profile fixture, or
with the repository's supported Windows credential-test setup.
