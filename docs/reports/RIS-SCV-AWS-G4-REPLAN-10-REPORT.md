# RIS-SCV-AWS-G4-REPLAN-10

**Status:** `RIS-SCV-AWS-G4-REPLAN-10 — UNSAFE PLAN / DO NOT APPLY`

**Date:** 2026-11-14

**Authorization:** Release Owner authorized one controlled RC2 G4 replan for `ris-dev` only.

**Execution:** operator `mayaws`; window approximately `2026-11-14T08:55Z–08:58Z`.

**Apply:** NOT AUTHORIZED, NOT EXECUTED.

## 1. Git baselines

| Ref | HEAD | State |
|---|---|---|
| RIS `origin/main` | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` | unchanged |
| RIS RC1 | `4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1` | unchanged |
| RC2 | `release/structured-cv-rc2-reconciled @ 6eeab5d37edc0eb8dabf284f0c5e9dc173b82751` | planned |
| Old rejected plan | `36632ab510cbef32030e111d82465aa7b2f8b65b2913181d107aa9021b79a57b` | preserved, DO NOT APPLY |

RC2 was not modified; no main merge or branch rewrite occurred.

## 2. AWS identity and target

| Field | Verified value |
|---|---|
| AWS account | `240571105849` |
| Caller ARN | `arn:aws:iam::240571105849:user/Mayaws` |
| Profile | `mayaws` |
| Region | `eu-central-1` |
| Environment | `ris-dev` |
| Workspace | `ris-dev` |
| Backend bucket | `mays-ris-tf-state-dev` |
| Effective state key | `env:/ris-dev/dev/terraform.tfstate` |
| Lock table | `mays-ris-tf-lock` |

`ris-dev2` was not contacted. No default-profile fallback occurred.

## 3. State verification

| Field | Before plan | After plan |
|---|---|---|
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` | unchanged |
| Serial | `61` | `61` |
| Resources | 250 | 250 |
| Instances | 291 | 291 |
| ETag | `8b41ea0825f396af01fb2721a88debb4` | unchanged |
| Object LastModified | `2026-11-09T11:35:42Z` | unchanged |

No state write, import, repair or workspace creation occurred. The lock table contained four
digest-cache rows and **no active LockID** after the plan.

## 4. Protected inputs

Protected file: `/tmp/opencode/ris-scv-rc2-09/protected/ris-dev.tfvars.json`, mode `0600`.

| Input | Verified |
|---|---|
| Allowlist | present; value withheld from Git, report and logs |
| `CONSENT_NOTICE_STATE_ENFORCED` | false, matches live |
| `CV_STORAGE_CONSENT_ENFORCED` | true, matches live |
| `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | true, matches live |
| Orders boundary | set |
| `STRUCTURED_CV_PROFILE_ENABLED` | false |

The protected file's four consent controls match the live state serial 61. No placeholder was
used.

## 5. Pinned Orders module

| Item | Verified |
|---|---|
| Builder pin | `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d` |
| Generated manifest source | `1dbb0cb` |
| Project | `ris-dev-mays-orders` |
| Module default | `ris-dev-mays-orders` |
| Lambda artifact SHA-256 | `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` |
| Builder reproducibility | Two consecutive builds at the pin were byte-identical in the 09 readiness run |
| Module validate | PASS |

No foreign module version was used. The plan was generated from the pinned module.

## 6. Init, validate and plan

- `terraform init -reconfigure` with explicit backend: SUCCESS.
- `workspace list` / `select ris-dev`: SUCCESS; workspace existed.
- `terraform fmt -check -recursive`: PASS.
- `terraform validate`: PASS with pre-existing deprecation warnings.
- One authorized `terraform plan`: SUCCESS.
- Plan artifacts are local and mode `0600` under `/tmp/opencode/ris-scv-rc2-10/`.

| Artifact | SHA-256 |
|---|---|
| Binary plan | `8d1cb396ae536c6a69c7b3f5285193955c8d3948d40111cba8d7341bd339f423` |
| Plan JSON | `3bc716e925c79c3fd33819ce7091314d4ae0633799cd69d07d8d2d763e5a2391` |
| Plan log | `bea358740b76c6555a4dc36a1b06c27a03caf15365082f1f5825d916203be548` |

The old plan remains untouched at its original path and hash.

## 7. Resource diff

**RC2 plan: 6 CREATE / 2 UPDATE / 1 DELETE / 0 REPLACE.**

### CREATE — expected

1. `GET /v1/partner/me/cv-builder-profiles`
2. `POST /v1/partner/me/cv-builder-profiles`
3. `GET /v1/partner/me/cv-builder-profiles/{profileId}`
4. `PATCH /v1/partner/me/cv-builder-profiles/{profileId}`
5. `DELETE /v1/partner/me/cv-builder-profiles/{profileId}`
6. `GET /v1/partner/me/cv-builder-profiles/{profileId}/export`

### UPDATE — expected

| Resource | Change |
|---|---|
| `module.dynamodb.aws_dynamodb_table.partner_profiles` | adds `gsi-structured-owner` alongside `gsi-parent` and `gsi-user` |
| `module.lambda.aws_lambda_function.agent` | code hash update; adds `STRUCTURED_CV_PROFILE_ENABLED=false`; all four consent flags remain present |

No IAM update is present.

### DELETE — NOT ACCEPTED

| Resource | Before |
|---|---|
| `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders` | existing policy on `ris-dev-mays-orders-orders-queue` would be destroyed |

This is an existing Orders queue policy, not part of the Structured-CV scope. The pinned builder
does not model this live resource. The plan is therefore unsafe for G5 and apply.

## 8. Security comparison with the rejected RC1 plan

| Area | Old RC1 plan | New RC2 plan |
|---|---|---|
| CREATE | 6 | 6 |
| UPDATE | 8 | 2 |
| DELETE | 2 | **1** |
| REPLACE | 0 | 0 |
| Erasure route | DELETE | no change — preserved |
| Documents CORS | DELETE | no change — preserved |
| Consent flags | REMOVE | no change — preserved |
| IAM `ConditionCheckItem` | REMOVE | no change — preserved |
| Orders boundary | REMOVE | no change — preserved |
| Health schedule | 15→5 min | no change — 15 min preserved |
| Orders SQS queue policy | no change | **DELETE — unsafe** |

The RC2 plan fixes the original regression set but introduces one new non-accepted delete.

## 9. G5 recommendation

**G5: DO NOT APPROVE THIS PLAN. `UNSAFE PLAN / DO NOT APPLY`.**

Required before any new plan:

- preserve `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders` in the generated module
  or through an explicitly reviewed root-level resource;
- resolve the pinned-builder/live-state mismatch without importing, deleting or recreating the
  existing queue or policy;
- obtain separate approval for a new plan run;
- require a new plan with 0 DELETE / 0 REPLACE and no unexpected IAM or health changes.

No apply, destroy, import, state mutation, consent activation, main merge or production deployment
occurred. XRepo task remains `IMPLEMENTING`.

**RIS-SCV-AWS-G4-REPLAN-10 — UNSAFE PLAN / DO NOT APPLY**

**STOP BEFORE APPLY.**
