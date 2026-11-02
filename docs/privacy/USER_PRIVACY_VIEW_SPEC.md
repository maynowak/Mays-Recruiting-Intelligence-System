# "Mein Datenschutz" — User View Specification (later gate)

Status: **SPECIFIED**, not implemented. No new public API in R08-G0.

## Views

1. **Overview**: stored categories, purposes, processing domains, active
   consents (if any), notice versions/digests, open requests, known
   limitations (backups, provider, Jobsearch browser storage).
2. **Receipts**: paginated journal from `PrivacyReceiptV1`; filter by event,
   domain and date; no raw CV/prompt/token data.
3. **Export**: request machine-readable JSON; status; download when complete.
4. **Erasure**: request with explicit scope and consequences; PREVIEW then
   EXECUTE; status and partial-completion limitations.
5. **Request status**: `operationId`, steps, completed/partial/blocked,
   evidence level, retention caveats.

## Minimal API shape (later)

```text
GET  /me/privacy
GET  /me/privacy/receipts?cursor=...&limit=...
POST /me/privacy/export
POST /me/privacy/erasure        (preview=true|false)
GET  /me/privacy/requests/{operationId}
```

All routes require the existing verified human context. A receipt/operation is
readable only by the matching user/tenant/partner/issuer. Admin access, if
ever added, is a separate explicit scope and audit path.

## JSON export

- `schemaVersion`
- `subjectRef` (opaque)
- `generatedAt`
- `dataCategories[]` with purpose, domain, retentionPolicyRef
- `receipts[]` (minimal fields)
- `erasureRequests[]` (status/limitations)
- `limitations[]` (backup/PITR, provider, Jobsearch browser data)

No CV text, prompts, tokens, presigned URLs or secrets.

## PDF report

The PDF is a rendering of the same minimal JSON: category counts, purposes,
receipt timeline, request status, retention/backup explanations. It must not
duplicate CV content or raw provider payloads. It is not a legal certificate.

## UX constraints

- No dark-pattern consent; withdrawal must be as easy as consent.
- Explain backup/PITR and provider limits in plain language.
- Do not promise immediate physical deletion where only logical deletion or
  version markers are implemented.
- Show `REVIEW REQUIRED` references for legal basis/retention rather than
  invented text.
