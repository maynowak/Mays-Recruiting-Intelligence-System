# RIS-R08-G2C-5 — RIS-DEV HANDOFF

## Handoff decision

No `ris-dev2` upgrade result is transferable to `ris-dev`. The `ris-dev2`
state is empty and its historical ownership is unresolved. `ris-dev` requires
an independent account/resource/state baseline before any operation.

## Required `ris-dev` baseline

Use the separately documented permanent identity only after a new guard:

```text
project   = ris-dev
environment = dev
region    = eu-central-1
workspace = ris-dev
state     = env:/ris-dev/dev/terraform.tfstate
```

The baseline must independently identify the current Cognito pool and clients,
Jobsearch/API domains, CloudFront distributions/OAC, ACM/DNS, Lambda/API,
DynamoDB/SQS, Orders dependencies, IAM and CloudTrail. Do not copy IDs from
`ris-dev2`, `mays-ris` or `ris-dev-pf`.

## Transferable construction lessons

- Project name, workspace and state key must be one explicit tuple.
- An empty or teardown state is not an upgrade baseline.
- Protected identity resources require ID-level evidence before planning.
- External Jobsearch identity must be an explicit Terraform mode, not an
  accidental consequence of skipping modules.
- Mays-Orders lifecycle must be independently enabled and output-bound.
- Privacy/erasure resources may be wired but execution remains disabled.
- Plans and state bodies stay outside Git; approval covers an exact plan hash.

## Required transformation/recovery work

Before a `ris-dev` plan, decide separately whether:

1. authoritative `ris-dev` state can be proven and in-place upgrade is safe; or
2. a reviewed external-identity foundation design is implemented for a new,
   explicitly isolated test project.

Do not migrate data, import resources, recreate Cognito, change DNS/ACM or
rebind CloudFront without a dedicated ownership and recovery procedure.

## Acceptance checklist

- [ ] New account/profile/region guard passes.
- [ ] Current `ris-dev` state serial/resource inventory is complete.
- [ ] Cognito pool, clients and users preserved.
- [ ] Jobsearch domain/CloudFront/OAC/DNS/ACM preserved.
- [ ] API/Lambda/DynamoDB/SQS/Orders smoke tests pass with synthetic data.
- [ ] IAM/PITR/S3/CloudTrail evidence reviewed.
- [ ] All privacy/erasure/cutover flags remain false.
- [ ] Exact plan hash approved before apply.
- [ ] Rollback/recovery owner and procedure assigned.

## Current handoff status

**RIS-DEV handoff: BLOCKED pending independent baseline.** The current work
provides construction and gate criteria only; it does not authorize a `ris-dev`
plan or deployment.
