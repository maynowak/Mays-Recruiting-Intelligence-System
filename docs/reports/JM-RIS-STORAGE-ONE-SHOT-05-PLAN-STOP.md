> **RIS documentation copy.** Terraform pre-plan only; no apply, deployment,
> env or notice change.

# JM-RIS-STORAGE-ONE-SHOT-05 — PLAN STOP

## Result

`PLAN STOP — OUT-OF-SCOPE DRIFT`

No Terraform apply, deployment, merge, push, notice change, or live write was
performed. The saved plan is **not approved**.

## 1. Plan identity

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-one-shot-05-v4-draft.tfplan` |
| Plan SHA-256 | `392d107478a391fe02a4527a28581cf115a8acfa2a71ce34b322b3260087393a` |
| Terraform | `1.16.1` |
| State bucket/key | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage | `42` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| State object VersionId | `wVw.GTLeSJ6IN7WXS02qrQSU2xiguw8x` |
| Plan complete/applyable | `true` / `true` |
| Notice | `application-storage/1.0` remains `DRAFT` |
| Pilot allowlist | confirmed operator `<issuer>|<sub>` in the plan |

The plan was created with `AWS_PROFILE=mayaws` and the existing RIS-DEV backend.

## 2. Active changes (must be fully reviewed)

| Resource | Action | Classification |
| --- | --- | --- |
| `module.lambda.aws_lambda_function.agent` | update | **Expected pilot change**: v4 code + `CONSENT_NOTICE_STATE_ENFORCED=false` + `CONSENT_PILOT_ALLOWLIST=<operator>` |
| `module.health_plane.aws_lambda_function.health_publisher` | update | **Unexpected/out of scope**: filename path drift only |
| `module.health_plane.aws_lambda_function.health_writer` | update | **Unexpected/out of scope**: filename path drift only |
| `module.orders_reader[0].aws_lambda_function.reader` | update | **Unexpected/out of scope**: filename path drift only |
| `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders` | **delete** | **STOP — destructive, outside pilot scope** |
| `module.mays_orders[0].module.sqs_worker.aws_iam_role.worker` | update | **STOP — removes `permissions_boundary`, outside pilot scope** |

The plan reports `267 no-op`, `5 update`, `1 delete` resource changes.

### Agent Lambda — expected delta

- `source_code_hash`: `783PJahGgBAGcS3cbwd7SNhc5o5RQNKplp9/RAxEEio=` →
  `WEl8n14qkyTQezjOq5yyTuhZO8DInnmC/a++wJN7cMM=`
- Env additions:
  - `CONSENT_NOTICE_STATE_ENFORCED="false"`
  - `CONSENT_PILOT_ALLOWLIST=<confirmed operator identity>`
- Existing global gates remain `false`; `PARTNER_SURFACE_ENABLED=true`.
- No notice approval and no `legalApprovalRef` are added.

## 3. Protected resources

No active changes were found for:

- Cognito
- CloudFront
- DNS / Route53
- ACM
- DynamoDB tables
- API Gateway routes/integrations
- Partneredge integration

However, the destructive Mays-Orders SQS policy delete and IAM boundary removal
are sufficient to stop the plan. The plan cannot be applied as-is.

## 4. Why this is a STOP

The RIS-DEV plan contains changes beyond the approved pilot scope:

1. Health Lambda filename paths point to the previous external checkout; a plan
   would update them even though the code is not part of the pilot.
2. The generated Mays-Orders module wants to delete the SQS queue policy.
3. The same module wants to remove the worker IAM `permissions_boundary`.

These are not consent/notice/ApplicationV1 changes. Applying them could affect
shared RIS-DEV/Orders behavior and is prohibited by the task.

## 5. Required next step before a new plan

A separate authorized reconciliation is required:

- Explain and resolve the health/reader filename path drift, or explicitly
  exclude those resources from the pilot plan through an approved mechanism.
- Reconcile the generated Mays-Orders module with the deployed state so it
  produces **no** SQS policy delete and **no** IAM boundary removal.
- Re-run the plan and verify that the only active change is
  `module.lambda.aws_lambda_function.agent`.
- Re-check protected resources and document the new plan SHA-256.
- Only then request the bundled apply/deploy/E2E GO.

No `-target`, `-replace`, `-destroy`, state import, unlock, or apply was used or
is authorized as a workaround.

## 6. Vercel Production deployment plan — prepared, not applied

Target: `https://www.mays-job-matcher.app`, project `maymilly/mays-job-matcher`.
No preview target, no Vercel mutation.

Server-side (names only; existing secret values not printed):

```text
RIS_API_BASE_URL
RIS_PARTNER_CREDENTIAL
RIS_COGNITO_ISSUER
RIS_COGNITO_CLIENT_ID
RIS_APPLICATION_STORAGE_ENABLED=true
RIS_CONSENT_SERVICE_ENABLED=true
RIS_CONSENT_NOTICE_VERSION=1.0
RIS_CONSENT_TEXT_VERSION=application-storage-consent-2026-11-07-v4
RIS_CONSENT_TEXT_SHA256=8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7
RIS_CONSENT_TEXT_STATE=APPROVED   # only after final text/notice approval
RIS_TEST_USER_ALLOWLIST=<confirmed operator issuer|sub>
```

Frontend (production, only after backend plan approval):

```text
VITE_RIS_APPLICATION_STORAGE_ENABLED=true
VITE_RIS_CONSENT_UI_ENABLED=true
```

The existing per-user capability gate ensures only the server-allowlisted
operator gets remote mode; all other users remain in session mode.

## 7. Current blockers

1. Final operator/legal approval of v4 text and notice, with a real
   `legalApprovalRef` — still missing.
2. Out-of-scope Terraform drift in health/reader/Orders — plan not applicable.
3. No final plan approval / bundled GO.

## 8. Final status

`BLOCKED BEFORE APPLY — PLAN CONTAINS OUT-OF-SCOPE CHANGES`

No live persistence or production activation is claimed.
