# Privacy Receipt Journal — Durable Storage (R08-A1)

Status: **IMPLEMENTED** repository + infrastructure contract; **production
writes disabled** (`PRIVACY_RECEIPT_JOURNAL_ENABLED=false`). No public API and
no CRUD integration in R08-A1.

## Storage decision

A dedicated DynamoDB table `${project}-${environment}-privacy-receipts` is used
instead of a namespace in `partner-profiles`.

Reasons:

- separate IAM actions (Put/Get/Query only), no accidental `Scan`/`Delete`
- separate retention/erasure domain from profile data and cursors
- no interaction with 10/2/5 capacity counters, lifecycle guards or
  idempotency records
- one-item-per-receipt key and a subject-scoped GSI for bounded lists
- independent future retention/TTL policy and audit
- cost is on-demand and negligible for receipt-sized items

## Table

| Property | Value |
|---|---|
| Name | `${project_name}-${environment}-privacy-receipts` |
| Billing | PAY_PER_REQUEST |
| PK | `receiptId` (S) |
| GSI | `gsi-subject`: HASH `scopeKey`, RANGE `scopeSort` (ALL) |
| TTL | **none** — retention is REVIEW REQUIRED; no premature deletion |
| Capacity/guards | none; not part of 10/2/5 |

Item fields:

```text
receiptId, scopeKey, scopeSort, subjectRef, tenantRef,
partnerApplicationRef, issuerRef, eventType, recordedAt,
schemaVersion, contentHash, payload, createdAt, updatedAt
```

- `scopeKey = SHA256(tenantRef | partnerApplicationRef | issuerRef | subjectRef)`
  with a separator; no raw identity tuple in the key.
- `scopeSort = recordedAt + "#" + receiptId`.
- `payload` is the validated `PrivacyReceiptV1` object; no CV text, prompts,
  tokens or presigned URLs.
- No `parentId`, no capacity counter, no lifecycle guard, no TTL.

## Append / idempotency contract

- `append_receipt(receipt, context)`:
  - requires a validated `PrivacyReceiptV1`
  - requires exact receipt/context identity match
  - sets `recordedAt` server-side (the caller timestamp is not trusted)
  - conditional `PutItem` with `attribute_not_exists(receiptId)`
  - same receipt ID + same semantic content (timestamp excluded) → returns
    the stored receipt, no duplicate
  - same receipt ID + different content → `PrivacyReceiptConflict`
  - no update/delete method; historical receipts are not rewritten by this
    repository
- `contentHash` covers the receipt except `recordedAt`; on read it is
  recomputed and mismatches fail closed.
- Concurrent identical appends: one conditional write wins; the loser reads
  the stored receipt consistently and returns it if equal, otherwise conflicts.
- Storage errors are `PrivacyReceiptStorageError`, never a false success.

## Read / pagination

- `get_receipt(receiptId, context)`: PK `GetItem`, `ConsistentRead=True`,
  exact identity verification; foreign/missing → NotFound.
- `list_receipts(context, cursor, limit)`: GSI `gsi-subject` query by
  `scopeKey`, newest first, `Limit` clamped to 50, `LastEvaluatedKey` wrapped
  in the existing R07 secure cursor store.
  - cursor is bound to scope `privacy-receipts`, resource type
    `PrivacyReceipt`, parent `scopeKey`, identity context and 15-min expiry.
  - invalid/foreign cursor → `PrivacyReceiptInvalidCursor`.
  - GSI is eventually consistent; pages are not a transactional snapshot.
  - no table scan in the normal read path.

## Fail-closed configuration

- `PRIVACY_RECEIPT_JOURNAL_ENABLED` defaults to false; all journal operations
  raise `PrivacyReceiptJournalDisabled` until explicitly enabled.
- Terraform Lambda env sets it to `"false"` in R08-A1.
- R08-A2 may flip it only after retention/legal policy and integration review.
- Missing table name also disables the journal.
- No CRUD handler writes receipts in this gate.

## IAM

`lambda_privacy_receipts` allows only:

- `dynamodb:PutItem`
- `dynamodb:GetItem`
- `dynamodb:Query`
on the table and its index.

No `Scan`, `UpdateItem`, `DeleteItem` in R08-A1. Erasure/retention deletion
requires a later, separately reviewed policy extension.

## R08-A2 atomic integration strategy

### DynamoDB-only profile writes

Profile mutation, capacity counter, idempotency record, lifecycle guard and
receipt can be one `TransactWriteItems` if every item is distinct and there is
one action per item.

- Receipt `Put` condition: `attribute_not_exists(receiptId)`.
- If the transaction cancels because the receipt already exists:
  - read it consistently and compare `contentHash`;
  - same content + same operation semantics → replay success;
  - different content → conflict;
  - do not reapply the profile mutation blindly.
- Unknown commit outcome: use the existing idempotency proof/operation state;
  never report success without a consistent read.
- Keep one receipt action per item; no receipt update in the same transaction.

### S3 / CV upload

S3 and DynamoDB cannot be one atomic transaction.

- Write `CV_STORAGE_CONFIRMED` only after `HeadObject` verifies the object and
  the CV status transition is successful.
- Use a durable outbox/operation state if the receipt write fails after the CV
  is marked ready; retry the receipt independently.
- Never claim storage in a receipt before verification.
- For erasure, write a completion receipt only after all object versions and
  delete markers are verified absent; otherwise partial/blocked.
- Do not use a receipt as a substitute for S3 cleanup.

## Retention

- No TTL and no invented retention period.
- Production writes remain disabled until retention/legal policy is approved.
- DynamoDB TTL is not an immediate physical-deletion proof.
- Test data lives only in the isolated DynamoDB Local table and is deleted
  with that table.

## Browser authentication boundary

`X-Api-Credential` is an opaque `ris_...` bearer secret (32 random bytes,
SHA-256 lookup digest). It is a confidential partner credential and must never
be:

- stored in browser code/localStorage
- exposed as `VITE_*` or any public frontend config
- logged or returned in API responses

The existing human JWT + `X-Api-Credential` dual-auth is retained. A browser
must not hold the partner credential. The later browser path needs one of:

1. a Jobsearch backend/BFF holding the partner credential and forwarding the
   verified user JWT, or
2. a separately reviewed RIS end-user auth/delegation gate.

No new browser auth is implemented in R08-A1. The journal repository itself is
identity-bound server-side and does not trust client-supplied identity.
