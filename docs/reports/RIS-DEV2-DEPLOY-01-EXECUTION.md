# RIS-DEV2-DEPLOY-01 — Controlled Foundation Deployment

**Result:** RIS FOUNDATION DEPLOYED / SMOKE TESTS PASS / PROTECTED INFRASTRUCTURE UNCHANGED

The initial plan was blocked by the original blanket CloudFront guard. R1
introduces a narrow, test-covered exception for exactly the two isolated
`ris-dev2` health resources. The revised plan was created against the same
configured backend and workspace. The plan was explicitly approved and applied
without recalculation; the foundation is deployed and verified.

## Execution matrix

| Phase | Result | Evidence |
|---|---|---|
| Validate | **PASS** | Account/region guard, state baseline, builder, Lambda artifacts, Terraform init/validate and regression tests |
| Plan | **PASS** | R1 saved plan; 153 creates, 0 updates, 0 deletes, 0 replacements |
| Apply Gate | **GO** | Explicit approval received for the exact plan hash |
| Apply | **PASS** | `153 added, 0 changed, 0 destroyed`; exit 0 |
| Verify | **PASS** | State, AWS resources, authorizers, Lambda and health smoke tests verified |
| Clean | **PASS** | No repository cleanup; pre-existing worktree preserved |
| Protected Infrastructure | **UNCHANGED** | No Cognito, DNS or ACM actions; existing Jobsearch CloudFront not addressed |

## Baseline and guards

| Item | Value |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| Initial deployment commit | `4b259706c287fda1b138ac8e69edbd6c728c7e06` |
| R1 implementation commit | `390632ef99e9081d752c217f7ee578646110b27e` |
| AWS profile | `default` |
| AWS account | `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| Backend bucket | `ris-dev2-tf-state-dev` |
| Backend key | `env:/ris-dev2/dev/terraform.tfstate` |
| Lock table | `ris-dev2-tf-lock` |
| State serial before plan | `17` |
| State serial after apply | `23` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Resources in state before plan | `0` |
| Resources in state after apply | `160` |
| Terraform | `1.17.0` |

The default-profile STS guard matched account `262370457690`, region
`eu-central-1`, and principal `arn:aws:iam::262370457690:user/devnemo`.

## Configuration used for the plan

- `identity_mode = external`
- External Cognito account: `240571105849`
- Pool: `eu-central-1_ojbmoiYGM`
- Issuer: `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM`
- Human client: `7ldhihlpdgsgcl3puvu4oi7ksv`
- M2M client: `82ji073smu1b3fsvj96sonso`
- `orders_lifecycle = disabled`

The Cognito module was disabled by external mode. The plan contains no
Cognito pool, client, domain, DNS or ACM resource actions. The protected
`ris-dev` identity remains reference-only.

## Local validation

- Pinned Orders builder: **PASS** in the isolated deployment workspace after
  building its required Lambda artifact.
- RIS Lambda bundles (`--bundle all`): **PASS**.
- Terraform `init -backend=false`: **PASS**.
- Terraform `validate`: **PASS**, with existing provider deprecation warnings.
- Relevant G2C identity/bootstrap/contract/plan-guard regressions: **24 passed**.
- Python installer/builder/backend/runner compilation: **PASS**.
- `terraform fmt -check` for `ris-dev2.tfvars`: **PASS**.

The original checkout's 39 untracked files and the pre-existing deletion of
`terraform/modules/mays_orders/variables.tf` were not overwritten. Generated
module files and deployment artifacts were created only in the isolated
temporary deployment workspace.

## R1 Plan Guard

The installer now permits only this exact set when the project is `ris-dev2`
and environment is `dev`:

```text
module.health_public.aws_cloudfront_distribution.health_public       ["create"]
module.health_public.aws_cloudfront_origin_access_control.health_public ["create"]
```

The guard rejects every other CloudFront address or action, including update,
delete and replacement. Cognito, Route53 and ACM resource actions remain
strictly forbidden. Regression coverage includes wrong addresses, wrong
actions, wrong project, and protected Cognito/DNS/ACM types.

The Health module is isolated by names and tags:

- S3 origin bucket: `ris-dev2-dev-health-public`
- OAC: `ris-dev2-dev-health-oac`
- origin ID: `S3-health-public`
- tags: `Project=ris-dev2`, `Environment=dev`
- no aliases, no custom ACM certificate, no Route53 record
- CloudFront default certificate only; S3 public access is blocked and OAC
  uses SigV4
- exactly two CloudFront/OAC resources appear in the plan

## R1 Plan evidence

Plan artifact:

```text
C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-foundation-r1.tfplan
```

SHA-256:

```text
FC30B406F16DB860203539D079730B8B9A27A4A359505B8430AAF0A9F40F431D
```

Machine-readable plan JSON was generated outside the repository. Action
summary:

```text
create: 153
update: 0
delete: 0
replace: 0
read: 3
```

CloudFront/OAC scan found exactly:

```text
module.health_public.aws_cloudfront_distribution.health_public       create
module.health_public.aws_cloudfront_origin_access_control.health_public create
```

No `aws_cognito_*`, `aws_route53_*` or `aws_acm_*` actions were present. No
existing CloudFront distribution or OAC is referenced by the plan. The two
new resources are the explicitly approved isolated Health exception.

## Apply and verification

The explicit approval was received for SHA-256
`FC30B406F16DB860203539D079730B8B9A27A4A359505B8430AAF0A9F40F431D`.
The same saved plan was applied; no replacement plan was generated.

Apply result:

```text
Apply complete! Resources: 153 added, 0 changed, 0 destroyed.
exit: 0
```

Verification evidence:

- AWS identity: account `262370457690`, principal
  `arn:aws:iam::262370457690:user/devnemo`, region `eu-central-1`.
- API: `8apxb6fgne`, endpoint
  `https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com`.
- Human JWT authorizer: external issuer, audience
  `7ldhihlpdgsgcl3puvu4oi7ksv`.
- M2M JWT authorizer: external issuer, audience
  `82ji073smu1b3fsvj96sonso`; M2M route present.
- Lambda `ris-dev2-dev-agent`: Python 3.14, `Active`, last update
  `Successful`.
- DynamoDB: 17 `ris-dev2` application tables verified; the separate backend
  lock table is excluded from that application count.
- SQS: five expected queues verified (work, DLQ, CV, ATS, match).
- Health CloudFront: distribution `E1IZKHFPZ5X7SN`, domain
  `d3axlsioawbq92.cloudfront.net`, origin `S3-health-public`, aliases empty,
  default CloudFront certificate, tags `Project=ris-dev2` and
  `Environment=dev`.
- Health OAC: `E30BLRTMAWVYN1`, name `ris-dev2-dev-health-oac`, SigV4 and
  `SigningBehavior=always`.
- Public health smoke test: HTTP **200**.
- Protected API health smoke without JWT: HTTP **401 Unauthorized**, as
  required by the API contract.
- Target-account Cognito pools named `ris-dev2`: **none**; external Cognito
  remained reference-only.
- Privacy/erasure/freeze/cutover execution flags: all **false**.

## Apply gate

Remaining operational risks are the normal cost and propagation time of the
new CloudFront distribution and ongoing Lambda/API/IAM operation. No existing
protected identity or domain resource was included or changed.

```text
RIS FOUNDATION: DEPLOYED
SMOKE TESTS: PASS
PROTECTED INFRASTRUCTURE: UNCHANGED
```
