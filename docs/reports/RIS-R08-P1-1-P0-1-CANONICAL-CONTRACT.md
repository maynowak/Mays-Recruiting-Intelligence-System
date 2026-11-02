# R08-P1-1 / P0-1 — Canonical User & CV Contract

**Status:** COMPLETE — contract definition only; runtime migration remains
open.  **Date:** 2026-11-01

## Baseline and scope

| Check | Result |
|---|---|
| RIS branch / initial HEAD | `feature/ris-partner-profile-persistence-v1` @ `b76adfa` |
| Initial tracked status | clean |
| Existing untracked files | 39, preserved |
| Jobsearch baseline | `main` @ `c787feaf99a6`, read-only |
| Handler/runtime changes | none |
| AWS/deployment/journal | none; journal remains disabled |

P0-1 was not previously complete. The existing R08-JM-G0 matrix still listed
F-JM-01 through F-JM-06 and F-JM-13 as open P0 findings.

## Canonical decisions

### UserProfileV1

- `schemaVersion` is integer `1`.
- `version` is a positive optimistic-concurrency token.
- `status` is exactly `active | disabled | pending`.
- `nickname`, `firstName`, `lastName` are the mutable name fields.
- `userId`, `tenantId` and `email` are server-authoritative response fields;
  client identity fields are rejected.
- The canonical update contract is partial `PATCH`, carrying
  `expectedVersion` or the equivalent `If-Match` header. Conflicting values
  are invalid and stale values must become HTTP `409` in the runtime gate.
- The contract module keeps the old `displayName`, uppercase status and
  missing-version representation readable for migration; `canonical_dict()`
  emits only the v1 response shape.

### CVDocumentV1

- `cvId` identifies the user-owned CV aggregate; `documentId` identifies the
  secure document record. They are never interchangeable.
- Canonical fields are `filename`, `contentType: application/pdf`, and
  `sizeBytes >= 1`.
- Canonical processing status is `pending | ready | failed | deleted`.
- Legacy `name`/`size` are read aliases. `upload_pending` maps to `pending`,
  `error` and `delete_failed` map to `failed`; no unknown or ambiguous status
  is silently accepted. `deleted` is a canonical lifecycle state and does not
  claim physical S3 purge.
- The canonical DTO contains only allow-listed metadata (`pageCount`,
  `language`) and never CV text, browser files, URLs, tokens or S3 keys.
- `canonical_dict()` requires a server-assigned `documentId`, verified PDF
  content type and positive verified size. The existing legacy `to_dict()` is
  retained until the handler/repository migration in P0-2/P0-3.

### Upload ticket

`DocumentUploadTicketV1` is the public contract: `documentId`, `uploadUrl`,
absolute `expiresAt`, and `requiredHeaders`. Internal S3 keys are forbidden.
The server creates `documentId`; the client cannot choose an ownership or key
component. Upload preparation, direct PUT, server-side HEAD verification and
complete-to-`ready` remain the required lifecycle. The current runtime still
uses the legacy `docId`/`expiresIn` response and therefore remains a P0-2
implementation task; no handler was changed in this gate.

## Artifacts

- `jobsearch/partner_profile_contract.py` — canonical projections, aliases,
  status mapping, patch/version validators and upload-ticket DTO.
- `docs/API/openapi-platform.yaml` — UserProfileV1, CVDocumentV1 and upload
  ticket schemas, including PATCH/409 contract.
- `tests/fixtures/r08_p1_1/` — synthetic UserProfile, CVDocument and upload
  ticket fixtures.
- `tests/test_r08_p1_1_canonical_contract.py` — positive, negative, legacy
  compatibility, version-conflict and no-S3-key tests.

## Acceptance and remaining gates

P0-1 is accepted when the canonical fixtures validate, forbidden identity and
S3-key fields fail closed, legacy aliases map explicitly, and existing RIS
contract tests remain green. This gate does not claim runtime conformance:
handlers, persistence field migration, upload-complete response projection,
and real HTTP `PATCH`/`If-Match` behavior belong to P0-2/P0-3.

## Test evidence

- P0-1 targeted contract/OpenAPI set: **117 passed, 250 subtests**.
- Broader partner/API contract regression: **575 passed, 256 subtests**.
- Full RIS regression selection including privacy and integration tests:
  **692 passed, 45 skipped, 256 subtests**. The skips are the established
  planned R08 capabilities and unavailable DynamoDB Local prerequisites.
- `git diff --check`: **PASS**.

**P0-2:** **GO for local implementation** of the document API security and
runtime projection. **BLOCKED for AWS-E2E/product release** until the runtime
returns the canonical ticket, enforces tenant ownership and passes the
handler/OpenAPI regression without exposing `key`.

No receipt activation, AWS operation, deployment or production approval is
included in this report.
