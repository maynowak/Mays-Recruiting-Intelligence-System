# RIS-JOBSEARCH-APPLICATION-ORCH-01B — Cockpit and Documents

## Result

```text
PACKAGE B — IMPLEMENTED LOCALLY / MOTO RUNTIME EVIDENCE OPEN
```

## Cockpit

`GET /v1/partner/me/applications/metrics` is added under the existing partner
namespace and JWT/credential boundary. The repository consumes every
owner-scoped cursor page and returns `total`, `drafts`, `submitted`,
`interviews`, `openFollowUps`, and `overdueFollowUps`.

Status/stage list filters remain mutually exclusive and signed into cursors.
The existing deterministic GSI ordering is retained. Metrics are not derived
from the first page.

## Documents and CV references

- `documents` supports cover-letter draft, immutable metadata-bearing versions,
  CV references and document status.
- Cover-letter versions require the application job ID and store no PDF bytes,
  S3 keys, presigned URLs or CV hashes.
- The existing `PartnerProfileRepository` verifies CV ownership and optional
  `documentId` binding using the authenticated user, tenant, partner and issuer.
- Export includes application documents and cover-letter child metadata.
- Existing transactional delete/erasure child traversal remains in use.

Legacy plain-text cover-letter requests remain accepted and are normalized to a
manual version for compatibility.

## API and infrastructure

- Existing CRUD routes were reused.
- Added only `GET /v1/partner/me/applications/metrics`.
- Added the corresponding explicit JWT-protected API Gateway route.
- No new authentication, table, S3 architecture or credential path was added.

## Evidence

- Metrics algorithm test: **15 passed** in the combined local subset.
- Full application selection after integration: **30 passed, 11 skipped**;
  Moto-dependent tests are skipped because `boto3` is unavailable.
- Python compilation and `git diff --check`: PASS.
- No live API, AWS or deployment test was run.

## Commits

- `6c1344c` — complete metrics and unit evidence
- `b3fb276` — metrics API route and API documentation
- `e592321` — owned CV-reference verification

Package B is locally implemented but remains not release-ready until Moto
runtime evidence and later live gates are available.
