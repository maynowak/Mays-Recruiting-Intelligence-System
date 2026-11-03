# RIS-APPLICATION-DEPLOY-03K — Drift Reconciliation & Apply Readiness

**Result:** **DRIFT RECONCILED / PLAN REVIEWABLE**

**Apply:** **NOT EXECUTED**

`REVIEWABLE` is not an Apply approval. The earlier 03E/03H approvals do not
apply to this plan artifact.

## 1. Executive summary

The new 03J plan was compared with the preserved 03C plan using fresh,
read-only `terraform show -json` output. The two plans contain the same 85
drift entries, with identical addresses, resource types, actions, and complete
before/after structures:

- 85 unchanged / previously explained;
- 0 changed / requires review;
- 0 new / requires review;
- 0 unverified / blocked.

The 12 active actions are also identical to 03C and are limited to the
ApplicationV1 scope. There are no active protected-resource actions. The
CloudFront drift is reconciled against the 03D evidence and current read-only
CloudFront data as the previously documented `null`/empty-collection
normalization.

**Decision: `REVIEWABLE`**, pending a separate explicit Apply approval naming
the exact 03J plan hash.

## 2. Plan identity and checkpoint

| Item | Result |
|---|---|
| Repository root | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1` |
| Branch | `feature/ris-application-persistence-v1` |
| HEAD | `c560b904986a1e8dbb98dcdc957f3e61cf0ea010` |
| Working tree | Existing `AGENTS.md` modification preserved; no other changes added |
| New plan | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03j.tfplan` |
| New plan SHA-256 | `587E02FC61DE16BD74BFDDDF1B02625C411EFE6F9CD9903DD7CA9925AC243078` |
| Previous plan | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03c.tfplan` |
| Previous plan SHA-256 | `65410136A4FB1EF720FB143F9304F8B6A54BEE026C18AA4EE8F527075F4ED196` |
| Terraform | `1.17.0` / Windows `amd64` |
| Provider | `hashicorp/aws 6.67.0` |
| Lockfile SHA-256 | `716772AF0E40828C58183844578A2663AB82C6DF6CCD4AE0BCA6F1FE57B50AD7` |

Both plans existed and were readable through `terraform show -json`. No
Terraform plan, Apply, init, state write, import, unlock, or AWS mutation was
performed in 03K.

## 3. AWS and state baseline

Read-only verification confirmed:

| Check | Result |
|---|---|
| AWS profile | `default` |
| AWS account | `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| State bucket | `ris-dev2-tf-state-dev` |
| State key | `env:/ris-dev2/dev/terraform.tfstate` |
| Lock table | `ris-dev2-tf-lock` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State serial | `23` |
| State SHA-256 | `2476b37a32bfb1208ae38d3b932a6a4be569fbff6673538eeb1ee35f30a32840` |

The state serial and hash remain unchanged from the 03J baseline.

## 4. Drift reconciliation

The old and new plan JSONs were indexed by `resource_drift[*].address` and
compared recursively without normalizing potentially semantic values. The
comparison result is:

| Category | Count | Result |
|---|---:|---|
| `UNCHANGED / PREVIOUSLY EXPLAINED` | 85 | PASS |
| `CHANGED / REQUIRES REVIEW` | 0 | PASS |
| `NEW / REQUIRES REVIEW` | 0 | PASS |
| `UNVERIFIED / BLOCKED` | 0 | PASS |

The type distribution is also identical:

| Resource type | Count |
|---|---:|
| API Gateway routes | 56 |
| API Gateway integration | 1 |
| API Gateway stage | 1 |
| CloudFront distribution | 1 |
| CloudTrail | 1 |
| EventBridge rules | 2 |
| CloudWatch log groups | 2 |
| CloudWatch alarms | 7 |
| IAM policies | 1 |
| IAM roles | 3 |
| Lambda event source mapping | 1 |
| Lambda functions | 3 |
| S3 buckets | 5 |
| S3 object | 1 |
| **Total** | **85** |

The 03D classification remains applicable: 76 entries are provider/computed
normalizations and 9 are state/remote relationship representations. No new
ID, ARN, IAM policy, origin, security, or sensitive-value difference appeared
in the new plan.

## 5. CloudFront reconciliation

**Status: `CLOUDFRONT DRIFT RECONCILED`**

Target: `E1IZKHFPZ5X7SN` / `module.health_public.aws_cloudfront_distribution.health_public`.

| Property | 03D evidence | Current read-only result | Assessment |
|---|---|---|---|
| Distribution ID | `E1IZKHFPZ5X7SN` | same | match |
| ETag | `E23ZP02F085DFQ` | `E23ZP02F085DFQ` | match |
| Status | `Deployed` | `Deployed` | match |
| Enabled | `true` | `true` | match |
| Origin | `ris-dev2-dev-health-public.s3.eu-central-1.amazonaws.com` | same | match |
| Origin ID | `S3-health-public` | same | match |
| OAC | `E30BLRTMAWVYN1` | same | match |
| Aliases | state `null`, plan `[]` | `[]` | normalization only |
| Ordered cache behaviors | empty | quantity `0` | match |
| Viewer certificate | CloudFront default certificate | same | match |

The only CloudFront drift fields are the previously evidenced `aliases:
null -> []` and `tags: null -> {}` representations. The OAC has no drift
entry. The distribution has no active `resource_changes` action.

## 6. Active plan actions

The new plan contains exactly 11 creates, 1 in-place update, 0 deletes and 0
replacements. All 12 actions are `EXPECTED`:

| Address | Action | Technical effect |
|---|---|---|
| `module.dynamodb.aws_dynamodb_table.applications` | create | PAY_PER_REQUEST ApplicationV1 table with `gsi-owner` |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_applications` | create | Scoped ApplicationV1 DynamoDB permissions |
| `module.api.aws_apigatewayv2_route.applications_create` | create | Application create route |
| `module.api.aws_apigatewayv2_route.applications_list` | create | Owner-scoped list route |
| `module.api.aws_apigatewayv2_route.applications_get` | create | Get route |
| `module.api.aws_apigatewayv2_route.applications_patch` | create | Update route |
| `module.api.aws_apigatewayv2_route.applications_status` | create | Status transition route |
| `module.api.aws_apigatewayv2_route.applications_history` | create | History route |
| `module.api.aws_apigatewayv2_route.applications_cover_letter` | create | Cover-letter version route |
| `module.api.aws_apigatewayv2_route.applications_export` | create | Export route |
| `module.api.aws_apigatewayv2_route.applications_delete` | create | Delete route |
| `module.lambda.aws_lambda_function.agent` | update | ApplicationV1 bundle hash and table binding |

All nine routes use the existing API, integration, and human JWT authorizer
(`8apxb6fgne`, `oybmena`, `9i4w8r`) with `authorization_type=JWT`. The IAM
policy is limited to ApplicationV1 table/GSI operations. The Lambda update
adds `APPLICATIONS_TABLE=ris-dev2-dev-applications`; privacy and erasure
execution flags remain false.

The active action set matches 03C exactly: 11 creates, 1 update, 0 deletes,
and 0 replacements.

## 7. Protected-infrastructure matrix

| Protected area | Active `resource_changes` | Drift assessment | Result |
|---|---|---|---|
| Cognito pool, clients, domains, OAuth | None | No Cognito drift | PASS |
| CloudFront distribution | None | Reconciled normalization only | PASS |
| CloudFront OAC | None | No OAC drift | PASS |
| Route53 / DNS | None | No drift | PASS |
| ACM certificates | None | No drift | PASS |
| JWT authorizers | None | Existing authorizer referenced only | PASS |
| Orders lifecycle | None | `orders_lifecycle=disabled` | PASS |
| Privacy/Erasure/Freeze/Cutover | None | All execution flags remain false | PASS |

No protected resource has an active create, update, delete, or replacement
action. Drift and active changes were evaluated separately.

## 8. Readiness decision

**`REVIEWABLE`**

All 03K-E conditions are satisfied:

- plan identity and SHA-256 verified;
- provider and lockfile context consistent;
- account, workspace, lineage and serial verified;
- 85/85 drift entries unchanged and previously explained;
- CloudFront drift reconciled against 03D evidence and live read-only data;
- zero active protected-resource actions;
- all 12 ApplicationV1 actions technically explained;
- zero deletes and replacements;
- no privacy/erasure execution activation;
- Jobsearch and real applicant data are outside scope.

## 9. Next step

Prepare a separate Apply approval for exactly:

```text
C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03j.tfplan
SHA-256: 587E02FC61DE16BD74BFDDDF1B02625C411EFE6F9CD9903DD7CA9925AC243078
```

That approval is not granted by this report. No Apply or AWS mutation was
performed in 03K.
