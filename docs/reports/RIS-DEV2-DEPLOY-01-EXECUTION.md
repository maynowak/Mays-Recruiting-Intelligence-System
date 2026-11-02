# RIS-DEV2-DEPLOY-01 — Controlled Foundation Deployment

**Result:** VALIDATE PASS / PLAN CREATED / APPLY BLOCKED BY PROTECTED-SCOPE GUARD

The `ris-dev2` foundation plan was created against the configured `ris-dev2`
backend and workspace. Apply was not executed because the plan creates a
CloudFront distribution and CloudFront OAC, while this deployment contract
explicitly requires STOP for any CloudFront create/update/delete/replace
action. No AWS resource mutation was performed.

## Execution matrix

| Phase | Result | Evidence |
|---|---|---|
| Validate | **PASS** | Account/region guard, state baseline, builder, Lambda artifacts, Terraform init/validate and regression tests |
| Plan | **PASS / GUARD BLOCKED** | Saved plan; 153 creates, 0 updates, 0 deletes, 0 replacements |
| Apply Gate | **BLOCKED** | New `module.health_public` CloudFront distribution and OAC are in the plan |
| Apply | **NOT RUN** | No `terraform apply` executed |
| Verify | **NOT RUN** | No apply occurred |
| Clean | **NOT RUN** | Plan retained outside repository for review; existing worktree preserved |
| Protected Infrastructure | **UNCHANGED / EXISTING SCOPE NOT MUTATED** | No Cognito, DNS or ACM actions; external protected resources not imported |

## Baseline and guards

| Item | Value |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| Commit | `4b259706c287fda1b138ac8e69edbd6c728c7e06` |
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

## Plan evidence

Plan artifact:

```text
C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-foundation.tfplan
```

SHA-256:

```text
B19456A4DEA1462FF6E58EEF8B696B87B8BF46841566341BE31145F3A0FC65DB
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

Protected-scope scan found:

```text
module.health_public.aws_cloudfront_distribution.health_public       create
module.health_public.aws_cloudfront_origin_access_control.health_public create
```

No `aws_cognito_*`, `aws_route53_*` or `aws_acm_*` actions were present. The
CloudFront resources appear to be new RIS-owned health presentation
infrastructure rather than the existing Jobsearch distribution, but the
deployment prompt's explicit CloudFront-create guard still requires STOP.

## Apply and verification

No apply approval was requested or assumed because the plan is not compliant
with the supplied protected-scope guard. Therefore no resources were created,
no post-apply smoke test was possible, and `RIS FOUNDATION: DEPLOYED` cannot
be reported.

## Required decision

Either:

1. explicitly revise the protected-scope policy to permit these two new,
   separately named RIS health CloudFront resources while retaining the
   existing Jobsearch CloudFront distribution unchanged; then review and
   approve this exact plan hash; or
2. change the Terraform foundation so health presentation does not create
   CloudFront/OAC, then regenerate and re-review the plan.

Until one of these decisions is made:

```text
RIS FOUNDATION: NOT DEPLOYED
SMOKE TESTS: NOT RUN
PROTECTED INFRASTRUCTURE: EXISTING RESOURCES UNCHANGED; PLAN BLOCKED
```
