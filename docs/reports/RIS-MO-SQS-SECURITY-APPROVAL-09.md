# RIS-MO-SQS-SECURITY-APPROVAL-09

**Status: BLOCKED — PLAN INPUTS / SCOPE APPROVAL**

- SQS Security: **APPROVAL RECOMMENDED — interim Option B; not granted**
- Orders Pin: **INTEGRATED** on `feature/ris-mo-pin-ceebc37-09b` (`b315050`)
- RIS Root: **VALID** with Orders `ceebc37`
- Consent: **PRESERVED** (no consent code or live flag change in this task)
- Plan-Inputs: **INCOMPLETE**
- Overall: **BLOCKED** until protected inputs exist and the plan scope is explicitly approved.

No Terraform plan/apply, AWS mutation, deployment or main merge.

## 1. Pin integration

| Item | Value |
| --- | --- |
| Orders candidate | `ceebc374e35132ee45613b9637909a5b9e77992a` |
| Orders branch | `fix/mo-ris-pin-compat-08a` |
| RIS integration branch | `feature/ris-mo-pin-ceebc37-09b` |
| RIS integration commit | `b315050` |
| Previous RIS pin | `016cdfd` |
| New RIS pin file | `installer/mays-orders-builder.pinned.json` |
| Builder constant | `PINNED_COMMIT = ceebc37…` |
| Historical clone pin | unchanged (`5cf50a0…`, not used for builder) |

Pin integration proof:

- builder fetched `ceebc37` detached/clean and generated the orders-service module;
- 8 child modules incl. `agent_transport`;
- 9 inputs / 23 outputs; transport outputs injected exactly once;
- contract and ARN/ID audits PASS;
- generated module and RIS root `fmt` / `init -backend=false` / `validate` PASS;
- focused tests **102 PASS**, installer **43 PASS**, pinning **6 PASS**;
- no generated module, `.terraform`, lockfile or `lambda.zip` committed.

## 2. SQS security review — Option B

Live queue `ris-dev-mays-orders-orders-queue` read-only confirmed:

- `Principal: "*"`
- actions: `SendMessage`, `ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes`
- no conditions
- visibility `30`, retention `120`, no DLQ/redrive

Known principals are all same-account:

| Role | Need |
| --- | --- |
| `ris-dev-mays-orders-handler-role` | `SendMessage` |
| `ris-dev-dev-orders-reader` | `SendMessage` |
| `ris-dev-mays-orders-sqs-worker-role` | `Receive/Delete/Get` |
| `ris-dev-dev-agent` | **not a producer of this queue** |

Option B (`ceebc37`) changes only the policy principal to
`arn:aws:iam::240571105849:root`. It does not change the action set, queue
visibility/retention, DLQ/redrive, or queue identity.

Security effect:

- closes cross-account Send/Receive/Delete exposure;
- same-account effective permissions are unchanged (identity policies already
  grant the required actions);
- no documented cross-account path is broken;
- Terraform expected change: one in-place `SetQueueAttributes` UPDATE on
  `aws_sqs_queue_policy.orders`, no queue replacement, no message loss;
- account-root is not least privilege; B-full/C-minimal remain follow-ups.

**Recommendation:** approve Option B only as a documented **interim** under
the plan assertions P1–P7 from the Gate-08 analysis. This report does not grant
that approval.

## 3. Plan inputs — INCOMPLETE

| Required input | Status |
| --- | --- |
| Protected `--var-file` mode 0600 with `application_consent_enforced`, `cv_storage_consent_enforced`, `search_profile_storage_consent_enforced`, `consent_notice_state_enforced` = `true` and the 2 allowlist entries | **MISSING** — no protected tfvars exists in workspace/tmp; `application_consent_enforced` cannot come from the overlay |
| New Orders pin on the plan branch | **READY** on `b315050` |
| Generated `terraform/modules/mays_orders` | **MISSING in the committed tree** (generated/ignored; must be rebuilt at plan time) |
| `terraform/lambda.zip` and `lambda/dist/orders-reader.zip` | **MISSING** (gitignored build artifacts) |
| Scope approval for non-policy changes | **OPEN** |

The Lambda module preconditions protect against a missing notice-state or
allowlist when a storage gate is enabled, but they do **not** stop a plan that
omits the protected file and therefore flips the live `true` flags to default
`false` and clears the allowlist. The file is mandatory, not optional.

No real allowlist values are recorded here.

## 4. Expected plan scope (not approved)

A plan from this branch is **not** policy-UPDATE-only. Expected deltas:

1. `update` `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders`
   (wildcard → account-root).
2. `create` `module.api.aws_apigatewayv2_route.partner_erasure`
   (`POST /v1/partner/me/erasure` on the kernel API; live has only
   `POST /me/erasure`).
3. `create` five IAM inline policies:
   `lambda_order_result_send`, `lambda_order_result_secret`,
   `dispatch_result_send`, `dispatch_result_secret`,
   `reader_agent_dispatch` (duplicate grants, but new IAM resources).
4. `update` Lambda env `+ORDERS_BASE_URL`, `+ATS_API_BASE_URL`.
5. Lambda code update if the artifact is rebuilt from branch source; live
   `UCdP…` lacks the P0 search-profile/CV-metadata erasure code.
6. Reader code update if `orders-reader.zip` is rebuilt.

No delete/replace, no Cognito/CloudFront/CORS/consent change is expected.
The “no IAM widening” claim needs qualification: the grants are duplicates of
existing paths but the resources are net-new.

## 5. State / live confirmation

- Profile `mayaws`, account `240571105849`, region `eu-central-1`.
- State `mays-ris-tf-state-dev`, key `env:/ris-dev/dev/terraform.tfstate`,
  workspace `ris-dev`, serial **83**, lineage
  `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`, 271 resources.
- Lambda `ris-dev-dev-agent`: `$LATEST`, CodeSha `UCdP…`, no version/alias.
- Consent flags all `true`; allowlist 2 entries; partner surface `true`.
- Queue: visibility 30, retention 120, no DLQ, live wildcard policy.
- Consent table: 50 rows (9 current + 41 events); current proofs complete.
- Cognito/CloudFront: pool `eu-central-1_ojbmoiYGM`, kernel API
  `g6901and25`; CloudFront `E1IP0DIEAXAZPY` in state. No change planned.
- Foreign CloudFront `E1R3BHTJNMC6XW` is not in state; out of scope.

## 6. Gates

| Gate | Result |
| --- | --- |
| SQS Security | **APPROVAL RECOMMENDED (interim B; not granted)** |
| Orders-Pin | **INTEGRATED** (`b315050`) |
| RIS Root | **VALID** with `ceebc37` |
| Consent | **PRESERVED** |
| Plan-Inputs | **INCOMPLETE** |
| Gesamt | **BLOCKED — PLAN INPUTS / SCOPE APPROVAL** |

## 7. Required before an authorized plan

1. Operator creates a protected 0600 var-file with the four `true` flags and
   the two allowlist entries; path and contents never in Git/reports.
2. Release Owner approves the **scope** in §4 (route create, five IAM creates,
   two env keys, optional code update), not just the SQS UPDATE.
3. Rebuild `lambda.zip` and `orders-reader.zip` deterministically, or
   explicitly choose the captured pre-Gate05 artifact to keep Lambda code
   unchanged.
4. Generate `terraform/modules/mays_orders` from `ceebc37` at plan time.
5. Run the fresh plan with P1–P7 assertions from Gate-08:
   no delete/replace, one policy UPDATE, queue shape unchanged, no IAM
   boundary removal/widening, no Cognito/CloudFront/CORS/consent change.
6. Separate apply approval bound to plan SHA, state serial/lineage and shape.
7. Post-apply: queue policy negative test, same-account send/receive/delete
   smoke, consent/gate smoke; no real user data.

**BLOCKED — PLAN INPUTS / SCOPE APPROVAL**

No plan, apply, deployment or main merge occurred.
