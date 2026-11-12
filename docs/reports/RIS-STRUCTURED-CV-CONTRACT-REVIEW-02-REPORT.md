# RIS-STRUCTURED-CV-CONTRACT-REVIEW-02

**Status:** `RIS-STRUCTURED-CV-CONTRACT-02 — TECHNICALLY ALIGNED / IMPLEMENTATION GATES DOCUMENTED`
**Date:** 2026-11-12
**RIS branch:** `feature/ris-structured-cv-contract-01`
**RIS starting HEAD:** `c14bc7f`
**Jobsearch 03B HEAD:** `c4c2cde`
**Scope:** contract/documentation/tests only

## 1. Baseline

- RIS base was verified against `origin/main` (`f830a5e`); the review branch is
  `feature/ris-structured-cv-contract-01`.
- Jobsearch 03B was read at `c4c2cde` without changing product code.
- No RIS/Jobsearch merge, deployment, AWS, Terraform, consent activation or
  private CV data was touched.

## 2. Schema reconciliation

| Jobsearch type | RIS DTO | Decision |
|---|---|---|
| `CvBuilderDraftV1` | `CvBuilderDraftV1` | Same schema version; exact nested object and limits in OpenAPI. |
| `CvBuilderExperienceV1` | `CvBuilderExperienceV1` | Exact fields, 20-entry max, month format `YYYY-MM` or empty. |
| `CvBuilderEducationV1` | `CvBuilderEducationV1` | Exact fields, 20-entry max, institution/degree preserved. |
| `CvBuilderProjectV1` / Certificate / Language / Link | same-named schemas | Exact fields and enum values; 20-entry max. |
| `CvBuilderProfileV1` | `StructuredCvProfileV1` | Server `profileId` replaces trusted local `cvId`; local profile schema is not changed. |
| `CvBuilderImportReviewSummary` | `ImportReviewV1` | Durable DTO adds `schemaVersion: 1`; 03B summary is adapted only when individual items exist. |
| `CvBuilderImportReviewItem` | `ImportReviewItemV1` | Full item shape; `applied` optional in old data → default false; 2,000-char text/original cap; reason enum. |

### Corrected limits found during review

The previous draft was too permissive:

- Entry arrays: **20** (not 100) for experience/education/projects/
  certificates/languages/links.
- Skills: **100** entries, each **100 characters**.
- Review items: **500**; text/original each **2,000 characters**.
- Name: **80** characters.
- Profile payload target: **300,000 bytes** under the DynamoDB 400 KiB limit.

The OpenAPI draft now contains exact nested schemas with
`additionalProperties: false`, array limits, month patterns and enums.

### `cvId` ↔ `profileId`

- Local `CvBuilderProfileV1.cvId` remains a session identity.
- Server `profileId` is the durable identity.
- Adapter sidecar:

```text
DurableProfileRef { localCvId, profileId, version }
```

- A durable load may adopt `profileId` as local `cvId` only when no local
  profile with that id exists; otherwise show a conflict.
- Update uses `profileId` plus expected version, never a guessed local id.
- A missing/stale mapping is a conflict, not a reason to create a duplicate.

### Review specifics

- `importReview.schemaVersion` is required in the durable stored form.
- 03B summaries have no `schemaVersion`; the adapter adds `1` only when
  individual `items` are present.
- Counts-only summaries with `total > 0` are rejected as
  `IMPORT_REVIEW_INCOMPLETE`; they are not silently persisted.
- Older items missing `applied` normalize to `false`; `applied` is never
  inferred from `accepted`.
- `id`, `index`, `original`, `text`, `edited`, `page`, `sectionHeading`,
  `reason`, `target`, `status` and `suggestedTarget` are preserved.
- `accepted` and `applied` stay distinct; duplicate application prevention
  remains a client/back-end rule.

## 3. OpenAPI hardening

- Added full nested `CvBuilderDraftV1` schemas and fixed limits.
- `PATCH` now requires `If-Match` (`IfMatchRequired`); missing proof is
  `428 PRECONDITION_REQUIRED` in the contract; stale proof is 409.
- `POST` keeps required `Idempotency-Key`; semantic create retries return the
  original profile.
- Review `reason`, `target`, `status`, language level, link kind and template
  are explicitly enumerated.
- Unknown schema versions are rejected by enum/version checks.
- `StructuredCvProfileV1` does not expose owner keys; owner fields are not in
  request/response schemas.
- `gsi-user` alone is not sufficient for exact owner isolation and pagination:
  the contract requires a dedicated server-derived owner index
  (`gsi-structured-owner` proposal) or equivalent, with signed owner-scoped
  cursors. No filter-only approximation is accepted.

## 4. Decision matrix

| Topic | Proposal | Status |
|---|---|---|
| Capacity | 20 profiles/user | REVIEW REQUIRED (10 may fit current UI) |
| Consent purpose | `cv-builder-profile-storage` | REVIEW REQUIRED |
| Notice | DRAFT `structured-cv-profile-storage-2026-11-12-draft-1` | DRAFT / no legal approval |
| Art. 9 | explicit special-category assessment/consent | REVIEW REQUIRED |
| Retention | while profile exists; no invented period | REVIEW REQUIRED |
| Withdrawal | block writes; read/export/delete grace policy | REVIEW REQUIRED |
| Export/delete after withdrawal | preserve data-subject rights | REVIEW REQUIRED |
| Backup/restore | replay deletion ledger; no synchronous purge claim | REVIEW REQUIRED |
| Erasure order | add structured-profile step to existing PrivacyErasure/R08 | REVIEW REQUIRED |
| BFF route | `/api/ris/cv-builder-profiles` | proposal; verify before implementation |
| Flags | client/server flags off by default | REVIEW REQUIRED |
| `importReview.schemaVersion` | required durable field, adapter for 03B | technically aligned |
| Missing `applied` | normalize false | technically aligned |
| `cvId`/`profileId` | session sidecar mapping | technically aligned |

No DRAFT notice or legal item is activated by this contract.

## 5. Contract tests

Added `tests/test_structured_cv_contract_document.py` (contract-only):

| Test | Result |
|---|---|
| OpenAPI YAML/path/idempotency/If-Match parse | PASS |
| 44 review items round-trip + ≤300 KB | PASS |
| Missing `applied` rejected at durable boundary | PASS |
| Unknown top-level/import/cv schema versions rejected | PASS |
| Unknown fields, 101 skills, invalid template rejected | PASS |
| Two distinct profile resources | PASS |
| Owner/version/export/erasure/gsi markers present | PASS |
| No private path/name markers in contract artifacts | PASS |

Executed:

```bash
python3 -m pytest -q tests/test_structured_cv_contract_document.py
# 8 passed
```

OpenAPI YAML parse: **PASS**, 3 paths, 18 schemas.

## 6. Changes

- Updated `docs/contracts/STRUCTURED-CV-PROFILE-V1.md`
- Updated `docs/api/openapi-structured-cv-profile-v1.draft.yaml`
- Updated `docs/privacy/STRUCTURED-CV-PROFILE-STORAGE-V1-DRAFT.md`
- Added `tests/test_structured_cv_contract_document.py`
- This report

No production `docs/api/openapi-platform.yaml` change. No product code,
Terraform, AWS, consent catalog, main merge or deployment.

## 7. Open gates

1. Legal/Art. 9 and notice approval
2. Retention/withdrawal policy
3. Capacity decision
4. Dedicated owner-index/IaC design
5. BFF route and flag ownership
6. Backend implementation + synthetic contract tests
7. Jobsearch UI/BFF integration
8. Separate controlled deployment approval

**STOP before backend implementation, BFF/UI code, merge or deployment.**
