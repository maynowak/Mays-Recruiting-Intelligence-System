# RIS-APPLICATION-DEPLOY-03J — Clean Provider Alignment & Saved Replan

**Result:** **CLEAN PLAN CREATED / APPLY NOT EXECUTED**

**Decision:** **BLOCKED**

The provider/dependency inconsistency is resolved for the current
configuration and a new reproducible plan was created. Deployment remains
blocked because the refreshed plan still reports 85 drift entries, including a
protected CloudFront distribution drift. No drift was suppressed.

## 1. Root cause addressed

The previous 03C plan was created with a transient dependency selection that
included `hashicorp/time` `0.14.2`, although the active Terraform root has no
`time` requirement. The committed lockfile retained that orphaned selection,
and the saved plan could not be applied against a clean current dependency
context.

The current root was verified to have exactly one active provider requirement:

```text
registry.terraform.io/hashicorp/aws
constraint: ~> 6.0
selected:   6.67.0
```

No artificial `time` dependency was added. The old 03C plan was not used.

## 2. J1 provider alignment

| Check | Result |
|---|---|
| Terraform root | repository `terraform/` |
| Terraform | `1.17.0` / Windows `amd64` |
| Active required providers | AWS only |
| `hashicorp/time` required by active modules | No |
| Regular `terraform init` | PASS |
| Backend migration | Not performed |
| Provider upgrade | Not performed |
| Terraform validate | PASS, deprecation warnings only |
| Terraform fmt check | PASS |
| Final lockfile providers | AWS `6.67.0` only |
| Final lockfile SHA-256 | `716772AF0E40828C58183844578A2663AB82C6DF6CCD4AE0BCA6F1FE57B50AD7` |

Terraform removed the orphaned `hashicorp/time` block and normalized the AWS
constraint from `>= 6.0.0, ~> 6.0` to `~> 6.0`. The final lockfile was created
by regular Terraform initialization and committed separately:

```text
455dba1 build(terraform): align lockfile with active providers
```

The provider was installed and used from the isolated J data directory with
the final lockfile. No repository provider binary or CLI mirror was added.

## 3. J2 baseline

| Check | Result |
|---|---|
| Branch | `feature/ris-application-persistence-v1` |
| HEAD before report commit | `455dba14d1651bbae381ebdf2072d4979a0631e0` |
| AWS profile | `default` |
| AWS account | `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| State bucket | `ris-dev2-tf-state-dev` |
| State key | `env:/ris-dev2/dev/terraform.tfstate` |
| Lock table | `ris-dev2-tf-lock` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State serial before plan | `23` |
| State serial after plan | `23` |
| State SHA-256 before/after | `2476b37a32bfb1208ae38d3b932a6a4be569fbff6673538eeb1ee35f30a32840` |
| CloudFront `E1IZKHFPZ5X7SN` | Deployed and enabled |

The plan used the documented `ris-dev2` variables, including
`orders_lifecycle=disabled`, external identity mode and `eu-central-1`. No
Privacy/Erasure/Freeze/Cutover activation flag was enabled.

## 4. New plan artifact

The new plan was generated with normal refresh and state locking, without
`-target`, `-replace`, `-destroy`, `-refresh=false` or `-lock=false`.

| Item | Value |
|---|---|
| Plan path | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03j.tfplan` |
| Plan SHA-256 | `587E02FC61DE16BD74BFDDDF1B02625C411EFE6F9CD9903DD7CA9925AC243078` |
| Plan JSON | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03j-plan.json` |
| Terraform plan exit code | `0` |
| Terraform version in plan | `1.17.0` |
| Plan format | `1.2` |

The former plan `ris-dev2-03c.tfplan` was not supplied to any command and
remains preserved separately.

## 5. Complete active-action guard

The plan JSON contains 164 resource-change entries and 85 drift entries. The
active actions are exactly:

| Action | Count |
|---|---:|
| Create | 11 |
| Update in place | 1 |
| Delete | 0 |
| Replacement | 0 |

Creates:

- `module.dynamodb.aws_dynamodb_table.applications`;
- `module.lambda.aws_iam_role_policy.lambda_dynamodb_applications`;
- nine ApplicationV1 API routes: list, create, get, patch, status, history,
  cover-letter versions, export and delete.

Update:

- `module.lambda.aws_lambda_function.agent` — ApplicationV1 bundle hash and
  `APPLICATIONS_TABLE=ris-dev2-dev-applications` binding.

The active address/action set is identical to the 03C plan's active set:
11 creates, 1 update, 0 deletes and 0 replacements. The active routes use
the existing API `8apxb6fgne`, existing integration `oybmena`, and existing
human JWT authorizer `9i4w8r` with `authorization_type=JWT`.

## 6. Protected-infrastructure matrix

| Protected area | Active action | Drift | Guard result |
|---|---|---:|---|
| Cognito pool, clients, domain, OAuth | None | 0 Cognito entries | PASS |
| CloudFront `E1IZKHFPZ5X7SN` | None | 1 distribution entry | **BLOCKED** |
| CloudFront OAC | None | No active OAC action | PASS for active scope |
| Route53 / DNS | None | None observed | PASS |
| ACM | None | None observed | PASS |
| JWT authorizers | None | No authorizer drift entry | PASS |
| Existing DynamoDB tables | None | None observed | PASS |
| Orders integration | None; `orders_lifecycle=disabled` | No active Orders action | PASS |
| Privacy/Erasure/Freeze/Cutover flags | None; all remain false | No activation action | PASS |

The CloudFront drift is not treated as harmless or implicitly approved. The
plan does not include any active change to it, but the drift remains a hard
review blocker under the established deployment guard.

## 7. Drift inventory and comparison with 03C

The new plan reports the same 85 drift entries as the earlier plan:

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
| S3 buckets/objects | 7 |
| **Total** | **85** |

Compared with 03C:

- active action set: unchanged;
- create/update/delete/replacement counts: unchanged;
- drift count: unchanged at 85;
- provider context: corrected to AWS-only and reproducible;
- old plan hash: preserved and not reused;
- new plan hash: different and requires its own approval.

## 8. Remaining risks

1. The protected CloudFront drift has not been technically disposed.
2. The remaining 84 drift entries include shared API, IAM, Lambda, S3,
   CloudTrail, EventBridge and CloudWatch resources and require review before
   any Apply authorization.
3. Terraform emitted existing AWS provider deprecation warnings; these did not
   invalidate the plan but should be handled separately from this deployment.
4. The new plan has no Apply authorization. The earlier 03E/03H approvals do
   not apply to this artifact.

## 9. Decision and gate

**BLOCKED**

The provider alignment and replan are complete, but the plan is not cleared
for Apply because protected-resource drift remains unresolved. A future Apply
requires a separate review/disposition of the 85 drift entries and a new
explicit approval naming the exact new plan SHA-256.

**Apply was not executed. No AWS resource or Terraform state was mutated.**
