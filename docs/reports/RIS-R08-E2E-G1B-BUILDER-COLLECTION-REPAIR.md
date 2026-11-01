# R08-E2E-G1B — BUILDER TEST COLLECTION REPAIR

**Status:** BUILDER COLLECTION VERIFIED / REGRESSION BASELINE BLOCKED

## Scope and safety

- Baseline: `449bf9da7be278887eac10ce7b20e02e53e2a218`
- No AWS calls, deployments, Terraform changes or productive erasure
- No package installation was performed in G1B
- Receipt journal and productive erasure remain disabled
- Jobsearch and Orders production code were not changed
- The 39 pre-existing untracked files were preserved

## Root cause

The generated Builder under `installer/projects/mays_order_builder` is a
separate Python project embedded in the RIS repository. Its tests intentionally
use top-level imports from several different working directories:

- `cognito_backup` and `module_builder` from the Builder root;
- `installer` from the Builder root, which collides with RIS's `installer`;
- Lambda modules such as `index`, `errors` and `state_machine` from
  `lambda/src`;
- seed tools such as `delete_seed_orders` from `scripts`.

Root-level pytest collection supplied none of these project-local import roots.
A global `PYTHONPATH` was rejected because it causes the Builder's `installer`
package to shadow RIS's `installer` package. The repair is the tracked root
`conftest.py`: it temporarily adds only the required Builder path during
Builder collection, then restores the RIS import namespace before root RIS
tests are collected. No Builder or installer runtime semantics were changed.

## Collection results

| Run | Result |
|---|---|
| G1 before repair | 2,360 collected, 16 Builder collection errors |
| Builder-only after repair | 329 collected; remaining standalone environment dependencies resolved by the existing local R07A environment |
| Full RIS collection after repair | **2,685 collected, 0 errors** |

The full collection was executed with the already-existing local R07A Python
environment. A temporary read-only `sys.path` append supplied its available
vendored HTTP modules; no package was installed or modified.

## Regression execution

The available RIS test suite was run without the deployed HTTP E2E test
`tests/test_http_e2e_integration.py`, because that test requires deployed
infrastructure and the G1B boundary forbids AWS calls.

Result:

| Result | Count |
|---|---:|
| Passed | 2,185 |
| Failed | 45 |
| Skipped | 56 |
| Subtests passed | 339 |

The 45 failures are not collection failures and were not hidden or converted
to skips. Representative pre-existing/environmental causes include:

- `terraform/ris-dev2.tfvars` is intentionally preserved but one test expects
  no local tfvars file;
- AWS CLI/profile-dependent tests cannot run in this no-AWS environment;
- Windows path separator assumptions in source-scanning tests;
- missing `C:\tmp\opencode` expected by Builder tests;
- tests invoking `python3` on Windows where only the Python launcher is
  available;
- existing wrapper/project-pinning and symlink/security baseline failures.

The 56 skips are retained as skips and include tests requiring unavailable
external/deployed conditions. No test was disabled or artificially marked
passing.

## Cleanup

- No Java or DynamoDB Local process was started for G1B.
- No test service was left active.
- Port `18000` was checked and is not listening.
- No foreign files or processes were removed.
- Temporary G1B result files were outside the repository and are cleanup-only
  artifacts.

## E2E-G2 readiness

**BLOCKED.** The Builder collection gate is now green, but G2 still requires
the unresolved G1 blockers: AWS/IAM authorization, version-aware S3 deletion,
distributed fencing, upload-ticket cutover, quiescence, G5 category coverage,
Object Lock/legal hold, retention approval, backup/restore reconciliation and
controlled activation evidence. The 45 regression failures also prevent a
clean full regression release claim.

## Commit

```text
test(ris): repair builder test collection
```
