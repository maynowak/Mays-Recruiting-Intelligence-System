# RIS-R08-C0F-2C — DURABLE UPLOAD TICKET LEDGER

**Status:** LOCAL LEDGER VERIFIED / CROSS-SERVICE PRODUCTION RISKS OPEN

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `81cfae22b1b154d35d4452c9000f7dc5da234d5c`
- RIS only; no AWS, deployment, real S3 call or productive erasure
- Receipt journal and productive erasure persistence remain disabled
- 39 original untracked files preserved

## Ledger contract and integration

`UploadTicketLedgerV1` stores only:

- ticket, CV and document references;
- user/tenant/partner/issuer scope;
- issued/expiry timestamps;
- status and version.

It never stores upload URLs, S3 keys, credentials or object content.

The existing CV upload-ticket route now uses the ledger when
`ERASURE_UPLOAD_TICKET_LEDGER_ENABLED=true`. Registration is one DynamoDB
transaction containing USER and CV freeze `ConditionCheck`s, the ticket `Put`
and a scope-bound idempotency-marker `Put`. Registration or guard failure
prevents the presigned URL from being returned. If presigning fails, the
registered ticket transitions to `PRESIGN_FAILED`. CV completion re-reads the
ledger and transitions the ticket to `COMPLETED` with a versioned,
guard-rechecked transaction before the CV metadata is finalized.

When freeze enforcement is enabled without the ledger, CV ticket issuance is
fail-closed. With both mechanisms disabled, existing behavior remains
unchanged. The ledger remains explicitly opt-in and is not activated in
production by this gate.

## Quiescence and cutover

Ledger records can be projected into the C0F-2B quiescence evidence. Known
issued tickets remain relevant until their known expiry, but expiry is not
treated as proof that an upload completed or that no S3 request is in flight.
The final version/delete-marker inventory and active-action check remain
mandatory.

The cutover rule is strict: before first use of the ledger-backed erasure
path, the system must either prove that all historical ticket issuances are
registered or mark the legacy population as unknown and block quiescence.
`unregistered_tickets_unknown=True` is an explicit blocking assessment. No
retroactive ticket TTL or retention period is invented.

## Remaining boundaries

- Registration and guard checks are atomic within DynamoDB only; a presign
  request and S3 upload remain outside that transaction.
- A previously returned presigned URL cannot be revoked by the ledger.
- Distributed worker fencing and the DynamoDB-to-S3 race remain open; local
  leases are not treated as production proof.
- Existing IAM still needs explicit `s3:ListBucketVersions` and
  `s3:DeleteObjectVersion`; no IAM/Terraform change was applied.
- Object Lock, legal hold, bucket Deny conditions and unknown old tickets
  remain hard blockers.

## Verification

| Check | Result |
|---|---|
| Upload-ticket ledger tests | **4 passed** |
| S3 adapter/quiescence plus C0B–C0F-2B regression | **304 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| Real AWS/S3 calls | **None** |

Covered cases include atomic registration failure, duplicate/idempotent
issuance, foreign-scope conditions, versioned completion, expiry/unknown
expiry, unknown legacy tickets and quiescence with active tickets.

## Gate decision

- **R08-C0F-2C local:** **GO** — durable ticket contract and local atomic
  registration path verified.
- **R08-C1 local:** **BLOCKED** — historical unregistered tickets,
  cross-service fencing and production IAM/Object-Lock verification remain
  unresolved.
