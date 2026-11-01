# R08-P1-1 / P0-2 — Document API Security

**Status:** COMPLETE — runtime security and response projection implemented
**Date:** 2026-11-01

## Baseline and scope

| Check | Result |
|---|---|
| RIS baseline | `feature/ris-partner-profile-persistence-v1` @ `95fe85aa` |
| Existing untracked files | 39 preserved |
| P0-1 status | complete; canonical DTO/ticket contract available |
| Jobsearch / Orders | unchanged; Jobsearch read-only at `c787feaf` |
| AWS / deployment | none |
| Receipt journal | unchanged and disabled |
| P0-3 through P0-5 | not implemented in this gate |

## Security changes

### F-JM-13 closed

`POST /me/documents`, `GET /me/documents/{docId}` and their document helper
responses no longer expose `key`, bucket paths or `expiresIn`. Public upload
responses contain exactly the canonical transport fields:

```json
{
  "documentId": "server-generated",
  "uploadUrl": "short-lived-presigned-url",
  "expiresAt": "absolute-RFC3339-time",
  "requiredHeaders": {"Content-Type": "application/pdf"}
}
```

Download responses contain `documentId`, `downloadUrl` and `expiresAt`.
Partner CV upload/download responses use the same absolute-expiry contract.
The presigned URL remains the only browser transport for the object; the S3
key remains internal to the storage helper.

### Identity, tenant and ownership

- Legacy document handlers now resolve tenant context from the verified JWT
  claim or server-side partner registry resolution.
- Missing or conflicting tenant context returns `403`; unauthenticated
  callers still receive `401`.
- `build_key` and every public document operation fail closed without a
  non-empty tenant. The historical `tenant/default` fallback is removed.
- User identity and tenant are never read from the request body or URL as an
  authorization source. The route's document id is checked against the
  authenticated user's tenant/user-derived key.
- Partner CV routes retain their existing partner application, tenant,
  issuer, parent-chain and ownership checks; the storage helper now also
  requires the resolved tenant.

### Logging and data minimization

Errors log only stable exception labels/messages already used by the handlers;
no presigned URL, S3 key, JWT, credential or bucket path is added to logs or
error responses. Delete acknowledgements expose only `deleted` and
`documentId`; physical purge remains explicitly separate.

## Compatibility decision

The existing RIS Jobsearch repository contains no productive document-upload
client; Jobsearch currently retains browser `File` objects/session state. The
server-side upload flow remains create/prepare → direct PUT → server-side
HEAD/complete. The public field names are normalized at both legacy and
partner routes. No legacy public S3-key compatibility mode is retained,
because it would violate the security contract. Existing internal helper
metadata (`head_document`) may still contain a key for server-only lifecycle
logic; it is not serialized into public DTOs.

## Tests and evidence

- Targeted document/security/contract/OpenAPI suite: **114 passed, 250
  subtests**.
- Full RIS regression selection: **695 passed, 45 skipped, 256 subtests**.
  Skips remain the established planned R08 capabilities and unavailable
  DynamoDB Local prerequisites.
- `git diff --check`: required before commit.

## Closed findings

- **F-JM-13:** internal S3 key and legacy `docId`/`expiresIn` exposure —
  closed for legacy and partner document response DTOs.
- Legacy implicit `tenant/default` fallback — closed.
- Upload/download ticket OpenAPI/runtime mismatch — closed for the changed
  routes (`documentId`, `expiresAt`, `requiredHeaders`).
- Missing-tenant and public-response key leakage tests — added.

## Remaining risks / next gate

- S3 version/delete-marker purge is not implemented; a delete acknowledgement
  is not a physical purge certificate.
- UserProfile PATCH/If-Match and optimistic version enforcement remain P0-3.
- CVDocument canonical response persistence/field migration remains P0-4.
- Upload-complete lifecycle and verified-size/status integration remain P0-5;
  this gate did not add receipt writes or processing behavior.
- AWS-E2E and product release remain blocked until these gates and the existing
  erasure/retention approvals are complete.

**P0-3:** **GO for local implementation**. Product/AWS release remains
**BLOCKED** by the subsequent contract and erasure gates.
