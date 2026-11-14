# RIS-SCV-MO-SQS-POLICY-FORENSICS-11

**Status:** `RIS-SCV-MO-SQS-POLICY-FORENSICS-11 — SECURITY CLASSIFIED / REMEDIATION DECISION PENDING`

**Date:** 2026-11-14

**Mode:** local forensic review only. No AWS access, no new Terraform plan, no state or SQS mutation.

## 1. Git baselines

| Repository / ref | HEAD |
|---|---|
| RIS `origin/main` | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` |
| RIS RC1 | `4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1` |
| RIS RC2 | `release/structured-cv-rc2-reconciled @ 6eeab5d37edc0eb8dabf284f0c5e9dc173b82751` |
| Mays-Orders builder clone | `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d` |
| Mays-Orders F-03 fix | `a2fb385a428e4c30b40ad61807d5ea23f2b182ae` |
| Mays-Orders RC.3 packaging | `086a8be` (on MO `main`, after the pin) |

Locked plan:

`8d1cb396ae536c6a69c7b3f5285193955c8d3948d40111cba8d7341bd339f423`

The plan hash was rechecked and matches. The old RC1 plan `36632ab5…` remains untouched.

## 2. Pinned builder

- RIS pin: `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`.
- Generated module source: `1dbb0cb`; project `ris-dev-mays-orders`.
- F-03 commit `a2fb385` is an ancestor of the pin.
- RC.3 release packaging `086a8be` is **after** the pin but does not alter the pinned module code
  relevant to F-03; RC.3 explicitly records the same F-03 fix and identifies the pin as
  code-identical for the module path.
- No foreign module version is involved.

## 3. F-03 security history

Mays-Orders `a2fb385` (F-03) is documented in
`docs/reports/MO-MODULE-SQS-RESOURCE-POLICY-FIX-03.md`.

Before the fix, `terraform/modules/sqs/main.tf` created:

```hcl
resource "aws_sqs_queue_policy" "orders" {
  queue_url = aws_sqs_queue.orders.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowAccessFromAccount"
      Effect    = "Allow"
      Principal = "*"
      Action = ["sqs:SendMessage", "sqs:ReceiveMessage",
                "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = aws_sqs_queue.orders.arn
    }]
  })
}
```

The fix removed the resource policy and left a comment stating that access is controlled only by
IAM identity policies. The justification in the F-03 report:

- wildcard principal;
- no condition and no account restriction;
- permissions already handled by the Lambda and worker IAM roles;
- least privilege and account portability.

`a2fb385` is included in the pinned builder. The RC.3 release note repeats that F-03 is resolved by
removal and that the pin is code-identical to the module code.

## 4. Terraform state and plan evidence

Resource address:

`module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders`

Queue URL:

`https://sqs.eu-central-1.amazonaws.com/240571105849/ris-dev-mays-orders-orders-queue`

The serial-61 state and the new plan’s `before` value both contain the legacy policy:

| Field | Observed |
|---|---|
| Sid | `AllowAccessFromAccount` |
| Effect | `Allow` |
| Principal | `*` |
| Actions | `sqs:SendMessage`, `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` |
| Resource | queue ARN for `ris-dev-mays-orders-orders-queue` |
| Condition | none |
| Account/role binding | none beyond the queue ARN |
| Cross-account condition | none |

The plan action is `delete` of that existing state resource. The queue itself is not deleted.

The current pinned module contains no `aws_sqs_queue_policy` resource. Its IAM contracts instead
grant:

- handler role: `sqs:SendMessage` on the queue ARN;
- worker role: `sqs:ReceiveMessage`, `sqs:DeleteMessage`, `sqs:GetQueueAttributes` on the queue ARN.

All of these are identity policies in the same account, scoped to the queue ARN.

## 5. Security classification

**Classification: `LEGACY UNSAFE`.**

The policy matches the pre-F-03 wildcard resource policy exactly:
`Principal "*"`, no condition, no account restriction. The fact that IAM identity policies also
apply does not make a wildcard resource policy acceptable. It is the exact contract F-03 removed.

This classification is based on the state and plan `before` values produced by the authorized
RC2 plan refresh. No new AWS API read was made in this forensic task.

## 6. Terraform ownership

The resource is currently owned by the old generated module address and is present in the live
state. The pinned module no longer declares it. Therefore the delete is not an RC2 regression; it
is the F-03 security remediation colliding with a stale/legacy Terraform resource.

The queue is not being recreated, imported or changed. The resource-policy ownership is the only
question.

## 7. Solution options

### Option A — do not restore; separate security remediation

- Keep the F-03 fix.
- Do not recreate the wildcard policy.
- Remove the legacy policy in a separately approved security change, not silently inside the
  Structured-CV release.
- Re-run a new G4 plan after that approved change to obtain a clean Structured-CV-only delta.

**Security:** best — preserves F-03.
**Terraform ownership:** requires a deliberate ownership/cleanup decision.
**Pin change:** none.
**State mutation:** only through the approved remediation apply; no blind `state rm`.
**AWS mutation:** one policy delete, separately approved.
**RIS risk:** low if IAM identity paths are verified.
**Orders risk:** low if handler/worker IAM permissions are confirmed live.
**Approval:** Security/Orders owner + Release Owner + separate plan/apply gate.

### Option B — scoped resource policy

- Design a least-privilege resource policy with explicit account/role principal and conditions.
- Add it to the module and pin only after a separate security design decision.
- Do not create a new queue and do not import the existing queue.

**Security:** potentially acceptable only with a reviewed scope; not currently evidenced.
**Terraform ownership:** would require a new resource contract and pin decision.
**Pin change:** yes, separately approved.
**State mutation:** none if the existing state resource is replaced deliberately; still requires a plan.
**AWS mutation:** resource-policy update.
**RIS/Orders risk:** functional regression if principal/conditions are wrong.
**Approval:** Security review, module owner, pin change, G4/G5/G6.

### Option C — stale state ownership only

- Claim the live resource policy no longer exists and reconcile state.
- Requires a current live AWS policy read and ownership evidence.

**Security:** unknown until read.
**Terraform ownership:** state reconciliation only after evidence.
**Pin change:** none.
**State mutation:** possible but prohibited without separate approval.
**AWS mutation:** none if truly absent.
**RIS/Orders risk:** hidden drift if the policy actually exists.
**Approval:** separate live-read and state-ownership decision.

## 8. Evaluation matrix

| Criterion | Option A | Option B | Option C |
|---|---|---|---|
| Security | Preserves F-03; best | Needs new scoped design | Unknown until live read |
| Terraform ownership | Deliberate removal decision | New module contract | State reconciliation |
| Pin change | None | Required | None |
| State mutation | Via approved remediation apply | Via approved plan | Only after evidence |
| AWS mutation | Policy delete, separate | Policy update | None if absent |
| Risk for RIS | Structured-CV plan must wait | Higher change surface | Drift risk |
| Risk for Orders | Low if IAM verified | Functional risk | Unknown |
| Approval need | Security + Release + G6 | Security + module + G4/G5/G6 | Live read + state owner |

## 9. Recommendation

**Smallest safe path: Option A.**

Do **not** reintroduce the legacy wildcard policy just to avoid a Terraform DELETE. Do not hide
the delete with `-target`, `state rm`, `ignore_changes`, or `removed { destroy = false }`.

Recommended sequence:

1. Obtain a separate read-only AWS confirmation of the queue policy and the handler/worker IAM
   permissions.
2. Obtain Security/Orders approval to remove the legacy F-03 policy as a standalone remediation.
3. Apply that remediation only under its own reviewed plan and G6 authorization.
4. Re-run G4 for RC2 and require a Structured-CV plan with six route creates, the GSI, the agent
   update and **0 DELETE / 0 REPLACE**.
5. Reject any plan that touches CORS, erasure, consent, IAM `ConditionCheckItem`, Orders boundary,
   health schedule, Cognito, CloudFront, DNS or existing data unexpectedly.

Option B is only appropriate if a current, scoped resource policy is proven necessary. The
evidence currently shows the IAM identity policies already grant the required queue operations.

Option C is not supported because the plan’s `before` value contains the live policy; a current
live read would be required before claiming stale state.

## 10. Required approvals

- Security/Orders owner: F-03 remediation or scoped-policy decision.
- Release Owner: separate G4 plan, G5 review and G6 apply for any policy change.
- No approval is inferred from this forensic report.
- No IAM or queue policy change may be bundled silently into Structured-CV activation.

## 11. Open evidence gaps

1. No live AWS `GetQueueAttributes`/policy read was performed in this task.
2. The plan refresh proves the policy existed at plan time, but a direct current policy read is
   still recommended before remediation.
3. Live handler/worker IAM attachments and their effective permissions were not queried.
4. No decision has been made whether the legacy policy is to be removed now or after a
   scoped-policy review.
5. The old RC1 plan and current RC2 plan remain non-apply artifacts.

## 12. Boundaries

- No AWS access.
- No new Terraform plan.
- No apply, import, destroy or state mutation.
- No SQS policy change or queue creation.
- No main merge.
- No consent activation.
- No XRepo `COMPLETED`; task remains `IMPLEMENTING`.

**RIS-SCV-MO-SQS-POLICY-FORENSICS-11 — SECURITY CLASSIFIED / REMEDIATION DECISION PENDING**

**STOP BEFORE FURTHER AWS PLAN AND APPLY.**
