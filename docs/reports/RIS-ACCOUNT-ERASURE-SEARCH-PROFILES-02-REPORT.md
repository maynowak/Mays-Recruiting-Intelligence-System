# RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-02 — Deployment Readiness

**Result:** `DEPLOYMENT READY / GO`  
**Apply:** not executed — this GO is not an apply approval  
**Date:** 2026-11-08

## 1. Baseline

| Field | Value |
| --- | --- |
| Branch | `feature/jm-ris-cv-storage-integration-01` |
| Source HEAD | `624d48c72dff8be5c6f13f238b7ac228f72f808d` |
| Working tree | clean (only gitignored `node_modules`) |
| P3 implementation | `30668ff` |
| P3 report/test | `a0ab8db`, `a3e28fb`, `624d48c` |
| P3 report | `docs/reports/RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-01-REPORT.md` |

The deployment source is `624d48c`; it contains the same runtime code as
`30668ff` plus documentation/test-total updates. No uncommitted runtime
changes exist.

## 2. AWS / Terraform target

| Field | Value |
| --- | --- |
| AWS profile | `mayaws` |
| STS identity | `arn:aws:iam::240571105849:user/Mayaws` |
| Account | **240571105849** |
| Region | `eu-central-1` |
| Terraform | 1.16.1 |
| Workspace | `ris-dev` |
| State | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage | **49** / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Resources | 250 |

The plan was a normal plan with state locking; no `-target`, `-replace`,
`-refresh=false` or disabled lock. State remained serial 49 after planning.

## 3. Runtime configuration (read-only)

- Lambda `ris-dev-dev-agent`: `Active`, current code
  `j6eiYk09A8cF9idJBqklzGFaSafDMq+Bsara634PzUI=`.
- `PARTNER_PROFILE_TABLE=ris-dev-dev-partner-profiles`.
- IAM policy `lambda_dynamodb_partner_profiles` includes
  `dynamodb:DeleteItem`, `TransactWriteItems`, `ConditionCheckItem`,
  `GetItem`, `PutItem`, `Query`, `UpdateItem` on the table and its indexes.
- Existing flags unchanged:
  - `ERASURE_APPLICATIONS_ENABLED=false`
  - `ERASURE_WRITE_FREEZE_ENABLED=false`
  - `ERASURE_S3_PHASE_REPOSITORY_ENABLED=false`
  - `ERASURE_OPERATION_REPOSITORY_ENABLED=false`
  - `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true`
  - `CV_STORAGE_CONSENT_ENFORCED=true`
  - `CONSENT_NOTICE_STATE_ENFORCED=false`
  - `CONSENT_PILOT_ALLOWLIST` unchanged.
- The P3 step uses the existing partner table and handler context; no new
  feature flag is required or introduced.
- Identity scoping is covered by tests for user, tenant, partner application
  and issuer; missing context/storage fails closed.

## 4. Build and tests

Deterministic bundle:

```text
python3 lambda/build_zip.py --bundle agent
sha256(terraform/lambda.zip) = fe8075a271a2b1d207bbdfc9d51329f344e2eedf28a06976f3288b443e812c81
filebase64sha256              = /oB1onGisdIHu9/J1RMp80Ti7t8ooGl28yiLRD6BLIE=
```

Tests actually executed:

| Suite | Result |
| --- | --- |
| `tests/test_account_search_profile_erasure.py` | **14 passed** |
| Privacy/erasure focused set (10 files) | **104 passed** |
| Partner profile regression set (5 files) | **146 passed** |
| `terraform validate` | **Success** (provider deprecation warnings only) |
| `terraform fmt -check` | **PASS** |
| Full RIS suite (`tests --ignore=tests/integration`) | **2551 passed, 17 skipped, 16 pre-existing unrelated failures** |

The 16 full-suite failures match the previously reported feature-external
project-config/composite/health/platform baseline. No new regression was found.

## 5. Terraform plan

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-account-erasure-02.tfplan` |
| Plan SHA-256 | `277c3206809309acbdc5fdcd4b2c91d4d8344851c2cc320f298fed475d3dbcba` |
| Changes | **0 add, 1 change, 0 destroy, 0 replace** |
| Active change | `module.lambda.aws_lambda_function.agent` UPDATE |
| Code hash | `j6eiYk09A8cF9idJBqklzGFaSafDMq+Bsara634PzUI=` → `/oB1onGisdIHu9/J1RMp80Ti7t8ooGl28yiLRD6BLIE=` |
| Environment delta | **none** |

No Cognito, CloudFront, DNS/Route53, ACM, Mays-Orders, DynamoDB, API Gateway,
S3, health-plane or partner-edge change. No feature flag changes. No delete or
replacement. No unexplained drift.

## 6. Deployment gates

| Gate | Result |
| --- | --- |
| Code matches P3 `624d48c` | PASS |
| Required runtime variables available | PASS |
| IAM delete/transact permission on partner table | PASS |
| Relevant tests successful | PASS |
| No new security regression | PASS |
| Plan only approved resource class | PASS |
| Protected resources unchanged | PASS |
| Open S3/document phases remain incomplete | PASS (reported as pending, not success) |

## 7. Risks / open limits

- Jobsearch still does not call `/me/erasure`; its user-facing erasure action
  remains disabled. This is a separate cross-repo follow-up.
- The plan updates only the Lambda code. S3/document metadata erasure remains
  governed by the existing phases and is not claimed complete if pending.
- No physical backup/PITR purge is claimed.
- Deployment/apply requires a separate explicit approval for the plan hash
  above.

## 8. Decision

`RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-02 — DEPLOYMENT READY / GO`

This is readiness only. No Terraform apply, AWS mutation, push, merge or
deployment was performed.
