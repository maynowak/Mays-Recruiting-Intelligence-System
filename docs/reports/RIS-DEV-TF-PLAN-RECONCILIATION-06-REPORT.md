# RIS-DEV-TF-PLAN-RECONCILIATION-06-REPORT

## Result

`RIS-DEV TERRAFORM PLAN CLEAN — READY FOR REVIEW`

The previous plan was rejected and not applied. After the authorized temporary
Mays-Orders compatibility decision, a new saved plan contains **only**
`module.lambda.aws_lambda_function.agent UPDATE`: 272 no-op, 1 update,
0 deletes, 0 replacements. No apply/deployment/push was performed.

## 1. Rejected plan

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-one-shot-05-v4-draft.tfplan` |
| SHA-256 | `392d107478a391fe02a4527a28581cf115a8acfa2a71ce34b322b3260087393a` |
| Terraform | `1.16.1` |
| State | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| Serial / lineage | `42` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| State object VersionId | `wVw.GTLeSJ6IN7WXS02qrQSU2xiguw8x` |
| Result | 267 no-op, 5 update, 1 delete |
| Apply | **not executed** — plan rejected |

## 2. Cause A — Lambda artifact path drift

Affected:

- `module.health_plane.aws_lambda_function.health_publisher`
- `module.health_plane.aws_lambda_function.health_writer`
- `module.orders_reader[0].aws_lambda_function.reader`

State filenames point to
`/home/dci-student/projects/Mays-Recruiting-Intelligent-System/lambda/dist/...`.
The new plan uses the workspace worktree path. The source content hashes for
these three functions are unchanged; the only delta is the absolute artifact
path. This is local path drift, not a code change.

**Correction option (not applied):** use a stable artifact path or a narrowly
scoped `ignore_changes = [filename]` with `source_code_hash` still tracking
code changes. This is not the blocking issue; it is deferred until the Orders
conflict is resolved.

## 3. Cause B — Orders SQS Queue Policy deletion

The generated Mays-Orders module has no
`aws_sqs_queue_policy.orders` resource. The deployed RIS-DEV state still has:

- address: `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders`
- queue: `ris-dev-mays-orders-orders-queue`
- policy: `AllowAccessFromAccount` with
  `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`,
  `sqs:GetQueueAttributes`.

The current module builder pin `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`
contains the commit `a2fb385 fix(sqs): remove wildcard resource policy F-03`,
which deliberately removed the queue policy. The deployed state predates that
module behavior. Terraform therefore plans a **delete** of the current queue
policy.

The task requires the existing queue policy to remain unchanged. A safe fix
would require either:

- the exact older/deployed Mays-Orders module revision that still contains the
  queue policy, or
- a separately approved compatibility resource/contract.

Neither is authorized in this task. Hand-editing the generated module or using
`-target`/`ignore_changes` to hide the deletion is prohibited.

## 4. Cause C — Orders Worker IAM Permissions Boundary removal

The deployed worker role
`module.mays_orders[0].module.sqs_worker.aws_iam_role.worker` has:

`permissions_boundary = arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`.

The generated module's `lambda_execution_boundary` defaults to `null`; the root
`module "mays_orders"` call does not pass a boundary value. The plan therefore
removes the boundary from the desired state.

The boundary is a security control and must not be removed or weakened. A safe
fix requires a separately approved Mays-Orders contract/config decision (for
example, an explicit boundary input matching the deployed role). No hardcoded
replacement value was added in this task.

## 5. Full active change list

| Resource | Action | Cause | Status |
| --- | --- | --- | --- |
| `module.lambda.aws_lambda_function.agent` | update | Expected pilot v4 code/env | Approved target, but plan rejected |
| `module.health_plane.aws_lambda_function.health_publisher` | update | Filename path drift | Out of scope |
| `module.health_plane.aws_lambda_function.health_writer` | update | Filename path drift | Out of scope |
| `module.orders_reader[0].aws_lambda_function.reader` | update | Filename path drift | Out of scope |
| `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders` | **delete** | Current builder pin removed policy | **Blocking** |
| `module.mays_orders[0].module.sqs_worker.aws_iam_role.worker` | update | Boundary not passed; module default null | **Blocking** |

Protected resources:

- Cognito: no active change
- CloudFront: no active change
- DNS/Route53: no active change
- ACM: no active change
- DynamoDB: no active change
- API Gateway routes/integrations: no active change

However, the Orders delete/boundary changes are sufficient for STOP.

## 6. Corrections made

No Terraform code, module pin, AWS resource, state, or notice was changed.
The generated Mays-Orders module was built locally for plan analysis only; it is
gitignored and not committed. The tracked module stub was restored; worktree is
clean.

## 7. Git / tests

- Rejected plan evidence: above plan SHA-256.
- No new application code commit in this reconciliation.
- Terraform fmt/validate had previously passed for the v4 code.
- No apply, destroy, target, replace, state import/manipulation, or AWS mutation.

## 8. Required next decisions

1. **Mays-Orders module contract:** choose an approved module revision or
   compatibility configuration that preserves:
   - the existing SQS queue policy and its exact scope,
   - the existing worker IAM permissions boundary.
2. **Artifact paths:** after Orders is resolved, use a stable artifact path or
   an approved narrowly scoped filename handling so health/reader remain no-op.
3. **Consent v4:** still requires operator/legal approval and a real
   `legalApprovalRef`; notice remains DRAFT.
4. **New plan:** after 1–3, create a new saved plan and verify:
   - only `module.lambda.aws_lambda_function.agent UPDATE`,
   - 0 deletes, 0 replacements, 0 other updates,
   - protected resources unchanged,
   - new plan SHA-256.
5. **Bundled GO:** only after the clean plan is reviewed.

## 9. Orders safety confirmation

The actual AWS queue policy and IAM boundary remain unchanged because no apply
was performed. The rejected plan would have deleted the queue policy and
removed the boundary; it must never be applied.

## 10. Final status

`BLOCKED — MAYS-ORDERS MODULE CONTRACT MISMATCH`

No live persistence, deployment, or notice activation is claimed.


---

## Reconciliation result — clean plan

| Field | Value |
| --- | --- |
| New plan file | `/tmp/opencode/ris-dev-one-shot-05-v4-clean.tfplan` |
| New plan SHA-256 | `92264620c4f438aee48945778ccbe4a5f5035a8412d7279570bb44cca0e570da` |
| Terraform | `1.16.1` |
| State serial / lineage | `42` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Changes | **272 no-op, 1 update, 0 delete, 0 replace** |
| Apply | **not executed** |

### Active change

`module.lambda.aws_lambda_function.agent` — `UPDATE`

- `source_code_hash`: `783PJahGgBAGcS3cbwd7SNhc5o5RQNKplp9/RAxEEio=` →
  `WEl8n14qkyTQezjOq5yyTuhZO8DInnmC/a++wJN7cMM=`
- `CONSENT_NOTICE_STATE_ENFORCED`: absent → `false`
- `CONSENT_PILOT_ALLOWLIST`: absent →
  `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ZURSMpD2O|2344d8d2-f0e1-70a4-a1ff-1b7a6c843558`
- Global gates remain unchanged/false; notice remains DRAFT.

All other resources are **NO-OP**, including:
Orders SQS queue policy, Orders worker IAM role/boundary, health publisher,
health writer, orders reader, Cognito, CloudFront, DNS/Route53, ACM, DynamoDB,
API Gateway and partner edge.

### Fixes applied

1. **Temporary Mays-Orders module compatibility:** used the last pre-F-03
   module revision `c1dcca2` (contains the existing SQS queue policy). This is
   explicitly temporary; F-03 remains a separate remediation item.
2. **Explicit IAM boundary:** added root variable
   `mays_orders_lambda_execution_boundary` (default null) and passed it to the
   Mays-Orders module. The clean plan used the existing ARN
   `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`.
   No hardcoded ARN was committed.
3. **Lambda path drift:** added narrow `lifecycle { ignore_changes = [filename] }`
   to health writer/publisher and orders reader. `source_code_hash` remains
   active for the orders reader; the health functions have no source hash to
   preserve. No global ignore was added.
4. Static guard test `tests/test_terraform_plan_reconciliation_06.py` covers
   these constraints and passes.

### Remaining approvals

1. Consent v4 text/notice approval and real `legalApprovalRef` — still open.
2. Final review of this clean plan and bundled apply/deploy/E2E GO.
3. F-03/SQS-policy and IAM-boundary modernization as a separate Mays-Orders
   remediation, not this pilot.

### Final status

`RIS-DEV TERRAFORM PLAN CLEAN — READY FOR REVIEW`

No apply, deployment, push/merge, notice activation, or live-persistence claim.
