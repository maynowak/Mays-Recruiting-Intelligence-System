# RIS Installer Parameters

## Overview
The RIS installer orchestrates Mays-Orders and Mays-RIS installations with explicit context propagation.

## Core Parameters
- `--project-name` : Project identity, also Terraform workspace
- `--environment` : dev/test/prod
- `--profile` : AWS profile for execution
- `--region` : AWS region

## RIS Backend Configuration
- `--backend-bucket` : S3 bucket for Terraform state
- `--backend-region` : Region for backend
- `--backend-lock-table` : DynamoDB lock table

## Orders Orchestration
Orders is invoked via Mays-Order-AWS-installer with propagated context.

Parameters passed to Orders:
- `--profile`, `--region`, `--project-name`, `--environment`

Environment variables passed to the Orders child process (not CLI flags —
the Orders CLI reads them from the environment):
- `PROJECT_NAME` : component project identity, e.g. `mays-ris-<name>-mays-orders`
- `TERRAFORM_WORKSPACE` : pinned to the component project name. **Required** —
  without it `InstallationContext.from_env()` falls back to the `default`
  workspace and locks the wrong state.
- `ALLOW_AWS_OPERATIONS` : `false` in dry-run, `true` only with `--yes`

Terraform variables passed as `--var` on the Orders `plan`:
- `project_name`, `aws_region`
- `enable_cognito_backup=false` — see below

## Orders project name limits

The Orders component derives nearly every AWS resource name from its project
name. AWS rejects names over service limits, but Terraform only reports the
overflow during plan, after the backend is initialised.

The installer therefore **fails closed before any AWS call**:

| Level | Flags | Max length | Binding resource |
|---|---|---|---|
| RIS project | — | **39** | CloudTrail S3 bucket |
| Orders component | `enable_cognito_backup=false` (composite default) | **39** | CloudTrail S3 bucket |
| Orders component | `enable_cognito_backup=true` (Orders default) | **23** | Cognito backup S3 bucket |

Checked in `RisInstallContext.__post_init__()` for the RIS name and in
`orders_component_project_name()` for the Orders name.

Because the Orders component name carries the `-mays-orders` suffix (12 chars),
the RIS name part has **27 chars** of headroom.

Composite installations disable the Cognito backup module because its bucket
name is `mays-orders-cognito-backup-Development-<project_name>` and the
`Development` segment is hardcoded in the pinned Orders Terraform — no
composite name fits. The flag is set by the installer itself
(`ORDERS_ENABLE_COGNITO_BACKUP`) and passed on every plan, so it survives runs
without explicit flags.

On violation the installer exits non-zero and lists **every** overflowing
resource, not just the first:

```
error: orders component project name 'too-long-name-mays-orders' (40 chars)
exceeds the AWS name limit of 23 chars for enable_cognito_backup=true:
  - cognito_backup_s3_bucket: ... is 80 chars, AWS limit 63 (max project_name 23, got 40)
  - cognito_backup_scheduler_role: ... is 74 chars, AWS limit 64 (max project_name 30, got 40)
```

Full derivation and source references: **[AWS-NAME-LIMITS.md](AWS-NAME-LIMITS.md)**

## Examples

### Local test
```bash
python3 -m installer.ris --project-name mays-ris-test-e2e-01 --environment test \
  --profile mayaws --backend-bucket mays-ris-tf-state-dev --backend-region eu-central-1 \
  --backend-lock-table mays-ris-tf-lock validate
```

### Composite project (name must stay <= 39 chars)
```bash
python3 -m installer.ris --project-name mays-ris-composite-a --environment test \
  --profile mayaws --region eu-central-1 \
  --backend-bucket mays-ris-tf-state-dev --backend-region eu-central-1 \
  --backend-lock-table mays-ris-tf-lock plan
```

Orders component name is derived as `mays-ris-composite-a-mays-orders` (32 chars).

## Safety
- Preflight validates AWS identity
- Project-name length is checked against AWS limits before any AWS call
- Plan is dry-run by default
- Apply requires --yes
