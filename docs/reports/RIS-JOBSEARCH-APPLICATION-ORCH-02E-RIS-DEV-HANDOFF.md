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
| Documents | GATE-14 historical CV/S3 live foundation; ApplicationV1 metadata-only documents, cover-letter versions, configured CV/profile ownership and documentId checks | Verify the new ApplicationV1 reference chain with a configured ProfileRepository fixture, authenticated HTTP/export and live object lifecycle |
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

## Executable acceptance criteria for open gates

| OI | Owner | Command/test | Expected evidence | Target | Approval |
|---|---|---|---|---|---|
| OI-07 | Jobsearch/RIS-DEV | Execute approved session-transfer preview/confirm matrix with duplicate, retry and partial-failure cases | Per-item result artifact, no-loss reconciliation and rollback/retry proof | Authenticated integration environment | Jobsearch + RIS-DEV |
| OI-08 | RIS-DEV/platform | Run authenticated HTTP E2E through the approved BFF/delegation path; verify JWT tenant/issuer/partner binding and absent browser partner secret | CI/live E2E report plus redacted request/response evidence | `ris-dev` integration environment | Security + platform |
| OI-09 | Privacy/platform | Run retention, export-signing, hard-delete/tombstone and backup/PITR restore/delete acceptance suite | Approved privacy decision, retention config, restore/delete evidence and erasure receipt | Controlled non-production environment | Privacy/legal + platform |
| OI-10 | RIS-DEV | Run package, plan and live verifier only with approved profile/workspace/backend guards | Plan artifact, live HTTP/S3/DynamoDB evidence, check results and deployment approval record | Authorized `ris-dev` | RIS-DEV release owner |

Until each row has its named evidence and approval, the corresponding OI is
OPEN and deployment remains BLOCKED.

## GAP-05 evidence boundary

`docs/reports/GATE-14-SECURE-CV-STORAGE-01.md` (commit `2fb346e`) is accepted
as **LIVE VERIFIED HISTORICAL** evidence for the unchanged CV/S3 foundation:
synthetic upload, byte-identical download, deletion, tenant isolation, private
storage, encryption, public-access blocking, IAM and cleanup. It is not claimed
as an ApplicationV1 live-reference test.

`docs/reports/RIS-JOBSEARCH-APPLICATION-ORCH-03A-OWNERSHIP.md` (commit
`ce9ef29`) is **VERIFIED LOCAL** evidence for ApplicationV1 ownership,
documentId matching, tenant/partner/issuer isolation and fail-closed missing
repository behavior. The combined configured ProfileRepository/ApplicationV1
HTTP/export chain remains **PARTIAL / OPEN** and is tracked in
`docs/reports/RIS-JOBSEARCH-APPLICATION-GAP05-EVIDENCE-RECONCILIATION-02.md`.
