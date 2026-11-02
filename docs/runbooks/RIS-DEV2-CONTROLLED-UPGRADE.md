# RIS-DEV2 Controlled Upgrade Runbook

**Status:** Template only; current `ris-dev2` execution is blocked before plan.

## Identity guard

Before every stage, verify explicitly:

```text
profile  = default
account  = 262370457690
region   = eu-central-1
project  = ris-dev2
environment = dev
workspace = ris-dev2
state = env:/ris-dev2/dev/terraform.tfstate
```

Abort on any mismatch. Do not use another project, backend or state path.

## Stage 0 — State and protected baseline

1. Confirm the current State is authoritative, non-empty and complete.
2. Confirm lock table status and backup/recovery posture.
3. Capture protected Cognito, CloudFront, OAC, ACM and DNS IDs/ARNs.
4. Match every ID to live AWS and to exactly one state address.
5. Stop if any mapping is missing, conflicting, deleted or externally owned.

The current rehearsal fails at this stage: serial 17 has zero resources and the
historical IDs are not live.

## Stage 1 — Offline construction

1. Build Lambda bundles using the repository package contract.
2. Run `terraform fmt -check`, `terraform validate` and the approved local
   regression selections without backend access.
3. Keep privacy receipt, freeze, erasure execution, upload ledger and cutover
   flags false.
4. Resolve installer/Builder pin and fixture failures; do not hide them with
   skips.

## Stage 2 — Read-only AWS preflight

Use only the approved profile/account. Read state metadata, resource
descriptions, schemas, PITR/backups, S3 controls, IAM, API, Cognito,
CloudFront/DNS/ACM, Orders dependencies and CloudTrail. Do not invoke Lambda or
write test data.

## Stage 3 — Controlled plan

Only after Stage 0 and Stage 2 pass:

1. Initialize the verified existing backend/workspace.
2. Produce one saved plan outside Git.
3. Review every create/update/delete/replace.
4. Require zero protected-resource changes, no foreign project changes, no
   implicit Cognito/Orders installation, no state migration and no activation
   flag changes.
5. Record plan hash and complete change list for separate approval.

Never use `-target`, `-replace`, `state rm`, import or manual state edits to
make a plan appear safe.

## Stage 4 — Apply and acceptance (separate authorization)

Apply only the approved plan after repeating the identity and protected-ID
guards. Then verify pool/client/user preservation, CloudFront/OAC/DNS/ACM
identity, API/Lambda/DynamoDB/SQS/Orders/monitoring smoke behavior and CloudTrail
evidence with synthetic data only. Do not activate productive erasure,
receipt, freeze, upload cutover or S3 execution.

Any protected-ID change, unexpected delete/replace, state drift or runtime
error is an immediate stop; do not destroy/recreate or repair state ad hoc.

## Recovery rules

- Historical state versions are evidence, not automatic restore inputs.
- State recovery, import and migration require separate ownership evidence and
  authorization.
- Keep `ris-dev2`, `ris-dev-pf` and `ris-dev` in separate state/workspace and
  plan artifacts.
- Never commit state bodies, plan binaries, credentials or Lambda environment
  values.
