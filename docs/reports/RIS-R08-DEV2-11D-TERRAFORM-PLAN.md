# RIS-R08-DEV2-11D — Controlled Terraform Plan

## Guards

- Account/profile/region: `262370457690` / `default` / `eu-central-1`;
- workspace: `ris-dev2`;
- canonical state: `env:/ris-dev2/dev/terraform.tfstate`, serial 25;
- no active lock found; plan used `-lock=false` only for this read-only plan;
- no backend migration or state mutation;
- `terraform init`, `validate` and `fmt -check -recursive` completed;
- temporary plan and variable files were not committed.

## Change summary

| Action | Count |
|---|---:|
| CREATE | 1 |
| UPDATE | 2 |
| DELETE | 0 |
| REPLACE | 0 |

| Resource | Action | Reason | R08 scope | Approval |
|---|---|---|---|---|
| `module.api.aws_apigatewayv2_route.applications_metrics` | CREATE | New metrics route | Yes | Apply approval |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_work` | UPDATE | Add `TransactWriteItems`; correct index ARN | Yes | IAM/Apply approval |
| `module.lambda.aws_lambda_function.agent` | UPDATE | Local R08 bundle code hash differs from live | Yes | Lambda/Apply approval |

No Health Lambda action remains. No DELETE, REPLACE, Cognito, CloudFront/OAC,
Route53/DNS, ACM, DynamoDB table, SQS queue, event-source mapping, or IAM
trust-policy action was present. The plan is technically scoped, but it is not
an Apply authorization.

## Plan decision

**PLAN: REVIEWED — R08 SCOPE CLEAN — APPLY NOT AUTHORIZED.**

The exact saved plan was temporary and has been removed. A future Apply must
use a newly generated, hash-verified plan after final approval and fresh
protected-resource checks.
