# RIS-R08-B1 — USER PRIVACY DATA INSPECTION

**Status:** IMPLEMENTED / LOCAL ACCEPTANCE COMPLETE (available dependencies)

## Scope and contract

RIS now exposes the read-only route:

`GET /v1/partner/me/privacy/inspect`

The route reuses the existing `_partner_profile_context` dual-auth boundary.
The user, tenant, partner application and issuer are taken only from the
verified context; no request parameter can select another subject. The response
contains independent opaque cursors for CV document metadata, manual search
profiles, CV search profiles, ATS search profiles and privacy receipts.

The response reports `COMPLETE` only when all categories are inspectable.
Unavailable stores are represented by `status: UNAVAILABLE`,
`storageStatus: unavailable` and `code: unavailable`, and set the overall
status to `PARTIAL`. An authorized empty store is reported as `no_data`, not as
unavailable. UserProfile is a singular category and is read with tenant
verification.

Only public metadata/DTO fields are projected. S3 keys, document contents,
JWTs, credentials and presigned URLs are not returned. No CRUD, erasure,
receipt-writing, Jobsearch, Orders, AWS or deployment behavior was changed.

## Data coverage

| Category | Inspection | Retention reference | Local result |
|---|---|---|---|
| UserProfile | Name/contact profile projection | `RIS-JOBSEARCH-RETENTION-POLICY-V1#user-profile` | Available when configured; `no_data` when absent |
| CVDocument | Metadata DTO only | `RIS-JOBSEARCH-RETENTION-POLICY-V1#cv-metadata` | Paginated |
| ManualSearchProfile | Public profile DTO | `RIS-JOBSEARCH-RETENTION-POLICY-V1#manual-search-profile` | Paginated |
| CVSearchProfile | Public profile DTO | `RIS-JOBSEARCH-RETENTION-POLICY-V1#cv-search-profile` | Paginated |
| ATSSearchProfile | Public profile DTO | `RIS-JOBSEARCH-RETENTION-POLICY-V1#ats-search-profile` | Paginated |
| Privacy Receipts | Authorized receipt projection | `RIS-PRIVACY-RECEIPT-RETENTION-DECISION#REVIEW_REQUIRED` | `UNAVAILABLE` while journal is disabled |

## Verification

| Check | Result |
|---|---|
| `tests/test_partner_privacy_inspection.py` | **4 passed** |
| B1/privacy receipt/API focused run | **111 passed** (252 subtests) |
| Existing privacy-erasure regression | **12 passed, 6 known pre-existing failures** |
| `py_compile` (`lambda/handler.py`, B1 test) | **PASS** |
| `git diff --check` | **PASS** |
| OpenAPI YAML parse | **PASS** |
| DynamoDB Local | Not available; no installation performed |

The six pre-existing failures are in `test_privacy_erasure_security.py`
and require `boto3` for the existing work-item lookup. They are unrelated to
the B1 read-only path. The complete repository collection additionally cannot
collect ten modules in this environment because `boto3` and/or `requests` are
not installed; no dependency was installed or changed.

The receipt journal is intentionally disabled under the existing R08-A1
decision, so receipt inspection is correctly and explicitly `UNAVAILABLE`.
Real DynamoDB persistence, cross-page integration and receipt pagination could
not be claimed locally.

## Acceptance decision

- **B1:** PASS for the implemented, locally testable read-only inspection and
  its security/partial-coverage contract.
- **Coverage:** PARTIAL at runtime while DynamoDB stores are unavailable or
  unconfigured and while the receipt journal is disabled; this is visible in
  the response and is never represented as empty data.
- **R08-B2 Export-Readiness:** **BLOCKED**. Export requires successful
  persistence-backed inspection verification and an approved/available
  receipt-storage policy; those prerequisites are not available in this gate.
