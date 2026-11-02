# R08-E2E-G2B-0 — STATIC INFRASTRUCTURE SECURITY PREFLIGHT

**Status:** STATIC PREFLIGHT BLOCKED / AWS E2E BLOCKED

## Baseline and boundary

- Starting HEAD: `7094b0194d68ffc36a53de8d5f924e1afd9b4942`
- Compared with G0 integration readiness and G2A IAM wiring.
- No AWS/STS, remote-state access, Terraform plan/apply/destroy or deployment.
- No Jobsearch/Orders changes and no `.tfvars` changes.
- The 39 pre-existing untracked files were preserved.

## Fully wired components

### UserProfile and partner-profile guard

- UserProfile table and ARN are sourced from the DynamoDB module and passed to
  the Lambda module.
- UserProfile has read/write access plus `DeleteItem` and
  `TransactWriteItems` on the base table ARN. Index access is limited to the
  existing read/query statement.
- The partner-profile table has the existing `GetItem`, `PutItem`,
  `UpdateItem`, `DeleteItem`, `Query` and `TransactWriteItems` permissions.
- The guarded UserProfile transaction references both the UserProfile table
  and the partner-profile guard table. Both table ARNs are independently
  authorized; no wildcard resource was added.
- Existing application-level tenant/partner/issuer conditions and freeze
  checks remain unchanged.

### ErasureOperation persistence

- Dedicated `${project_name}-${environment}-erasure-operations` table,
  hash key `resourceId`, with name/ARN outputs and Lambda environment wiring.
- IAM is limited to `GetItem`, `PutItem` and `TransactWriteItems` on that
  table. This covers idempotent creation (two writes in one transaction),
  point reads and versioned conditional `PutItem` updates.
- No scan, delete, TTL, GSI or runtime activation was added.

### Write-Freeze and S3 phase persistence

- Write-Freeze uses the existing partner-profile table and its already-present
  point read/update/transaction permissions.
- Dedicated `${project_name}-${environment}-s3-erasure-phases` table,
  hash key `resourceId`, with name/ARN outputs and Lambda environment wiring.
- S3-phase IAM is limited to `GetItem` and `TransactWriteItems` on the phase
  table. Its transaction also condition-checks the guard and operation tables;
  those two table ARNs are separately authorized by the existing guard and
  operation policies.
- The phase and operation repositories remain disabled by explicit Lambda
  environment flags.

### Documents bucket and version operations

- Documents bucket naming remains `${project_name}-${environment}-documents`.
- Versioning, SSE-S3 and public-access blocking remain present.
- Existing object permissions remain scoped to `${documents_bucket_arn}/tenant/*`.
- `s3:DeleteObjectVersion` is scoped to that same tenant object prefix.
- `s3:ListBucketVersions` is scoped to the documents bucket ARN, which is the
  resource type supported by this bucket-level operation.
- No permission was added to the root data bucket or Orders resources.

### Receipt and activation flags

All relevant Lambda activation flags are explicit `false`:

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

Table-name bindings alone do not activate a repository.

## Missing wiring and rights

### UploadTicketLedger — not provisioned or wired

`UploadTicketLedgerRepository` requires an `UPLOAD_TICKET_LEDGER_TABLE`,
`GetItem`, `TransactWriteItems`, and a table that participates in transactions
with the partner-profile guard table. No Terraform table, output, Lambda name
binding or dedicated IAM policy exists. This is intentionally fail-closed by
the explicit `ERASURE_UPLOAD_TICKET_LEDGER_ENABLED=false` flag.

Before activation, the project needs an approved table key/retention contract,
cross-table transaction IAM review, historical-ticket inventory and cutover
evidence. No table was invented in this preflight.

### UploadCutover — not provisioned or wired

`UploadCutoverRepository` requires an `UPLOAD_CUTOVER_TABLE` and conditional
`PutItem` persistence. No Terraform table, output, Lambda name binding or IAM
policy exists. The explicit `ERASURE_UPLOAD_CUTOVER_ENABLED=false` flag keeps
this path disabled.

Before activation, the project needs an approved retention/evidence contract,
table schema, operator access model and proof that all legacy upload issuers
and paths are covered.

### No missing rights found for currently wired paths

The static source-to-policy review found no additional required DynamoDB
action for UserProfile, partner-profile guard, ErasureOperation or S3-phase
transactions. `TransactWriteItems` is authorized on every table ARN included
in the corresponding transaction for the currently wired repositories.

## Security and operational risks still open

These are not safely solvable by this static preflight:

1. **Object Lock/legal hold:** the documents bucket has versioning, but no
   Object Lock configuration or legal-hold evidence.
2. **Bucket denies:** no documents-bucket deny policy proves protection against
   unapproved version deletion or late uploads.
3. **Distributed S3 fencing:** local adapter contracts require a fencing
   callback, but deployed S3 request-boundary fencing is unverified.
4. **Backup/PITR:** no DynamoDB PITR/AWS Backup configuration or restore-
   reconciliation evidence exists in this Terraform tree.
5. **Retention:** operation, phase, receipt and upload-ledger retention is not
   approved; no TTL was added.
6. **AWS IAM evidence:** no policy simulation, deployed Lambda invocation or
   CloudTrail evidence was permitted in this gate.
7. **Existing unrelated scopes:** the pre-existing data-bucket Lambda policy
   and broad log-group scope were not expanded here and require a separate
   least-privilege review; they are not part of the erasure wiring.

## Prioritized AWS verification list

1. Verify the rendered IAM policy in a non-production account and simulate
   every cross-table transaction, including guard, operation and phase ARNs.
2. Verify table names, keys, ARNs, Lambda environment values and project/
   environment isolation from Terraform outputs without using remote state in
   this gate.
3. Verify documents-bucket version inventory, tenant-prefix listing,
   version-specific deletion, Object Lock/legal holds and bucket-deny behavior.
4. Verify DynamoDB PITR/backup, restore reconciliation and approved retention
   before enabling any persistence path.
5. Provision and test UploadTicketLedger/Cutover only after their schemas,
   historical issuer inventory, IAM scope and activation approval exist.
6. Run non-production CAS/restart/resume and stale-worker tests with all
   activation flags explicitly controlled; then collect CloudTrail evidence.

## Verification

| Check | Result |
|---|---|
| Changed Terraform files `fmt -check` | **PASS** |
| Terraform `validate` | **PASS**, existing provider deprecation warnings only |
| Privacy/Erasure/Upload/S3 target tests | **80 passed** |
| IAM/API/Privacy static tests | **109 passed, 252 subtests** |
| `git diff --check` | **PASS** |
| Lambda `py_compile` | **PASS** |
| AWS/STS/plan/apply/remote state | **NOT RUN** |
| Port 18000 | **not listening** |

The recursive `terraform fmt -check` remains blocked only by the pre-existing
Builder Terraform file and preserved `terraform/ris-dev2.tfvars`; neither is
part of this change.

## Decision

**G2B Static Readiness: BLOCKED.** The currently enabled-by-wiring contracts
are statically consistent, but UploadTicketLedger/Cutover persistence and the
required Object Lock, bucket-deny, PITR/backup and deployed IAM evidence are
missing. No activation is safe yet.

**AWS E2E: BLOCKED.** No AWS evidence was collected under the boundary.

**Production: BLOCKED.**

## Commit

```text
test(ris): complete static infrastructure security preflight
```
