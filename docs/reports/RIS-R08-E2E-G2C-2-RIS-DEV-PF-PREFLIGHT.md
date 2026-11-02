# R08-E2E-G2C-2 — RIS-DEV-PF ISOLATED TEST PREFLIGHT

**Status:** STATIC ISOLATION READY / AWS READ-ONLY BLOCKED

## Baseline and boundary

- Branch: `feature/ris-partner-profile-persistence-v1`.
- Starting HEAD: `487ea978c5abd085b872e9b357190e00f8211ea6`.
- G2C-0 and G2C-1 were reviewed.
- No AWS/STS call, remote-state read, Terraform plan/apply/destroy,
  installation, deployment or deletion was performed.
- No global default, `.tfvars`, Jobsearch, Orders or existing installation was
  changed. The 39 pre-existing untracked files were preserved.

## Actual test deployment identity

The isolated test identity is explicitly:

```text
project_name = ris-dev-pf
environment  = dev
aws_region   = eu-central-1
workspace    = ris-dev-pf
```

This value is passed as an explicit installer/Terraform input. It is not a
global default and does not alter the permanent `ris-dev` installation or the
legacy `mays-ris` identity.

The local identity derivation was verified without AWS:

```text
workspace                 ris-dev-pf
backend key input         dev/terraform.tfstate
workspace key prefix      env:
effective state path      env:/ris-dev-pf/dev/terraform.tfstate
Orders component identity ris-dev-pf-mays-orders
RIS name-limit validation PASS
```

## Namespace and state isolation

The executable installer contract derives the workspace verbatim from
`project_name`, keeps `environment` separate, and supplies
`workspace_key_prefix=env:`. The intended isolated backend tuple is therefore:

| Dimension | `ris-dev-pf` test value | Exclusion |
|---|---|---|
| Project | `ris-dev-pf` | not `ris-dev`, not `mays-ris` |
| Environment | `dev` | no environment-to-workspace substitution |
| Workspace | `ris-dev-pf` | distinct from `ris-dev`/`mays-ris` |
| State object | `env:/ris-dev-pf/dev/terraform.tfstate` | distinct state path |
| Backend region | `eu-central-1` | must be explicitly confirmed |
| Backend lock table | configured value only | no lock/state adoption inferred |
| Orders component | `ris-dev-pf-mays-orders` | distinct component namespace |

The backend bucket and lock table must still be supplied explicitly for a
future read-only gate. A distinct state key is necessary but not sufficient:
the operator must confirm bucket ownership, object existence and lock records
before any initialization using remote state.

## Static resource namespace

The Terraform modules use `project_name` and/or
`${project_name}-${environment}` for names and `Project` tags. For this test,
the expected families are:

| Resource family | Expected `ris-dev-pf` pattern |
|---|---|
| Cognito pool/client/domain | `ris-dev-pf-dev-users`, `ris-dev-pf-dev-client`, prefix domain `ris-dev-pf-dev` |
| API/authorizers | `ris-dev-pf-dev-api`, `ris-dev-pf-dev-jwt-*` |
| Lambda/roles/policies | `ris-dev-pf-dev-agent`, `ris-dev-pf-dev-*` |
| DynamoDB | `ris-dev-pf-dev-*` including ledger, cutover and erasure tables |
| SQS/DLQ | `ris-dev-pf-dev-*` queues |
| Documents/data S3 | `ris-dev-pf-dev-documents`, `ris-dev-pf-dev-data` |
| Health S3/Lambda | `ris-dev-pf-dev-health-*` |
| Monitoring | `ris-dev-pf-*` dashboards/alarms |
| CloudTrail | `ris-dev-pf-trail`, `ris-dev-pf-cloudtrail-<account>` |
| Orders component | `ris-dev-pf-mays-orders-*` |

The G2B resources remain parametrized and isolated: upload-ticket ledger,
upload-cutover, erasure-operations and S3-erasure-phases all receive the
`ris-dev-pf-dev-` prefix. IAM policies are named from the same project and
environment and receive table/bucket ARNs from the same module instance.

## Shared-resource and collision review

### S3

The documents, data, health and CloudTrail bucket names are project-derived,
so the intended test names do not equal the documented `ris-dev-*` or legacy
`mays-ris-*` families. S3 names are globally constrained; read-only checks
must confirm no unrelated owner or bucket already uses a candidate name. The
test must not adopt a bucket based on name alone, and no Object Lock or version
state may be changed by preflight.

### Cognito domains

The default Cognito domain is also project/environment-derived and should be
`ris-dev-pf-dev`, distinct from `ris-dev-dev` and `mays-ris-dev`. The module's
`custom_domain_enabled` default is `false`, so this isolated test must use the
prefix domain unless a separately approved unique custom domain and
`us-east-1` ACM certificate are supplied. The existing `ris-dev` overlay is
not loaded for `ris-dev-pf`; project overlays are exact-name and fail closed.

Reusing the permanent custom domain `auth.mays-job-matcher.app` would break
isolation and is a blocker. No custom domain was configured or changed here.

### Shared AWS services

IAM is account-global, CloudTrail is account/audit-sensitive, and API Gateway,
Cognito, S3 and CloudWatch names/quotas can be shared or globally constrained.
The static configuration derives names, but cannot prove live absence or
ownership. The `ris-dev` and `mays-ris` families are explicitly excluded from
adoption, mutation and deletion.

## Activation flags

The current Lambda configuration keeps all relevant privacy/erasure paths
disabled:

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

No flag was changed and no receipt, freeze, ledger, cutover or S3 operation was
executed.

## Local verification

| Check | Result |
|---|---|
| Explicit `ris-dev-pf` identity derivation | **PASS** |
| Focused isolation/wiring/name-limit tests | **140 passed, 6 skipped** |
| Terraform `fmt -check` on relevant modules | **PASS** |
| Terraform `validate` | **PASS**, existing provider deprecation warnings only |
| Broader installer subset | **154 passed, 2 failed** |
| `git diff --check` | pending final report commit check |
| AWS/STS/remote state/plan/apply/destroy | **NOT RUN** |

The two broader installer failures are pre-existing environmental/test
assumptions: one composite dry-run reaches Orders pin enforcement with no
resolved checkout, and one test's mocked subprocess output is not valid STS
JSON. They do not represent an AWS call and do not test the `ris-dev-pf`
identity. The focused isolation suite passes.

## Authorized AWS read-only preflight for `ris-dev-pf`

Only after explicit authorization, use the resolved account/profile and
`eu-central-1` to inspect, without mutation:

1. `sts get-caller-identity` and caller region/profile.
2. The explicitly supplied backend bucket: ownership/tags, region,
   encryption/versioning, and exact object
   `env:/ris-dev-pf/dev/terraform.tfstate`.
3. The lock table: table status and only the lock records for the
   `ris-dev-pf` path; do not delete stale locks.
4. Read-only existence/tag checks for every `ris-dev-pf-*` and
   `ris-dev-pf-dev-*` candidate across S3, Cognito, DynamoDB, SQS, Lambda,
   IAM, API Gateway, CloudWatch and CloudTrail.
5. Explicit negative checks that no `ris-dev-*` or `mays-ris-*` resource is
   selected for adoption, and that the custom domain is not the permanent
   `ris-dev` domain.
6. If a candidate exists, verify owner tags, Terraform association and schema
   before planning; foreign or ambiguous resources are blockers.

The evidence must be saved outside the repository or redacted before sharing;
state contents, ARNs and configuration may contain sensitive information.

## Decision

**RIS-DEV-PF AWS READ-ONLY: BLOCKED.** Static namespace/state isolation is
ready, but account, backend, lock, resource absence/ownership and Cognito
domain evidence are not available. No Terraform plan or deployment is
authorized. `ris-dev` remains unchanged and all activation flags remain
`false`.

## Commit intent

```text
docs(ris): prepare isolated ris-dev-pf preflight
```
