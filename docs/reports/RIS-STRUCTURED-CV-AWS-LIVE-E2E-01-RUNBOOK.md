# Structured CV AWS Deployment / Live-E2E Runbook

**Task:** `RIS-STRUCTURED-CV-AWS-LIVE-E2E-01`

**Status:** `LIVE-E2E RUNBOOK READY / DEPLOYMENT APPROVAL REQUIRED`

**Scope:** Offline preparation only. No AWS discovery, STS, plan, state access,
apply, IAM/Cognito/CloudFront/DNS mutation or real CV processing has been
executed.

## 1. Preconditions and ownership

Before any AWS operation, the Release Owner must provide in writing:

- exact AWS account id and alias;
- region (expected `eu-central-1`, verify—do not assume);
- Terraform workspace, backend bucket/key, lock table and state lineage/serial;
- protected resources and existing Cognito/CloudFront/DNS baselines;
- authorized operator identity/profile and change window;
- explicit G4 discovery/plan approval, then separate G6 apply approval.

If any item is missing, STOP. Do not infer account, workspace or state.

## 2. Deployment sequence

### Phase 0 — Read-only local baseline

1. Verify Git SHAs in RIS and Jobsearch.
2. `git status --short`; preserve unrelated files.
3. Run `terraform fmt -check -recursive terraform`.
4. Run `terraform init -backend=false` and `terraform validate` only.
5. Build Lambda bundles deterministically (`python lambda/build_zip.py --bundle all`).
6. Verify no secrets/PII in diff or bundle.

### Phase 1 — G4 AWS discovery/plan (separate approval)

1. Verify STS identity, account, region.
2. Verify backend workspace/key/state ownership and state serial/lineage.
3. Snapshot protected-resource baseline.
4. Confirm no alternate state/workspace.
5. Review expected delta: partner-profile GSI, default-off Lambda env and any
   explicitly approved API Gateway route delta.
6. Create a saved plan; archive plan JSON.
7. Record SHA-256 and state serial/lineage.
8. Review: creates/updates/deletes/replacements, IAM, data, Cognito/CloudFront/
   DNS, route/auth changes, cost and rollback.

### Phase 2 — G6 apply (separate approval)

1. Compare plan SHA to approved value.
2. Apply only the exact approved plan. No `-target`, `-replace`, `-destroy`,
   `-refresh=false` or `-lock=false`.
3. Keep feature flags OFF.
4. Record apply result/state serial.
5. Do not activate consent or the product route unless separately approved.

### Phase 3 — C2A health only

With flags OFF:

- invoke health/read-only endpoints;
- verify no Structured-CV write route is exposed;
- verify 503/404 fail-closed behavior;
- verify existing PDF/search/application/privacy routes remain healthy;
- verify Lambda logs do not contain CV content.

### Phase 4 — C2B activation (only after privacy approval)

Do not proceed until the Privacy package is human-approved and the notice is
ACTIVE/APPROVED with a legal approval reference, feature flags are explicitly
enabled, test identities are approved and the release owner signs the
activation plan.

## 3. Test manifest

### Infrastructure

| Test | Evidence |
|---|---|
| Health endpoint | status/body/timestamp |
| GSI available/queryable | synthetic owner query; AWS request id |
| DynamoDB transaction create/update/delete | item/version/state evidence |
| Idempotency same/different payload | IDs/status only |
| Capacity 20→delete→create | counts/receipts |
| Version conflict | HTTP 409/ETag |
| IAM allows only required actions | policy/CloudTrail |
| Authorizer present | JWT route metadata |

### Security

| Test | Expected |
|---|---|
| Missing token | 401 |
| Invalid token | 401 |
| Foreign user | 404 |
| Foreign tenant/partner/issuer | 404 |
| Consent absent | 403 |
| Consent withdrawn | 403 |
| DRAFT notice | 403/blocked |
| Partner credential absent | 401/403; no write |

### User flow (synthetic)

1. Login with approved synthetic identity.
2. Create profile with 44-review/71-skill fixture.
3. Save/load/version update.
4. Logout/login; reload full profile.
5. Duplicate; verify distinct profile id.
6. Export; verify full JSON/review.
7. Delete; verify 204 then 404.
8. Account erasure; verify profile/review/capacity handled.
9. Privacy inspect/export.
10. Cleanup all synthetic ids and verify no residual live item.

### Negative HTTP matrix

`401, 403, 404, 409, 413, 422, 428, 503` plus network timeout, concurrent
updates, repeated create, repeated delete, session switch and partial erasure.
No status may be reported PASS without a captured response/evidence reference.

## 4. Cleanup

Cleanup must use documented synthetic IDs only. Record before/after:

- profile `profileId`s and versions;
- review item ids/count;
- capacity counter (`capacity#SCVP#<ownerKey>`);
- idempotency records and expiry (do not purge others);
- privacy inspect/export categories;
- erasure operation receipt/status;
- CloudWatch log references (no CV contents).

Verify no unrelated tenant/partner/user rows are touched. Document
backup/PITR limitations: live deletion does not prove physical backup purge.

## 5. Rollback / recovery

- Keep previous Lambda/API/GSI plan artifacts and deployment IDs.
- If the API route or flag causes regression, disable the flag first (OFF) and
  roll back the approved route/Lambda change.
- A GSI add cannot be safely “rolled back” by assuming data deletion; use a
  reviewed Terraform plan and preserve existing table items.
- Never restore an old backup into production without replaying deletion/
  erasure reconciliation.
- Escalate any unexplained delete/replace/protected-resource change.

## 6. Required evidence pack

- Git SHAs and command outputs;
- plan file path, SHA-256, state serial/lineage;
- apply output and post-state serial;
- CloudTrail/API request IDs;
- synthetic ids only;
- HTTP response matrix;
- cleanup verification;
- signed gate approvals (G4/G6/C2A/C2B).

## 7. Current blockers

- A separate G4 AWS discovery/plan approval is not present.
- A separate G6 apply approval is not present.
- Privacy/legal notice approval is not present.
- API Gateway route delta is not included in the current backend branch.
- Real DynamoDB/GSI transaction verification is not executed.

**No deployment or live E2E was executed.**
