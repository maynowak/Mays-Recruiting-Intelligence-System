# R08 Privacy Roadmap

Status: **R08-A1 IMPLEMENTED / R08-B1-B2A VERIFIED LOCAL / R08-C VERIFIED LOCAL SYNTHETIC**.
Receipt writes remain fail-closed. R08-G0 and R08-POLICY-01 provide technical
decision packages, not legal approval. R08-A2 production emission, persistence-
backed/live B verification, full R08-C execution, R08-D legal/cross-domain work
and release remain blocked or review-required. This current status supersedes
the older “B/C not started” wording below; historical gate reports remain
unchanged and are interpreted through the current reconciliation report.

**ORCH-02 (2026-11-04):** Local-only versioned recovery/CAS contract, opaque
deletion-ledger evidence, restore reappearance detection, fail-closed erasure
completion checks and RIS worker cancellation admission hardening are
implemented and tested. Durable deletion-ledger persistence, actual PITR/
restore, live SQS/DLQ/redrive evidence and production activation remain
BLOCKED; no retention period was approved.

**SECURITY-FINAL-REVIEW-06 (2026-11-04):** Worker fence, retry CAS, terminal
failure handling, API cache headers and local ApplicationV1 resume contracts
are locally verified. SECURITY-07 wires the existing ApplicationV1 executor
into public `/me/erasure`; PR readiness and production remain BLOCKED by live
and legal gates. Gate B remains NO-GO.

## R08-A — User evidence journal

### R08-A1 — Durable journal repository (COMPLETE)

- Dedicated DynamoDB table `privacy-receipts` (PK `receiptId`, GSI
  `gsi-subject` on `scopeKey`/`scopeSort`, no TTL).
- `append_receipt` / `get_receipt` / `list_receipts` with validated
  `PrivacyReceiptV1`, server timestamp, conditional insert, content-hash
  idempotency, conflict rejection and secure bounded pagination.
- Exact subject/tenant/partner/issuer isolation; IAM `PutItem`/`GetItem`/`Query`
  only; no scan path.
- `PRIVACY_RECEIPT_JOURNAL_ENABLED=false` until retention/legal policy is
  approved; no CRUD emission and no public API in A1.
- See `docs/reports/RIS-R08-A1-PRIVACY-RECEIPT-STORAGE.md`.

### R08-A2 — Atomic integration and emission (BLOCKED)

- Emit server-verified events at existing write points: profile create/
  update/delete, CV storage confirmation, notice acknowledgement, consent.
- DynamoDB profile mutation + receipt in one `TransactWriteItems` where
  possible; S3/CV via verified status + durable outbox/reconciliation.
- Read-only `privacy.receipts` and `privacy.request_status` contracts remain
  R08-B.
- **Blockers:** retention/legal policy approval, integration review, and the
  browser/BFF delegation decision. `REVIEW_REQUIRED` remains an explicit
  placeholder, not a legal finding.

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
R08-G0 (contract) -> R08-A1 (journal repository)
                  -> R08-A2 (atomic emission) -> R08-B (inspect/export/view)
                  -> R08-C (erasure) -> R08-D (cross-domain/legal)
```

R08-A1 is complete as an internal, fail-closed repository. A production privacy
release remains blocked until retention/legal review, R08-A2 integration and
R08-C/R08-D are complete.
