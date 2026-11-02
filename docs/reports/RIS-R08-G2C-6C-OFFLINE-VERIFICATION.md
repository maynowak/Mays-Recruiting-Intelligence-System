# RIS-R08-G2C-6C — Offline Verification and Deployment Guards

**Status:** IMPLEMENTED / CONTRACT VERIFIED / DEPLOYMENT BLOCKERS DOCUMENTED

## Fixes

1. Added the two existing privacy inspection/export handler routes to the API
   Terraform module. Both reuse the human JWT authorizer and the existing
   Lambda proxy; no new identity or privacy execution capability is enabled.
2. Updated the canonical API route inventory count and API standard rows.
3. Made installer dry-run stop before composite preflight/component lifecycle,
   so a dry-run cannot invoke Orders pin enforcement or any later operation.
4. Added G2C-6 static guards for managed/external identity, Orders modes,
   external references and protected-resource non-declaration.

## Actual verification

| Suite | Result | Classification |
|---|---:|---|
| G2C-6 mode/protection tests | 6 passed | PASS |
| API/OpenAPI + partner contract subset | 74 passed, 260 subtests | PASS |
| Installer/runner/backend/pinning subset | 92 passed, 3 failed | BLOCKED |
| Python compilation (`installer/ris.py`) | PASS | PASS |
| Terraform fmt on changed files | PASS | PASS |

## Remaining installer failures

- `test_validate_skips_workspace_without_backend`: test patches the shared
  subprocess runner with an empty stdout, so the mandatory read-only STS guard
  correctly rejects unparsable identity output. This is not safe to weaken in
  production code.
- Two project-pinning tests compare a Windows `Path` string against a
  forward-slash suffix. The implementation resolves the configured local
  directory correctly; the assertion is platform-specific.

The prior dry-run pin-enforcement failure is fixed and no longer appears in the
result. No failures were hidden with skips and no AWS write was performed.

## Builder and Terraform boundaries

The full Builder scenario remains NOT RUN/timeout-blocked from the G2C-5
baseline. Terraform validation is BLOCKED in this checkout because the
generated `terraform/modules/mays_orders` module is absent. It is a local
builder artifact, not a reason to restore State or commit generated resources.

Privacy/erasure execution, receipt, freeze, cutover and S3 execution flags
remain false.
