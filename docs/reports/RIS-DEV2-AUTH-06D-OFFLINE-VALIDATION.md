# RIS-DEV2-AUTH-06D — Offline Validation

## Result

```text
FUNCTIONAL VALIDATION PASS / PACKAGING REGRESSION ENVIRONMENT-BLOCKED
```

## Functional validation

The required local ApplicationV1/auth/contract/credential/privacy selection
was run after the artifact build:

- **177 passed**;
- **304 subtests passed**;
- Lambda ZIP import smoke: **PASS**;
- `handler.lambda_handler is handler.handler`: **PASS**;
- ZIP handler structure and dispatcher-fix check: **PASS**.

The ZIP import smoke used `terraform/lambda.zip` directly and verified the
root `handler.py`, entry-point alias and corrected `_application_routes` call.

## Packaging test result

The full selected command including `tests/test_lambda_packaging.py` produced
**181 passed, 1 failed, 2 skipped, 304 subtests passed**. The sole failure was
`TestSourceChange::test_f_change_detected_and_g_restored_noop`: its temporary
repository copy could not resolve a large archived-evidence path on this
Windows runner (`WinError 3`). This is an environment/path-copy failure, not
a handler or artifact assertion failure. The remaining packaging tests passed
(`4 passed, 2 skipped, 1 deselected` when excluding that environment-sensitive
case).

The prior known Windows ACL/symlink limitations in the admin credential suite
remain documented separately. No production code or security check was
weakened to accommodate the runner.

## Gate decision

Because the complete packaging selection has an environment failure, the
strict offline gate is not declared fully green:

```text
DEPLOYMENT BLOCKED — OFFLINE REGRESSION ENVIRONMENT FAILED
```

Functional evidence is sufficient to continue preparing the plan, but not to
authorize a deployment. No AWS code update, Terraform plan/apply, alias change
or rollback was executed.
