# RIS-JOBSEARCH-APPLICATION-ORCH-02E — RIS-DEV Handoff

## Decision: INTEGRATION HANDOFF READY / DEPLOYMENT GO BLOCKED

The local RIS implementation and contract evidence can be handed to the
separate RIS-DEV team for review. This document is **not** a deployment
authorization and does not approve `ris-dev2`, `ris-dev`, AWS, Terraform Apply,
or production rollout.

## Handoff matrix

| Area | Local evidence | RIS-DEV action |
|---|---|---|
| Status/stage | GAP-01 additive model and Moto roundtrip | Verify deployed legacy compatibility |
| Details/PATCH | 48 ApplicationV1 tests; date, channel, contact, notes, salary, nullable PATCH and versions | Run authenticated API matrix |
| Follow-ups | Moto lifecycle, UTC overdue, nullable update and stale-version tests | Verify timezone and UI mapping |
| Metrics/pagination | Owner-scoped all-page algorithm, signed cursor and Moto metrics test | Verify scale, latency and concurrent mutation behavior |
| Documents | Metadata-only documents, cover-letter versions, configured CV/profile ownership and documentId checks | Verify CV/profile fixture ownership, export shape and live object lifecycle |
| Security | 18 boundary/privacy tests | Verify real JWT/partner credential isolation |
| Delete/erasure | IN_PROGRESS marker, 100-action resumable batches, stale-delete guard, idempotency cleanup and executor resume test | Approve retention, backup/PITR semantics and user-visible erasure receipt |
| Session transfer | No route implemented | Separate design/approval required |

## Explicit missing live gates

- Authorized `ris-dev`/`ris-dev2` preflight and deployment plan.
- Live API CRUD, metrics, cursor, status, follow-up and 409 matrix.
- Live DynamoDB GSI/transaction/scale behavior and concurrent mutation test.
- Live S3/CV/document ownership, export and erasure verification.
- Privacy retention/legal-basis approval and backup/PITR erasure semantics.
- BFF/delegation proof that partner credentials remain server-side.
- Session-transfer preview/confirm design and implementation.
- Authenticated HTTP E2E for every route and error envelope.
- Metrics, CV/document ownership and delete/export evidence against `ris-dev`.

Ownership for these gates is RIS-DEV/platform/privacy, not this local branch.
