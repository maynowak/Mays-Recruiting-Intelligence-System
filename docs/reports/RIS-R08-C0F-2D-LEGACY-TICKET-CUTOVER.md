# RIS-R08-C0F-2D — LEGACY UPLOAD TICKET CUTOVER

**Status:** LOCAL CUTOVER CHECK VERIFIED / HISTORICAL LEGACY POPULATION BLOCKS

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `784a072906a11982cc1017798c3ab0810346fa90`
- RIS only; no AWS, deployment, real S3 calls or productive erasure
- Receipt journal and productive erasure persistence remain disabled
- 39 original untracked files preserved

## Issuer inventory

The repository contains two upload-ticket issuers:

1. the partner CV route
   `/v1/partner/me/cvs/{cvId}/document/upload`, now ledger-capable; and
2. the generic legacy `POST /me/documents` route, which has no CV reference or
   verified partner issuer context and is not representable in
   `UploadTicketLedgerV1`.

The document presigner currently returns an `expiresAt` based on its configured
900-second signing interval, but historical generic tickets were not persisted.
That value is not used as retroactive proof for old tickets.

When cutover or ticket-ledger enforcement is enabled, the generic legacy route
fails closed instead of issuing an untracked ticket. No historical ticket is
invented or marked registered.

## Versioned cutover state

`UploadCutoverEvidenceV1` and `UploadCutoverStateV1` record:

- cutover introduction/effective evidence and version;
- expected and covered issuers;
- expected and covered upload paths;
- proof that new registration is ledger-backed;
- unknown legacy-ticket state;
- an explicitly evidenced historical maximum expiry, if one exists;
- zero active actions and complete empty final inventory;
- opaque evidence reference.

`UploadCutoverRepository` persists the state with compare-and-swap version
conditions. Restart/resume with a stale version conflicts. A cutover is
`PROVEN` only when every required field is evidenced. Missing historical
expiry, unknown issuers/paths, unregistered tickets, open actions, incomplete
pagination, non-empty inventory or stale evidence remains `BLOCKED`.

The C0F-2B quiescence assessment now accepts `cutover_proven`; an unproven
cutover blocks lease acquisition. Expiry alone never proves that an upload
finished or that an S3 request ended. Final version/delete-marker inventory
and active-action checks remain mandatory.

## Open boundaries

- Historical generic tickets cannot be retroactively verified under the
  current contract, so quiescence remains blocked until explicit evidence
  proves the population.
- The DynamoDB-to-S3 request race and distributed fencing remain unresolved.
- Existing presigned URLs cannot be revoked by this ledger.
- IAM versioned-list/delete permissions, Object Lock and bucket Deny behavior
  remain deployment blockers; no permissions were changed.

## Verification

| Check | Result |
|---|---|
| Cutover and legacy-path tests | **5 passed** |
| C0B–C0F-2C regression | **309 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| Real AWS/S3 calls | **None** |

## Gate decision

- **R08-C0F-2D local:** **GO** for the versioned, fail-closed cutover check.
- **R08-C0F-2E Distributed Fencing:** **BLOCKED** — no cross-service atomic
  fencing guarantee exists.
- **R08-C1 local:** **BLOCKED** — unknown historical tickets and production
  S3/IAM/Object-Lock verification remain unresolved.
