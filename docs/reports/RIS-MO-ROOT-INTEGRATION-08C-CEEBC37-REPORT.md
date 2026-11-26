# RIS-MO-ROOT-INTEGRATION-08C — Follow-up verification of pin candidate `ceebc37`

Status: **BUILD VERIFIED — FINAL PIN CANDIDATE (technical integration proven;
SQS/IAM policy decision still open, so pin migration stays unapproved)**

Branch: `integration/ris-mo-root-08c` (base `e237b45`, includes builder
portability `cce4cf5`)
Tested Orders version: `ceebc374e35132ee45613b9637909a5b9e77992a`
(`fix(iam): let the RIS result consumer receive the optional boundary`, base
`386d741`)
Predecessor proof: `docs/reports/RIS-MO-ROOT-INTEGRATION-08C-REPORT.md`
(`386d741`, BUILD VERIFIED / PIN NOT APPROVED)

No main merge, no Terraform plan/apply, no AWS access or mutation, no
deployment. Committed RIS builder pin stays `016cdfd`; pin override and all
generated artifacts exist only in `/tmp/opencode/ris-root08-c-ceebc37`.

## Method

Fresh temp copy of the worktree (`rsync`, no `.git`, no `installer/projects`),
Orders test version cloned locally and verified clean at `ceebc37`. Pin
override only in the temp copy (`installer/mays-orders-builder.pinned.json` and
`PINNED_COMMIT`). Then the unchanged RIS wrapper end-to-end:

```
python3 -m installer.build_mays_orders_module --project-name ris-dev --force
```

## Delta vs `386d741`

`git diff --stat 386d741 ceebc37`: 8 files, +233/−4.

| Change | Effect |
| --- | --- |
| `terraform/modules/agent_transport/main.tf` | new optional input `lambda_execution_boundary` (string, default `""`, no account ARN) |
| `terraform/modules/agent_transport/lambda.tf` | `permissions_boundary = var.lambda_execution_boundary != "" ? var.lambda_execution_boundary : null` on `aws_iam_role.result_consumer` |
| `terraform/main.tf` | passes `lambda_execution_boundary = var.lambda_execution_boundary` to `module.agent_transport` |
| `module_builder/catalog.py` | binds `lambda_execution_boundary` to `agent_transport` as well as `sqs_worker` (free selection keeps the variable declared) |
| `module_builder/tests`, `lambda/tests` | 4 new tests |
| `docs/*` | Agent A report/audit |

No change to SQS queue policy, queue attributes, GSI, HMAC/envelope, `apply_result`,
`identity.py`, module outputs or the orders-service preset variable set.

Generated-module delta (386d741 build vs ceebc37 build, 42 source files):
**exactly three `.tf` files differ** — `main.tf`,
`modules/agent_transport/main.tf`, `modules/agent_transport/lambda.tf` — plus
`module-builder.manifest.json` (timestamp). 38/42 files byte-identical;
`lambda/dist/lambda.zip` identical
(`fa0dee9e2381e85ef897daa76635f15d9c7fc2c07592963a8c0cfca98818a983`).

```
main.tf:                                + lambda_execution_boundary = var.lambda_execution_boundary
agent_transport/main.tf:                + variable "lambda_execution_boundary" (default "")
agent_transport/lambda.tf:              + permissions_boundary = ... != "" ? ... : null
```

## Verification

| Step | Result |
| --- | --- |
| RIS wrapper build from `ceebc37` | PASS — orders-service, 8 child modules incl. `agent_transport` |
| Manifest pin | `source.commit = ceebc37…`, 42 files |
| RIS transport outputs | 3 injected once with exact refs (`results_queue_url`, `results_queue_arn`, `result_hmac_secret_arn`) |
| Inputs / outputs | 9 inputs, 23 outputs incl. `sqs_queue_name`; IAM contract OK; SQS IAM document has no wildcard |
| Contract audit (`validate_generated_contract`, `check_arn_id_contract`) | PASS; 9/9 real root output references declared, no undeclared inputs |
| Module `fmt -check -recursive` | PASS |
| Module `init -backend=false` + `validate` | PASS — `Success! The configuration is valid.` |
| RIS root `fmt -check -recursive` | PASS |
| RIS root `init -backend=false` + `validate` | PASS — `The configuration is valid` (only pre-existing deprecation warnings) |
| RIS focused tests (5 files, `MO_ORDERS_SRC=ceebc37/lambda/src`) | **102 passed, 0 failed** |
| RIS installer tests | 43 passed |
| Orders `module_builder` tests at `ceebc37` (independent re-run) | **96 OK** |

No builder, module or RIS-wiring error occurred. The known builder-clone
artifact side effect (`lambda/dist/lambda.zip` rebuilt → dirty guard on an
immediate second run) is unchanged and not pin-specific.

## Residual items for the pin candidate

1. **SQS queue policy (decisive, unchanged).** `ceebc37` inherits `016cdfd`:
   `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders` with
   account-root principal (Send/Receive/Delete/GetAttributes, no
   `aws:SourceArn`/`SourceAccount` condition). File is byte-identical to the
   `386d741` proof. Live queue carries the legacy wildcard policy; `ceebc37`
   would UPDATE it, the main line (`a2fb385`) would DELETE the resource.
   Policy/remediation decision remains with the release owner (Forensics 11:
   live policy `LEGACY UNSAFE`).
2. **Boundary is module-capable but not RIS-wired.** The new optional input is
   available and defaults to `""` → `null` (no account ARN shipped). The RIS
   root has no `lambda_execution_boundary` variable and does not pass one to
   `module.mays_orders`; in a boundary-enforcing account an explicit RIS wiring
   addition would still be required for Orders roles. Pre-existing gap, not a
   build defect.
3. Unchanged pre-existing items: empty `ris_result_producer_role_arns` default
   yields an empty policy principal; handler role (`module.iam`) has no
   boundary in any compared ref; gsi3/gsi4, `apply_result` guard, HMAC allowlist
   and policy-gate coverage of agent-transport resources remain open decisions.

## Verdict

`ceebc37` is **BUILD VERIFIED as the final pin candidate**: it integrates
cleanly with the RIS root (build, injection, contract audit, module and root
Terraform checks, focused and cross-repo contract tests) and its only delta vs
`386d741` is the bounded, optional result-consumer IAM boundary.

Pin **migration is not approved by this proof**: the SQS/IAM queue-policy
decision and the remaining policy items must be decided separately; `ceebc37`
does not change them.

## Boundaries

- No AWS credentials used, no STS/discovery, no plan/apply, no state access, no
  SQS/IAM/API Gateway/Cognito/CloudFront mutation, no deployment, no main merge.
- No generated module, `.terraform`, lockfile or artifact committed; committed
  RIS pin and source files unchanged (`git status` clean apart from docs).
