# RIS-R08-G2C-7D-2 — Terraform Plan Input Contract

**Status:** CROSS-ACCOUNT CONTRACT VERIFIED / OFFLINE VALIDATION PASS /
OWNER-SIDE LIVE CONFIRMATION REQUIRED / TERRAFORM PLAN NOT AUTHORIZED

## State decision

The current empty serial-17 State cannot be approved as an in-place upgrade
baseline: lineage-to-resource ownership and protected-resource associations are
not proven. The preferred construction is a separately approved isolated
bootstrap State. G2C-7D-2 does not initialize it, create a workspace, write a
backend object, migrate, import or restore any historical version.

The historical tuple remains protected evidence:

```text
profile=default
account=262370457690
region=eu-central-1
project=ris-dev2
environment=dev
workspace=ris-dev2
bucket=ris-dev2-tf-state-dev
lock_table=ris-dev2-tf-lock
key=env:/ris-dev2/dev/terraform.tfstate
```

## Intended plan inputs

The intended isolated foundation uses `identity_mode=external`. The external
identity account is now an explicit separate input from the RIS deployment
account. Current `ris-dev` references are usable as `RIS_DEV_CONFIG_VERIFIED`
protected inputs, but still require authorized owner-side live confirmation
before plan approval.
`orders_lifecycle=disabled` is the preferred candidate because no current
ris-dev2 Orders/API/runtime resources were found and the RIS Terraform core has
no required Orders reader dependency. This remains subject to functional owner
confirmation; it must not silently change to `managed`. If Orders functionality
is required, use `external` with independently verified table/queue ARNs and
URLs.

## Plan-input evidence matrix

| Field | Source | Verified? | Sensitive? | Plan status |
|---|---|---:|---:|---|
| AWS account | STS, profile `default` | YES | No | ready |
| AWS region | session/STS contract | YES | No | ready |
| AWS principal | STS | YES | No | ready |
| Backend bucket/key | G2C-5/7D-1 read-only inventory | YES | No | protected, no write |
| Lock table | DynamoDB read-only inventory | YES | No | protected, no write |
| Workspace | bootstrap contract | YES as declaration | No | approval required |
| Identity mode | Terraform/G2C-7C contract | YES: external supported | No | explicit input required |
| Cognito pool ID/ARN | `ris-dev` deployment/configuration evidence | CONFIG VERIFIED; owner-side live check required | No | contract ready; plan gate pending |
| Cognito issuer | `ris-dev` configuration + regional issuer contract | CONFIG VERIFIED; owner-side live check required | No | contract ready; plan gate pending |
| Human/M2M clients | `ris-dev` deployment/configuration evidence | CONFIG VERIFIED; owner-side live check required | No | contract ready; plan gate pending |
| Orders lifecycle | Terraform contract | YES: disabled candidate | No | owner confirmation required |
| Orders external refs | not required for disabled | N/A | No | no dummy refs |
| RIS resource names | Terraform modules/`ris-dev2` prefix | YES structurally | No | collision check at later gate |
| IAM ARNs | Terraform module outputs/policies | YES structurally | No | review actual plan |
| Lambda environment | Terraform source | YES; execution flags false | No | safe by default |
| Privacy/erasure flags | Lambda Terraform environment | YES: literal false | No | must remain false |
| Protected CloudFront/DNS/ACM | live discovery | external/UNKNOWN | No | no ownership/actions |

## Expected owned resource boundary

Subject to a later approved plan, RIS may create only its own foundation:
API Gateway and authorizers, Lambda/runtime roles, DynamoDB tables, SQS,
RIS-owned S3/document buckets, monitoring, health and audit resources. Exact
creates require the actual saved plan.

The following are prohibited from the plan:

- Cognito pool, clients, domains, users or OAuth updates in external mode;
- CloudFront, OAC, DNS, ACM or TLS resources;
- managed Orders resources when lifecycle is `disabled` or `external`;
- resources or state addresses belonging to `ris-dev`, `ris-dev-pf`,
  `mays-ris` or foreign Orders installations;
- state migration, import, replacement of protected resources or deletion of
  historical backend objects.

## Offline checks

- Terraform `init -backend=false`: PASS.
- Terraform `init -backend=false` and `validate`: BLOCKED by the preserved
  deletion of generated `terraform/modules/mays_orders/variables.tf`; this
  leaves four root module arguments without declarations. The deletion was
  not restored or regenerated in this contract-only task.
- Terraform `fmt -check`: PASS.
- G2C-7D static plan-input tests: **7 passed**.
- G2C-7C bootstrap tests: **5 passed**.
- G2C-6 identity protection tests: **6 passed**.
- No remote Terraform plan was executed.

## G2C-7D-3 prerequisites

1. Obtain authoritative current Cognito pool, human/M2M client and issuer
   references from the owning account/team without changing AWS profile under
   this workflow.
2. Verify the external OAuth/domain contract and CloudFront/OAC ownership.
3. Confirm that Orders is not required, or provide external Orders references.
4. Approve the isolated State/backend bootstrap tuple and recovery owner.
5. Build Lambda artifacts and generated Orders module locally as required.
6. Run one remote plan only after separate authorization; save it outside Git,
   calculate SHA-256, and review every action.

## STOP and recovery rules

Stop on account/profile/region mismatch, missing external identity values,
protected-resource changes, foreign state addresses, unexpected Deletes or
Replacements, implicit Cognito/Orders creation, state drift, lock/recovery
uncertainty or any privacy flag becoming true. Do not repair by importing,
restoring historical State, deleting locks or applying a partial plan.

**Plan preparation:** READY after owner-side read-only identity confirmation.
**Remote plan:** NOT AUTHORIZED. **Apply:** NOT AUTHORIZED.
