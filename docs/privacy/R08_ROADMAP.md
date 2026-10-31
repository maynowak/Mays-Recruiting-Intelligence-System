# R08 Privacy Roadmap

Status: **SPECIFIED**. R08-G0 implemented only the receipt contract and
analysis. No privacy API, storage or new erasure code.

## R08-A — User evidence journal

- Append-only receipt storage in the existing data layer (no new public table
  without a storage review).
- Emit server-verified events at the existing write points: profile create/
  update, CV metadata create, cursor/erasure requests, credential revocation.
- Identity binding: subject/tenant/partner/issuer; no CV text/prompts/tokens.
- Read-only `privacy.receipts` and `privacy.request_status` contracts.
- Contract tests for schema, binding, forbidden content, pagination and
  tenant/partner isolation.
- **Blocker to clear before start:** legal notice/consent wording and
  retention references; storage retention decision. `REVIEW_REQUIRED` may be
  used as an explicit placeholder, not a legal finding.

## R08-B — Inspect/export and "Mein Datenschutz"

- `privacy.inspect` across RIS domains (data categories, purposes, domains,
  limitations).
- `privacy.export` JSON; PDF rendering later.
- User view/API with verified self-only access.
- Must include partner profiles, S3 version counts (not content), cursor/
  idempotency counts, work items, and explicit backup/provider limitations.
- No raw CV text/prompts/tokens in export or PDF.

## R08-C — Erasure lifecycle

- Internal guarded erase for ATS → CVSP → manual → CV metadata.
- S3 **all versions + delete markers** purge and verification; no false
  physical-purge claim.
- Cursor, idempotency, capacity and lifecycle records for the subject.
- Work-item retention decision; terminal work may remain for duplicate
  suppression.
- Cognito deletion/session revocation as an explicit authorized step.
- PREVIEW/EXECUTE, operation ID, partial completion, idempotent resume,
  no public cascade and no permanent parent-409 block.
- Restore/backup reconciliation against a deletion ledger.

## R08-D — Cross-domain and provider evidence

- Authorized internal Mays-Orders privacy call only when an order is actually
  linked to the subject; no CV data copied to Orders.
- Provider evidence handling: `third_party_confirmed` only; client-reported
  events never promoted.
- Jobsearch/browser boundary documentation and, if required, a separate
  Jobsearch privacy path.
- Legal/processor review, DSFA screening, retention finalization.

## Sequencing

```text
R08-G0 (contract) -> R08-A (journal) -> R08-B (inspect/export/view)
                  -> R08-C (erasure) -> R08-D (cross-domain/legal)
```

R08-A can start on the contract, but a production privacy release is blocked
until R08-C/R08-D and legal review are complete.
