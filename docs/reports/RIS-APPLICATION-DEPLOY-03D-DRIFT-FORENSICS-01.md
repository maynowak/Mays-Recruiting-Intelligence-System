# RIS-APPLICATION-DEPLOY-03D — Drift Forensics 01

**Status:** REVIEWABLE, **not an Apply approval**

## 1. Executive Summary

The existing Terraform plan was inspected without recalculation. Its SHA-256
remains unchanged. All 85 `resource_drift` entries are classified:

- 76 provider-normalization or computed-attribute differences;
- 9 state/remote relationship representations managed by separate resources;
- 0 unresolved entries;
- 0 changed sensitive values.

The drift does not produce an active protected-resource action in
`resource_changes`. The CloudFront entry for `E1IZKHFPZ5X7SN` is explained by
`null` versus empty-collection representations only. Read-only CloudFront
configuration matches the saved state and Terraform configuration.

The result is **REVIEWABLE**, not approved. Apply remains prohibited until the
caller explicitly approves this exact plan and all normal deployment gates are
met.

## 2. Plan identity and verification

| Item | Result |
|---|---|
| Branch | `feature/ris-application-persistence-v1` |
| HEAD | `e7fcc4c3e193f0d9c6c699dda831a2f8ca15015d` |
| Worktree | clean before this report; no implementation changes |
| Plan | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03c.tfplan` |
| Plan SHA-256 | `65410136A4FB1EF720FB143F9304F8B6A54BEE026C18AA4EE8F527075F4ED196` |
| Terraform | `1.17.0` |
| Plan format | `1.2` |
| Resource changes | 164 entries: 152 no-op, 12 active |
| Resource drift | 85 |
| Plan complete/applyable metadata | `true` / `true` |
| State serial | 23 before and after inspection |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |

`terraform show -json` was run against the existing binary plan. A local,
external `init -backend=false` was needed only to cache the `hashicorp/time`
provider schema required by `show`; it did not contact the remote backend and
did not calculate a new plan. No Apply, refresh-only operation, state write,
import, unlock or AWS mutation occurred.

## 3. Complete drift classification

### 3.1 Provider normalization / computed attributes — 76 entries

These entries differ only in empty-value representation (`null` versus `[]` or
`{}`), computed API Gateway deployment metadata, or provider-managed empty
collections. They have no active configuration action.

| Resource family | Count | Difference |
|---|---:|---|
| Existing API routes | 56 | `authorization_scopes: null -> []`; `request_models: null -> {}`; M2M route has only `request_models` |
| API integration | 1 | `request_parameters: null -> {}`; `request_templates: null -> {}` |
| API stage | 1 | computed `deployment_id: "" -> "i86piw"`; `stage_variables: null -> {}` |
| CloudFront distribution | 1 | `aliases: null -> []`; `tags: null -> {}` |
| CloudTrail | 1 | `exclude_management_event_sources: null -> []` |
| EventBridge rules | 2 | `tags: null -> {}` |
| CloudWatch log groups | 2 | `tags: null -> {}` |
| CloudWatch alarms | 7 | action lists `null -> []`; `tags: null -> {}` |
| Lambda event source mapping | 1 | empty `function_response_types`, `queues`, `topics`, and `tags` |
| Lambda functions | 3 | `layers: null -> []`; health functions also `tags: null -> {}` |
| Health HTML S3 object | 1 | `metadata: null -> {}`; `tags: null -> {}` |
| **Total** | **76** | provider/computed normalization |

The 56 existing route addresses are:

```text
module.api.aws_apigatewayv2_route.agents
module.api.aws_apigatewayv2_route.apiprofiles_create
module.api.aws_apigatewayv2_route.apiprofiles_get
module.api.aws_apigatewayv2_route.apiprofiles_list
module.api.aws_apigatewayv2_route.apiprofiles_status
module.api.aws_apigatewayv2_route.apiprofiles_update
module.api.aws_apigatewayv2_route.credentials_create
module.api.aws_apigatewayv2_route.credentials_disable
module.api.aws_apigatewayv2_route.credentials_enable
module.api.aws_apigatewayv2_route.credentials_get
module.api.aws_apigatewayv2_route.credentials_list
module.api.aws_apigatewayv2_route.credentials_revoke
module.api.aws_apigatewayv2_route.credentials_rotate
module.api.aws_apigatewayv2_route.erasure
module.api.aws_apigatewayv2_route.health
module.api.aws_apigatewayv2_route.introspection
module.api.aws_apigatewayv2_route.m2m_agent_execute
module.api.aws_apigatewayv2_route.me
module.api.aws_apigatewayv2_route.offers
module.api.aws_apigatewayv2_route.offers_create
module.api.aws_apigatewayv2_route.offers_grant
module.api.aws_apigatewayv2_route.offers_item
module.api.aws_apigatewayv2_route.offers_status
module.api.aws_apigatewayv2_route.offers_update
module.api.aws_apigatewayv2_route.offers_withdraw
module.api.aws_apigatewayv2_route.partner_agent_execute
module.api.aws_apigatewayv2_route.partner_ats_profiles_create
module.api.aws_apigatewayv2_route.partner_ats_profiles_delete
module.api.aws_apigatewayv2_route.partner_ats_profiles_get
module.api.aws_apigatewayv2_route.partner_ats_profiles_list
module.api.aws_apigatewayv2_route.partner_ats_profiles_update
module.api.aws_apigatewayv2_route.partner_cv_search_profiles_create
module.api.aws_apigatewayv2_route.partner_cv_search_profiles_delete
module.api.aws_apigatewayv2_route.partner_cv_search_profiles_get
module.api.aws_apigatewayv2_route.partner_cv_search_profiles_list
module.api.aws_apigatewayv2_route.partner_cv_search_profiles_update
module.api.aws_apigatewayv2_route.partner_cvs_create
module.api.aws_apigatewayv2_route.partner_cvs_delete
module.api.aws_apigatewayv2_route.partner_cvs_document_complete
module.api.aws_apigatewayv2_route.partner_cvs_document_get
module.api.aws_apigatewayv2_route.partner_cvs_document_upload
module.api.aws_apigatewayv2_route.partner_cvs_get
module.api.aws_apigatewayv2_route.partner_cvs_list
module.api.aws_apigatewayv2_route.partner_cvs_update
module.api.aws_apigatewayv2_route.partner_manual_profiles_create
module.api.aws_apigatewayv2_route.partner_manual_profiles_delete
module.api.aws_apigatewayv2_route.partner_manual_profiles_get
module.api.aws_apigatewayv2_route.partner_manual_profiles_list
module.api.aws_apigatewayv2_route.partner_manual_profiles_update
module.api.aws_apigatewayv2_route.platform
module.api.aws_apigatewayv2_route.privacy_export
module.api.aws_apigatewayv2_route.privacy_inspect
module.api.aws_apigatewayv2_route.profile
module.api.aws_apigatewayv2_route.profile_create
module.api.aws_apigatewayv2_route.profile_delete
module.api.aws_apigatewayv2_route.profile_update
```

### 3.2 State/remote relationship representation — 9 entries

These are not unexplained external changes. The live relationship is present
and represented in Terraform by a separate resource or binding:

| Address | Difference | Read-only evidence |
|---|---|---|
| `module.health_plane.aws_iam_policy.health_publisher` | `attachment_count: 0 -> 1`; tags null/empty | policy attached to health publisher role |
| `module.iam.aws_iam_role.lambda_role` | inline policy `[] -> ris-dev2-lambda-policy` | IAM listing confirms policy |
| `module.lambda.aws_iam_role.lambda_execution` | inline policy `[] ->` existing agent policies | IAM listing confirms policies |
| `module.health_plane.aws_iam_role.health_publisher` | managed policy ARNs `[] ->` existing health policy ARN | IAM listing confirms attachment |
| `aws_s3_bucket.data` | inline versioning false -> true | live S3 versioning is Enabled; separate resource manages it |
| `module.documents.aws_s3_bucket.documents` | inline versioning false -> true | live S3 versioning is Enabled; separate resource manages it |
| `module.health_plane.aws_s3_bucket.health_state` | versioning false -> true; tags null/empty | live S3 versioning is Enabled; separate resource manages it |
| `module.cloudtrail.aws_s3_bucket.trail` | inline policy empty -> CloudTrail policy | live policy exists; policy resource manages it |
| `module.health_public.aws_s3_bucket.public_presentation` | inline policy empty -> OAC policy; tags null/empty | live OAC policy exists; policy resource manages it |

These are state/provider representation differences, not planned resource
actions. No table, bucket, role or policy is replaced or deleted.

### 3.3 External infrastructure changes

**No actual external infrastructure change was proven.** The read-only AWS
checks corroborate the normalized/relationship classifications. The plan's
`resource_drift` section describes refresh-time before/after values, not
additional Apply actions.

### 3.4 Unresolved drift

**0 entries.** No drift item had an unexplained value change after comparing
the saved state, plan representation, Terraform configuration and read-only
AWS metadata.

### 3.5 Sensitive-value assessment

No changed value is a credential, token, password, private key or secret.
Terraform marks many nested fields as sensitive in the JSON structure, and
some unchanged fields have names such as credential/table references; those
values were not copied into this report. No sensitive field appears in a drift
difference.

## 4. CloudFront forensics

### Result: `CLOUDFRONT DRIFT EXPLAINED`

Target distribution: `E1IZKHFPZ5X7SN`

| Property | State / plan | Live read-only result | Assessment |
|---|---|---|---|
| Distribution ID | `E1IZKHFPZ5X7SN` | `E1IZKHFPZ5X7SN` | matches |
| ARN | account 262370457690 distribution ARN | same | matches |
| ETag | `E23ZP02F085DFQ` | `E23ZP02F085DFQ` | matches |
| Status | `Deployed` | `Deployed` | matches |
| Enabled | `true` | `true` | matches |
| Origin | `ris-dev2-dev-health-public.s3.eu-central-1.amazonaws.com` | same | matches |
| Origin ID | `S3-health-public` | same | matches |
| OAC | `E30BLRTMAWVYN1` | same; SigV4/always signing | matches |
| Cache behavior | GET/HEAD, redirect HTTPS, zero TTLs | same | matches |
| Ordered cache behaviors | empty | quantity 0 | matches |
| Aliases | state `null`; plan `[]` | quantity 0 | provider normalization |
| Certificate | CloudFront default certificate | CloudFront default certificate | matches |
| Terraform action | drift `update`; resource change `no-op` | no Apply action | no infrastructure change |

The saved-state/refresh difference contains only `aliases: null -> []` and
`tags: null -> {}`. The Terraform module defines the same enabled distribution,
default `health.html`, S3 origin, OAC, default CloudFront certificate, no
aliases and the same cache behavior. The OAC has no drift entry. No additional
CloudFront or OAC action appears in `resource_changes`; the protected
distribution is unchanged by this plan.

## 5. `resource_drift` versus `resource_changes`

| Comparison | Result |
|---|---|
| Drift entries | 85 |
| Resource-change entries | 164 total |
| No-op resource-change entries | 152 |
| Active resource-change entries | 12 |
| Protected active actions | 0 |
| Deletes | 0 |
| Replacements | 0 |

The presence of a drift entry does not mean Terraform will perform that
refresh difference. The active action set is separately guarded below.

## 6. Complete assessment of the 12 active actions

All nine routes target existing API `8apxb6fgne`, existing Lambda integration
`oybmena`, and existing human JWT authorizer `9i4w8r`. They are JWT-protected
and ApplicationV1-specific.

| Address | Action | Purpose / risk | Assessment |
|---|---|---|---|
| `module.api.aws_apigatewayv2_route.applications_create` | create | Create ApplicationV1 route | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_list` | create | List scoped applications | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_get` | create | Get one application | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_patch` | create | Update application | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_status` | create | Status transition | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_history` | create | History entry | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_cover_letter` | create | Cover-letter version | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_export` | create | Application export | EXPECTED / allowed |
| `module.api.aws_apigatewayv2_route.applications_delete` | create | Application deletion | EXPECTED / allowed |
| `module.dynamodb.aws_dynamodb_table.applications` | create | PAY_PER_REQUEST table with `gsi-owner` | EXPECTED / allowed; no replacement |
| `module.lambda.aws_iam_role_policy.lambda_dynamodb_applications` | create | Scoped DynamoDB permissions | EXPECTED / allowed |
| `module.lambda.aws_lambda_function.agent` | update | ApplicationV1 bundle and table env binding | EXPECTED / in-place only |

The IAM policy is limited to `PutItem`, `GetItem`, `Query`, `DeleteItem` and
`TransactWriteItems` on the ApplicationV1 table and owner-GSI ARN. It does not
grant access to Cognito, CloudFront, DNS, ACM, S3, SQS or unrelated tables.

The Lambda update changes the code hash and adds only
`APPLICATIONS_TABLE=ris-dev2-dev-applications`; privacy/erasure execution
flags remain disabled.

## 7. Decision matrix

| Category | Result |
|---|---|
| 85 drift entries fully classified | **PASS** |
| Protected resources in active `resource_changes` | **0 — PASS** |
| CloudFront drift explained | **PASS** |
| ApplicationV1 changes | **EXPECTED** |
| IAM change | **PASS — least-privilege ApplicationV1 policy** |
| State/plan consistency | **PASS — hash, lineage and serial verified** |
| Apply recommendation | **REVIEWABLE, not approved** |

## 8. Next deployment decision

The drift is forensically explained and does not show a protected-resource
change or ApplicationV1-unrelated active action. The plan is therefore
**REVIEWABLE** for a separate approval decision.

This report does **not** approve Apply. The exact plan remains blocked until
the Auftraggeber explicitly approves its SHA-256, resource counts and scope.
No AWS E2E phase may begin before that approval and a successful in-place
Apply.
