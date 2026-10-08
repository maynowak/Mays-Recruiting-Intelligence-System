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
- `--orders-state-mode` : local|s3
- `--orders-backend-bucket` / `--orders-backend-lock-table` : only if state-mode s3

## Examples

### Local test
```bash
python3 -m installer.ris --project-name mays-ris-test-e2e-01 --environment test \
  --profile mayaws --backend-bucket mays-ris-tf-state-dev --backend-region eu-central-1 \
  --backend-lock-table mays-ris-tf-lock validate
```

### Orders with local state
```bash
python3 -m installer.ris --project-name mays-ris-test-e2e-01 --environment test \
  --profile mayaws --orders-state-mode local plan
```

## Safety
- Preflight validates AWS identity
- Plan is dry-run by default
- Apply requires --yes
