# StructuredCvProfileV1 — RIS/Jobsearch Contract

**Status:** DRAFT / CONTRACT ONLY — technically aligned with CV-BUILDER-03B; not implemented, not deployed, not legally approved
**Date:** 2026-11-12
**Repositories:** `maynowak/Mays-Recruiting-Intelligence-System`, `maynowak/mays-jobsearch`
**Related Jobsearch evidence:** CV-BUILDER-02F/03A/03B
**Supersedes:** nothing. This is a new resource contract.

> This contract does **not** extend PDF/CV-document storage, search-profile
> storage, ATS-profile storage or the `/me/profile` identity record.

## 1. Purpose and non-goals

Persist editable structured CV-builder profiles across sessions and logins,
including the 03B import-review backlog, so “Meine Lebensläufe” can offer
explicit durable save/load/update/delete.

Non-goals:

- PDF bytes or presigned uploads (existing CV-document contract);
- search configuration (existing search-profile contracts);
- AI/OCR processing;
- automatic persistence without explicit user action;
- automatic consent, legal approval or production activation.

## 2. Resource model

```json
{
  "schemaVersion": 1,
  "profileId": "cvp-<server-uuid>",
  "name": "Bewerbung Cloud",
  "cvData": {
    "schemaVersion": 1,
    "personal": {},
    "profile": {},
    "experience": [],
    "education": [],
    "skills": [],
    "projects": [],
    "certificates": [],
    "languages": [],
    "links": []
  },
  "template": "classic",
  "importReview": {
    "schemaVersion": 1,
    "sourceName": "synthetic-cv.pdf",
    "pageCount": 3,
    "pendingAcknowledged": true,
    "selectedSections": ["personal", "profile", "experience", "education", "skills", "projects", "certificates", "languages", "links"],
    "skills": { "total": 71, "selected": 58, "unselected": 13, "limited": true },
    "items": [
      {
        "id": "review-0-2",
        "index": 0,
        "text": "corrected or accepted text",
        "original": "original parsed text",
        "edited": false,
        "target": "experience",
        "status": "pending",
        "applied": false,
        "page": 2,
        "sectionHeading": "Professional Experience",
        "reason": "incomplete-experience",
        "suggestedTarget": "experience"
      }
    ],
    "total": 34,
    "pending": 34,
    "accepted": 0,
    "ignored": 0
  },
  "version": 1,
  "createdAt": "2026-11-12T12:00:00Z",
  "updatedAt": "2026-11-12T12:00:00Z"
}
```

### Field rules

| Field | Rule |
|---|---|
| `profileId` | Server-generated, immutable, `cvp-` plus UUID; never client-supplied. |
| `schemaVersion` | Exactly `1` for this contract. |
| `name` | 1–80 visible characters, no control characters, client-supplied. |
| `cvData` | Existing Jobsearch `CvBuilderDraftV1`; schema version 1. Client-supplied; server validates shape and limits. |
| `template` | `classic`, `modern` or `compact`. |
| `importReview` | Optional session sidecar from 03B. Required fields as above; no server-side AI inference. |
| `version` | Server-owned, starts at 1, increments on each accepted PATCH. |
| `createdAt`, `updatedAt` | Server-owned ISO-8601 UTC. |
| `owner` | **Never in request/response body.** Derived from verified context. |

### Review item rules

- `id` is stable for the life of the profile and must survive reload.
- `original` and `text` are preserved; `text` may be corrected by the user.
- `status` is `pending`, `accepted` or `ignored`.
- `applied` records an actual draft write, separate from `accepted`.
- `page`, `sectionHeading`, `reason` and `suggestedTarget` preserve provenance.
- `target` is one of `ignore`, `profile`, `experience`, `education`, `skills`,
  `projects`, `certificates`, `links`.
- Rewriting a review item must not create an implicit accepted/applied state.
- Review items are embedded in the profile **for V1** so there are no orphan
  review records. A future chunked sidecar would be a new schema version.

### Ownership and isolation

Every stored record carries server-derived:

- `userId` (verified JWT `sub`)
- `tenantId` (verified tenant claim / partner registry)
- `partnerApplicationId` (verified partner context)
- `issuer` (verified issuer binding)

Every read, update, export and delete filters on all four values. Email,
nickname and client-supplied identity fields are never owner keys. Foreign,
missing or cross-tenant/partner/issuer IDs return the same `404 NOT_FOUND`.

## 3. Schema reconciliation with CV-BUILDER-03B

### CvBuilderDraftV1

The RIS `cvData` payload is the existing Jobsearch draft without a second
schema. The accepted limits are the 03B validation limits:

- `experience`, `education`, `projects`, `certificates`, `languages` and
  `links`: each at most **20** entries.
- `skills`: at most **100** entries, each at most **100** characters.
- `personal.fullName` 200, `email` 320, `phone` 80, `location` 200;
  `profile.headline` 200, `summary` 4,000;
  `experience.employer`/`position` 200, `description` 5,000;
  `education.institution`/`degree` 200, `description` 5,000;
  `projects.name` 200, `projects.technologies` joined length 500,
  `projects.description` 3,000;
  `certificates.name`/`issuer` 200; `languages.language` 100;
  `links.label` 200, `links.url` 1,000.
- `startMonth`/`endMonth`/`date` are `""` or `YYYY-MM`; `current` is boolean;
  language level is `basic|conversational|professional|fluent|native`;
  link kind is `portfolio|github|linkedin|other`.
- `cvData.schemaVersion` must be `1`. Unknown versions are rejected with
  `422 UNSUPPORTED_SCHEMA_VERSION`; no best-effort migration.

### CvBuilderProfileV1 and profileId/cvId

The local `CvBuilderProfileV1.cvId` is **not** an owner identity and is not
sent as a server key. Keep a session-only sidecar mapping:

```text
DurableProfileRef {
  localCvId: "cvb-...",
  profileId: "cvp-...",
  version: 1
}
```

Rules:

- Before durable save, the local `cvId` remains the session identity.
- After a successful create, store `localCvId → profileId → version` in the
  Jobsearch session adapter; do not overwrite unrelated local profiles.
- A durable load may hydrate a local profile whose `cvId` is the server
  `profileId` **only if no local profile with that id exists**. Otherwise show
  a conflict and require an explicit choice; never overwrite the local draft.
- On update, send the server `profileId` and expected version, not the local
  `cvId`, unless the local `cvId` was explicitly mapped to that profile.
- A stale/missing mapping is a conflict, not a reason to create a duplicate.
- Server `profileId`, owner fields, timestamps and version are server-owned.

### ImportReviewV1

The 03B `CvBuilderImportReviewSummary` is a session summary. The durable DTO
adds `schemaVersion: 1` and requires individual `items` to be present whenever
`total > 0`; a counts-only summary is not silently stored as if complete.

- Stored `importReview.schemaVersion` is always `1`; unknown versions are
  rejected with `422 UNSUPPORTED_SCHEMA_VERSION`.
- The Jobsearch adapter normalizes a 03B summary without `schemaVersion` to
  `1` only when its items are present; otherwise `IMPORT_REVIEW_INCOMPLETE`.
- `CvBuilderImportReviewItem.applied` is optional in older 03B data and
  defaults to **false** on read. It is never inferred from `accepted`.
- `accepted` is a decision; `applied` is an actual draft write. Both are
  preserved.
- Item `id`, `index`, `original`, `text`, `edited`, `page`, `sectionHeading`,
  `reason` and `suggestedTarget` are preserved losslessly. `text`/`original`
  are capped at 2,000 characters; larger or truncated data is rejected, never
  silently shortened.
- Items are capped at 500. A larger backlog is rejected rather than dropping
  items.

### Review status/reason enums

`status`: `pending | accepted | ignored`. `applied`: boolean (default false
when absent). `target`/`suggestedTarget`: `ignore | profile | experience |
education | skills | projects | certificates | links`. `reason` is one of the
03B unassigned reasons: `unknown-section`, `training`, `certification-goal`,
`target-roles`, `document-notes`, `incomplete-experience`,
`incomplete-education`, `incomplete-language`, `project-reference`,
`ambiguous`.

## 3. Storage shape

Reuse the existing `partner-profiles` table, but do **not** rely on `gsi-user`
alone for structured-profile isolation: it is keyed by `userId`/`resourceType`
and filters tenant/partner/issuer after the query. The contract requires a
dedicated owner index (implementation proposal: `gsi-structured-owner`) with a
server-derived compound `ownerKey` and `profileId`/`resourceId` range:

```text
resourceId       = "cvp-<uuid>"                  (PK)
ownerKey         = H(tenant|partner|issuer|subject) (new GSI hash)
userId           = verified subject
resourceType     = "StructuredCvProfile"
tenantId         = verified tenant
partnerApplicationId = verified partner
issuer           = verified issuer
version          = integer
createdAt/updatedAt = ISO-8601
payload          = StructuredCvProfileV1 body
```

A signed cursor must bind the full owner scope and index query. If the owner
index is not approved, implementation is blocked rather than falling back to
an unscoped scan or a filter-only approximation.

A dedicated capacity counter and lifecycle guard use the existing
`capacity#`/`lifecycle#` mechanics. No table scan is permitted on normal CRUD.

### Size and capacity

DynamoDB's 400 KiB item limit applies to the complete item, not just `payload`.

- Maximum serialized profile payload: **300,000 bytes** (conservative headroom
  for keys, identity and DynamoDB overhead).
- Maximum review items: **500**.
- Maximum single review text/original: **2,000 characters** each.
- `cvData` arrays: experience/education/projects/certificates/languages/links
  each ≤**20**; skills ≤**100**; skill length ≤**100** (matching the 03B
  builder validation limits).
- Oversize rejects with `413 PAYLOAD_TOO_LARGE` / `PROFILE_TOO_LARGE`; no
  truncation, no partial save and no silent review loss.
- Proposed per-user capacity: **20 structured CV profiles**
  (`REVIEW_REQUIRED`; implementation may choose 10). Capacity uses the
  existing atomic counter transaction pattern.
- If future payloads exceed the safe limit, a new chunked sidecar schema must
  be designed and versioned; V1 does not split a profile invisibly.

## 4. API contract

Base namespace (new, independent):

```text
/v1/partner/me/cv-builder-profiles
```

Dual auth: Cognito access JWT **and** server-side `X-Api-Credential`; partner,
tenant, API profile and issuer must be active. The browser never sends the
partner credential.

| Method | Path | Function | Success |
|---|---|---|---|
| POST | `/v1/partner/me/cv-builder-profiles` | create | 201 |
| GET | `/v1/partner/me/cv-builder-profiles` | list metadata | 200 |
| GET | `/v1/partner/me/cv-builder-profiles/{profileId}` | read full | 200 |
| PATCH | `/v1/partner/me/cv-builder-profiles/{profileId}` | update | 200 |
| DELETE | `/v1/partner/me/cv-builder-profiles/{profileId}` | delete | 204 |
| GET | `/v1/partner/me/cv-builder-profiles/{profileId}/export` | JSON export | 200 |

### Create

```http
POST /v1/partner/me/cv-builder-profiles
Authorization: Bearer <access-token>
X-Api-Credential: <server-only>
Idempotency-Key: <UUID>
Content-Type: application/json

{ "name": "...", "cvData": {...}, "template": "classic", "importReview": {...} }
```

- `Idempotency-Key` required (128-bit UUID, 1–128 chars); raw key never stored,
  only a scope-bound hash.
- A semantic retry returns the original profile and does not duplicate it.
- `201`; `ETag: "v1"`.
- Client identity/version/timestamps/profileId are rejected, not ignored.

### List

`GET ...?limit=1..50&cursor=<signed-scope-cursor>` returns metadata only:
`profileId`, `name`, `template`, `version`, `createdAt`, `updatedAt`. Content
is loaded by ID. Cursor is signed, owner/issuer-bound and never a raw DynamoDB
key.

### Read

`GET .../{profileId}` returns full `StructuredCvProfileV1` and `ETag`.
`If-None-Match` may return 304. Foreign/missing IDs return 404.

### Update

`PATCH .../{profileId}` requires a valid version proof: the contract requires
`If-Match: "vN"`; a body `expectedVersion: N` is accepted only as a legacy
BFF compatibility fallback and must be validated server-side. Missing proof is
`428 PRECONDITION_REQUIRED`; stale proof is `409 VERSION_CONFLICT`. Mutable fields: `name`, `cvData`, `template`,
`importReview`. `profileId`, owner, `schemaVersion`, `version`, `createdAt`
and `updatedAt` are immutable/server-owned. Missing fields remain unchanged;
`null` removes optional `importReview` only by explicit contract (prefer
`importReview: null` only if UI supports clearing it).

- Matching version → 200 with incremented `version`/`ETag`.
- Stale version → `409 VERSION_CONFLICT`; no write.
- Validation/size → `422`/`413`; no partial write.

### Delete

`DELETE .../{profileId}` with optional `If-Match`. Own profile:
**204** on success. Idempotent replay for the same owner: **204**; foreign or
unknown ID: **404** (safe enumeration shape). A version mismatch is
`409 VERSION_CONFLICT`. Deletion is hard delete of the profile item/review
sidecar; backups/PITR follow the retention contract.

### Export

`GET .../{profileId}/export` returns a versioned JSON envelope containing
`profile`, `importReview`, `exportedAt`, `schemaVersion` and
`source: "ris-structured-cv-profile"`. No PDF, token, credential, presigned
URL or AI-provider data. `Content-Disposition: attachment`.

### Pagination, errors, idempotency

- Errors: `{ "error": "safe human message", "code": "CODE" }`; no payload text,
  identity or DynamoDB expressions.
- Codes: `UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`, `VALIDATION_ERROR`,
  `VERSION_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `CAPACITY_EXCEEDED`,
  `PAYLOAD_TOO_LARGE`, `CONSENT_REQUIRED`, `CONSENT_WITHDRAWN`,
  `NOTICE_NOT_ACTIVE`, `STORAGE_DISABLED`, `INTERNAL_ERROR`.
- Idempotency records are owner-scope hashed; same key + different payload is
  `409 IDEMPOTENCY_CONFLICT`; same payload returns original result.
- All writes use conditional version/capacity checks; no last-write-wins.

## 5. Consent and privacy gate

Purpose (proposal, not automatically equivalent to existing purposes):

```text
cv-builder-profile-storage
```

Notice proposal (DRAFT, no legal approval):

```text
structured-cv-profile-storage-2026-11-12-draft-1
state: DRAFT
legalApprovalRef: null
```

- Create/PATCH require an active `GRANTED` consent with accepted notice version.
- `GET`/list/export/delete must remain usable for data-subject rights according
  to the approved privacy policy; exact post-withdrawal readability is an open
  legal decision.
- Withdrawal blocks new writes immediately; proposed behavior is to mark the
  profile unavailable for normal product reads and schedule deletion within
  30 days, while allowing export/delete in that grace period (`REVIEW_REQUIRED`).
- Regrant does not silently restore withdrawn data; data already purged remains
  purged. A profile is never automatically recreated from browser state.
- Art. 9 assessment is mandatory: CV free text may contain health, union,
  religious or other special-category data. Proposed basis: explicit consent
  under Art. 9(2)(a), subject to legal approval.
- No AI/provider transfer is authorized by this storage consent.
- Notice versioning, DRAFT/APPROVED/ACTIVE/SUPERSEDED lifecycle follows
  `CONSENT-V1.md`.
- No production consent activation in this contract task.

## 6. Retention, export and erasure

- Active profile: until explicit delete or verified account erasure; no
  indefinite silent retention. Proposed operational maximum is
  `REVIEW_REQUIRED`, not an invented legal period.
- Review items are embedded; deleting the profile removes the entire sidecar.
- Export includes full draft and review provenance; no PDF-only assumption.
- Account erasure: add a `structured-cv-profiles` step to the existing
  `PrivacyErasure`/R08 flow, owner-scoped and idempotent, deleting the profile
  and embedded review. Resume after partial failure; do not claim completion
  while items remain.
- Privacy inspect/export categories must include structured profiles and review
  metadata.
- Backups/PITR/CloudTrail/CloudWatch are not synchronously purged; restoration
  must replay the deletion ledger before promotion. No physical purge claim.
- Audit receipts contain IDs, hashes, phase/state and counts, never CV text or
  review text.

## 7. Jobsearch BFF contract

Proposed route (must be verified before implementation):

```text
/api/ris/cv-builder-profiles
```

- Reuse existing BFF auth: bearer token, server-side RIS credential, same
  partner/tenant/issuer validation.
- No RIS credential, owner ID or partner ID in browser responses.
- Methods/status/errors mirror the RIS contract; add `Idempotency-Key` and
  `If-Match`/`expectedVersion`.
- Feature flag: `VITE_RIS_CV_BUILDER_PROFILE_STORAGE_ENABLED` (client) and
  server-side `RIS_CV_BUILDER_PROFILE_STORAGE_ENABLED`; off by default.
- No AI/provider call; no PDF upload; no session data copied into RIS unless
  the user clicks durable save.
- Existing CV PDF list and search-profile BFF remain unchanged.

## 8. Existing UI contract

Reuse “Profil → Lebenslauf → Meine Lebensläufe” (`CvBuilderProfileList` and
existing editor/import UI). No second profile manager.

Add later, after contract/backend approval:

- `Dauerhaft speichern` explicit action.
- Per-profile storage status: `session-only`, `durable`, `unsaved-changes`,
  `save-error`, `conflict`.
- Load/update/delete durable profiles.
- Conflict dialog with no forced overwrite.
- Consent grant/withdraw/regrant state.
- Keep existing create/duplicate/rename/download/delete and PDF list unchanged.
- Session-only remains clearly labeled; no automatic RIS write.

## 9. Test contract

Synthetic only; no private CV content:

1. Create + reload after login.
2. Edit + save increments version.
3. Stale expectedVersion → 409, no overwrite.
4. Other user/tenant/partner/issuer → 404.
5. Missing consent → 403/`CONSENT_REQUIRED`; no write.
6. Withdrawn consent → writes blocked; export/delete policy verified.
7. Regrant → new write allowed; old purged data not silently restored.
8. Duplicate via create → new profile ID; no shared owner leakage.
9. Delete → 204, idempotent replay, export 404.
10. Full export includes draft and all review items.
11. Account erasure removes profile/review; partial/resume behavior.
12. 44-item review backlog round-trip, including `applied` and page/section.
13. Multiple profiles: 2+ profiles isolated; profile switch correct.
14. Large payload within limits; oversize → 413 no truncation.
15. Repeated create key/same payload idempotent; different payload conflict.
16. Delete/profile switch/identity reset does not leak old report.
17. Existing 03B review integrity and 03A handoff regressions.

## 10. Open decisions (must be resolved before implementation)

1. Capacity count (proposed 20) and whether 10 matches existing UI.
2. Retention period and withdrawal grace period.
3. Exact post-withdrawal GET vs export/delete behavior.
4. Legal basis and Art. 9 approval; notice text approval.
5. DynamoDB item size margin and whether chunked sidecar is needed for V2.
6. Whether list returns full review counts or metadata only.
7. BFF route naming and feature-flag ownership.
8. Account-erasure ordering and receipt category naming.
9. Backup/PITR restore reconciliation responsibility.
10. Who operates/monitors the new resource (RIS controller/processor model).

**No implementation, migration, consent activation, AWS/Terraform mutation,
main merge or production deployment is authorized by this document.**
