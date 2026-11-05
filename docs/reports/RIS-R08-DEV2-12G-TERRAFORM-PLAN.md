# RIS-R08-DEV2-12G — Terraform Plan

Plan context was re-verified read-only: account `262370457690`, profile
`default`, region `eu-central-1`, workspace `ris-dev2`, canonical backend
state key `env:/ris-dev2/dev/terraform.tfstate`, state serial `25`, state
object unchanged, and no running Terraform process. The two lock-table rows
remain digest caches; no force-unlock or cleanup was performed.

Saved plan used `r08_pitr_enabled=true` only for review. It was not applied.

| Resource | Action | Purpose | Risk | Status |
|---|---|---|---|---|
| `module.api.aws_apigatewayv2_route.applications_metrics` | CREATE | existing R08 metrics route | route behavior review | existing planned R08 change |
| `module.dynamodb.aws_dynamodb_table.deletion_ledger` | CREATE | durable deletion evidence | new table/cost; no migration | review required |
| five `module.dynamodb.aws_dynamodb_table.*` R08 tables | UPDATE | enable opt-in PITR | recovery cost; no replacement | explicit approval |
| `module.lambda.aws_iam_role_policy.lambda_deletion_ledger` | CREATE | table/index least privilege | policy review | review required |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_work` | UPDATE | WorkItems IAM correction | runtime permission change | existing R08 change |
| `module.lambda.aws_lambda_function.agent` | UPDATE | bundle/env wiring | code update; flags remain false | review required |

Plan summary: **3 CREATE, 7 UPDATE, 0 DELETE, 0 REPLACE**. Health-Lambda
artifact actions are absent. Cognito, CloudFront, DNS, ACM, Jobsearch,
Orders and existing data resources have no planned actions. The temporary
plan and variables file are evidence artifacts only and are not committed.

Status: **REVIEWED / APPLY NOT AUTHORIZED**.
