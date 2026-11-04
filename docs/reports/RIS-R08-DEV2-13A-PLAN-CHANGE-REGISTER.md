# RIS-R08-DEV2-13A — Exact Plan Change Register

Fresh read-only plan evidence was generated against the current canonical
DEV2 backend with `r08_pitr_enabled=true`. Current state: serial 25, lineage
`a0bd361d-5cd1-a207-a8c0-e6888f0be082`, 181 resources. Plan result:
**3 CREATE, 7 UPDATE, 0 DELETE, 0 REPLACE**.

| Terraform address | Action | Purpose | Before / after | Risk | Approval |
|---|---|---|---|---|---|
| `module.api.aws_apigatewayv2_route.applications_metrics` | CREATE | `GET /v1/partner/me/applications/metrics` to existing integration | absent -> JWT route on API `8apxb6fgne` | API exposure/contract review | separate approval |
| `module.dynamodb.aws_dynamodb_table.deletion_ledger` | CREATE | durable deletion evidence | absent -> `ris-dev2-dev-deletion-ledger`, PK `ledgerId`, GSI `gsi-operation` | new table, cost, migration | separate approval |
| `module.dynamodb.aws_dynamodb_table.erasure_operations` | UPDATE | PITR | disabled -> enabled | PITR cost/restore scope | separate approval |
| `module.dynamodb.aws_dynamodb_table.privacy_receipts` | UPDATE | PITR | disabled -> enabled | PITR cost/restore scope | separate approval |
| `module.dynamodb.aws_dynamodb_table.s3_erasure_phases` | UPDATE | PITR | disabled -> enabled | PITR cost/restore scope | separate approval |
| `module.dynamodb.aws_dynamodb_table.upload_cutover` | UPDATE | PITR | disabled -> enabled | PITR cost/restore scope | separate approval |
| `module.dynamodb.aws_dynamodb_table.upload_ticket_ledger` | UPDATE | PITR | disabled -> enabled | PITR cost/restore scope | separate approval |
| `module.lambda.aws_iam_role_policy.lambda_deletion_ledger` | CREATE | ledger table/index access | absent -> `GetItem`, `PutItem`, `Query` | IAM review | separate approval |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_work` | UPDATE | existing WorkItems correction | malformed index ARN + missing transaction action -> table/index ARN + `TransactWriteItems` | runtime permission change | separate approval |
| `module.lambda.aws_lambda_function.agent` | UPDATE | bundle and ledger environment wiring | prior hash/env -> current bundle; ledger variables added, flag `false` | runtime/code cutover | separate approval |

The plan was compared to refreshed state, not a stale snapshot. No other
resource has a non-no-op action. In particular, Health Lambdas, Cognito,
CloudFront/OAC, DNS/Route53, ACM, SQS queues, event-source mappings,
Jobsearch, Orders and existing table schemas are absent from the change set.

Status: **EXACT SCOPE VERIFIED / APPLY NOT AUTHORIZED**.
