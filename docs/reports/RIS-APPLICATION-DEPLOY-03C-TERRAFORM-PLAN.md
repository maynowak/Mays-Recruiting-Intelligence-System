# RIS-APPLICATION-DEPLOY-03C — Saved Terraform Plan

**Status:** **BLOCKED — plan saved, Apply not approved**

## Plan identity

| Item | Value |
|---|---|
| Account | `262370457690` |
| Principal | `arn:aws:iam::262370457690:user/devnemo` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| Backend bucket | `ris-dev2-tf-state-dev` |
| Effective state key | `env:/ris-dev2/dev/terraform.tfstate` |
| Lock table | `ris-dev2-tf-lock` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State serial at plan | `23` |
| Git commit | `f8deeb7f55b733b93f2297fefa17834c1c4000cf` |
| Plan file | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03c.tfplan` |
| Plan SHA-256 | `65410136A4FB1EF720FB143F9304F8B6A54BEE026C18AA4EE8F527075F4ED196` |
| Plan JSON | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03c-plan.json` |

The plan used normal refresh behavior and state locking. It did not use
`-target`, `-replace`, `-destroy`, `-refresh=false` or `-lock=false`. The
remote state remained serial `23` with the same lineage after planning. The
two DynamoDB lock-table records observed afterward are S3 backend digest
records (`...-md5`), not active Terraform lock records.

## Active resource actions

Machine checking of `resource_changes[*].change.actions` found:

| Action | Count |
|---|---:|
| Create | 11 |
| Update | 1 |
| Delete | 0 |
| Replacement | 0 |
| No-op resource entries | 152 |

Creates:

- `module.dynamodb.aws_dynamodb_table.applications`
- `module.lambda.aws_iam_role_policy.lambda_dynamodb_applications`
- `module.api.aws_apigatewayv2_route.applications_create`
- `module.api.aws_apigatewayv2_route.applications_list`
- `module.api.aws_apigatewayv2_route.applications_get`
- `module.api.aws_apigatewayv2_route.applications_patch`
- `module.api.aws_apigatewayv2_route.applications_status`
- `module.api.aws_apigatewayv2_route.applications_history`
- `module.api.aws_apigatewayv2_route.applications_cover_letter`
- `module.api.aws_apigatewayv2_route.applications_export`
- `module.api.aws_apigatewayv2_route.applications_delete`

The nine routes all use the existing API `8apxb6fgne`, existing integration
`oybmena`, human JWT authorizer `9i4w8r`, and `authorization_type = JWT`.

The ApplicationV1 table is `ris-dev2-dev-applications`, PAY_PER_REQUEST, with
keys `applicationId`/`entityKey` and GSI `gsi-owner` on `ownerKey`/`updatedAt`.
The new IAM policy grants only `PutItem`, `GetItem`, `Query`, `DeleteItem` and
`TransactWriteItems` on the application table and its owner GSI ARN.

The sole update is:

- `module.lambda.aws_lambda_function.agent`: new ApplicationV1 bundle hash
  and `APPLICATIONS_TABLE=ris-dev2-dev-applications` environment binding.

No active Cognito, CloudFront/OAC, DNS, ACM, JWT-authorizer, existing-table,
S3, SQS, Orders or unrelated IAM action is present. No replacement is present.

## Drift and hard blocker

The machine-readable plan reports **85 `resource_drift` entries** even though
the active plan actions above are limited to ApplicationV1. Counts by type:

| Drift type | Count |
|---|---:|
| API Gateway routes | 56 |
| API Gateway integration/stage | 2 |
| CloudFront distribution | 1 |
| CloudTrail | 1 |
| EventBridge rules | 2 |
| CloudWatch log groups/alarms | 9 |
| IAM policy/roles | 4 |
| Lambda/event source mappings | 4 |
| S3 buckets/object | 7 |
| **Total** | **85** |

The drift includes existing API routes, shared IAM/Lambda resources and the
protected `module.health_public.aws_cloudfront_distribution.health_public`
(`E1IZKHFPZ5X7SN`). Some differences appear to be provider/state
normalization (for example `null` versus empty API route collections and S3
versioning represented by a separate resource), but this has not been
authorized as harmless drift. Under the deployment guard, unexpected drift is
a hard blocker and cannot be suppressed with `-refresh=false` or a targeted
plan.

## Protected-infrastructure matrix

| Component | Active action | Drift observed | Gate |
|---|---|---|---|
| External Cognito pool/clients/issuer | none | no Cognito drift entry | protected; cross-account reference |
| JWT authorizers | none | no active action | protected |
| CloudFront/OAC, including `E1IZKHFPZ5X7SN` | none | CloudFront drift entry | **BLOCKED pending disposition** |
| DNS / ACM | none | none observed | protected |
| Existing DynamoDB tables | none | none observed | no replacement |
| Orders lifecycle | none; remains disabled | none | protected |
| Privacy/erasure execution flags | no changes | live values remain false | protected |

## Apply recommendation

**DO NOT APPLY.** The exact plan is preserved outside the repository for
review, but it is not approved. First obtain an explicit technical
disposition for all 85 drift entries, especially the protected CloudFront and
shared API/IAM/Lambda drift, then create a fresh plan against the unchanged
configuration and re-run the complete guard. No Apply, E2E test, force-unlock,
state write, import, migration or automatic re-plan was performed after this
blocked result.
