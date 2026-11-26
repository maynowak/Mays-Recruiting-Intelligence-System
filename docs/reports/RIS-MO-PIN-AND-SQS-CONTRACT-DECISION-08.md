# RIS-MO-PIN-AND-SQS-CONTRACT-DECISION-08

**Status: PIN DECISION READY / SECURITY REVIEW REQUIRED**

- Pin candidate: Mays-Orders **`ceebc37`**
- Branch: `fix/mo-ris-pin-compat-08a` (base `386d741`)
- RIS integration proof: `integration/ris-mo-root-08c` at `a38ca46`
- No main merge, Terraform plan/apply, AWS mutation or deployment.

## 1. Pin candidate

`ceebc37` is the tested `386d741` version plus one minimal portability fix:

- optional `lambda_execution_boundary` input on `modules/agent_transport`;
- `permissions_boundary = var.lambda_execution_boundary != "" ? … : null`
  for the result-consumer role;
- root wiring and builder catalog binding;
- no SQS policy, queue attribute, GSI, HMAC, `apply_result`, identity or
  output change.

Generated-module delta vs `386d741`: exactly 3 `.tf` files plus manifest
timestamp; `lambda.zip` byte-identical.

## 2. RIS root integration — BUILD VERIFIED

Using the RIS builder (Linux portability `cce4cf5`) against `ceebc37`:

| Step | Result |
| --- | --- |
| Orders service generated from `ceebc37` | PASS — 8 child modules incl. `agent_transport` |
| RIS transport-output injection | PASS — 3 outputs, exact refs |
| Contract audit | PASS — 9 inputs / 23 outputs; 9/9 root refs declared |
| Module fmt / init -backend=false / validate | PASS / PASS / PASS |
| RIS root fmt -check / init -backend=false / validate | PASS / PASS / **valid** |
| RIS focused builder/injection/contract tests | **102 PASS, 0 failed** |
| RIS installer tests | 43 PASS |
| Orders module_builder at `ceebc37` | **96 PASS** |
| Orders lambda tests | **227 PASS** |
| Orders installer tests | **81 PASS** |

No builder, module or RIS-wiring error. Generated artifacts, `.terraform`
and lockfiles were not committed. The committed RIS pin remains `016cdfd`.

## 3. IAM / contract matrix

| Contract | `ceebc37` (pin) | main / live baseline | Decision |
| --- | --- | --- | --- |
| Agent transport | present, gated off by default | absent | keep pin line |
| Result consumer | present, HMAC/messageId, batch failures | absent | keep pin line |
| Result-consumer role boundary | now optional, empty→null | n/a | FIXED in `ceebc37` |
| Lambda root boundary default | account-specific in complete/custom; orders-service neutralises to `""` | null + validation | open follow-up; RIS orders-service path safe |
| SQS worker boundary | `""` → null | null + validation | equivalent |
| Orders queue policy resource | account-root principal | absent (F-03) | **security decision open** |
| Queue visibility/retention | 30 s / 120 s | 60 s / 4 d | pin matches live; main would change |
| DLQ/redrive | none | creates DLQ | pin matches live |
| Module inputs | 8 (agent vars) | 11 (adds `deployment_version` + SQS vars) | pin-specific RIS wiring; do not merge blindly |
| Module outputs | 20 + RIS injection = 23 | 22 incl. `mo_version`/privacy | pin contract verified for RIS |
| Cognito wiring | issuer/client-id env | different identity model | keep pin line |
| GSI / HMAC / apply_result | gsi1+gsi2 | gsi1+gsi2+gsi3 | untouched / separate decision |

## 4. Live SQS policy (read-only, re-confirmed)

Queue: `ris-dev-mays-orders-orders-queue`
(account `240571105849`, region `eu-central-1`).

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowAccessFromAccount",
    "Effect": "Allow",
    "Principal": "*",
    "Action": ["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes"],
    "Resource": "arn:aws:sqs:eu-central-1:240571105849:ris-dev-mays-orders-orders-queue"
  }]
}
```

Attributes: visibility `30`, retention `120`, no DLQ/redrive.

Semantics:

- Principal `*` is cross-account exposure, not anonymous public access.
- No conditions.
- Same-account callers rely on identity policies; the resource policy is not
  required for them.
- Live producers: MO handler role and RIS orders-reader role.
- Live consumer: MO SQS worker role (`Receive/Delete/Get`).
- `ris-dev-dev-agent` is **not** a producer of this queue; it reaches Orders
  over HTTP and uses separate work/result queues.

## 5. Options

| Option | Security | Functional | Terraform risk | Approval |
| --- | --- | --- | --- | --- |
| A — keep live wildcard | cross-account Send/Receive/Delete remains | none | no candidate models it; any apply changes it | not recommended |
| **B — account-root policy (`ceebc37`)** | closes cross-account; same-account delegation remains | none for documented paths | 1 UPDATE, queue shape unchanged | **recommended interim** |
| B-full — role-scoped principals | same as B for same-account; cosmetic in single account | none | new upstream commit | optional |
| C — remove policy | strongest; no cross-account | none for documented paths | 1 DELETE; named exception | preferred follow-up |

`A` is not acceptable. `C-via-main` must not be used: it bundles policy removal
with DLQ creation and 120 s → 4-day retention, which is a separate
Privacy/reliability decision.

## 6. Recommendation

**Use `ceebc37` as the pin candidate and adopt B (account-root policy) as the
interim security decision.**

- It closes the live cross-account wildcard exposure.
- It leaves queue shape (30/120, no DLQ) unchanged.
- It produces a policy UPDATE, not a DELETE/REPLACE; no queue replacement.
- It does not decide the main-line retention/DLQ bundle.

Follow-up, separately approved: **C-minimal** — remove
`aws_sqs_queue_policy.orders` from the 016cdfd line with a named delete
exception, then re-run this root proof and update the pin. This is the
strongest end state but is not the current candidate.

## 7. Open items / approvals

1. RIS Security approves B interim and the policy UPDATE; or approves C-minimal
   with a named delete exception and a new Orders commit.
2. Release Owner authorizes a fresh `ris-dev` plan; it must show the expected
   policy update only, no queue replacement, no DLQ/retention delta, no IAM
   widening, no Cognito/CloudFront change.
3. RIS root boundary wiring for `lambda_execution_boundary` remains absent
   (default empty/null; pre-existing gap for boundary-enforcing accounts).
4. Empty producer-principal default, handler-role boundary, GSI/`apply_result`/
   HMAC/policy-gate allowlist remain separate decisions.
5. No plan/apply/deploy until the plan is reviewed and approved.

## 8. Branches / commits

- Orders candidate: `fix/mo-ris-pin-compat-08a` **`ceebc37`** (pushed)
- Orders tested base: `386d741`; consolidated docs `c322baf`
- RIS proof: `integration/ris-mo-root-08c` **`a38ca46`** (pushed)
- RIS builder portability: `cce4cf5`
- RIS original pin: `016cdfd` (unchanged)
- No main merge, force-push, AWS mutation, plan/apply or deployment.

**PIN DECISION READY / SECURITY REVIEW REQUIRED**
