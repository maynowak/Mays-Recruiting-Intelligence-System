# R08-E2E-G2C-1 — DEPLOYMENT IDENTITY RECONCILIATION

**Status:** IDENTITY ANALYSIS COMPLETE / AWS READ-ONLY BLOCKED

## Baseline and boundary

- Branch: `feature/ris-partner-profile-persistence-v1`.
- Starting HEAD: `8f75a76b77453c0b33408dcc5f94e2f8cf0ee469`.
- G2C-0 was reviewed; its identity ambiguity is resolved locally as a source
  precedence issue, not as live AWS evidence.
- No AWS/STS calls, remote-state reads, Terraform plan/apply/destroy,
  installation, deployment or resource rename was performed.
- No source file, `.tfvars`, Jobsearch or Orders file was changed. The 39
  pre-existing untracked files were preserved.

## Root cause

`ris-dev` and `mays-ris` are not two spellings for one computed identity.
They are two distinct `project_name` values. The executable identity mapping is
verbatim:

```text
workspace = project_name
resource prefix = project_name-environment
state path = env:/project_name/environment/terraform.tfstate
```

Consequently, substituting one for the other selects a different Terraform
workspace, state object and resource family. A rename is a delete/create
rebuild, not an in-place rename.

The conflict was introduced by source drift:

1. Terraform `variables.tf` defaults `project_name` to `mays-ris`.
2. `installer.ris` defaults both its context and CLI argument to `mays-ris`.
3. `installer/terraform_runner.py` and tests use `mays-ris` as the historical
   default/example; the lock table default is also named `mays-ris-tf-lock`.
4. `terraform/main.tf` uses `mays-ris` only as the `Maker` default tag. That
   tag is not the deployment identity, but it reinforces the legacy wording.
5. Current deployment context and `AGENTS.md` identify `ris-dev` as the
   permanent development installation and explicitly classify `mays-ris` as
   legacy/destroyed.
6. Runtime, API, test and project-overlay references contain `ris-dev` names,
   while older deployment/history documents contain `mays-ris` names and
   examples.

This is therefore a code/default/documentation reconciliation problem. It
cannot be resolved by assuming that either state or resource family exists in
AWS.

## Deterministic comparison

Both rows use the repository region/environment unless explicitly overridden;
only the project identity changes.

| Dimension | Recommended target `ris-dev` | Legacy/default `mays-ris` |
|---|---|---|
| Terraform variable | `project_name=ris-dev` | `project_name=mays-ris` |
| Environment | `dev` | `dev` |
| Provider region | `eu-central-1` | `eu-central-1` |
| Workspace | `ris-dev` | `mays-ris` |
| Effective state key | `env:/ris-dev/dev/terraform.tfstate` | `env:/mays-ris/dev/terraform.tfstate` |
| Documented state bucket | `mays-ris-tf-state-dev` | not independently established |
| Lock table | `mays-ris-tf-lock` (static/default) | `mays-ris-tf-lock` (static/default) |
| RIS resource prefix | `ris-dev-dev-*` | `mays-ris-dev-*` |
| Orders component prefix | `ris-dev-mays-orders-*` | `mays-ris-mays-orders-*` |
| Installer config overlay | `project-configs/ris-dev.json` if present | `project-configs/mays-ris.json` if present |

The shared lock-table name does not make the deployments identical. It makes
correct state-path selection and lock inspection more important. Backend
bucket, region and lock-table values must be supplied explicitly before
Terraform initialization; defaults are not live evidence.

## Source trace

### Terraform

- `terraform/variables.tf`: defaults are `mays-ris`, `dev`, `eu-central-1`.
- `terraform/main.tf`: provider uses `var.aws_region`; resource modules receive
  `project_name` and `environment`; `local.prefix` is
  `${var.project_name}-${var.environment}`.
- `terraform/main.tf`: backend is partial, with static key
  `terraform.tfstate`, encryption and lock table `mays-ris-tf-lock`.
- No Terraform file maps `mays-ris` to `ris-dev`.

### Installer

- `RisInstallContext` defaults to `mays-ris`/`dev`/`eu-central-1`.
- `build_parser()` defaults `--project-name` to `mays-ris`.
- `workspace_for_project()` returns the supplied project name unchanged.
- `backend_config()` uses key `{environment}/terraform.tfstate` and
  `workspace_key_prefix=env:`. With workspace `project_name`, Terraform's
  effective path is `env:/{project_name}/{environment}/terraform.tfstate`.
- `terraform_vars()` makes the explicit context identity override ordinary
  extra variables. A project overlay is loaded only from the exact filename
  `installer/project-configs/{project_name}.json` and must declare the same
  `project_name`; it cannot alias identities.
- Backend bootstrap derives names from `project_name`/`environment` and refuses
  to adopt a bucket with a foreign `Project` tag.

### Documentation and tests

- `docs/architecture/DEPLOYMENT-CONTEXT.md` declares permanent dev as
  `ris-dev`, workspace `ris-dev`, and state key
  `env:/ris-dev/dev/terraform.tfstate`; it lists `mays-ris` as destroyed
  legacy. Per that document, changes require approval, so it was not edited.
- `AGENTS.md` independently identifies the same `ris-dev` target and warns
  against cross-wiring foreign families.
- `docs/architecture/SYSTEM-ARCHITECTURE.md`, API/runtime docs and project
  configuration tests contain current `ris-dev-*` runtime names, but some
  older architecture/auth text and installer documentation still say
  `mays-ris`.
- Tests deliberately cover both names as isolated test identities. Test data,
  historical audit logs and old deployment reports are not current AWS
  evidence.

## Recommended target identity

For the permanent development deployment, use exactly:

```text
project_name = ris-dev
environment  = dev
aws_region   = eu-central-1
workspace    = ris-dev
state key    = env:/ris-dev/dev/terraform.tfstate
```

Use the documented state bucket `mays-ris-tf-state-dev` and lock table
`mays-ris-tf-lock` only after read-only AWS verification confirms account,
ownership, region, tags, object path and lock status. The `mays-ris` defaults
must not be used implicitly for this target. No default was changed in this
gate because changing executable defaults could redirect future commands and
would be unsafe before live reconciliation.

## Migration and collision risks

1. Running with `mays-ris` against a `ris-dev` state creates a separate
   identity and can propose a second stack or fail on existing names.
2. Running with `ris-dev` against a `mays-ris` state can orphan, replace or
   destroy unrelated resources from Terraform's perspective.
3. Changing only the workspace or only the backend key is insufficient; the
   project variable, workspace, state object, resource prefix, overlay and
   Orders component identity must agree.
4. A state migration from any legacy path requires an approved, separately
   evidenced procedure. It is not a documentation correction and must not be
   inferred from historical reports.
5. API, Lambda, Cognito and resource IDs are installation-specific; names in
   prose cannot substitute for live outputs/state evidence.
6. Any legacy `mays-ris` resource found live must be classified by owner/tag,
   state association and runtime use before a plan. It must not be adopted or
   deleted automatically.

## Required AWS read-only evidence

Before G2C-2 can proceed, an explicitly authorized operator must verify:

1. `sts get-caller-identity` matches the intended account/principal and
   configuration is `eu-central-1`.
2. The candidate state bucket exists, is owned by the RIS project, is in the
   expected region, and has the expected encryption/versioning controls.
3. Both candidate object paths are checked read-only, including exact object
   existence, metadata and version history; state contents remain sensitive.
4. `mays-ris-tf-lock` exists in the same intended account/region and lock
   records for both candidate paths are inventoried without deletion.
5. Resource names/tags are inventoried for both `ris-dev-*` and `mays-ris-*`
   families across DynamoDB, Lambda, S3, Cognito, API Gateway, SQS, IAM and
   CloudTrail. No current existence is assumed from this report.
6. Current Lambda/API/Cognito outputs and runtime configuration are matched to
   exactly one project identity; foreign families and shared resources remain
   untouched.

## G2C-2 readiness decision

**G2C-2 AWS READ-ONLY Readiness: BLOCKED.** The local target is resolved to
`ris-dev`, but live account, backend, state-object, lock and resource evidence
has not been collected. The next gate may run only the approved read-only
matrix from G2C-0 using the exact `ris-dev` tuple. No Terraform plan or
deployment is authorized by this report.

## Commit intent

```text
docs(ris): reconcile deployment identity before aws preflight
```
