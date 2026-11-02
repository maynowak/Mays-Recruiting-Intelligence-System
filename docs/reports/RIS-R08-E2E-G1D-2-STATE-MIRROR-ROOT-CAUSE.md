# R08-E2E-G1D-2 — STATE-MIRROR ROOT CAUSE ANALYSIS

**Status:** COMPLETE / STATE-MIRROR GATE GREEN

## Baseline and scope

- Baseline HEAD: `0cd9b6bbcab394d67fc903c8d685aabb7c0b66b5`
- References: G1C triage and G1D-1 boundary reports
- No AWS calls, installations, deployments or Terraform changes
- No Jobsearch or Orders changes
- No DynamoDB Local, Java or other background service started

The two failures were reproduced directly with the existing R07A Python
environment:

```text
tests/test_state_mirror.py::TestSnapshot::test_snapshot_records_a_sha256
tests/test_state_mirror.py::TestRotation::test_keeps_the_newest
```

## Finding 1 — SHA-256 mismatch

### Evidence

The fixture creates an LF-only JSON string. `StateMirror.snapshot()` computed
the digest from `raw.encode("utf-8")`, but opened the destination in ordinary
Windows text mode. Windows translated every `\n` to `\r\n` during the write.

Observed reproduction:

- source payload length: 341 bytes
- stored file length: 359 bytes
- filename digest prefix: source digest (`7775d0c3...`)
- `MirrorEntry.sha256`: digest of the CRLF-translated file (`0f926559...`)
- stored bytes were not equal to `raw.encode("utf-8")`

### Classification

**Actual implementation defect**, specifically Windows newline translation.
The test assumption was correct: the module documentation and method contract
promise that the payload is written verbatim and the digest represents the
stored bytes.

### Fix

`open(..., newline="")` now disables universal-newline translation. The raw
state bytes and recorded SHA-256 therefore remain identical on Windows.

## Finding 2 — newest-entry rotation

### Evidence

The implementation intentionally orders snapshots by `st_mtime_ns`, because
the filename timestamp has only second resolution. On this Windows filesystem,
rapid file creates received identical mtimes:

```text
serial 6: 1793604194007066500
serial 7: 1793604194007066500
serial 8: 1793604194009073100
serial 9: 1793604194009073100
```

The filename tie-breaker is digest-based and not write-order-based. As a
result, rotation retained `[9, 8, 6]` instead of `[9, 8, 7]`.

### Classification

**Actual implementation defect**, specifically reliance on filesystem mtime
precision that is not guaranteed for rapid Windows creates. The test correctly
expresses the documented write-order contract.

### Fix

After exclusive creation, the implementation assigns a strictly increasing
mtime using the previous snapshot mtime plus a safety interval. Existing
`entries()` and rotation logic remains unchanged; no filename or state format
architecture was introduced.

## Verification

| Scope | Result |
|---|---:|
| State Mirror + Terraform runner tests | **55 passed** |
| Available Builder regression | 256 passed, 68 existing Builder/environment failures, 30 subtests passed |
| Full available RIS regression (HTTP deployed E2E excluded) | **2,189 passed, 42 failed, 56 skipped, 339 subtests passed** |
| Collection | 2,685 collected, 0 collection errors |

The remaining 42 failures are the G1C/G1D-1 environment, Builder baseline,
Windows test-assumption, planned-scope and installer findings. The two
State-Mirror failures are no longer present. The G1D-1 boundary failure is
also no longer present.

## Cleanup

- No test services or background processes were left running.
- Port `18000` is not listening.
- The 39 pre-existing untracked files were preserved.
- No tests were disabled or weakened.

## Commit

```text
fix(ris): preserve state mirror bytes and rotation order
```

## G1D-3 readiness

**GO for G1D-3.** The two State-Mirror root causes are evidenced and fixed.
The broader G1 baseline remains non-green with 42 known unrelated failures and
56 scoped skips; those are not reclassified by this task.
