# RIS-R08-DEV2-11C — PITR and Recovery Alignment

## Current status

Read-only verification found `PointInTimeRecoveryStatus: DISABLED` on all 17
RIS DEV2 DynamoDB application tables, including WorkItems, Applications,
ErasureOperations and PrivacyReceipts. The backend lock table was also not a
recovery target. No PITR enablement or restore was performed.

Terraform currently has no `point_in_time_recovery` block, AWS Backup resource,
or durable deletion-ledger resource. Terraform owns the 17 application tables
through `terraform/modules/dynamodb/main.tf`.

## Contract distinction

| Control | Status |
|---|---|
| PITR declared in Terraform | NO |
| PITR enabled in AWS | NO |
| Restore executed | NO live evidence |
| RecoveryPlanV1 | Local implementation/synthetic tests |
| Deletion ledger | Local in-memory contract; no durable live ledger |
| Restore deletion replay | No live evidence |
| Erasure-after-restore reconciliation | No live evidence |
| Fence after restore | Local contract only |

## Decision

No PITR Terraform change was added to the R08 plan. Adding it would expand the
plan to all in-scope tables and requires an approved backup/retention policy,
durable ledger design, IAM review, restore sandbox, replay and reconciliation
evidence. PITR activation alone would not close RG-10 and could make deleted
data available after restore without a durable replay authority.

**PITR CONFIGURATION: BLOCKED / SEPARATE APPROVAL REQUIRED.** RG-10 remains
RED/BLOCKED.

## Phase-12 update

Terraform now contains opt-in `r08_pitr_enabled=false` default for five R08 coordination tables and the separate deletion-ledger table. The review plan shows in-place PITR updates plus new ledger resources; no table replacement or deletion. This is configuration evidence, not activation, restore evidence, retention approval or erasure compliance.
