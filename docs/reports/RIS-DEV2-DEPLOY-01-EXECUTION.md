# RIS-DEV2-DEPLOY-01 — Controlled Foundation Deployment

**Result:** R1 PLAN GUARD PASS / PLAN READY FOR EXPLICIT APPLY APPROVAL

The initial plan was blocked by the original blanket CloudFront guard. R1
introduces a narrow, test-covered exception for exactly the two isolated
`ris-dev2` health resources. The revised plan was created against the same
configured backend and workspace. It is ready for explicit approval of this
exact saved plan; apply remains unexecuted.

## Execution matrix

| Phase | Result | Evidence |
|---|---|---|
| Validate | **PASS** | Account/region guard, state baseline, builder, Lambda artifacts, Terraform init/validate and regression tests |
| Plan | **PASS** | R1 saved plan; 153 creates, 0 updates, 0 deletes, 0 replacements |
| Apply Gate | **READY / EXPLICIT APPROVAL REQUIRED** | Only the two R1 allowlisted Health CloudFront creates are present |
| Apply | **NOT RUN** | No `terraform apply` executed |
| Verify | **NOT RUN** | No apply occurred |
| Clean | **NOT RUN** | Plan retained outside repository for review; existing worktree preserved |
| Protected Infrastructure | **UNCHANGED / EXISTING SCOPE NOT MUTATED** | No Cognito, DNS or ACM actions; existing Jobsearch CloudFront is not addressed |

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
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Resources in state before plan | `0` |
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
- Relevant G2C identity/bootstrap/contract regressions: **19 passed**.
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

No apply approval was assumed. Therefore no resources were created, no
post-apply smoke test was possible, and `RIS FOUNDATION: DEPLOYED` cannot yet
be reported.

## Apply gate

The plan is now ready for explicit approval. Remaining risks are the normal
cost and propagation time of a new CloudFront distribution, Lambda/API/IAM
foundation creation, and the requirement to use the exact saved plan without
replanning. No existing protected identity or domain resource is included.

Until the concrete plan hash is approved:

```text
RIS FOUNDATION: NOT DEPLOYED
SMOKE TESTS: NOT RUN
PROTECTED INFRASTRUCTURE: EXISTING RESOURCES UNCHANGED; APPLY PENDING
```
