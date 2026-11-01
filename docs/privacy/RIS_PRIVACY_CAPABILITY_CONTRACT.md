# RIS Privacy Capability Contract

Status: **PARTIALLY IMPLEMENTED**. R08-A1 delivers the internal receipt journal
repository and storage (production writes fail-closed); R08-B1/B2A deliver
read-only inspection/export; R08-C0A defines the storage-neutral erasure
operation/checkpoint contract. No new erasure execution is active. The
existing `POST /me/erasure` (G5) remains the only implemented account-level
deletion path.

## Domains and responsibilities

| Domain | Owner | RIS role | Current privacy state |
|---|---|---|---|
| Cognito identity | Mays-RIS installation | identity provider | user deletion not part of G5 erasure |
| UserProfile | RIS | controller of app profile | G5 deletes row |
| Work Items / Jobsearches / Entitlements | RIS | controller/processor | G5 cancels non-terminal work; terminal work retained; jobsearches not covered |
| Partner profiles (Manual/CVSP/ATS/CVDocument metadata) | RIS | controller | **not covered by G5** |
| S3 documents (versions/markers) | RIS | controller | G5 deletes current objects only; versions/markers remain |
| Cursor / idempotency / capacity / lifecycle records | RIS | controller | **not covered by G5**; TTL only for cursor/idempotency |
| Partner registry / credentials / API profiles | RIS | controller | credentials/profiles revoked; registry remains |
| Mays-Orders orders | Mays-Orders-AWS | separate controller/processor | internal `privacy/*` functions exist; no running instance assumed |
| Jobsearch browser/session/cache | Jobsearch UI | separate boundary | no RIS server-side cache found; not erased by RIS |
| AI provider | external provider | likely processor | no RIS server-side AI call found; transfer evidence only client/third-party |
| Logs / CloudTrail / CloudWatch | RIS | controller/processor | retention; not erased synchronously |
| Backups / PITR / S3 versions | AWS services | processor | not erased by G5 |

## Service interface (later implementation)

```text
privacy.inspect(subject, context) -> PrivacyInspectionV1
privacy.export(subject, context) -> PrivacyExportV1
privacy.erase(subject, context, options) -> PrivacyOperationV1
privacy.receipts(subject, context, cursor?) -> PrivacyReceiptPageV1
privacy.request_status(operationId, context) -> PrivacyOperationV1
```

- `context` is built only from verified JWT + `X-Api-Credential` + partner
  registry + tenant/issuer. No client-provided identity fields.
- `subject` is the Cognito `sub`; self-service means `subject == context.user`.
  Admin access requires a separate explicit scope and is audited.
- `inspect` returns categories, purposes, domains, receipt counts and known
  limitations; never CV text.
- `export` returns machine-readable JSON; a PDF is a later rendering of the
  same minimal view. No raw CV/prompt/token content.
- `erase` is PREVIEW or EXECUTE; EXECUTE requires an explicit policy and an
  operation record. The normal CRUD 409 for parents with children must not
  block the authorized erasure lifecycle; erasure uses an internal guarded
  path, not public cascade deletes.
- `receipts` is append-only, paginated, identity-bound, and returns only the
  `PrivacyReceiptV1` read model. **R08-A1 provides the internal repository
  only**; the public `privacy.receipts` read model/API is R08-B.
- `request_status` is bound to the same identity and to the operation ID.

## R08-C0A erasure operation contract

`agents.ecosystem.privacy_erasure_contract.ErasureOperationV1` is the
versioned, execution-neutral contract for the later C1 implementation. It is
bound to `operationId`, `idempotencyKey`, user, tenant, partner application and
issuer, and supports `USER` and single-`CV` scopes. Its statuses are
`PENDING`, `RUNNING`, `PARTIAL`, `FAILED` and `COMPLETED`; `COMPLETED` is
terminal and cannot be asserted while any required progress category is not
complete or skipped.

The logical DynamoDB item contract requires an idempotent conditional create
(`attribute_not_exists(operationId)`) and every update to verify the stored
`version` before atomically incrementing it. `idempotencyLookup` and
`scopeKey` are server-derived. Checkpoints contain only opaque server-side
references, phase/state, attempt and timestamps; raw DynamoDB keys, S3 keys,
continuation tokens, URLs, credentials and CV content are not public contract
fields. Checkpoint state is separate from `PrivacyReceiptV1` evidence.

R08-C0B adds `ErasureOperationRepository` as the conditional persistence
adapter for this contract. It is explicitly fail-closed unless
`ERASURE_OPERATION_REPOSITORY_ENABLED=true` is approved and configured. It
uses point reads and conditional writes/transactions only; no normal-path table
scan is available. The repository does not execute G5, delete data or write
receipts. `ErasureWriteFreezeV1` is the prepared next-gate contract for
blocking new uploads/profile changes while an operation is active; C0B does
not enforce it yet.

R08-C0C now couples USER/CV freeze `ConditionCheck` items to partner-profile
create/update/delete transactions when `ERASURE_WRITE_FREEZE_ENABLED=true`.
The legacy UserProfile routes now require the same verified partner context
while that mechanism is enabled and fail closed for JWT-only callers; their
Guard-`ConditionCheck` and UserProfile mutation share one transaction.
Presigned S3 upload URLs already issued before a freeze may remain valid;
upload completion and subsequent metadata mutations are guarded, but this is
not an absolute S3 network write lock.

Operation/checkpoint retention is **REVIEW_REQUIRED** and has no invented
 duration. The contract does not activate production persistence, call AWS,
 write receipts or delete data. C1 must add the subject guard and write-freeze
  enforcement only after policy approval.

## Receipt journal storage (R08-A1)

- Dedicated DynamoDB table `privacy-receipts`; PK `receiptId`, GSI
  `gsi-subject` (`scopeKey`/`scopeSort`), no TTL.
- `append_receipt` is a conditional insert with server timestamp and
  content-hash idempotency; same ID + different payload is rejected. There is
  no update/delete method.
- Exact subject/tenant/partner/issuer isolation from verified context; no
  client-chosen `subjectRef`.
- IAM is `PutItem`/`GetItem`/`Query` only; the normal read path uses PK/GSI, no
  scan. Pagination uses the R07 secure cursor store bound to scope
  `privacy-receipts`.
- `PRIVACY_RECEIPT_JOURNAL_ENABLED=false` (default and Terraform env) keeps
  production writes fail-closed until retention/legal policy and R08-A2
  integration are approved.
- See `docs/privacy/PRIVACY_RECEIPT_JOURNAL.md` and
  `docs/reports/RIS-R08-A1-PRIVACY-RECEIPT-STORAGE.md`.

## Erasure scope (R08-C)

Required order (subject to R08-C design):

1. Stop new processing: mark the subject/operation as deleting; revoke
   credentials and API profiles; revoke sessions/refresh tokens.
2. Delete ATS children, then CVSearchProfiles, then ManualSearchProfiles,
   then CV metadata; use an internal guarded path so the public parent-delete
   409 does not permanently block erasure.
3. Delete all S3 object versions and delete markers for the subject; verify
   emptiness before claiming physical deletion.
4. Delete cursor records, idempotency records, capacity counters and lifecycle
   guards associated with the subject/resources.
5. Delete/retain work items per explicit retention policy; terminal work may
   be retained for duplicate suppression and TTL.
6. Delete the UserProfile row.
7. Cognito user deletion/session revocation is a separate, explicitly
   authorized step; no claim of completion before it is verified.
8. Record `ERASURE_REQUESTED`, `ERASURE_PARTIALLY_COMPLETED` or
   `ERASURE_COMPLETED` with evidence level; never claim backup/PITR/provider
   deletion unless independently evidenced.

Partial completion is a first-class outcome. The operation record must allow
resume without double-deleting or re-creating data. An erasure receipt is not
a physical-purge certificate.

## Backups and restore

- G5 and R08-C erase active data only.
- DynamoDB PITR/backups, S3 old versions and CloudTrail/CloudWatch retention
  survive until their own expiry.
- The deletion ledger / receipt journal must be replayed before a restored
  environment is promoted; a restore must not resurrect an erased subject.
- Production retention periods are **REVIEW REQUIRED**; no invented period in
  this gate.

## Mays-Orders boundary

- Mays-Orders supports internal `privacy/inspect`, `privacy/export`,
  `privacy/erase` via direct Lambda invoke, project context, permissions and an
  internal secret.
- RIS may call it only when an order is actually linked to the subject and
  only via an authorized internal path. No CV data is copied to Orders.
- No public Orders privacy API is introduced.
- Historical test evidence does not prove a currently deployed instance.

## Jobsearch boundary

- No RIS-side Jobsearch cache is present in this repository.
- Browser session/cache data is outside RIS server control; sign-out/revocation
  and a Jobsearch-specific privacy path are required if Jobsearch stores data.
- No assumption that clearing a RIS session clears Jobsearch local storage.

## Provider evidence

- A browser event can prove that the user clicked/requested something, not
  that an external provider received or deleted data.
- `AI_TRANSFER_CONFIRMED` requires `third_party_confirmed` or
  `server_verified` evidence; otherwise record `AI_TRANSFER_REQUESTED` with
  `client_reported`/`requested`.
- No raw prompts/CV content in any receipt or export.
