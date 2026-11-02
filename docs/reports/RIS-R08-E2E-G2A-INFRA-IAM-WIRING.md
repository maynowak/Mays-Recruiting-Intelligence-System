# R08-E2E-G2A — INFRASTRUCTURE & IAM WIRING

**Status:** STATIC WIRING COMPLETE / AWS EVIDENCE BLOCKED

## Scope and baseline

- Starting HEAD: `b27cb607821ced0a7d3873ae0c90c07ec5ee6595`
- RIS only; no Jobsearch or Orders changes
- No AWS/STS calls, remote-state access, plan/apply/destroy, deployment or installation
- No `.tfvars` file was modified
- The 39 pre-existing untracked files were preserved
- G0 and G1D-3B remain the evidence baseline; production remains blocked

## Changed resources and wiring

### DynamoDB

Added two project/environment-isolated PAY_PER_REQUEST tables in
`terraform/modules/dynamodb/main.tf`:

- `${project_name}-${environment}-erasure-operations`, hash key `resourceId`
- `${project_name}-${environment}-s3-erasure-phases`, hash key `resourceId`

Both tables deliberately have no GSI or scan-oriented schema. Their outputs
are exported as names and ARNs, passed through `terraform/main.tf`, and exposed
to the Lambda module as environment bindings. This matches the existing
repositories' point-read, conditional-write and transaction contracts without
inventing retention, TTL or backup behavior.

### Lambda DynamoDB IAM

Updated the existing platform policy for the UserProfile table:

- `dynamodb:DeleteItem`
- `dynamodb:TransactWriteItems`

Both actions are scoped to `var.user_profile_table_arn` only. The existing
partner-profile guard policy remains separately scoped to the partner-profile
table; no cross-table wildcard was introduced.

Added operation-table permissions scoped to its table ARN:

- `dynamodb:GetItem`
- `dynamodb:PutItem`
- `dynamodb:TransactWriteItems`

Added S3-phase-table permissions scoped to its table ARN:

- `dynamodb:GetItem`
- `dynamodb:TransactWriteItems`

No `Scan`, `DeleteItem`, `dynamodb:*`, or index wildcard was added for either
new erasure table.

### Lambda S3 IAM

Extended the existing private documents policy only:

- `s3:ListBucketVersions` on the documents bucket ARN
- `s3:DeleteObjectVersion` on `${documents_bucket_arn}/tenant/*`

The existing object actions remain restricted to the tenant key prefix. The
version-list action is bucket-scoped because AWS models it as a bucket-level
operation; no data bucket or foreign bucket permission was added.

## Activation safety

The Lambda environment now carries the table names but keeps all relevant
runtime gates explicitly disabled:

```text
PRIVACY_RECEIPT_JOURNAL_ENABLED=false
ERASURE_OPERATION_REPOSITORY_ENABLED=false
ERASURE_S3_PHASE_REPOSITORY_ENABLED=false
ERASURE_S3_EXECUTION_ENABLED=false
ERASURE_S3_QUIESCENCE_ENABLED=false
ERASURE_WRITE_FREEZE_ENABLED=false
```

`ERASURE_OPERATION_TABLE` and `ERASURE_S3_PHASE_TABLE` are wiring only. No
erasure, receipt, freeze, quiescence, or S3-delete operation is activated by
this change. Existing application fail-closed behavior remains authoritative.

## Static verification

| Check | Result |
|---|---|
| Terraform fmt on all changed `.tf` files | **PASS** |
| Terraform validate | **PASS**, existing provider deprecation warnings only |
| Recursive `terraform fmt -check` | **BLOCKED by pre-existing** `installer/projects/mays_order_builder/terraform/main.tf` and preserved `terraform/ris-dev2.tfvars`; neither changed |
| Privacy/Erasure/IAM target tests | **98 passed** |
| Policy/API/Privacy static tests | **109 passed, 252 subtests** |
| `git diff --check` | **PASS** |
| Python compile check for Lambda handler | **PASS** |
| AWS/STS/plan/apply/remote state | **NOT RUN by boundary** |

## Tenant, naming and isolation review

- New names retain the existing `${project_name}-${environment}-...` pattern.
- Lambda receives names and ARNs from the same DynamoDB module instance; no
  hardcoded account, region or deployment identifier was added.
- Runtime tenant/partner/issuer fencing remains in the existing repositories
  and conditional transactions; no application bypass was introduced.
- S3 permissions remain on the private documents bucket and `tenant/*` object
  scope, not the root data bucket or Orders resources.
- No security flag is enabled by Terraform.

## Remaining AWS and operational evidence

The following are intentionally not asserted by local validation and remain
G2B/integration prerequisites:

1. AWS IAM policy simulation or deployed Lambda access for every transaction
   path, including all table ARNs present in cross-table `TransactWriteItems`.
2. Non-production verification that the documents bucket has versioning and
   that `ListBucketVersions`/`DeleteObjectVersion` are constrained to the
   intended tenant prefix.
3. S3 Object Lock, legal holds, bucket-deny policy and stale-worker fencing at
   the S3 request boundary.
4. DynamoDB PITR/AWS Backup configuration, restore reconciliation and approved
   erasure-operation/phase retention. No TTL or backup setting was invented.
5. Read-only AWS/STS identity and `mayaws` credential evidence, which was not
   requested or performed in this no-AWS gate.
6. DynamoDB Local or approved non-production integration evidence for CAS,
   transaction cancellation reasons, table existence and restart/resume.

## Decision

**G2B Readiness: BLOCKED.** The Terraform/IAM wiring is statically prepared,
but no AWS/IAM, Object Lock, bucket-deny, PITR/backup or deployed runtime
evidence exists under the current boundary. G2B may proceed only in an
explicitly approved non-production infrastructure/IAM gate.

**Production: BLOCKED.** This commit does not activate erasure or establish
production readiness.

## Commit

```text
feat(ris): prepare erasure infrastructure iam wiring
```
