# RIS-R08-B2A — USER PRIVACY DATA EXPORT

**Status:** IMPLEMENTED / LOCAL ACCEPTANCE COMPLETE (available dependencies)

## Git and scope

| Check | Result |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| Expected parent | `7d9d77d70e5a212bc5dffdb3d788b0f9c85d1b07` |
| Scope | RIS only; no AWS, deployment, Jobsearch, Orders or Redis changes |
| Untracked baseline | 39 preserved |

The export is exposed as the read-only route:

`GET /v1/partner/me/privacy/export`

It reuses the R08-B1 verified `_partner_profile_context` and existing profile
repositories. No client-provided user, tenant, partner or issuer identifier is
accepted. Every profile category is exhausted page by page using the existing
scope-bound opaque cursor mechanism. Cursor advancement is checked to prevent
an infinite export loop.

## Export contract

The versioned JSON envelope has `schemaVersion: 1`,
`exportType: RIS_USER_PRIVACY_EXPORT`, an overall `status`, a separate
`metadataExport` section and a separate `fileExport` section.

Metadata categories:

- UserProfile
- CVDocument metadata
- ManualSearchProfile
- CVSearchProfile
- ATSSearchProfile
- authorized Privacy Receipts, when the journal is available

An authorized empty category is `no_data`. A missing or failing store is
`UNAVAILABLE` and makes both metadata and overall export status `PARTIAL`.
`COMPLETE` is never returned when a category could not be fully collected.
The disabled receipt journal therefore remains explicitly `UNAVAILABLE`.

CV PDF contents are not embedded. Ready CVs are represented in `fileExport`
with their CV/document identifiers and the existing ownership-checked download
endpoint, which issues a short-lived secure download ticket. No presigned URL,
S3 key, JWT, credential or document content is stored in the export. File
completeness is explicitly separate: the current JSON export reports
`fileExport.status: NOT_INCLUDED` and `complete: false`.

## Verification

| Check | Result |
|---|---|
| B2A export + B1 inspection tests | **8 passed** |
| B2A/B1 + receipt + API consistency focused run | **115 passed, 252 subtests** |
| `py_compile` | **PASS** |
| OpenAPI YAML parse | **PASS** |
| `git diff --check` | **PASS** |
| DynamoDB Local | Not available; no installation performed |

The full repository collection remains environment-limited: modules requiring
`boto3` and/or `requests` cannot be collected here. Existing privacy-erasure
tests also retain their documented `boto3`-dependent failures. No dependency
was installed and no test was changed to manufacture a pass.

## Acceptance and remaining blockers

- **R08-B2A:** PASS for the locally testable, metadata-complete export path,
  secure scoping, pagination, partial-state handling and secret exclusion.
- **Export coverage:** Metadata is complete only when every category is
  collected. File export is intentionally not embedded; secure ticket retrieval
  remains a separate, authorized operation.
- **R08-B2B E2E-Readiness:** **BLOCKED**. DynamoDB-backed multi-page
  integration, real ownership checks against deployed stores, S3 ticket
  issuance and receipt pagination require the unavailable AWS/DynamoDB
  environment. The receipt journal also remains disabled by policy.
