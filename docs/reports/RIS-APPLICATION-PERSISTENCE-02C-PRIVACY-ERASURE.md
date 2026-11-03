# RIS-APPLICATION-PERSISTENCE-02C — Privacy and Erasure

**Status:** PARTIAL PASS / LEGAL REVIEW REQUIRED

## Data inventory

| Category | V1 behavior | Privacy result |
|---|---|---|
| application/job reference | stored in scoped ApplicationV1 item | included in inspect/export |
| status/history metadata | stored as metadata child records | included in export; resumable erase |
| cover-letter versions | explicitly supplied text child records | included in export; resumable erase |
| profile/CV | versioned references only | delegated to existing profile/document lifecycle |
| contact, salary, interview feedback | not accepted by V1 contract | data minimisation; future change requires review |
| application-owned attachments | no V1 storage path | not accepted; no hidden S3 path |
| tokens/credentials | never accepted or exported | prohibited |
| backups/PITR | operationally outside this feature | retention decision open |

## Implemented integration

- Privacy inspect/export expose an `ApplicationV1` category and fail partial /
  unavailable rather than claiming no data.
- `applications` is now a durable erasure category.
- `ProfileOnlyErasureExecutor` accepts the existing durable operation
  repository and, when the ApplicationV1 repository is injected, deletes
  owner-scoped application pages with persisted checkpoints and CAS operation
  versions.
- CV-scope erasure marks `applications` skipped; user-scope erasure deletes
  applications. Shared CV references are not deleted by application erasure.
- Replays treat an already-deleted application as successful; stale operation
  contexts are rejected by the existing freeze/context contract.
- No global erasure, freeze, cutover or privacy flag was enabled.

## Explicit legal gates

**LEGAL REVIEW REQUIRED** for Art. 6 legal basis, any Art. 9 special-category
content, controller/processor allocation, Jobsearch/partner processing roles,
draft/submitted/withdrawn retention, backup/PITR expiry, legal holds and DPIA
necessity. This engineering change grants no legal approval and does not set
retention periods.

## Evidence

- Privacy/erasure integration regression: **18 passed**.
- Application privacy contract tests: included in the phase regression.
- Synthetic data only; no S3 or AWS resource was accessed or mutated.
