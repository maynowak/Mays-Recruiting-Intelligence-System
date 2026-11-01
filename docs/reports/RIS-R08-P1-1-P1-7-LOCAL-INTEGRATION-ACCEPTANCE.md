# R08-P1-1 / P1-7 — Jobsearch v1 Local Integration Acceptance

**Date:** 2026-11-01  
**RIS branch:** `feature/ris-partner-profile-persistence-v1`  
**Expected/verified HEAD:** `0fb50467ecf9f5112d40c0843886d783b71f890e`  
**Decision:** **R08-PROFILES-01 BLOCKED** for formal acceptance; local implementation is GO.

## 1. Scope and baseline

| Check | Result |
|---|---|
| P0-1 through P1-6 reports | Reviewed; retained |
| RIS tracked working tree at start | Clean |
| Existing untracked files | 39 preserved |
| Jobsearch / Orders | Read-only; no changes |
| AWS / deployment / Terraform | Not used |
| General erasure | Not implemented or activated |
| Receipt journal | Remains disabled |

The verification uses the existing RIS handlers, repository interfaces,
contract DTOs, in-memory DynamoDB harnesses and fake S3 harnesses. No second
profile API or persistence architecture was introduced.

## 2. Contract and runtime acceptance matrix

| Resource / flow | Local result | Evidence |
|---|---|---|
| `UserProfile` GET → PATCH → GET | **PASS** | P0-1/P0-3 runtime and canonical contract tests; server-owned fields and optimistic versioning checked |
| `CVDocument` create | **PASS** | P0-1/P0-4/P1-6 API tests; canonical IDs/status/content-type validation |
| CV upload ticket | **PASS** | Server-generated document ID and presigned ticket; internal S3 key is not returned |
| Fake-S3 upload → complete → GET/List | **PASS** | P0-5 fake-S3 lifecycle, ownership and `HeadObject` verification tests |
| CV list pagination | **PASS** | `{items,nextCursor}`; empty/final page returns `null`; scoped opaque cursors, tamper/foreign/expiry cases checked |
| `ManualSearchProfile` CRUD | **PASS** | CRUD, pagination, validation, auth and isolation harness |
| `CVSearchProfile` CRUD | **PASS** | CRUD, pagination, parent ownership, validation and isolation harness |
| `ATSSearchProfile` CRUD | **PASS** | CRUD, criteria validation, pagination, parent ownership and isolation harness |
| Capacity limits | **PASS** | 10 CVs / 2 CV search profiles per CV / 5 ATS profiles per search profile; sixth/overflow writes return `409 capacity_exceeded` |
| Version conflicts / parallel last slot | **PASS** | Conditional-write conflict, stale update/delete and concurrent capacity tests |
| Idempotency | **PASS** | Retry identity and different-payload conflict tests |
| User / tenant / partner / issuer isolation | **PASS** | Cross-identity reads, writes, parents and cursors are rejected or hidden |
| Negative security | **PASS** | Forged identity, missing/invalid credential, wrong parent and unauthorized boundary tests |
| OpenAPI/runtime parity | **PASS** | `test_platform_openapi_contract.py`, `test_p20_api_contract_consistency.py`, YAML parse |
| Sensitive response/log absence | **PASS** | No S3 keys, credentials, cursor internals or document text in public DTOs/log assertions |

The focused Jobsearch-v1 fixture set contains and passes:
`user-profile-v1.json`, `cv-document-v1.json`, and `upload-ticket-v1.json`.
Canonical DTO parsing, server-authoritative fields, legacy status/name mapping,
and upload-ticket key rejection are covered by
`tests/test_r08_p1_1_canonical_contract.py`.

## 3. End-to-end synthetic handoff

The following is a synthetic, non-production example. Values are illustrative
and contain no real credentials or document contents.

```http
GET /v1/partner/me/profile
Authorization: Bearer <access-token>
X-Api-Credential: <credential>
```

```json
{
  "schemaVersion": 1,
  "userId": "user-synthetic-001",
  "tenantId": "tenant-synthetic-001",
  "status": "active",
  "nickname": "Example User",
  "version": 1
}
```

```http
POST /v1/partner/me/cvs
Content-Type: application/json

{"filename":"resume.pdf","contentType":"application/pdf"}
```

The response contains a server-owned `cvId`, `documentId`, and pending status.
The upload ticket exposes only the approved public ticket fields; the S3 key is
never returned. After fake-S3 PUT and completion verification:

```json
{
  "schemaVersion": 1,
  "cvId": "cv-synthetic-001",
  "documentId": "doc-synthetic-001",
  "filename": "resume.pdf",
  "contentType": "application/pdf",
  "processingStatus": "ready",
  "sizeBytes": 2048,
  "version": 1
}
```

`ManualSearchProfile`, `CVSearchProfile`, and `ATSSearchProfile` use their
documented collection/item routes and return their existing flat resource
objects. Collection responses use `items` and `nextCursor`.

## 4. Contract reconciliation: pending `sizeBytes`

The reconciled target contract is status-dependent:

| `processingStatus` | `sizeBytes` | Rule |
|---|---|---|
| `pending` | optional/omitted | No authoritative object size exists before verification |
| `ready` | required, positive | Must come from successful S3 `HeadObject` verification |
| `failed` / `deleted` | omitted by RIS | No fabricated value; historical internal values are not re-presented as authoritative |

The RIS local contract projection now accepts pending and terminal documents
without `sizeBytes`, requires a positive size for `ready`, and serializes the
field only for `ready`. Runtime S3 completion and ownership verification were
not weakened. New pending/terminal fixtures and contract tests cover the
status-dependent behavior, and OpenAPI uses explicit status branches.

### Jobsearch-v1 handoff required

Jobsearch-v1 must change its `CVDocumentV1` JSON Schema from an unconditional
required `sizeBytes` to status branches equivalent to the table above (or
introduce a separate pending DTO with the same semantics). The ready branch
must retain `type: integer` and `minimum: 1`; the pending and terminal branches
must not require a size. RIS did not modify Jobsearch source.

## 5. API contract parity

- Existing flat resource and `{"error": ...}` envelopes are preserved; no
  `{data,meta}` breaking wrapper was introduced.
- Stable error codes are present for `unauthorized`, `forbidden`, `not_found`,
  `validation`, `conflict`, `capacity_exceeded`, and `unavailable`.
- CV PATCH accepts canonical `expectedVersion`, `If-Match`, and legacy
  `version`; conflicting tokens validate and stale versions return `409`.
- CV list `limit` is restricted to 1–50; invalid limits return `422`.
- Invalid, expired, tampered, foreign, or scope-mismatched cursors are rejected
  without exposing internal keys.
- OpenAPI documents the CV cursor parameters, `nextCursor`, `If-Match`, error
  code field, and pending/ready CV semantics.

## 6. Test result and skipped-test accounting

### Executed result

The complete relevant RIS regression selection passed:

```text
741 passed, 45 skipped, 258 subtests passed
```

Additional quality checks:

```text
python -m py_compile lambda/handler.py   PASS
git diff --check                         PASS
```

### Skips — not counted as PASS

| Count | Group | Cause / disposition |
|---:|---|---|
| 39 | DynamoDB Local integration | `RIS_TEST_DYNAMODB_ENDPOINT` is unset; the suite refuses to guess an endpoint. Real DynamoDB Local conditional writes, GSI queries, counters and cursor persistence remain unverified. **Separate infrastructure gap.** |
| 6 | Planned privacy/receipt capability tests | R08-A1/A2/B/C planned capabilities: public receipt read model, inspect/export, CRUD emission, and erasure lifecycle are explicitly outside this profile persistence gate. Receipt journal remains disabled. |

The 39 DynamoDB Local tests are not represented as successful database
integration. They must be rerun with an approved local endpoint before release
acceptance.

## 7. Open findings and gate decision

| Finding | Severity | Status | Required next action |
|---|---|---|---|
| DynamoDB Local unavailable | P1 | **OPEN** | Configure `RIS_TEST_DYNAMODB_ENDPOINT`, rerun all 39 tests, and record the result |
| Jobsearch-v1 schema still requires pending `sizeBytes` | P1 contract | **OPEN** | Apply the status-dependent schema change upstream; RIS side is reconciled |
| Privacy receipt/erasure planned tests | Out of scope | **DEFERRED** | Separate R08 privacy capability gate; no activation here |

### Final decisions

- **R08-PROFILES-01: BLOCKED** for formal P1-7 acceptance because the real
  DynamoDB Local integration could not be executed. The RIS in-memory/fake-S3
  implementation gate is **GO**.
- **Jobsearch-Handoff: BLOCKED** until the upstream Jobsearch schema/fixture
  adopts the status-dependent `sizeBytes` contract.
- The RIS-side contract mismatch is reconciled without weakening S3
  verification; only the upstream schema remains open.

## 9. P1-7B contract reconciliation evidence

- RIS contract source: `jobsearch/partner_profile_contract.py` now omits
  `sizeBytes` for `pending`, `failed`, and `deleted`, and requires a positive
  value for `ready`.
- RIS runtime source: `lambda/handler.py::_serialize_cv` already had the safe
  ready-only emission and was intentionally unchanged.
- Fixtures: `tests/fixtures/r08_p1_1/cv-document-v1.json` remains the ready
  fixture; `cv-document-pending-v1.json` covers pending omission.
- OpenAPI: `PartnerCvV1` now selects explicit pending, ready, or terminal
  status branches; only the ready branch requires `sizeBytes`.
- Required upstream handoff: apply the equivalent status branches to the
  Jobsearch-v1 schema and update its pending fixture; do not make RIS emit a
  placeholder size.

## 8. P1-7A DynamoDB Local verification attempt

The existing local integration harness was inspected and used without changes:

- `tests/integration/dynamodb_local_support.py` requires an explicit loopback
  `RIS_TEST_DYNAMODB_ENDPOINT`, rejects non-loopback/AWS endpoints, pins test
  credentials, and generates isolated `ris-r07g0-*` table names.
- No Docker executable or server was available on the host.
- No Java executable or DynamoDB Local runner/JAR was present in the repository.
- `RIS_TEST_DYNAMODB_ENDPOINT` was unset.
- No external download or installation was performed, per scope.

The isolated command was executed:

```text
pytest tests/integration/test_partner_profile_dynamodb_local.py -q -rs
39 skipped in 0.24s
```

All 39 skips had the same explicit reason:
`RIS_TEST_DYNAMODB_ENDPOINT is not set; refusing to guess an endpoint`.
Therefore no DynamoDB Local test is reported as PASS, no local test instance
was started, and there were no temporary database resources to clean up.

**P1-7A result: BLOCKED — environment unavailable.** The next attempt must
provide an already-approved local DynamoDB endpoint (for example an existing
loopback service) and then rerun this exact integration module. The original
39 untracked files remain preserved; the pending `sizeBytes` contract finding
is unchanged.
