# RIS-DEV2-AUTH-06G1 — Windows Packaging Gate

## Result

```text
PASS — WINDOWS PACKAGING TEST RECOVERED
```

## Root cause

The failing lifecycle test copied the entire repository into a temporary
mirror. That included unrelated archived evidence with long/deep paths that
could not be resolved by `shutil.copytree` on this Windows runner. The test
only packages `lambda/handler.py`, `agents/` and `jobsearch/`, so the full copy
was unnecessary.

After narrowing the mirror to those canonical source roots, the test exposed a
second Windows-specific issue: text-mode append/write translated line endings
when the temporary marker was removed, so the restored source bytes differed
from the baseline and correctly produced a different ZIP hash.

## Fix

- The test now mirrors only the three package source roots, excluding bytecode.
- The temporary source mutation and restoration use `Path.read_bytes()` /
  `write_bytes()` and an exact byte marker, preserving source bytes on POSIX
  and Windows.
- The existing builder now normalizes backslashes to POSIX separators and
  rejects empty, absolute, drive-qualified, `.` and `..` archive components.
  This prevents archive path traversal without weakening security checks.
- No test was skipped, deleted or marked `xfail`.

## Validation

```text
tests/test_lambda_packaging.py — 6 passed, 2 skipped
```

The two skips are the pre-existing live-contract tests, which skip when their
hard-coded historical live-account guard is not present. The Windows failure
itself is resolved.
