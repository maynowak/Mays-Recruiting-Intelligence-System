# RIS-STRUCTURED-CV-CONTRACT-01

**Status:** `RIS-STRUCTURED-CV-CONTRACT-01 — CONTRACT READY FOR REVIEW`
**Date:** 2026-11-12
**RIS branch:** `feature/ris-structured-cv-contract-01`
**Base:** `f830a5e` (`origin/main`)
**Jobsearch baseline:** `a0dc1ec` (contract consumer, unchanged)
**Scope:** contract/documentation only

## 1. Deliverables

- `docs/contracts/STRUCTURED-CV-PROFILE-V1.md`
- `docs/privacy/STRUCTURED-CV-PROFILE-STORAGE-V1-DRAFT.md`
- `docs/api/openapi-structured-cv-profile-v1.draft.yaml`
- this report and the AI audit entry

No production `docs/api/openapi-platform.yaml` change was made. The draft is a
separate file so the productive contract is not silently expanded.

## 2. Resource decision

Created a new `StructuredCvProfileV1` contract. It is **not**:

- PDF/CV document storage;
- manual/CV/ATS search-profile storage;
- the `/me/profile` identity record.

It stores profile name, existing `CvBuilderDraftV1`, template, 03B
`importReview` sidecar, server version and timestamps. Owner identity is
derived only from verified tenant/partner/issuer/subject context.

## 3. API contract

New namespace:

`/v1/partner/me/cv-builder-profiles`

- `POST` create (required idempotency key; 201)
- `GET` list metadata (signed cursor; limit 1–50)
- `GET /{id}` full profile + ETag
- `PATCH /{id}` optimistic version / `If-Match`; 409 on conflict
- `DELETE /{id}` idempotent own-profile delete; 204
- `GET /{id}/export` full structured JSON including review provenance

Dual auth remains required: Cognito JWT + server-only `X-Api-Credential`.
Owner/tenant/partner/issuer filtering uses all four values; foreign or missing
resources return the same 404.

## 4. DynamoDB/item-size decision

The design reuses the existing `partner-profiles` table and `gsi-user`.

- Safe payload limit: **300,000 bytes**, leaving headroom below DynamoDB's
  400 KiB item limit.
- Maximum embedded review items: **500**; each text/original ≤2,000 chars.
- Oversize returns `413 PAYLOAD_TOO_LARGE` / `PROFILE_TOO_LARGE`; no silent
  truncation or partial save.
- Review items are embedded in V1 so delete/export cannot leave orphan review
  rows. A future larger payload requires a new chunked schema version.
- Proposed capacity: **20 profiles/user** (`REVIEW_REQUIRED`; not an
  implementation value yet).
- Idempotency/capacity/lifecycle behavior reuses existing conditional
  transaction patterns; no table scan on normal CRUD.

## 5. Review persistence

The contract preserves per item:

`id`, index, original/corrected text, edited, target, status, applied, page,
sectionHeading, reason, suggestedTarget.

`accepted` is separate from `applied`; duplicate application is detected by
the client/backend item ID and applied state. The review state belongs to the
same `profileId` and is included in read/export/delete.

## 6. Consent and privacy draft

Proposed purpose: `cv-builder-profile-storage`, separate from PDF and
search-profile purposes.

Proposed notice (DRAFT, not approved):

`structured-cv-profile-storage-2026-11-12-draft-1`

- `legalApprovalRef = null`; no automatic legal approval.
- Art. 9 assessment required because CV free text may contain special-category
  data.
- Create/PATCH require active consent and accepted notice.
- Withdrawal blocks writes; proposed read/export/delete and grace behavior is
  explicitly `REVIEW_REQUIRED`.
- Regrant never silently restores purged data.
- Storage consent does not authorize AI/provider transfer.

## 7. Erasure

The draft specifies a new owner-scoped `structured-cv-profiles` step in the
existing `PrivacyErasure`/R08 lifecycle:

- idempotent single-profile delete;
- account erasure deletes profile + embedded review;
- partial failure resumes; no false completion;
- privacy inspect/export includes this category;
- no orphan review sidecar;
- backups/PITR/CloudTrail are not claimed as synchronously purged;
- minimized receipts contain no CV/review text.

## 8. Jobsearch BFF and UI

Proposed BFF route:

`/api/ris/cv-builder-profiles`

The existing Jobsearch BFF auth/credential pattern is to be reused; no RIS
credential in the browser. Feature flags are proposed off-by-default:
`VITE_RIS_CV_BUILDER_PROFILE_STORAGE_ENABLED` and server-side
`RIS_CV_BUILDER_PROFILE_STORAGE_ENABLED`.

The existing “Meine Lebensläufe” UI is to be extended, not replaced:

- explicit “Dauerhaft speichern”;
- per-profile status (session-only / durable / unsaved / error / conflict);
- load/update/delete/duplicate via the existing builder list;
- conflict display;
- existing PDF list and search-profile UI unchanged.

## 9. Test contract

Defined synthetic cases for:

1. create + reload after login;
2. update + save;
3. version conflict;
4. identity switch;
5. foreign access;
6. missing consent;
7. withdrawn consent;
8. regrant;
9. duplicate;
10. delete;
11. full export;
12. account erasure;
13. 44-item review backlog;
14. multiple profiles;
15. large payload;
16. repeated requests/idempotency;
17. 03B review integrity + 03A handoff regressions.

No private CV data is used. These are contract tests to implement in the
separate backend/BFF/UI gates.

## 10. Explicit non-implementation

- No RIS Lambda handler, repository, Terraform, IAM, DynamoDB item, OpenAPI
  production route, consent catalog entry or feature flag was created.
- No AWS/Terraform/state mutation.
- No production consent activation.
- No Jobsearch product code/BFF/UI change in this contract task.
- No main merge and no production deployment.

## 11. Open decisions before implementation

1. Approved retention/withdrawal grace period.
2. Final legal basis and Art. 9 handling.
3. Capacity number (20 proposed; existing UI may require 10).
4. Exact read/export/delete behavior after consent withdrawal.
5. Final notice text/version and legal approval reference.
6. BFF route naming/flag ownership.
7. Privacy inventory/receipt category naming.
8. Backup/restore reconciliation owner.
9. Whether a later schema version needs chunked review sidecars.
10. Backend/BFF implementation sequencing.

**CONTRACT READY FOR REVIEW. STOP before backend, BFF, UI, merge or deployment.**
