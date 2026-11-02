# R08-P1-1 / P0-5 — CV Upload Completion & Ownership

**Status:** COMPLETE — local completion verification and ownership gate
**Date:** 2026-11-01

## Baseline and scope

| Check | Result |
|---|---|
| Branch / baseline | `feature/ris-partner-profile-persistence-v1` @ `9079863` |
| Existing untracked files | 39 preserved |
| P0-1 through P0-4 | complete and retained |
| AWS / deployment / Terraform | none |
| Jobsearch / Orders | unchanged; existing RIS repository/contract interfaces reused |
| Receipt journal | unchanged and disabled |
| General erasure | not implemented by this gate |

## Lifecycle guarantees

- The existing flow remains Create → server-generated upload ticket → direct
  S3 PUT → Complete. No second document store was introduced.
- Upload and completion operate on the stored CV record and its server-created
  `documentId`; client-supplied ids are never used to construct an S3 key.
  The optional `documentId` in Complete is only an echo check and mismatches
  are rejected.
- Repository ownership checks continue to bind `userId`, tenant, partner
  application and issuer. A caller cannot complete another caller's CV or use
  a foreign partner/issuer context.
- Complete calls `HeadObject` against the server-derived key and requires the
  expected document id, `application/pdf`, and a positive object size. Only
  then is the existing versioned row moved to `ready` and `sizeBytes` exposed.
- Missing, empty, wrong-content-type, mismatched or otherwise incomplete
  objects remain non-ready and return a conflict. No unverified size is
  invented.
- Repeated Complete is idempotent after verification. Complete, update and
  delete use the existing repository optimistic version checks; a concurrent
  delete conflict releases its temporary delete reservation rather than
  stranding the guard.

## Ticket and storage security

Presigned tickets remain short-lived transport only. Their S3 key is derived
from stored server-owned tenant/user/document data. Partner and issuer context
is supplied from the verified request context and repository ownership checks,
not from upload or completion payloads. Public responses contain no S3 key,
bucket path, credential or secret.

The existing delete report retains S3 `versionId`, delete-marker and physical-
purge classification internally for the current delete response. No receipt
activation or general erasure journal was added. Durable cross-operation
version-ID journaling remains a later privacy/erasure concern.

## Contract resolution

`CVDocumentV1` responses always emit the canonical common fields. `documentId`
and `sizeBytes` are optional while a row is pending because no object has been
verified. `sizeBytes` becomes present only for verified `ready` rows. OpenAPI
describes this pending/ready distinction instead of emitting a fabricated zero
or claiming a pending object is complete. Legacy `name`, `size` and lifecycle
values are accepted/read as compatibility aliases but never emitted publicly.

## Verification

- CV lifecycle, ownership, metadata and OpenAPI suite: **83 passed, 252
  subtests**.
- Full RIS regression selection: **738 passed, 45 skipped, 258 subtests**.
- DynamoDB Local was unavailable; repository/in-memory conditional, capacity
  and ownership harnesses were used. This verification gap remains open for
  AWS-equivalent validation.
- `py_compile` and `git diff --check`: passed before commit.

## Remaining risks / next gate

- S3 version IDs are available in the existing delete report but are not yet
  activated in a durable privacy receipt journal.
- Real DynamoDB Local/AWS integration and S3 versioned-bucket E2E remain
  outstanding; no AWS access or deployment was performed.
- Processing beyond upload verification remains out of scope.

**P1-6:** **GO for local implementation**. Product/AWS release remains
**BLOCKED** pending P1-6 privacy/erasure decisions and the documented local
AWS verification gap.
