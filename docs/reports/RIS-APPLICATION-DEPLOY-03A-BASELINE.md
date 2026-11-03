# RIS-APPLICATION-DEPLOY-03A — Baseline & Checkout Guard

**Status:** PASS for target/state identity; protected cross-account Cognito
details remain read-limited

## Checkout guard

| Check | Result |
|---|---|
| Branch | `feature/ris-application-persistence-v1` |
| HEAD | `f659a79fca812c2c8b9b3074d14898675d5d8c9a` |
| Expected checkpoint | matched `f659a79` |
| Worktree | clean; no untracked files or local changes |
| Jobsearch connection | none; out of scope |

## AWS identity and backend

Read-only boto3 verification used profile `default` and region
`eu-central-1`:

- Account: `262370457690`
- Principal: `arn:aws:iam::262370457690:user/devnemo`
- State bucket: `ris-dev2-tf-state-dev`
- State key: `env:/ris-dev2/dev/terraform.tfstate`
- Lock table: `ris-dev2-tf-lock` (`ACTIVE`)
- State lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082` (exact match)
- State serial: `23`
- Terraform state version: `1.17.0`
- State object size: `468977` bytes
- State SHA-256: `2476b37a32bfb1208ae38d3b932a6a4be569fbff6673538eeb1ee35f30a32840`

The serial is recorded, not forced. No import, migration, state push or
backend mutation was performed.

## Live baseline

The state contains 160 resource entries. Read-only live checks found:

- API Gateway HTTP API `ris-dev2-dev-api` / `8apxb6fgne`, `$default` stage,
  25 existing routes and two existing JWT authorizers.
- Lambda `ris-dev2-dev-agent`, Python 3.14, 128 MB, 30 seconds; current
  environment contains the existing profile, privacy, erasure and work-item
  bindings.
- 16 RIS DynamoDB tables are present, including the existing erasure,
  privacy, partner and work-item tables. `ris-dev2-dev-applications` is not
  present.
- Five RIS SQS queues are present: work queue, DLQ, ATS, CV and match.
- Existing health CloudFront distribution `E1IZKHFPZ5X7SN` is `Deployed` and
  enabled; its OAC and distribution remain outside the ApplicationV1 scope.
- Existing state output records `identity_mode=external` and
  `orders_lifecycle=disabled`; both are preserved as hard constraints.

ApplicationV1 is absent from the live baseline: no `applications` DynamoDB
table and no `/v1/partner/me/applications` API routes were found.

## Protected infrastructure notes

The state references Cognito pool `eu-central-1_ojbmoiYGM` in account
`240571105849` as an external identity resource. A read-only `DescribeUserPool`
from the deployment account returned `ResourceNotFoundException`, which is
consistent with the cross-account ownership boundary. No Cognito mutation was
attempted. The plan guard must treat the external pool, clients, issuer and
authorizer configuration as protected and reject any attempted change.

All erasure/privacy execution flags observed in the live Lambda environment
are disabled, including operation execution, write freeze, S3 execution,
quiescence, upload cutover and receipt journaling. No flag was changed.

## Authorization boundary

This phase authorized only identity, backend, state and live-baseline reads.
No Terraform plan or apply has been executed yet. The next phase is offline
validation; the saved remote plan remains subject to the later approval gate.
