# R08-E2E-G2C-0 — AWS DEPLOYMENT PREFLIGHT PLAN

**Status:** READ-ONLY PREFLIGHT PLAN / AWS E2E BLOCKED

## Baseline and boundary

- Repository: RIS, `feature/ris-partner-profile-persistence-v1`.
- Baseline HEAD: `af632b93f681603bda1ba910d2037533ea05c114`.
- This report is based on executable Terraform and installer sources plus the
  G2B-0/G2B-1 reports. It is not live AWS evidence.
- No AWS/STS calls, remote-state access, Terraform plan/apply/destroy,
  installation, deployment or productive deletion were performed.
- No Jobsearch/Orders or `.tfvars` files were changed. The 39 pre-existing
  untracked files remain preserved.

## Repository deployment identity

### Terraform root

`terraform/main.tf` is the root. It uses AWS provider `~> 6.0` and the
provider region is `var.aws_region`, whose repository default is
`eu-central-1`. The root modules include Cognito, DynamoDB, Lambda, API,
documents, SQS, monitoring, CloudTrail and the generated Orders component.

The default input identity is `project_name=mays-ris`, `environment=dev`, but
the repository deployment notes and `AGENTS.md` identify the permanent current
dev installation as `project_name=ris-dev`, `environment=dev`. This is a
material collision/rebuild risk, not a value to guess. The authorized
read-only gate must resolve the intended identity before any plan.

### Backend and workspace matrix

The root has a partial S3 backend:

```hcl
key            = "terraform.tfstate"
encrypt        = true
dynamodb_table = "mays-ris-tf-lock"
```

The installer must provide `bucket` and `region` explicitly. Its backend
contract supplies `workspace_key_prefix=env:` and derives the workspace
verbatim from `project_name`; `environment` is carried in the key. Therefore
the effective paths are:

| Intended identity | Workspace | State object | Expected state bucket |
|---|---|---|---|
| permanent dev (documented) | `ris-dev` | `env:/ris-dev/dev/terraform.tfstate` | `mays-ris-tf-state-dev` |
| legacy/default source value | `mays-ris` | `env:/mays-ris/dev/terraform.tfstate` | must not be assumed |

The lock table is statically named `mays-ris-tf-lock`. The bucket, lock table,
state object and workspace must be checked as one tuple; mixing a project,
environment or state path can cause cross-stack adoption or an unsafe new
state. A state migration or takeover is out of scope for this gate.

## Resource inventory to verify

### Existing/shared or previously defined families

The root configuration can address the existing RIS families: work items,
agent state/catalog, user profile, entitlements, jobsearches, partner
profiles, privacy receipts, API profiles, offers, credentials, partner
applications, SQS/DLQ, Lambda, API Gateway, Cognito, documents, monitoring and
CloudTrail. Historical deployment material records some `mays-ris-*` names,
while current repository deployment identity records `ris-dev-*`. That
material is a lead only and must not be treated as current AWS evidence.

### G2A/G2B additions or newly relevant resources

The current Terraform additionally defines or wires:

| Resource | Terraform address | Expected name pattern |
|---|---|---|
| Erasure operations | `module.dynamodb.aws_dynamodb_table.erasure_operations` | `${project}-${env}-erasure-operations` |
| S3 erasure phases | `module.dynamodb.aws_dynamodb_table.s3_erasure_phases` | `${project}-${env}-s3-erasure-phases` |
| Upload ticket ledger | `module.dynamodb.aws_dynamodb_table.upload_ticket_ledger` | `${project}-${env}-upload-ticket-ledger` |
| Upload cutover state | `module.dynamodb.aws_dynamodb_table.upload_cutover` | `${project}-${env}-upload-cutover` |
| Ledger IAM | `module.lambda.aws_iam_role_policy.lambda_upload_ticket_ledger` | project/env policy name |
| Cutover IAM | `module.lambda.aws_iam_role_policy.lambda_upload_cutover` | project/env policy name |

The two G2B tables are PAY_PER_REQUEST with a single `resourceId` string hash
key, no invented GSI or TTL. Their Lambda environment variables are
`UPLOAD_TICKET_LEDGER_TABLE` and `UPLOAD_CUTOVER_TABLE`. These variables do
not activate the repositories.

## Read-only AWS verification matrix

The following commands are the proposed evidence collection only. They must be
run by an explicitly authorized operator with the resolved profile/account,
region and identity. `<profile>`, `<region>`, `<project>` and `<env>` are
placeholders; no command below was executed for this report.

### 1. Account, region and identity

```bash
aws sts get-caller-identity --profile <profile>
aws configure get region --profile <profile>
```

**Evidence:** account ID, principal ARN, selected region, timestamp and
profile. **Blocker:** wrong account/profile/region, expired credentials,
unexpected principal or inability to prove authorization.

### 2. State backend and isolation

```bash
aws s3api head-bucket --bucket <state-bucket> --profile <profile>
aws s3api get-bucket-location --bucket <state-bucket> --profile <profile>
aws s3api get-bucket-versioning --bucket <state-bucket> --profile <profile>
aws s3api get-bucket-encryption --bucket <state-bucket> --profile <profile>
aws s3api get-object --bucket <state-bucket> --key env:/<project>/<env>/terraform.tfstate <local-readonly-copy> --profile <profile>
aws dynamodb describe-table --table-name mays-ris-tf-lock --profile <profile> --region <region>
```

**Evidence:** bucket ownership/tags, region, versioning/encryption, exact
state object existence and lock-table status. **Blocker:** missing or foreign
bucket/tag, unexpected state object, wrong key/workspace, unencrypted state,
active lock, or any need for state migration/adoption. State contents must be
handled as sensitive and not committed.

### 3. DynamoDB tables, keys, PITR and backups

```bash
aws dynamodb describe-table --table-name <table> --profile <profile> --region <region>
aws dynamodb describe-continuous-backups --table-name <table> --profile <profile> --region <region>
aws dynamodb list-backups --table-name <table> --profile <profile> --region <region>
aws dynamodb list-tags-of-resource --resource-arn <table-arn> --profile <profile> --region <region>
```

Run for every managed table, especially `user-profile`, `partner-profiles`,
`privacy-receipts`, `erasure-operations`, `s3-erasure-phases`,
`upload-ticket-ledger` and `upload-cutover`.

**Evidence:** table status, billing mode, key schema, GSIs, SSE, tags, PITR
and backup evidence. **Blocker:** same-name table with incompatible schema,
unmanaged data, disabled required PITR/backup policy, foreign ownership,
unexpected indexes, or a planned replacement containing data. For G2B tables,
also confirm no historical ticket/cutover rows are being silently treated as
registered evidence; do not mutate or seed them in preflight.

### 4. Lambda roles and effective IAM

```bash
aws lambda get-function-configuration --function-name <function> --profile <profile> --region <region>
aws lambda get-function --function-name <function> --profile <profile> --region <region>
aws iam get-role --role-name <role> --profile <profile>
aws iam list-role-policies --role-name <role> --profile <profile>
aws iam get-role-policy --role-name <role> --policy-name <policy> --profile <profile>
aws iam list-attached-role-policies --role-name <role> --profile <profile>
```

**Evidence:** function version/runtime, role trust policy, inline/attached
policies, exact table/bucket/queue ARNs, environment flags and log group.
The expected G2B grants are ledger `GetItem` and
`TransactWriteItems` only, and cutover `PutItem` only; freeze transaction
participants must have separately scoped permissions. **Blocker:** wildcard
or destructive permissions, wrong role/function, missing transaction
permission, wrong ARN, public secret/configuration, or any activation flag
not `false`.

### 5. Documents S3, versions, Object Lock and denies

```bash
aws s3api head-bucket --bucket <documents-bucket> --profile <profile>
aws s3api get-bucket-versioning --bucket <documents-bucket> --profile <profile>
aws s3api get-object-lock-configuration --bucket <documents-bucket> --profile <profile>
aws s3api get-bucket-encryption --bucket <documents-bucket> --profile <profile>
aws s3api get-public-access-block --bucket <documents-bucket> --profile <profile>
aws s3api get-bucket-policy --bucket <documents-bucket> --profile <profile>
aws s3api get-bucket-tagging --bucket <documents-bucket> --profile <profile>
```

For identified evidence objects only, use `head-object` and
`get-object-retention`; use `list-object-versions` only as an explicitly
approved metadata inventory, never delete or alter objects.

**Evidence:** versioning, AES256 encryption, public-access block, policy
denies, Object Lock mode/retention, legal holds and tenant-key convention.
**Blocker:** Object Lock/retention not approved, missing deny against unsafe
version deletion or late upload, public access, cross-tenant key evidence,
unexpected bucket owner, or inability to prove legal-hold handling. Terraform
currently configures versioning/encryption/PAB for documents but does not
configure Object Lock or a bucket policy; that is an explicit open gap.

### 6. CloudTrail and runtime audit

```bash
aws cloudtrail describe-trails --include-shadow-trails --profile <profile> --region <region>
aws cloudtrail get-trail-status --name <trail-arn> --profile <profile> --region <region>
aws cloudtrail get-event-selectors --trail-name <trail-arn> --profile <profile> --region <region>
aws s3api get-bucket-policy --bucket <trail-bucket> --profile <profile>
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/<project> --profile <profile> --region <region>
```

**Evidence:** multi-region trail, management read/write events, global
events, validation, logging status, trail bucket policy and Lambda log-group
retention. **Blocker:** trail disabled, wrong account/region, missing bucket
policy, no evidence for IAM/S3/DynamoDB changes, or logs without an approved
retention policy. The Terraform trail is `${project}-trail` with a separate
`${project}-cloudtrail-${account}` bucket.

### 7. Upload, cutover and erasure runtime checks

```bash
aws lambda get-function-configuration --function-name <function> --profile <profile> --region <region>
aws dynamodb describe-table --table-name <ledger> --profile <profile> --region <region>
aws dynamodb describe-table --table-name <cutover> --profile <profile> --region <region>
aws dynamodb describe-table --table-name <erasure-operations> --profile <profile> --region <region>
aws dynamodb describe-table --table-name <s3-erasure-phases> --profile <profile> --region <region>
```

**Evidence:** exact environment names, all lifecycle flags false, table
schemas/status, deployed code version and CloudTrail correlation for any
authorized non-mutating inspection. **Blocker:** missing table/variable,
schema drift, enabled repository/execution/freeze/cutover flag, absent
transaction participant authorization, or any claim that cutover is proven
without an approved `UploadCutoverEvidenceV1` record. No scan, write,
registration, cutover or erasure operation belongs in this gate.

## State, naming and cost risks

1. `ris-dev` is the documented permanent stack, but Terraform variable and
   historical deployment defaults still contain `mays-ris`. Do not run a plan
   until the operator explicitly confirms the project, workspace, state key,
   bucket and account tuple.
2. A new workspace/state path can make every existing resource appear absent;
   an existing state path can make a rename appear as destructive replacement.
   A name collision with an unmanaged resource must stop, not be adopted.
3. S3 state and CloudTrail buckets are globally/name constrained; DynamoDB,
   Lambda, Cognito, API Gateway and IAM names can collide across installations.
4. PAY_PER_REQUEST tables charge per request; PITR and on-demand backups add
   storage/backup cost. S3 versioning and audit logs retain multiple objects;
   CloudTrail data volume, CloudWatch logs, Lambda, API Gateway, Cognito and
   NAT/transfer usage can add variable cost. The G2B tables have no TTL, so
   retention cost cannot be assumed to disappear automatically.
5. A later plan must be reviewed for unexpected creates, replacements,
   policy changes, function redeployments, state/backend changes and destroys;
   `0 destroy` is a release criterion for this controlled dev preflight unless
   a separately approved replacement is documented.

## Required sequence and gates

1. **Read-only authorization:** approve the exact account/profile/region and
   execute the matrix above; collect immutable command output and timestamps.
2. **Resolve identity:** reconcile `ris-dev` versus `mays-ris`, verify bucket,
   lock table, workspace and state object, and stop on foreign resources or
   state ambiguity.
3. **Local package/validation:** build the required Lambda bundle, then run
   local `terraform init -backend=false`, `terraform validate` and
   `terraform fmt -check`; do not use remote state in this gate.
4. **Separately authorized plan:** only after gates 1–3 pass, initialize with
   the confirmed explicit backend and run a saved, reviewed plan with all
   activation flags still false. No apply is implied by plan approval.
5. **Deployment authorization:** require a separate written approval covering
   exact plan SHA, account, workspace, state lock, cost/backup posture and
   rollback. Apply only that reviewed plan, then collect runtime evidence.

## Decision

**AWS read-only preflight: BLOCKED pending explicit authorization and live
evidence.** No AWS/STS or remote-state operation was performed here.

**Controlled Terraform plan: NOT AUTHORIZED / NOT RUN.**

**Deployment/production: BLOCKED.** All erasure, upload-ledger, cutover and
S3 execution flags remain `false`; cutover evidence is unconfirmed.

## Commit intent

```text
docs(ris): prepare controlled aws deployment preflight
```
