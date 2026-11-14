# RIS-SCV-AWS-G4-EXECUTION-07

**Status:** `RIS-SCV-AWS-G4-EXECUTION-07 — BLOCKED / TARGET OR STATE MISMATCH`

**Date:** 2026-11-14 (UTC)

**Task:** `MAYS-SCV-RC3-001`

**Mode:** authorized G4 read-only discovery, Terraform init/validate/plan and plan analysis.

**Apply:** NOT AUTHORIZED AND NOT EXECUTED.

## 1. Authorization and operator

The Release Owner authorized one G4 run for the existing `ris-dev` environment only.

| Field | Verified value |
|---|---|
| Environment | `ris-dev` |
| AWS account | `240571105849` |
| AWS region | `eu-central-1` |
| AWS profile | `mayaws` |
| Operator identity | `arn:aws:iam::240571105849:user/Mayaws` |
| Execution | 2026-11-14; STS check at `06:41Z`, plan immediately after |
| Excluded target | `ris-dev2` |

`ris-dev2` was not contacted. No `default` profile fallback occurred.

## 2. Target and backend verification

STS returned account `240571105849`, region `eu-central-1`, profile `mayaws`.

| Field | Verified result |
|---|---|
| Backend bucket | `mays-ris-tf-state-dev` — exists, `eu-central-1` |
| Init key | `dev/terraform.tfstate` |
| Workspace key prefix | `env:` |
| Workspace | `ris-dev` — exists in backend workspace list |
| Effective state key | `env:/ris-dev/dev/terraform.tfstate` |
| State object | 915,293 bytes, LastModified `2026-11-09T11:35:42Z`, ETag `8b41ea0825f396af01fb2721a88debb4` |
| Lock table | `mays-ris-tf-lock` — ACTIVE |
| Temporary plan lock | acquired and released; no active `LockID` entry remained |

The effective path was confirmed by the actual backend configuration and by reading the object at
that exact key. The expected path and actual state object match.

## 3. State baseline

| Field | Before plan | After plan |
|---|---|---|
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` | unchanged |
| Serial | `61` | `61` |
| Resources in state JSON | 250 | 250 |
| Resource instances | 291 | 291 |
| State ETag | `8b41ea0825f396af01fb2721a88debb4` | unchanged |

The state was read only. No state migration, import, repair, workspace creation or state write
occurred.

Documented inventory includes 20 DynamoDB tables, 6 Lambda functions, 79 API Gateway routes,
4 authorizers, 2 Cognito user pools, 1 CloudFront distribution, 5 S3 buckets, 25 IAM role
policies and 2 EventBridge rules.

## 4. Release candidate

| Item | Verified value |
|---|---|
| Branch | `release/structured-cv-rc1` |
| HEAD | `4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1` |
| Feature flag | `STRUCTURED_CV_PROFILE_ENABLED=false` |
| RC1 worktree | `/home/dci-student/projects/mays-xrepo-orchestration/worktrees/ris-scv-g4-07` |
| Agent bundle | 84 files, SHA-256 `e8169faddbc9de00f1dc1968fe0a9654cbdf38e04d76ef8ad7b4f7430f746f33` |
| Reader bundle | SHA-256 `e405858718101db34a8d5c1237e36d41a47b7dceb8e0ebff8b01bd86d1c366e5` |

The tracked RC1 files were not modified. Local build artifacts and the generated Orders module
were used only for planning. The RC1 `terraform/.terraform.lock.hcl` provider update from
`terraform init` is a local side effect and is not committed.

## 5. Init, validate and plan

Commands (with `TF_DATA_DIR=/tmp/opencode/tfdata-ris-g4-07`, explicit profile and region):

```text
terraform init -reconfigure ...
terraform workspace select ris-dev
terraform fmt -check -recursive
terraform validate
terraform plan -input=false -lock=true \
  -var-file=/tmp/opencode/ris-g4-07/ris-dev.tfvars.json \
  -out=/tmp/opencode/ris-g4-07/ris-dev.tfplan
```

Results:

- `init`: SUCCESS; provider `hashicorp/aws v6.67.0`.
- `workspace select`: SUCCESS; `ris-dev` existed and was selected.
- `fmt -check -recursive`: PASS.
- `validate`: SUCCESS with pre-existing deprecation warnings.
- `plan`: SUCCESS; saved plan created.

Plan artifacts are local and protected, not committed:

| Artifact | SHA-256 |
|---|---|
| Plan `ris-dev.tfplan` | `36632ab510cbef32030e111d82465aa7b2f8b65b2913181d107aa9021b79a57b` |
| Plan JSON | `6c09477b7693fc85ef0a59c746a8b695e85fc8fbab1327aa16482ba111348b7e` |
| Plan log | `6d9e5d51c1f810dff7f8bb5e72d93479b48e0589809bce7a4fb2c8e95c5b767d` |
| Variables file | `f5740a16a3d1fc449aeda35c8c0b7c4c7c762e94a99e07b6bd2028dfaf2853c0` |

The plan file is mode `0600` under `/tmp/opencode/ris-g4-07/`.

## 6. Plan diff inventory

**Result: 6 CREATE / 8 UPDATE / 2 DELETE / 0 REPLACE.**

### CREATE — expected six Structured-CV routes

| Route | Evaluation |
|---|---|
| `GET /v1/partner/me/cv-builder-profiles` | expected |
| `POST /v1/partner/me/cv-builder-profiles` | expected |
| `GET /v1/partner/me/cv-builder-profiles/{profileId}` | expected |
| `PATCH /v1/partner/me/cv-builder-profiles/{profileId}` | expected |
| `DELETE /v1/partner/me/cv-builder-profiles/{profileId}` | expected |
| `GET /v1/partner/me/cv-builder-profiles/{profileId}/export` | expected |

All six use the existing Lambda integration `integrations/wqhnrcs` and existing JWT authorizer
contract. No new authorizer was planned.

### UPDATE

| Resource | Change | Evaluation |
|---|---|---|
| `module.dynamodb.aws_dynamodb_table.partner_profiles` | adds `gsi-structured-owner` (`ownerKey` HASH, `resourceId` RANGE, projection ALL) | expected GSI |
| `module.lambda.aws_lambda_function.agent` | code hash update, adds `STRUCTURED_CV_PROFILE_ENABLED=false`, **removes four live consent flags** | **STOP — regression** |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_partner_profiles` | removes `dynamodb:ConditionCheckItem` | **STOP — regression** |
| `module.health_plane.aws_cloudwatch_event_rule.health_publisher_schedule` | `rate(15 minutes)` → `rate(5 minutes)` | **unexpected drift** |
| `module.health_plane.aws_lambda_function.health_publisher` | filename path only | local-path churn |
| `module.health_plane.aws_lambda_function.health_writer` | filename path only | local-path churn |
| `module.orders_reader[0].aws_lambda_function.reader` | filename path only; source hash unchanged | local-path churn |
| `module.mays_orders[0].module.sqs_worker.aws_iam_role.worker` | removes `permissions_boundary` `Mays-Orders-Lambda-Execution-Boundary` | **STOP — security regression** |

Agent environment removals:

- `CONSENT_NOTICE_STATE_ENFORCED`
- `CONSENT_PILOT_ALLOWLIST`
- `CV_STORAGE_CONSENT_ENFORCED`
- `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`

These are live safety controls from the current `ris-dev` state, not authorized changes in G4.

### DELETE — unexpected

| Resource | Consequence | Evaluation |
|---|---|---|
| `module.jobsearch_edge[0].aws_apigatewayv2_route.partner["POST /v1/partner/me/erasure"]` | removes the live partner erasure route on API `c7e9pdwe78` | **STOP — functional/Privacy regression** |
| `module.documents.aws_s3_bucket_cors_configuration.documents` | removes document-bucket CORS configuration | **STOP — unexpected destructive config change** |

No DynamoDB table, S3 object, Cognito resource, CloudFront distribution, Route53 record or ACM
certificate is deleted by this plan. The two deletes above are nevertheless destructive and not
authorized by G4.

## 7. Protected resources

| Protected family | Plan result |
|---|---|
| Cognito User Pools / clients / domain / OAuth | no changes |
| CloudFront / OAC | no changes |
| Route53 / DNS / ACM | no changes |
| Existing DynamoDB tables and data | no delete/replace; one GSI add |
| Existing S3 objects | no object deletion; one CORS configuration deletion |
| API Gateway existing routes | one live erasure route would be deleted |
| IAM | two policy regressions (ConditionCheckItem and permissions boundary) |

## 8. Finding

The target identity, backend, state key, workspace, lineage and serial all match `ris-dev`.
However, the **RC1 plan does not model the current live `ris-dev` state**. Applying this plan
would:

1. delete the live partner erasure route;
2. remove the live documents-bucket CORS configuration;
3. remove consent safety flags from the agent Lambda;
4. remove the partner-profile `ConditionCheckItem` IAM permission;
5. remove the Orders worker permissions boundary;
6. change the health publisher schedule from 15 to 5 minutes.

This is a release/state mismatch, not a target-identity failure. The plan is therefore **not
eligible for G5 approval** and must not be applied.

## 9. G5 recommendation

**G5: DO NOT APPROVE THIS PLAN.**

Required remediation before a new G4/G5 plan:

- integrate/reconcile RC1 with the current live `main`/state contract, without force-push or
  rewrite;
- preserve the partner erasure route, documents CORS configuration, consent flags, IAM
  `ConditionCheckItem` and Orders permissions boundary;
- decide deliberately whether the health publisher schedule remains 15 minutes;
- regenerate the plan from the reconciled release candidate;
- re-run the G4 target/state checks and produce a new plan hash.

No merge, apply, consent activation, live E2E or production deployment was performed.

## 10. Evidence and git

- `init`, `workspace select`, `fmt`, `validate`, `plan`: exit `0` (plan excepted only by review
  classification, not command failure).
- State before/after: lineage unchanged, serial `61`, 250 resources.
- Plan: `36632ab510cbef32030e111d82465aa7b2f8b65b2913181d107aa9021b79a57b`.
- No apply, destroy, import, state operation, consent change or production deploy.
- Report commit: recorded in the docs branch commit.

**RIS-SCV-AWS-G4-EXECUTION-07 — BLOCKED / TARGET OR STATE MISMATCH**

**STOP BEFORE TERRAFORM APPLY.**
