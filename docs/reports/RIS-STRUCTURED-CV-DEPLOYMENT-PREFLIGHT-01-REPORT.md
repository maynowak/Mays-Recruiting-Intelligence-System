# RIS-STRUCTURED-CV-DEPLOYMENT-PREFLIGHT-01

**Status:** `TECHNICAL PREFLIGHT READY / AWS PLAN APPROVAL REQUIRED`

**Date:** 2026-11-13

**Branch:** `feature/ris-structured-cv-deployment-preflight-01`

**Baseline:** `0e08822`

**Scope:** Offline inventory, local checks and deployment-gate assessment. No
AWS call, Terraform plan against AWS, state access, apply, Cognito/CloudFront/DNS
mutation or consent activation.

## 1. Git baseline

- RIS structured-CV backend branch:
  `feature/ris-structured-cv-backend-hardening-02 @ 0e08822`.
- RIS main: `f830a5e` (not merged).
- Jobsearch reviewed separately at `feature/jm-cv-builder-03c-release-gate-01
  @ 52b6786`; its `/api/ris/cv-builder-profiles` route remains default-off.
- RIS source and Terraform were not changed by this preflight.

## 2. Implemented inventory

| Component | State | Evidence |
|---|---|---|
| `StructuredCvProfileV1` validation | Implemented | `jobsearch/structured_cv_profile.py` |
| Owner-scoped DynamoDB repository | Implemented | `StructuredCvProfileRepository` |
| `gsi-structured-owner` | Terraform locally defined | `terraform/modules/dynamodb/main.tf` |
| HTTP handler `/v1/partner/me/cv-builder-profiles` | Implemented, default-off | `lambda/handler.py`, flag `STRUCTURED_CV_PROFILE_ENABLED` |
| Create idempotency / If-Match / conflict mapping | Implemented | repository + handler tests |
| Delete + capacity transaction | Implemented, local tests | repository |
| Account erasure step | Implemented, table-gated | `PrivacyErasure` |
| Privacy inspect/export category | Implemented | `lambda/handler.py` |
| Consent purpose `cv-builder-profile-storage` | DRAFT, fail-closed | consent contract/repository |
| API Gateway route | **Not implemented** | no `cv-builder-profiles` route in `terraform/modules/api/main.tf` |
| Real DynamoDB GSI/transaction proof | **Not executed** | no AWS/Local DynamoDB evidence |

The missing API Gateway route is intentional for the current inactive state but
is a required C2B activation delta. It does not prevent an infrastructure-only
C2A plan from adding the GSI and default-off Lambda flag; it prevents live
exposure of the resource.

## 3. Terraform preflight

Local commands:

```text
terraform fmt -check -recursive terraform   PASS
terraform init -backend=false              PASS
terraform validate                         PASS (deprecation warnings only)
```

The partner-profile table currently has `resourceId` hash, existing `gsi-user`
and `gsi-parent`, and the new `gsi-structured-owner`:

- hash: `ownerKey` (server-derived SHA-256)
- range: `resourceId`
- projection: `ALL`
- no new table, no backfill, no replacement
- items without `ownerKey` are simply absent from the sparse index

Existing IAM policy for the partner-profile table already grants PutItem,
GetItem, Query, DeleteItem, UpdateItem, TransactWriteItems and `/index/*`. No
IAM widening is needed. The Lambda environment exposes
`STRUCTURED_CV_PROFILE_ENABLED`, default `false`.

Risks requiring a real plan review:

1. Adding a GSI to an existing table is an in-place table update in Terraform,
   but must not be assumed safe without an AWS plan and online-index backfill
   review.
2. API Gateway route additions for collection, item, export and consent status
   are absent. Product activation requires a separate reviewed route change.
3. The preview/BFF and RIS deployment ordering must be explicit; Jobsearch
   default-off behavior remains safe if RIS is not yet deployed.

## 4. Data-integrity assessment

- Create uses a transaction containing idempotency record, capacity counter and
  profile Put.
- Update uses version + owner condition; post-precheck conditional failure is
  re-read and mapped to `409` or `404`, never generic `503`.
- Delete and capacity release are in one transaction; bounded counter repair and
  `reconcile_capacity()` exist.
- List uses `gsi-structured-owner`; opaque server-side cursor; no regular-CRUD
  table scan.
- Profile payload is limited to 300,000 bytes and a conservative 400,000-byte
  item check; no silent truncation.
- Account erasure uses the existing `gsi-user` lookup and rechecks owner scope
  before deleting each profile.
- Idempotency records expire after 24h. After TTL expiry, a retry can no longer
  be proven idempotent by the server; the client must preserve uncertainty and
  must not infer ownership from name/template.

### Open data risks

- Privacy export collects up to 20 × ~300KB profiles into one JSON response;
  API Gateway/Lambda response limits need explicit headroom testing.
- Moto only simulates transaction cancellation and GSI queries. No real
  DynamoDB Local/GSI/transaction proof exists in this preflight.
- No PITR/backup restore reconciliation is implemented or claimed.
- No physical purge is claimed while backups may retain data.

## 5. Regression evidence

- Structured-CV focused suite: **43 passed**.
- Full RIS suite: **2576 passed / 56 skipped / 19 failed**.
- The 19 failures are the documented baseline set and are unrelated to
  Structured-CV:
  - 13 `test_wrapper_regression.py` wrapper/installer failures;
  - 3 `test_composite_lifecycle.py` argument-ordering failures;
  - 1 `test_health_plane_integration.py` health-event failure;
  - 1 `test_lambda_packaging.py` missing fixture/archive failure;
  - 1 `test_platform_handlers.py::TestAgentAPI::test_execute_agent` failure.
- No tests were removed or weakened.
- Terraform fmt/validate and `git diff --check` passed.

## 6. Deployment blockers / gates

**C2A infrastructure-only:** possible after an AWS account/state ownership
check, reviewed plan, explicit Release Owner approval and flags remaining OFF.
The GSI and Lambda flag can be planned; the API Gateway route remains absent.

**C2B product activation:** blocked until the route is added, a real DynamoDB
plan/deploy is verified, notice/consent is legally approved, retention/erasure
is signed off, and authenticated synthetic E2E is authorized.

## 7. Required next actions

1. Review this preflight in the human release gate.
2. Authorize a separate AWS discovery/planning task (G4) with named account,
   region, workspace, backend and protected-resource baseline.
3. Add and review the API Gateway route delta only in the activation task.
4. Run a real DynamoDB transaction/GSI verification after deployment.
5. Do not activate the feature before the privacy package is approved.

## 8. Commit

This report is committed on `feature/ris-structured-cv-deployment-preflight-01`.
