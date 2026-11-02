# R08-G2C-4B — STATE & OWNERSHIP FORENSIC RECOVERY

**Status:** READ-ONLY FORENSICS COMPLETE / UPGRADE BLOCKED

## Scope and safety

- Scope: only the `ris-dev2` Modi test-account history.
- Account: `262370457690`.
- Region: `eu-central-1`.
- Profile: explicit `default`.
- Backend bucket: `ris-dev2-tf-state-dev`.
- State key: `env:/ris-dev2/dev/terraform.tfstate`.
- No state version was restored or written.
- No import, `state push`, `state rm`, backend change, plan, apply, destroy or
  resource mutation was performed.
- `ris-dev`, `mays-ris`, `ris-dev-pf` and other installations were not queried
  or changed.

## 1. State-history reconstruction

The state object exists and was read by version ID only for in-memory forensic
comparison. The latest object is not used as an upgrade source.

| State serial | Resource count | Interpretation |
|---:|---:|---|
| 1 | 0 | empty initial state |
| 2 | 68 | partial installation |
| 3 | 114 | expanded installation |
| 4 | 142 | expanded installation |
| 5 | 187 | near-full installation |
| 6 | 187 | near-full installation |
| 7 | 183 | changed installation |
| 8 | 184 | changed installation |
| 9 | 184 | changed installation |
| 10 | 33 | teardown in progress |
| 11 | 13 | teardown in progress |
| 12 | 6 | teardown in progress |
| 13 | 3 | teardown in progress |
| 14 | 1 | teardown in progress |
| 15 | 1 | teardown in progress |
| 16 | 0 | empty post-destroy state |
| 17 | 0 | current empty state |

All versions have a lineage marker, but lineage alone does not prove current
resource ownership. The current State serial is 17 with zero resources. The
active lock table is `ris-dev2-tf-lock`; it was not modified.

### Backend/workspace comparison

The observed state key matches the intended Terraform convention:

```text
workspace            = ris-dev2
backend key input    = dev/terraform.tfstate
workspace_key_prefix = env:
effective object     = env:/ris-dev2/dev/terraform.tfstate
```

There is no current managed-resource inventory to support an upgrade. The
historical non-empty versions are evidence of prior runs only; no version was
selected as a recovery source.

## 2. Terraform address inventory

The history contains the expected RIS address families, including:

```text
module.cognito.aws_cognito_user_pool.users
module.cognito.aws_cognito_user_pool_client.client
module.cognito.aws_cognito_user_pool_client.m2m
module.cognito.aws_cognito_user_pool_domain.domain
module.health_public.aws_cloudfront_distribution.health_public
module.health_public.aws_cloudfront_origin_access_control.health_public
module.cloudtrail.aws_s3_bucket.trail
module.dynamodb.aws_dynamodb_table.*
module.api.aws_apigatewayv2_*
module.lambda.aws_lambda_function.agent
module.sqs.aws_sqs_queue.*
module.mays_orders.*
```

The address set changes substantially between serials 9 and 10 and then
shrinks through serial 15. This is consistent with teardown activity, not a
safe upgrade baseline. No current state address can be mapped to a live
resource from serial 17.

## 3. Protected-resource mapping matrix

The table records historical IDs extracted from state versions and the result
of read-only lookup in account `262370457690`. `NOT_FOUND` is live evidence at
the time of this gate, not permission to recreate or delete anything.

| Terraform address | Historical state ID/reference | Live read-only result | Decision |
|---|---|---|---|
| `module.cognito.aws_cognito_user_pool.users` | `eu-central-1_uhvqKPR7G`, `ris-dev2-dev-users` | `ResourceNotFoundException` | **BLOCKED** |
| `module.mays_orders.module.cognito[0].aws_cognito_user_pool.users` | `eu-central-1_DL1WisfSp`, `ris-dev2-mays-orders-users` | `ResourceNotFoundException` | **BLOCKED** |
| `module.cognito.aws_cognito_user_pool_client.client` | `k1kj78uo08fa2gbamdp2vhlkr`, pool `eu-central-1_uhvqKPR7G` | `ResourceNotFoundException` | **BLOCKED** |
| `module.cognito.aws_cognito_user_pool_client.m2m` | `2bb0svk27daiaehnfqqjh068bb`, pool `eu-central-1_uhvqKPR7G` | `ResourceNotFoundException` | **BLOCKED** |
| `module.mays_orders.module.cognito[0].aws_cognito_user_pool_client.app` | `1bcbfo22rn9nh4olsc9j4dhk4k`, pool `eu-central-1_DL1WisfSp` | `ResourceNotFoundException` | **BLOCKED** |
| `module.cognito.aws_cognito_user_pool_domain.domain` | domain `ris-dev2-dev`, historical CloudFront `d5cxcejge1ybj.cloudfront.net` | empty `DomainDescription` | **BLOCKED** |
| `module.health_public.aws_cloudfront_distribution.health_public` | `EIGB1XZJTNSGK`, `d15r78axba0a1z.cloudfront.net` | `NoSuchDistribution` | **BLOCKED** |
| `module.health_public.aws_cloudfront_origin_access_control.health_public` | `E3N0SKHULOX36P`, name `ris-dev2-dev-health-oac` | `NoSuchOriginAccessControl` | **BLOCKED** |
| ACM certificate resource | no `aws_acm_certificate` address in retained history | no state-owned certificate reference | **BLOCKED** |
| Route 53 record resource | no `aws_route53_record` address in retained history | no state-owned DNS reference | **BLOCKED** |

The historical reports contain additional IDs from other `ris-dev2` runs,
including a different Cognito pool. Those IDs are not a valid substitute for
the current state and reinforce that the protected baseline is ambiguous.

## 4. Ownership conclusion

The evidence supports this conclusion:

1. `ris-dev2` was deployed in account `262370457690` in earlier runs.
2. The state history records a full installation followed by staged teardown.
3. The current state is empty and the protected IDs extracted from historical
   versions no longer resolve to live resources.
4. The domain response is not sufficient to prove a live pool/domain mapping.
5. ACM and DNS are not represented as Terraform-owned resources in the
   retained state history.
6. Therefore there is no authoritative existing installation to upgrade from
   this state path, and no safe basis to create a new `ris-dev2` installation
   under the upgrade name.

This does not authorize cleanup of historical S3 object versions, backend
objects, lock records or any AWS resource.

## 5. Upgrade release criteria

An upgrade plan may be proposed only after all criteria below pass:

- account/region/profile guard passes;
- exact `ris-dev2` state object and lineage are confirmed authoritative;
- current state has the complete expected resource inventory;
- every protected Cognito pool/client/domain ID has one live match;
- every protected CloudFront distribution/OAC ID has one live match;
- ACM certificate and DNS mappings are explicitly identified and approved;
- no historical competing baseline remains unresolved;
- DynamoDB PITR/backups, S3 versioning/Object Lock/denies, IAM and CloudTrail
  evidence are collected;
- a plan is generated without `-target`, `-replace`, import or state surgery;
- the plan has zero protected-resource deletes/replacements and no foreign
  project changes;
- all activation flags remain `false`;
- the complete plan and change list receive separate approval.

Until then, the correct action is state/ownership recovery planning, not a
new deployment and not a plan against the empty state.

## Decision

**State reconstruction:** COMPLETE as read-only forensic analysis.

**Ownership resolution:** **BLOCKED.** Current state is empty; historical
protected IDs are not live and the domain/ACM/DNS mapping is incomplete.

**Controlled Terraform plan:** **NOT PROPOSED / NOT RUN.**

**Upgrade/apply:** **NOT AUTHORIZED.**

## Evidence handling

Only non-secret metadata, resource addresses, IDs/ARNs and status codes are
recorded here. State bodies, credentials and sensitive resource attributes were
not committed.
