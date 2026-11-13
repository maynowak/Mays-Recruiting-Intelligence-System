# RIS-STRUCTURED-CV-BACKEND-01 — Local Structured CV Persistence

**Status:** `RIS-STRUCTURED-CV-BACKEND-01 — VERIFIED LOCAL / DEPLOYMENT BLOCKED`

**Date:** 2026-11-13

**Branch:** `feature/ris-structured-cv-backend-01` (from contract `49eb13b`)

**Scope:** Local backend, tests and preparatory IaC. No AWS call, Terraform
apply, deployment, production activation, main merge or consent activation was
performed.

## 1. Git baseline

- Contract baseline: `49eb13b3814319a08a926e92a2f227368fabd67f`
  (`docs(contract): align structured CV profile with 03B`).
- Product implementation commit: `28f118f`
  (`feat(ris): add local structured CV profile backend`).
- Preparatory IaC commit: `3409c6c`
  (`chore(ris): prepare structured CV owner index and flag`).
- Jobsearch reference inspected: `c4c2cde`; no Jobsearch change.

## 2. Agent / governance record

- The commander performed the implementation and review; no subagent was used
  for a separate write scope.
- Read before work: target `AGENTS.md`, `docs/AI_AUDITLOG.md`,
  `docs/contracts/STRUCTURED-CV-PROFILE-V1.md`,
  `docs/reports/RIS-STRUCTURED-CV-CONTRACT-REVIEW-02-REPORT.md`,
  `docs/privacy/STRUCTURED-CV-PROFILE-STORAGE-V1-DRAFT.md`.
- All test data is synthetic. No private CV, PDF, email, address or phone
  number was used or committed.

## 3. Architecture decision

`StructuredCvProfileV1` is a new resource on the existing
`partner-profiles` DynamoDB table. The implementation reuses the existing
partner authentication boundary (`_partner_profile_context`), the existing
cursor store and the existing table/IAM surface. No second table, second
repository infrastructure or table scan was introduced.

Why not extend the PDF/search-profile resources: the structured CV has a
different schema, review provenance, owner key, retention and consent purpose.
Reusing their storage semantics would silently mix purposes and make erasure
and consent misleading.

## 4. Data model and validation

Implemented in `jobsearch/structured_cv_profile.py`:

- `schemaVersion = 1`, server-generated `profileId` with prefix `cvp-`.
- Required: `name`, `cvData`, `template`, `version`, `createdAt`, `updatedAt`.
- Optional: `importReview` with `schemaVersion = 1`.
- Exact nested draft fields and `additionalProperties`-style rejection of
  unknown fields.
- Limits: 20 entries per structured list, 100 skills (100 chars each),
  500 review items (2,000 chars per text field), 300,000-byte payload and a
  conservative 400,000-byte DynamoDB item check.
- Templates: `classic`, `modern`, `compact`.
- `importReview.items[].applied` is mandatory and must be `false` unless the
  item is `accepted`. Counts must equal the item statuses. A count-only review
  with pending items is rejected as `IMPORT_REVIEW_INCOMPLETE`; it is never
  silently stored as complete.
- No truncation: oversized or unknown data fails closed.

## 5. Owner isolation

The owner key is a SHA-256 over the verified server context:

`tenantId | partnerApplicationId | issuer | userId`

It is never accepted from a request body. Every get/update/delete/export
rechecks the owner key and all four identity fields; foreign owners receive
`NOT_FOUND`, not a disclosure that the profile exists. No email address is
used as a key.

## 6. Repository

`StructuredCvProfileRepository` uses the existing `PARTNER_PROFILE_TABLE` and
the existing server-side `CursorStore`:

- Create: server-generated ID, idempotency record, capacity counter and
  conditional profile Put in one `TransactWriteItems` call.
- List: query `gsi-structured-owner` with `ownerKey` hash and `resourceId`
  range; opaque cursor; no regular-CRUD table scan.
- Get: consistent read, owner verification.
- Update: `If-Match` version condition; no last-write-wins.
- Delete: owner-bound conditional delete; capacity counter is decremented
  best-effort after a successful delete.
- Export: full structured JSON including embedded review provenance.
- Account erasure: `erase_for_user` queries the existing `gsi-user` index
  (`userId` + `resourceType`) to find profiles across partner scopes, then
  rechecks the item's owner context before each delete. It is idempotent and
  can be resumed by repeating the operation.

## 7. GSI and Terraform preparation

`terraform/modules/dynamodb/main.tf`:

- Added `ownerKey` attribute.
- Added `gsi-structured-owner` with hash `ownerKey`, range `resourceId`,
  `ProjectionType=ALL`.
- Existing `gsi-user` and `gsi-parent` remain unchanged.
- Existing IAM policy already grants `Query` plus `/index/*`; no permission
  widening was needed.

`terraform/modules/lambda` and root variables add
`STRUCTURED_CV_PROFILE_ENABLED`, default `false`. The code default is also
`false`; code presence does not open the route.

Local checks: `terraform fmt -check -recursive terraform` PASS and
`terraform validate` PASS (deprecation warnings only). No plan, apply, state
read/write, import or AWS credential was used.

## 8. CRUD and HTTP adapter

Namespace: `/v1/partner/me/cv-builder-profiles`.

| Operation | Local behavior |
|---|---|
| Create | 201, server profile ID, `ETag: "v1"` |
| List | 200, owner-only metadata and next cursor |
| Get | 200, full profile, `ETag` |
| Update | 200, requires `If-Match`; 428 if absent; 409 if stale |
| Delete | 204; later delete returns 404 |
| Export | 200, full structured JSON |

The adapter reuses the existing dual-auth partner boundary. Errors do not echo
DynamoDB expressions or profile contents. The route is disabled with
`503 STRUCTURED_CV_PROFILE_STORAGE_DISABLED` before authentication/consent if
the feature flag is off.

The production OpenAPI was deliberately not changed. The separate draft
`docs/api/openapi-structured-cv-profile-v1.draft.yaml` was synchronized with
the implemented 428 behavior, no fake 304, no `expectedVersion` body field and
explicit local/deployment-blocked status.

## 9. Idempotency and concurrency

- `Idempotency-Key` is required (16–128 characters).
- The idempotency key is scoped by owner plus key; a foreign owner cannot
  reuse another owner's key.
- Same key + same content returns the existing profile.
- Same key + different content returns `409 IDEMPOTENCY_CONFLICT`.
- Idempotency records expire after 24 hours; TTL is cleanup only, correctness
  is enforced by the conditional Put.
- PATCH requires `If-Match: "vN"`. Missing -> 428; stale -> 409; successful
  update increments the version and returns the new ETag.
- Capacity is 20 profiles per owner and is enforced atomically with create.

## 10. Consent boundary

Added purpose `cv-builder-profile-storage` with DRAFT notice
`structured-cv-profile-storage-2026-11-12-draft-1` and
`legalApprovalRef=null`.

- Create and PATCH require an explicit `GRANTED` purpose.
- Missing, withdrawn, foreign-tenant or foreign-user consent -> 403.
- Consent-store unavailability -> 503.
- This purpose is not equated with `application-storage`, PDF/CV consent or AI
  processing consent.
- No existing production consent flag was changed. Synthetic tests use a local
  moto consent table only.

## 11. Privacy and erasure foundation

- Single-profile delete and full JSON export are implemented.
- Account erasure is wired into `PrivacyErasure` as an additional step when
  the partner-profile table is configured. It is not gated by the route flag,
  so data written while the feature was enabled can still be erased.
- The step reports a failure as `STRUCTURED_CV_ERASURE_FAILED` and keeps the
  overall result `complete=false`.
- Privacy inspect now exposes an owner-scoped `structuredCvProfiles` category
  with metadata, independent cursor and `UNAVAILABLE` instead of a false empty
  result when storage is unreachable.
- No audit receipt contains CV content.

Open privacy decisions remain: retention period, withdrawal read/export
window, backup/PITR reconciliation and physical purge. No complete erasure is
claimed while backups are not covered.

## 12. Tests and evidence

Focused new tests:

```text
tests/test_structured_cv_consent.py   2 passed
tests/test_structured_cv_profile.py  15 passed
tests/test_structured_cv_http.py      8 passed
tests/test_structured_cv_privacy.py   3 passed
                                      ----------
                                      28 passed
```

Coverage includes create/list/get/update/delete/export, duplicate create,
idempotency replay/conflict, version 428/409, interrupted-write result,
foreign user/tenant/partner/issuer, missing/withdrawn consent, unknown schema,
disabled flag, 44 review items, accepted vs applied, large drafts, 300-KB
limit, DynamoDB item size, 101 skills, invalid templates, multiple profiles,
concurrent update, delete then export, 20-profile capacity, delete releasing
capacity and account erasure across partner scopes.

Full RIS suite on this branch:

```text
2559 passed, 56 skipped, 19 failed, 425 subtests passed
```

Baseline comparison at contract commit `49eb13b`:

```text
2533 passed, 56 skipped, 19 failed, 425 subtests passed
```

The same 19 baseline failures remain (wrapper/installer, composite lifecycle,
health pipeline, lambda packaging fixture, platform handler). They are
unrelated to this change and were not repaired by weakening tests. The new
work adds 26 net passing tests.

Additional gates:

- `python3 -m pytest tests/test_structured_cv_contract_document.py ...`:
  42 passed (contract + backend + privacy inspection).
- `terraform fmt -check -recursive terraform`: PASS.
- `terraform validate`: PASS (deprecation warnings only).
- Draft YAML parse: PASS.
- `git diff --check`: PASS.
- Secret/private-data grep: no matches in changed source/tests/docs.

### GSI verification boundary

The owner GSI was created and queried in a local moto DynamoDB table; owner
isolation, pagination and list results were exercised. The installed moto
version cannot execute this table's `TransactWriteItems` shape, so the
transaction subset was simulated explicitly in tests. This is not an AWS
verification. No DynamoDB Local or live index creation was performed.

## 13. Not verified live

- No AWS account, STS identity, state serial or Lambda deployment was read or
  changed.
- No Terraform plan/apply or GSI creation in AWS.
- No API Gateway route or authorizer change.
- No Cognito, CloudFront, DNS, ACM, S3 or Orders mutation.
- No production consent notice approval or feature activation.
- No authenticated browser E2E; no real CV/profile was written.
- No backup/PITR or physical purge verification.

## 14. Open legal/privacy decisions

`REVIEW_REQUIRED` remains for: Art. 9 special-category content, notice text and
legal approval, retention/withdrawal grace, read/export/delete after
withdrawal, capacity 20 vs 10, backup restore reconciliation, and whether
account erasure must cover every partner scope in one operation.

## 15. Commits

- `28f118f` — local backend, HTTP adapter, consent and erasure foundation.
- `3409c6c` — preparatory owner GSI and default-off flag.
- Documentation commit(s) are recorded by the branch history immediately
  following this report.

## 16. Next integration gates

1. Human review of this report and the decision matrix.
2. Approve notice/legal/retention/withdrawal/Art. 9 decisions.
3. Approve a Terraform plan containing `gsi-structured-owner` and the
   default-off flag; no apply before approval.
4. Add the API Gateway route only in a separately reviewed activation step.
5. Build the Jobsearch BFF/consent UI and extend “Meine Lebensläufe”.
6. Run synthetic authenticated E2E for create/reload/update/conflict/consent/
   export/delete/erasure/idempotency.
7. Only then consider main integration and deployment. This task stops before
   RIS deployment and Jobsearch BFF integration.
