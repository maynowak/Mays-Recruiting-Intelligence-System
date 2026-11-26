# RIS-MO-SQS-SECURITY-APPROVAL-09 — Agent B: builder pin migration to `ceebc37`

Status: **PIN MIGRATED IN BRANCH / BUILD + CONTRACT + TERRAFORM + TESTS VERIFIED LOCAL**
Branch: `feature/ris-mo-pin-ceebc37-09b` (base `4581505`)
Orders pin: `016cdfd6ac62565dcec9a2fee78cb898fb919e59` → `ceebc374e35132ee45613b9637909a5b9e77992a`
(`fix(iam): let the RIS result consumer receive the optional boundary`, branch
`fix/mo-ris-pin-compat-08a`)

No main merge, no force-push, no branch deletion, no AWS access/mutation, no
Terraform plan/apply, no state write, no deployment. Historical composite
clone pin (`installer/mays-orders-clone.pinned.json`, `5cf50a0…`) unchanged.

## Scope

1. Builder pin only: `installer/mays-orders-builder.pinned.json` and
   `PINNED_COMMIT` in `installer/build_mays_orders_module.py`.
2. Regenerate the orders-service module from `ceebc37` with the Linux-portable
   builder (`cce4cf5`, unchanged).
3. RIS transport-output injection + generated-contract audit (builder path,
   unchanged code).
4. `terraform fmt -check -recursive` / `init -backend=false` / `validate` on the
   generated module and the RIS root.
5. Focused builder/injection/contract/installer tests.

The build ran in a temp copy (`/tmp/opencode/ris-pin09-b`, no `.git`, no
`installer/projects`), as in the 07D/08C proofs, so no generated module,
`.terraform`, lockfile or `lambda.zip` entered the worktree. The worktree diff
is limited to the pin files plus this report and the audit entry.

## Pin provenance

The Orders commit was fetched from `https://github.com/maynowak/mays-order-aws.git`
into `/tmp/opencode/pin09-builder`, detached at the pin, working tree clean:

```
ceebc374e35132ee45613b9637909a5b9e77992a fix(iam): let the RIS result consumer receive the optional boundary
```

Commit diff `016cdfd..ceebc37`: 10 files, +340/−4 (agent-transport boundary,
`terraform/main.tf` wiring, `module_builder/catalog.py` binding, tests, docs).
No SQS policy, queue attribute, GSI, HMAC/envelope, `apply_result`, identity or
output change.

## Build and contract evidence

```
python3 -m installer.build_mays_orders_module --project-name ris-dev --force   -> exit 0
python3 -m installer.build_mays_orders_module --check                          -> exit 0
```

| Check | Result |
| --- | --- |
| Manifest pin | `source.commit = ceebc374e35132ee45613b9637909a5b9e77992a`, 41 files written |
| Preset | `orders-service`, 8 child modules incl. `agent_transport` |
| Inputs | 9 (`enable_agent_transport`, `external_cognito`, `lambda_execution_boundary`, `log_retention_days`, `monitoring_enabled`, `order_dispatch_queue_url`, `project_name`, `ris_result_producer_role_arns`, `tags`) |
| Outputs | 23 incl. `sqs_queue_name` |
| RIS transport injection | `results_queue_url`, `results_queue_arn`, `result_hmac_secret_arn` each exactly once, exact refs to `module.agent_transport[0]` |
| Contract audit | `validate_generated_contract` PASS, `check_arn_id_contract` PASS; IAM SQS document has no wildcard (`resources = [var.sqs_queue_arn]`) |
| `lambda/dist/lambda.zip` | `fa0dee9e2381e85ef897daa76635f15d9c7fc2c07592963a8c0cfca98818a983` (unchanged) |

## Terraform evidence

| Step | Result |
| --- | --- |
| Generated module `fmt -check -recursive` | PASS |
| Generated module `init -backend=false` + `validate` | PASS — `Success! The configuration is valid.` |
| RIS root `fmt -check -recursive` | PASS |
| RIS root `init -backend=false` + `validate` | PASS — valid, only pre-existing deprecation warnings |

## Delta vs the previous pin (`016cdfd` build)

A second RIS build of `016cdfd` in `/tmp/opencode/ris-pin09-b-base016`
(exit 0, validate PASS) was diffed against the `ceebc37` build:

- **42/42 module files semantically identical except three `.tf` files** plus
  `module-builder.manifest.json` (timestamp); `lambda.zip` byte-identical.
- `main.tf`: `+ lambda_execution_boundary = var.lambda_execution_boundary`
- `modules/agent_transport/main.tf`: new optional input
  `lambda_execution_boundary` (string, default `""`)
- `modules/agent_transport/lambda.tf`: `permissions_boundary = var.lambda_execution_boundary != "" ? var.lambda_execution_boundary : null`
  on `aws_iam_role.result_consumer`

Reproducibility: the `ceebc37` build is file-identical to the 08C proof copy
(`/tmp/opencode/ris-root08-c-ceebc37`) apart from the manifest timestamp and
`.terraform`.

## Tests (temp copy, `PYTHONDONTWRITEBYTECODE=1`, no pytest cache)

| Command | Result |
| --- | --- |
| `tests/test_build_mays_orders_transport_outputs.py`, `test_build_mays_orders_portability.py`, `test_mo_contract_compat.py`, `test_order_transport_contract.py`, `test_terraform_agent_transport.py` with `MO_ORDERS_SRC=…/mays_order_builder/lambda/src` | **102 passed, 0 failed** |
| `tests/test_ris_installer.py` | **43 passed** |
| `tests/test_project_pinning.py` | **6 passed** |

No pin-value assertion in the suite had to be changed; no test was skipped or
weakened.

## Risks / open decisions (unchanged by this migration)

1. **SQS queue policy (decisive, still open).** `ceebc37` inherits `016cdfd`:
   `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders` with
   account-root principal (Send/Receive/Delete/GetAttributes, no
   `aws:SourceArn`/`SourceAccount`). Verified in the generated module. A plan
   would **UPDATE** the live legacy-wildcard policy, not delete it; the Orders
   main line (`a2fb385`) removes the resource (DELETE). Release/Security
   decision still required before any plan.
2. **Boundary is module-capable but not RIS-wired.** New input defaults to `""`
   → `null`; the RIS root has no `lambda_execution_boundary` variable and does
   not pass one to `module.mays_orders`. Pre-existing gap, not a build defect.
3. Unchanged pre-existing items: empty `ris_result_producer_role_arns` default,
   handler-role boundary, gsi3/gsi4, `apply_result` guard, HMAC allowlist and
   policy-gate coverage of agent-transport resources.
4. The known builder-clone side effect persists: a rebuild rewrites
   `lambda/dist/lambda.zip` in the clone, so an immediate second run trips the
   dirty-worktree guard (pre-existing tooling behaviour, not pin-specific).

## Boundaries

- No AWS credentials used, no STS/discovery, no plan/apply, no state access, no
  SQS/IAM/API Gateway/Cognito/CloudFront mutation, no deployment, no main merge.
- No generated module, `.terraform`, lockfile, `lambda.zip` or clone committed.
- Worktree diff: `installer/mays-orders-builder.pinned.json`,
  `installer/build_mays_orders_module.py`, this report, `docs/AI_AUDITLOG.md`.
