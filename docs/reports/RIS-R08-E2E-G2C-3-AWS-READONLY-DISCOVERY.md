# R08-E2E-G2C-3 — RIS-DEV-PF AWS READ-ONLY DISCOVERY

**Status:** BLOCKED — AWS ACCOUNT/PROFILE MISMATCH

## Baseline and boundary

- Branch: `feature/ris-partner-profile-persistence-v1`.
- Starting HEAD: `d1139439b6f344e6e3c467633a584e16915e8f87`.
- Target identity: `project_name=ris-dev-pf`, `environment=dev`,
  `eu-central-1`.
- The user explicitly authorized read-only AWS discovery.
- No Terraform init/plan/apply/destroy, remote-state read, workspace
  operation, AWS mutation, Lambda invocation, deployment or activation was
  performed.
- No credentials, state contents or secret values were written to this report.

## Account and profile evidence

The documented target profile `mayaws` is not configured in the local AWS
configuration. The AWS CLI is not installed/in `PATH`, so the first CLI check
could not run.

The available local boto3 profile `default` was checked with the read-only STS
`GetCallerIdentity` operation:

| Field | Observed value |
|---|---|
| Profile | `default` |
| Region supplied | `eu-central-1` |
| Account | `262370457690` |
| Principal | `arn:aws:iam::262370457690:user/devnemo` |
| Credential material | not printed or copied |

The repository deployment context documents account `240571105849` and profile
`mayaws`. The observed account therefore does not match the intended RIS
deployment account. The principal is also not the documented deployment
principal. This is a hard safety blocker.

## Discovery actions and stopping point

The following were attempted only as local/client setup checks:

1. AWS CLI `aws sts get-caller-identity --profile mayaws` — unavailable because
   the AWS CLI executable is not installed or on `PATH`.
2. boto3 session with profile `mayaws` — stopped with `ProfileNotFound`.
3. Local profile-name inspection — only `default` is present in both local AWS
   config/credentials section names.
4. boto3 STS with `default` — succeeded and proved the wrong account above.

After the account mismatch was established, no S3, DynamoDB, Lambda, IAM,
API Gateway, Cognito, SQS, CloudTrail or state/lock query was sent. In
particular, the following remain **unverified**, not absent:

- backend bucket `mays-ris-tf-state-dev`;
- target state key `env:/ris-dev-pf/dev/terraform.tfstate`;
- DynamoDB lock status;
- `ris-dev-pf-*` resource existence or ownership;
- Cognito prefix `ris-dev-pf-dev` availability;
- Lambda activation flags;
- conflicts with `ris-dev-*` or `mays-ris-*` resources.

No existing `ris-dev` or `mays-ris` resource was read or modified.

## Target identity and expected names

The local target remains unchanged and is statically isolated as:

```text
project_name = ris-dev-pf
environment  = dev
region       = eu-central-1
workspace    = ris-dev-pf
state        = env:/ris-dev-pf/dev/terraform.tfstate
```

Expected resource families are `ris-dev-pf-dev-*`, project-scoped
`ris-dev-pf-*`, `ris-dev-pf-trail`, `ris-dev-pf-cloudtrail-<account>` and
`ris-dev-pf-mays-orders-*`. These are Terraform-derived expectations only;
they are not live existence evidence.

## Activation flags

The repository configuration still specifies all relevant flags as `false`:

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

No flag was changed or evaluated in a deployed runtime.

## Required remediation before retry

1. Configure or obtain the explicitly authorized `mayaws` profile for account
   `240571105849`, or provide a separately approved profile/account tuple.
2. Ensure the AWS CLI or equivalent boto3 credentials are available without
   placing credentials in the repository.
3. Re-run STS first and verify account, principal and `eu-central-1` before
   any resource query.
4. Only after that identity gate passes, run the G2C-3 read-only matrix for
   `ris-dev-pf` and the exact backend/state/lock names. Do not use the current
   `default` profile for RIS discovery.
5. Keep Terraform plan and deployment separately unauthorized until the full
   read-only evidence is reviewed.

## Decision

**Read-only Preflight: BLOCKED.** The only usable credentials resolve to the
wrong AWS account, and the documented `mayaws` profile is unavailable.

**Terraform Plan Readiness: BLOCKED.** No backend, state, lock or resource
evidence was collected.

**Deployment: NOT AUTHORIZED.** `ris-dev` and `mays-ris` remain untouched;
`ris-dev-pf` has not been created or adopted; all activation flags remain
`false`.

## Commit intent

```text
docs(ris): record ris-dev-pf aws readonly discovery blocker
```
