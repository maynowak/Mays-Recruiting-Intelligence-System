# R08-E2E-G2B-1 — UPLOAD LEDGER & CUTOVER INFRASTRUCTURE

**Status:** STATIC WIRING COMPLETE / OPERATIONAL CUTOVER UNCONFIRMED

## Baseline and boundary

- Starting HEAD: `561ed4df6e4e4bf0e85a398d4e00a0e0d5e0d8fd`
- G2B-0 identified the missing UploadTicketLedger and UploadCutover wiring.
- No AWS/STS, remote-state access, plan/apply/destroy, installation or deployment.
- No Jobsearch/Orders changes and no `.tfvars` changes.
- The 39 pre-existing untracked files were preserved.

## Added DynamoDB resources

Two dedicated PAY_PER_REQUEST tables were added to the existing DynamoDB
module. Both retain the project/environment naming boundary and use the
repository contract's server-derived `resourceId` key without invented GSIs,
TTL or retention settings:

| Contract | Terraform resource | Name pattern | Key |
|---|---|---|---|
| UploadTicketLedgerV1 | `upload_ticket_ledger` | `${project_name}-${environment}-upload-ticket-ledger` | `resourceId` (S) |
| UploadCutoverStateV1 | `upload_cutover` | `${project_name}-${environment}-upload-cutover` | `resourceId` (S) |

Names and ARNs are exported by the DynamoDB module, passed through the root
module, and supplied to Lambda as:

```text
UPLOAD_TICKET_LEDGER_TABLE
UPLOAD_CUTOVER_TABLE
```

No historical ticket rows, markers or cutover state were seeded or migrated.
The new tables therefore do not treat any historical ticket as registered.

## IAM wiring

### UploadTicketLedgerV1

The dedicated Lambda policy grants only:

- `dynamodb:GetItem` on the upload-ticket ledger table ARN
- `dynamodb:TransactWriteItems` on the upload-ticket ledger table ARN

This covers:

- registration of the ticket and server-derived idempotency marker in one
  transaction;
- replay lookup with a consistent point read; and
- versioned `Update` transitions in transactions.

Each ledger transaction also contains USER/CV freeze `ConditionCheck`s on the
existing partner-profile guard table. That table remains authorized by the
existing partner-profile policy, so all table ARNs participating in the
transaction have independent allow statements. No scan, delete, direct
`PutItem`, index wildcard or `dynamodb:*` permission was added.

### UploadCutoverStateV1

The dedicated Lambda policy grants only:

- `dynamodb:PutItem` on the upload-cutover table ARN

This matches the repository's conditional create/version update contract. No
scan, read, delete or transaction permission was added because the current
repository does not perform those operations.

## Activation and isolation

All relevant flags remain explicitly disabled:

```text
PRIVACY_RECEIPT_JOURNAL_ENABLED=false
ERASURE_OPERATION_REPOSITORY_ENABLED=false
ERASURE_S3_PHASE_REPOSITORY_ENABLED=false
ERASURE_S3_EXECUTION_ENABLED=false
ERASURE_S3_QUIESCENCE_ENABLED=false
ERASURE_WRITE_FREEZE_ENABLED=false
ERASURE_UPLOAD_TICKET_LEDGER_ENABLED=false
ERASURE_UPLOAD_CUTOVER_ENABLED=false
```

The table-name environment variables are wiring only and do not activate
either repository. Tenant, partner-application and issuer isolation remains
enforced by the existing runtime item fields and freeze conditions. S3 object
keys and version operations are unchanged and remain scoped to the existing
documents-bucket tenant prefix.

## Cutover evidence boundary

The infrastructure is prepared, but cutover is **not proven**. This change
does not:

- inventory historical issuers or upload paths;
- register old tickets retroactively;
- assert that all historical ticket expiries have passed;
- assert zero active upload actions;
- assert an empty final version/delete-marker inventory; or
- set `ERASURE_UPLOAD_CUTOVER_ENABLED=true`.

Operational cutover requires an approved evidence record satisfying every
`UploadCutoverEvidenceV1` predicate, followed by a controlled non-production
verification. Until then the repository must remain disabled and any cutover
state remains `BLOCKED`.

## Remaining security gaps

These remain outside static table/IAM wiring:

1. S3 Object Lock and legal-hold evidence.
2. Documents-bucket deny policy against unauthorized version deletion and
   late uploads.
3. Distributed request-boundary fencing for stale S3 workers.
4. DynamoDB PITR/AWS Backup, retention approval and restore reconciliation.
5. AWS IAM simulation, deployed Lambda access and CloudTrail evidence.
6. Historical upload-ticket inventory and issuer/path cutover proof.

No security flag was enabled to hide any of these gaps.

## Verification

| Check | Result |
|---|---|
| Changed Terraform files `fmt -check` | **PASS** |
| Terraform `validate` | **PASS**, existing provider deprecation warnings only |
| Upload ledger/Cutover/S3/Privacy regression | **75 passed** |
| IAM/API/Privacy static tests | **109 passed, 252 subtests** |
| `git diff --check` | **PASS** |
| Lambda `py_compile` | **PASS** |
| AWS/STS/plan/apply/remote state | **NOT RUN** |
| Port 18000 | **not listening** |

The recursive repository `terraform fmt -check` continues to report only the
pre-existing Builder Terraform file and preserved `terraform/ris-dev2.tfvars`;
neither is part of this change.

## Decision

**G2B Static Readiness: GO** for the UploadTicketLedger/Cutover Terraform,
environment and least-privilege IAM wiring. This is a static wiring GO only;
all activation flags remain false.

**AWS E2E: BLOCKED.** No AWS, IAM, S3, backup or deployed runtime evidence was
collected.

**Production: BLOCKED.** Cutover evidence, Object Lock/bucket-deny,
PITR/restore and operational fencing remain unverified.

## Commit

```text
feat(ris): wire upload ticket ledger and cutover infrastructure
```
