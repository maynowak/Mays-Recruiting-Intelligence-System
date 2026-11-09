> **Historical report.** Current consolidated P3 status:
> `MAYS-P3-FINAL-REPORT.md`.

> **Post-report note (2026-11-09):** current RIS-DEV state is serial **54**,
> not 50, after temporary test-allowlist setup/rollback and the local
> partner-context handler fix. See `MAYS-P3-FINAL-REPORT.md` for the current
> blocker: `/me/erasure` is on the kernel API (different Cognito pool) and is
> not reachable from the Jobsearch partner edge.

# RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-03 — Deployment Report

**Result:** `DEPLOYED / POST-DEPLOY VERIFIED`  
**Date:** 2026-11-08  
**Scope:** RIS agent Lambda only

No push, merge, rollback or additional Terraform change was performed. No
real account, CV, application or document was deleted.

## 1. Baseline at apply

| Field | Value |
| --- | --- |
| Branch | `feature/jm-ris-cv-storage-integration-01` |
| Source runtime HEAD | `624d48c` |
| Docs HEAD at apply | `bdea525` |
| AWS profile | `mayaws` |
| STS identity | `arn:aws:iam::240571105849:user/Mayaws` |
| Account / region | `240571105849` / `eu-central-1` |
| Terraform | 1.16.1 |
| Workspace | `ris-dev` |
| State | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage before | **49** / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Resources before | 250 |
| Lambda before | `ris-dev-dev-agent`, `Active`, `j6eiYk09A8cF9idJBqklzGFaSafDMq+Bsara634PzUI=` |

The operator order named the exact plan hash and was treated as the explicit
apply authorization for that hash. No new plan was generated.

## 2. Plan consumed

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-account-erasure-02.tfplan` |
| SHA-256 | `277c3206809309acbdc5fdcd4b2c91d4d8344851c2cc320f298fed475d3dbcba` |
| Changes | **0 CREATE, 1 UPDATE, 0 DELETE, 0 REPLACE** |
| Only resource | `module.lambda.aws_lambda_function.agent` |
| Code hash | `j6eiYk09A8cF9idJBqklzGFaSafDMq+Bsara634PzUI=` → `/oB1onGisdIHu9/J1RMp80Ti7t8ooGl28yiLRD6BLIE=` |
| Environment delta | none |

Preflight confirmed the plan hash, state serial/lineage, old Lambda code hash,
plan shape, and empty environment delta before apply.

## 3. Apply result

```text
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

No `-target`, `-replace`, `-destroy`, force, refresh bypass or disabled state
lock was used. No rollback was executed.

## 4. Post-deploy state

| Field | Value |
| --- | --- |
| State serial after | **50** |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Resources after | 250 |
| Lambda state | `Active` |
| Lambda code hash after | `/oB1onGisdIHu9/J1RMp80Ti7t8ooGl28yiLRD6BLIE=` |
| Last modified | `2026-11-08T18:00:41.000+0000` |

State diff before/after contains only
`module.lambda.aws_lambda_function.agent`. All other 249 resource addresses and
instances are unchanged.

## 5. Runtime / IAM / data checks

- `PARTNER_PROFILE_TABLE=ris-dev-dev-partner-profiles`.
- Lambda execution role `ris-dev-dev-agent` has the existing partner-profile
  inline policy with `GetItem`, `PutItem`, `Query`, `DeleteItem`,
  `UpdateItem`, `ConditionCheckItem`, `TransactWriteItems` on the table and its
  indexes.
- DynamoDB table `ris-dev-dev-partner-profiles` is `ACTIVE`.
- Erasure flags remain unchanged:
  - `ERASURE_APPLICATIONS_ENABLED=false`
  - `ERASURE_WRITE_FREEZE_ENABLED=false`
  - `ERASURE_S3_PHASE_REPOSITORY_ENABLED=false`
  - `ERASURE_OPERATION_REPOSITORY_ENABLED=false`
  - `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true`
  - `CV_STORAGE_CONSENT_ENFORCED=true`
  - `CONSENT_NOTICE_STATE_ENFORCED=false`
  - `CONSENT_PILOT_ALLOWLIST` unchanged.

## 6. Smoke checks

Non-destructive only:

- Kernel API `GET /health` → `401 Unauthorized` (JWT route; expected auth
  boundary, no 5xx).
- Partner API `GET /v1/partner/me/consents` without token → `401 Unauthorized`.
- No delete, erasure, account, CV or application operation was invoked.

## 7. Protected resources

State diff and plan confirm no change to:

- Cognito pools/clients
- CloudFront
- Route53 / DNS
- ACM
- Mays-Orders
- API Gateway
- S3
- DynamoDB
- Partner Edge

## 8. Open limits

- Jobsearch still has no active `/me/erasure` client/UI; its erasure action
  remains disabled. This is a separate cross-repo follow-up.
- Full S3/document/PITR/backup erasure is not claimed; open document work is
  reported as incomplete by the code.
- No real user account was erased. A synthetic production E2E requires a
  separate `RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-04` approval.
- No general rollout.

## 9. Decision

`RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-03 — DEPLOYED / POST-DEPLOY VERIFIED`

No push or merge. The next step is the separately authorized synthetic
production E2E.
