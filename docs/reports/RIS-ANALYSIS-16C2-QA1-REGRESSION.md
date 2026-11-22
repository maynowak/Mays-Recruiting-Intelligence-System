# RIS-ANALYSIS-16C2-QA1 â€” Full Regression Recovery

**Date:** 2026-11-22
**Base:** `95b7c4f` on `feature/ris-analysis-integration-07`
**Scope:** test-environment recovery, Mays-Orders fixtures, full regression.
**No Terraform apply, no AWS mutation, no synthetic activation B, no Mays
transport C, no main merge, no production deployment.**

---

## 1. Test environment repaired

Isolated venv:
`C:/Users/DCI-Student/AppData/Local/Temp/opencode/ris-qa1-venv`

Installed from the existing requirements plus the two missing test modules:

| Package | Version |
|---|---|
| pytest | 9.2.0 |
| pytest-subtests | 0.15.0 |
| requests | 2.34.2 |
| moto | 5.2.5 |
| boto3 / botocore | 1.44.9 |

`requirements.txt` now lists `pytest-subtests>=0.11.0` and
`requests>=2.31.0` under Testing. No production dependency changed.

### `ConsentContext` NameError

Root cause: the three consent test modules wrapped their imports in
`try/except ImportError`, set `boto3`/`mock_aws` fallbacks, and then used
`ConsentContext` unconditionally. A missing `moto` produced a `NameError`, not
a consent-logic failure.

Minimal fix:

- skip cleanly with the missing dependency when `moto`/`boto3`/`botocore` is
  absent;
- let every other `ImportError` propagate;
- update the expected purpose lists for the current `analysis-processing`
  purpose.

Consent state/grant logic was **not** weakened.

## 2. Mays-Orders integration fixtures

| State | Value | Use |
|---|---|---|
| RIS pin | `5cf50a0` | Composite installer tests |
| Generated module | `016cdfd` | Contract/module tests; actual applied module |
| Local review checkout | `9627eb2` | Review reference only; not used for assertions |

Added an ignored detached worktree:

`installer/projects/mays_orders` @ `5cf50a0`

This is a local test fixture, not a Mays code change. Composite lifecycle:
**43 passed** (previously 40 passed / 3 blocked).

Extended Mays run (`MO_ORDERS_SRC`/`MO_ORDERS_MODULE` = generated `016cdfd`):

- **54 passed**
- **1 known failure**:
  `test_generated_module_artifact::test_ris_transport_outputs_are_exposed_additively`

Finding: the generated module `016cdfd` exposes 20 outputs but not
`results_queue_url`, `results_queue_arn` or `result_hmac_secret_arn`. The
builder's `--check` currently passes with that output set. The test expects the
additive RIS result outputs. This is a **module-contract drift**, not an apply
regression; the applied plan does not consume those module outputs. The
generated module was not edited.

## 3. Additional test-harness fixes

- Windows `st_mode`/symlink limitations: skip only the POSIX ACL/file-mode and
  symlink tests on Windows; production output checks remain intact on POSIX.
- Windows-only POSIX mode check in `tools/ris_admin/credentials.py`: the
  Windows `st_mode` cannot represent ACL bits; the symlink/O_EXCL checks remain.
- `test_dispatch_ingress_env`: added the Correction-14 `WORK_ITEMS_TABLE` and
  queue config, with boto3 clients mocked.
- `test_platform_handlers`: added `WORK_ITEMS_TABLE` and corrected the tenant
  claim to `custom:tenant_id`.
- `test_health_plane_integration`: terminal entitlement denial is now
  `DEAD_LETTER` (Correction-14), still not a health degradation.
- `test_dependency_check`: use `sys.executable` instead of Linux-only
  `python3`.
- ATS HTTP mock: set `status_code=200` for the response contract.
- `test_lambda_bridge_e2e`: updated to the Correction-14 persist â†’ work queue â†’
  worker path; registers the addition agent and uses a fake SQS.
- Mays env isolation: `ORDERS_TABLE` is restored after the standalone E2E and
  unsigned-result tests.

## 4. Results

### Default full suite (no optional Mays/parser fixtures)

**3185 passed, 134 skipped, 0 failed, 441 subtests passed.**

This is the full `tests/` suite with the isolated venv and a temporary
`mayaws` credential-process alias.

### Full suite with all available local fixtures

**3250 passed, 68 skipped, 1 known failure, 441 subtests passed.**

The one failure is the generated-module output drift in section 2.

### Focused evidence

| Area | Result |
|---|---|
| Five agent packages | **all VALIDATED** |
| Agent lifecycle/install (INSTALL, UPDATE, ENABLE, DISABLE, DETACH_PARTNER, UNINSTALL, PURGE block, VERIFY) | **34 passed** |
| Composite lifecycle with `5cf50a0` fixture | **43 passed** |
| Saved-plan installer + plan/shared-infra guards | included in **376 passed, 12 subtests** |
| Analysis CV/job/match, offers, entitlements, synthetic identity | included in focused/full runs |
| OrdersPort status/result, reader, agent gate | included in focused/full runs |
| Mays contract/dispatch/handoff | included in focused/full runs |
| Addition/ATS local regression | **95 passed, 9 subtests** |
| Parser matrix with local Node CLI | **15 passed** |

### Comparison with 16C2

16C2's **739 passed / 41 skipped / 13 subtests** was a focused relevant
subset. QA1 ran the complete `tests/` suite: 3185 default, 3250 with fixtures
(plus the one documented module-contract failure).

## 5. Remaining skips (fixture run, 68)

| Reason | Count |
|---|---:|
| Local DynamoDB not configured (`RIS_TEST_DYNAMODB_ENDPOINT` absent) | 39 |
| Windows POSIX ACL/file-mode or symlink privilege | 12 |
| Live AWS contract tests without live credentials | 6 |
| Privacy features intentionally planned/not implemented (R08) | 6 |
| `mayaws` profile unavailable to the packaging check | 2 |
| Captured real plan absent from this host | 2 |
| CloudFront OAC public-health security finding | 1 |

None was disabled to manufacture a green total; the Windows and environment
gates are explicit `skipIf` reasons.

## 6. Boundaries and verdict

- No AWS mutation, Terraform apply, synthetic activation, Mays transport or
  main merge.
- The test environment is recovered; the default full suite is green.
- The single extended-fixture failure is a precise, pre-existing generated
  module contract drift, not a product regression and not repaired by editing
  the foreign/generated module.
- B and C remain independent gates.

Machine-readable evidence:
`docs/reports/RIS-ANALYSIS-16C2-QA1-REGRESSION.json`.

