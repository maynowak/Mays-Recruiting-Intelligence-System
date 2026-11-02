# R08-E2E-G1C — REGRESSION FAILURE TRIAGE

**Status:** ANALYSIS COMPLETE / G1D BLOCKED

## Scope and evidence

- HEAD checked: `51024665afdf499e7fd98870f9ee7995039586bd`
- G1B report: `docs/reports/RIS-R08-E2E-G1B-BUILDER-COLLECTION-REPAIR.md`
- No installation, AWS call, deployment, Terraform change or test service was
  performed.
- The regression was rerun with the existing R07A environment, dummy AWS
  variables, and `tests/test_http_e2e_integration.py` excluded because it
  requires deployed infrastructure.
- Result: **2,185 passed, 45 failed, 56 skipped, 339 subtests passed**.
- No test was disabled, reclassified or changed to force a pass.

## Failure classification

| Group | Count | Tests / evidence | Classification |
|---|---:|---|---|
| Windows path separators | 3 | `test_agent_catalog_terraform_seed.py`, `test_dryrun_handoff.py`, `test_partner_terraform_wiring.py` | **Faulty test assumption**: implementation emits valid Windows paths while assertions require POSIX strings. |
| Preserved development tfvars | 1 | `test_cognito_email_verification_config.py::test_no_tfvars_file_is_required` | **Environment / preserved baseline artifact**: `terraform/ris-dev2.tfvars` was required to remain untouched. |
| Composite wrapper fixture/lifecycle | 3 | `test_global_flags_precede_command`, `test_extra_args_after_command`, `test_full_output_not_truncated` | **Existing Builder/baseline failure**: the local Orders project/pin fixture does not reach the mocked subprocess path; no command/result is captured. |
| AWS CLI context | 1 | `test_discover_subprocess_env_keeps_path` | **Missing test dependency**: `aws` executable is unavailable; traceback is `AwsValidationError: aws CLI not available`. |
| Dry-run fixture security scan | 1 | `test_entitlement_provisioning.py::test_no_wildcards_in_the_terraform_change` | **Missing dependency**: test invokes `git`, unavailable in the R07A subprocess PATH. |
| Lambda source-change fixture | 1 | `test_lambda_packaging.py::test_f_change_detected_and_g_restored_noop` | **Missing dependency**: same unavailable `git` subprocess. |
| Partner repository coupling | 1 | `test_partner_profile_contract_reconciliation.py::test_repository_module_has_no_agent_or_model_import` | **Actual RIS regression**: `jobsearch/partner_profile_repository.py:39` imports `agents.ecosystem.privacy_erasure_contract`. The import was introduced by `8c5bcdc`; the parent revision has no such import. |
| OpenAPI privacy routes | 1 | `test_platform_openapi_contract.py::test_no_spec_route_without_terraform_or_imperative_source` | **Planned capability gap / test expectation**: `/v1/partner/me/privacy/export` and `/inspect` are documented but intentionally not implemented in this scope. |
| Project pinning subprocesses | 6 | all six `tests/test_project_pinning.py` failures | **Missing dependency**: each setup fails before the assertion because `git init --bare` cannot start (`WinError 2`). |
| Credential symlink tests | 5 | `TestOutputDestination` symlink cases | **Missing Windows capability**: `os.symlink` fails with `WinError 1314` because symlink privilege is unavailable. |
| Credential output/security cascade | 16 | remaining `tests/test_ris_admin_credentials.py` failures | **Windows test-environment mismatch**: temporary directories are treated as group/other writable, so `precheck_output_destination` rejects the fixture before the intended authorization, idempotency, revoke, list/show or CLI assertion. |
| Installer dry-run/pinning | 1 | `test_install_dry_run_performs_no_mutation` | **Existing Builder/pin baseline failure**: Orders lifecycle stops at `HEAD None != pinned ...`; no productive mutation occurs. |
| Installer validation identity | 1 | `test_validate_skips_workspace_without_backend` | **Missing/invalid AWS test dependency**: mocked subprocess returns empty/non-JSON STS output, producing `STS returned unparsable output`. |
| State mirror hash | 1 | `test_snapshot_records_a_sha256` | **Unresolved component defect**: recorded digest differs from the exact raw payload digest. This is not explained by Windows path or external tooling. |
| State mirror rotation | 1 | `test_keeps_the_newest` | **Unresolved component defect**: ten ordered snapshots retain `[6, 9, 7]`, not `[9, 8, 7]`; ordering is not reliably based on write order. |
| Dependency-check launcher | 2 | `tests/unit/tools/test_dependency_check.py` exit/json tests | **Missing Windows dependency**: tests invoke `python3`; Windows returns launcher/app-alias code `9009`, so no JSON is produced. |

**Total: 45 failures.** Classification totals: **1 actual RIS regression, 42
environment/baseline/test-assumption or planned-gap failures, and 2 unresolved
component defects**. The state-mirror findings are explicitly classified as
unresolved rather than hidden inside the environment bucket.

## Root causes and affected files

1. **Windows portability assumptions** — several static checks compare paths
   without normalizing `/` and `\\`; affected tests are listed above.
2. **Unavailable external executables** — `aws`, `git`, and `python3` are
   invoked as literal subprocess commands. The existing R07A environment has
   neither the required AWS CLI/profile nor those Windows command names.
3. **Windows security semantics** — symlink creation needs a privilege not
   granted to this process, and POSIX mode checks do not model Windows ACLs.
4. **Preserved local artifacts and Builder state** — `ris-dev2.tfvars` and the
   Orders project/pin state were preserved as required; tests assuming a clean
   clone therefore fail before their target assertions.
5. **Actual coupling regression** — `jobsearch/partner_profile_repository.py`
   now imports the agent privacy module. The test contract explicitly forbids
   this boundary crossing. The introducing commit is identifiable in history;
   no claim is made that the failure existed before that commit.
6. **State mirror behavior** — hash calculation and same-second rotation need
   a separate implementation decision and targeted investigation. No
   speculative production fix was applied in G1C.

## Skip classification (56)

| Cause | Count | Scope |
|---|---:|---|
| DynamoDB Local endpoint absent | 39 | `tests/integration/test_partner_profile_dynamodb_local.py`; skips explicitly refuse to guess an endpoint. |
| Captured real plan absent | 2 | `tests/test_dryrun_handoff.py`; fixture-dependent handoff checks. |
| CloudFront/OAC not implemented | 1 | `tests/test_health_security.py`; recorded security finding. |
| AWS credentials absent | 2 | `tests/test_lambda_packaging.py`; credential-dependent packaging checks. |
| Live AWS observability contracts | 6 | `tests/test_observability_foundation.py`; live credentials required. |
| Planned privacy capability | 6 | `tests/test_privacy_capability_planned.py`; R08-A/B/C work is explicitly planned, not silently omitted. |

**Total: 56 skips.** These are scope/environment skips, not reclassified
failures.

## Fix decision

No minimal test-configuration correction is justified by the evidence. A
path-normalization or executable-alias change would alter test assumptions or
the execution environment rather than repair RIS behavior. The genuine
repository coupling and the two state-mirror findings require deliberate
production/design decisions and are therefore left unchanged.

## Verification and cleanup

- Full collection remains green: **2,685 collected, 0 collection errors**.
- No Java/DynamoDB Local process was started.
- Port `18000` was checked and is not listening.
- The 39 pre-existing untracked files were preserved.
- No tracked production or test file was modified by G1C.

## G1D readiness

**BLOCKED.** G1C analysis is complete, but G1D cannot be declared ready while
the actual partner-profile coupling regression, two state-mirror defects, and
the environment-dependent baseline failures remain unresolved or explicitly
accepted. G2 remains blocked by the previously documented AWS/IAM, S3
fencing/version deletion, upload cutover, quiescence, retention,
backup/restore and erasure-activation gates.

## Commit

```text
test(ris): classify regression failure baseline
```
