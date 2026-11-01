# R08-P1-1 / P0-4 — CVDocument V1 Normalization

**Status:** COMPLETE — runtime response normalization and metadata boundary
**Date:** 2026-11-01

## Baseline and scope

| Check | Result |
|---|---|
| Branch / baseline | `feature/ris-partner-profile-persistence-v1` @ `b8d48e9` |
| Existing untracked files | 39 preserved |
| P0-1 through P0-3 | complete and retained |
| Jobsearch / Orders | no product or persistence changes; existing contract/repository reused |
| AWS / deployment | none |
| Receipt journal | unchanged and disabled |
| P0-5 | not implemented or advanced by this gate |

## Canonical response contract

All partner CV create/get/list/update responses now use the public
`CVDocumentV1` projection:

- `schemaVersion: 1`, `cvId`, server-assigned `documentId` when allocated,
  `filename`, `contentType: application/pdf`, lifecycle status, timestamps and
  `version`.
- Legacy `name` is accepted as an input compatibility alias but is never
  emitted. `filename` is also accepted as the canonical input name.
- Legacy `upload_pending` maps to `pending`; `error` and `delete_failed` map
  to `failed`. Unknown statuses fail closed; no status is promoted to `ready`
  without the existing verification path.
- `sizeBytes` is emitted only for `ready` rows with a positive size. The
  existing `HeadObject` verification in `/document/complete` is the source of
  that ready transition. Pending rows retain pending semantics and do not
  expose an unverified size.
- `cvId` and `documentId` remain distinct; no S3 key, bucket path, URL or
  internal repository field is included in the DTO.

## Metadata and compatibility

The writable metadata allowlist is exactly `pageCount` and `language`.
Unknown metadata fields, invalid page counts, invalid languages and unknown
top-level CV payload fields are rejected. Legacy records remain readable; only
the canonical metadata subset is projected publicly, while legacy persistence
is not rewritten by this gate.

The existing repository, server-generated CV ids, document ids, ownership
checks, partner/issuer checks, optimistic version conflict behavior and
10-CV capacity counter remain in use. No second document persistence was
introduced.

## Verification

- Focused CV/OpenAPI/contract suite: **115 passed, 252 subtests**.
- RIS regression selection: **735 passed, 45 skipped, 258 subtests**.
- DynamoDB Local was not available; repository/in-memory atomic and capacity
  harnesses were used. This verification gap is documented and does not
  authorize AWS release.
- `git diff --check`: passed before commit.

## Security and remaining risks

- User, tenant, partner and issuer isolation remains enforced by the existing
  repository context and was covered by the regression suite.
- Public DTOs contain no S3 keys or presigned URLs; upload/download tickets
  remain transport-only.
- Physical S3 purge, upload-complete processing, and any receipt activation
  remain outside this gate.

**P0-5:** **GO for local implementation**, with DynamoDB Local/E2E verification
still required when available. Product/AWS release remains **BLOCKED** until
P0-5 and the outstanding privacy/erasure approvals are complete.
