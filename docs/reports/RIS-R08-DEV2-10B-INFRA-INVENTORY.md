# RIS-R08-DEV2-10B — Infrastructure Inventory

Read-only discovery found a coherent DEV2 stack in account `262370457690`,
region `eu-central-1`.

| Area | Verified state | R08 relevance |
|---|---|---|
| API Gateway | HTTP API `8apxb6fgne`, `$default`, auto-deploy | Existing API; no replacement planned |
| Human authorizer | JWT, pool `eu-central-1_K3dkdSipZ`, audience `21j28p71vogg0m41tcue0ib3l4` | Existing Cognito chain |
| M2M authorizer | JWT, issuer pool `eu-central-1_ojbmoiYGM`, audience `82ji073smu1b3fsvj96sonso` | External fallback preserved |
| Lambda | `ris-dev2-dev-agent`, Python 3.14, 30s, 128 MB | Live code is pre-PR; update planned |
| Event source | Enabled SQS mapping from `ris-dev2-dev-work-queue`, batch 5 | Worker evidence still live-open |
| Application table | `ris-dev2-dev-applications`, ACTIVE, 0 items, `gsi-owner` | Present and correctly bound |
| WorkItems table | `ris-dev2-dev-work-items`, ACTIVE, 0 items, `gsi-user`, `gsi-status` | Fence uses existing `workId` table |
| Erasure tables | Operations, S3 phases, upload ledger/cutover present, 0 items | Runtime bindings present; activation disabled |
| Partner registry | `ris-dev2-dev-partner-applications`, ACTIVE, 0 items, `gsi-client` | Scope binding infrastructure present |
| SQS/DLQ | Four work queues route to `ris-dev2-dev-dlq`, max receive 3 | Live redrive evidence not executed |
| S3 | Data/documents/health buckets exist; private access blocks verified | No object mutation performed |
| CloudFront | Distribution `E1IZKHFPZ5X7SN`, Deployed, enabled, default certificate | Protected; no plan action |
| CloudWatch | Three Lambda log groups, 14-day retention; seven alarms OK | Operational evidence available |
| CloudTrail | `ris-dev2-trail` logging, latest delivery no error | Audit trail active |

All 17 Terraform-managed DynamoDB tables exist and are ACTIVE. Item counts
were zero except the seeded agent catalog (2). Point-in-time recovery was
reported **DISABLED** for WorkItems, Applications, ErasureOperations and
PrivacyReceipts, and the same setting was observed across the discovered
tables. No resource was modified.
