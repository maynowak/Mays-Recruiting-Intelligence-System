# R08-P1-1 / P0-3 — UserProfile PATCH & Versioning

**Status:** COMPLETE — local runtime and contract implementation
**Date:** 2026-11-01

## Scope and baseline

| Check | Result |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| Baseline | `9802b67cbfd1d04cca9fdd2eadb4453cfdc9fbbb` (P0-2) |
| Existing untracked files | 39 preserved |
| Jobsearch / Orders | no product/runtime changes; contract parser reused only |
| AWS / deployment | none |
| Receipt journal | unchanged and disabled |
| CVDocument lifecycle | unchanged; P0-4/P0-5 remain out of scope |

## Implementation

- `GET /me/profile` and profile creation now return the canonical
  `UserProfileV1` projection: integer `schemaVersion: 1`, positive `version`,
  normalized lowercase status, mutable name fields, server-stored email,
  server-owned IDs, and timestamps.
- `PATCH /me/profile` is explicitly dispatched. Only `nickname`, `firstName`
  and `lastName` may change; `expectedVersion` is a concurrency token, not a
  persisted client-controlled field.
- `expectedVersion` in the body and `If-Match` are both accepted. Missing
  tokens return `428`; malformed or conflicting tokens return `400`; stale
  versions return `409`.
- The DynamoDB update is conditional on authenticated `userId`, resolved
  tenant, and `(attribute_not_exists(version) OR version = expectedVersion)`.
  The update writes `version = expectedVersion + 1` in the same operation.
- Legacy rows without `version` are readable as version `1`. Their first
  successful versioned update upgrades them to version `2` atomically; there
  is no read-then-write migration.
- Identity, tenant, email, status, roles, audit timestamps, and unknown fields
  cannot be changed through PATCH. Authentication and P0-2 document ownership
  behavior remain unchanged.

## Evidence

Focused UserProfile/OpenAPI/tenant suite: **83 passed, 252 subtests**.

Full RIS regression selection: **731 passed, 45 skipped, 258 subtests**.
Skips are the established planned capabilities and unavailable local AWS
prerequisites; no AWS access or deployment was performed.

`git diff --check`: required and passed before commit.

## Security findings

- Forged `userId`, `tenantId`, email, status and other identity/audit fields are
  rejected and never become persistence updates.
- Cross-tenant conditional updates fail closed and do not disclose another
  tenant's profile; stale updates cannot overwrite a newer version.
- Concurrent updates using the same version have at most one successful
  writer in the local atomic-table regression.
- No credentials, JWTs, presigned URLs or internal storage data were added to
  logs or error responses.

## Remaining gate

P0-4 is **GO for local implementation**. Product/AWS release remains blocked
until the CVDocument canonical persistence/lifecycle gates and the existing
privacy/erasure approvals are complete.
