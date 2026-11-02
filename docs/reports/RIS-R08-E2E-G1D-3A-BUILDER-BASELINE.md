# R08-E2E-G1D-3A — BUILDER BASELINE REPAIR

**Status:** BUILDER PATH REPAIR COMPLETE / BASELINE STILL BLOCKED

## Scope

- Starting HEAD: `8669851074e59a43e21bfd5c953e2a17004c1339`
- No installation, AWS access, deployment or Terraform change
- No Jobsearch or Orders production changes
- Existing 39 untracked files preserved

## Reconciliation

The RIS baseline and the embedded Builder baseline were executed separately.
Their failure counts are not added together.

| Suite | Before | After |
|---|---:|---:|
| RIS available regression | 2,197 passed / 34 failed / 56 skipped / 339 subtests | **same** |
| Builder full available run | 256 passed / 68 failed / 30 subtests | **264 passed / 60 failed / 30 subtests** |
| Builder Lambda tests in isolation | not usable at runtime (`index` import path absent) | **76 passed / 0 failed / 30 subtests** |

The RIS count remains 34. The Builder failures are separate and are not
counted as RIS failures. Related RIS failures remain separately identified:
the RIS Lambda copy fixture, composite lifecycle, installer pin/STS, and
executable failures are not silently converted by the Builder repair.

## Selected root cause and repair

Builder Lambda tests use top-level imports (`index`, `errors`,
`order_service`, etc.) from `lambda/src`. The root collection isolation
correctly removed Builder paths before RIS tests, but this also removed the
Lambda path before Builder tests executed. Runtime-only mock targets then
failed with `ModuleNotFoundError: index`.

The root `conftest.py` now scopes the existing Builder Lambda source path to
each Builder Lambda test during `pytest_runtest_setup` and removes it during
teardown. The colliding top-level `installer` namespace is cleaned after
Builder runtime tests. This is test-harness isolation only; no Builder or
Orders implementation was changed.

## Remaining Builder failures

The 60 remaining Builder failures are grouped as follows:

| Group | Count | Evidence / classification |
|---|---:|---|
| Builder artifact integrity | 2 | Existing generated Lambda artifacts are stale. Rebuilding would be a Builder artifact operation and was not performed under the no-install/no-production-change boundary. |
| AWS profile context | 1 | `mayaws` identity requires unavailable AWS credentials. |
| Guide encoding/fixture | 1 | Windows decoding produces mojibake, so the expected German absence text is not found. |
| Builder installer CI tree | 33 | Expected `ci/` pipeline/buildspec/IAM files are absent from the preserved local Builder fixture; multiple assertions fail at the same missing-tree root cause. |
| Builder Lambda runtime/fixture | 11 | Tests now execute but several use the real DynamoDB-backed service path or fail with Windows subprocess/directory assumptions; isolated import collection is repaired. |
| Module-builder generated project | 12 | Generated layout/artifact assertions fail on Windows separators, missing `C:\tmp\opencode` fixtures, literal `python3`, and generated-tree differences. |

No security assertion was weakened and no expected result was changed to force
green.

## RIS remaining blockers

The RIS suite remains **2,197 passed, 34 failed, 56 skipped, 339 subtests**.
The 34 failures are the previously reconciled groups: preserved tfvars,
composite/Orders fixture, Lambda copy fixture, planned privacy routes,
project-root assumptions, Windows credential/symlink capability, installer
pinning/STS, and `python3` launcher assumptions. AWS/STS, credential and
privacy-scope findings remain explicitly separate blockers.

## Collection and cleanup

- Collection: **2,686 tests, 0 collection errors**
- No test services were started.
- Port `18000` was checked and is not listening.
- No tests were removed, disabled or reclassified.

## Commit

```text
test(ris): repair builder runtime test isolation
```

## G1D-4 readiness

**BLOCKED.** The selected Builder import-path root cause is fixed and the
isolated Lambda gate is green, but 60 Builder failures and 34 RIS failures
remain. AWS/STS, credential, privacy-scope, Builder fixture and executable
constraints require separate gates.
