# RIS-R08-DEV2-10C — Code/Resource Mapping

| Code component | Required resource | Current state | Required change | Risk |
|---|---|---|---|---|
| Durable subject fence | Existing WorkItems table keyed by `workId` | Present, empty | No table migration; deploy code/IAM | Historical rows must fail closed if present |
| Worker atomic admission | WorkItems table + Lambda role | Existing policy lacks `TransactWriteItems` and has malformed index ARN | In-place IAM policy update | Must verify exact policy before apply |
| ApplicationV1 repository | Applications table + `gsi-owner` | Present, empty; env binding verified | No table creation | Owner/tenant/partner/issuer isolation remains test gate |
| Public Application erasure | Existing `POST /me/erasure` route and agent Lambda | Route exists; live Lambda is pre-PR | Update Lambda artifact | No productive erasure activation allowed |
| Erasure checkpoints | ErasureOperations/S3 phase tables | Present, empty; flags false | No schema creation | Resume evidence remains synthetic/live-open |
| Partner registry scope | Partner applications table + `gsi-client` | Present, empty; env binding verified | No table creation | Synthetic identity must be separately provisioned later |
| Recovery/deletion ledger | Local code contracts; no dedicated live ledger resource | No live ledger evidence | Separate migration/design approval | RG-10 remains blocked |
| Metrics API | API HTTP JWT route | Missing in live state | Create `GET /v1/partner/me/applications/metrics` | New route requires API contract/smoke approval |
| Lambda packaging | Agent and health bundles | Live agent SHA differs from local rebuilt bundle | Update artifacts only after approval | Health bundle updates are unrelated scope risk |

No new DynamoDB table, Cognito pool/client, CloudFront distribution, DNS or
ACM resource is required by the reviewed plan. The runtime environment already
contains `APPLICATIONS_TABLE`, `WORK_ITEMS_TABLE`, partner registry and erasure
table names. All productive erasure, receipt journaling, S3 erasure execution,
quiescence, freeze and upload-cutover flags are currently `false`.
