# RIS-MO-ROOT-INTEGRATION-08C — Report

Status: **BUILD VERIFIED — PIN NOT APPROVED** (RIS root integrates the tested
Mays-Orders version `386d741` technically clean; the SQS/IAM queue-policy
decision remains open, so the pin is not approved for migration)

Branch: `integration/ris-mo-root-08c` (base `e237b45`, includes Linux builder
`cce4cf5`)
Orders test version: `386d74169aa567a1e7c2f0aef4c602695d6e755d`
(`fix(mo): keep agent transport contract in preset and custom selection`,
child of `016cdfd`)

No main merge, no Terraform plan/apply, no AWS access or mutation, no
deployment. The committed builder pin (`016cdfd`) is unchanged; the pin
override and all generated artifacts exist only in
`/tmp/opencode/ris-root08-c`.

## Method

- Copied the worktree to `/tmp/opencode/ris-root08-c` (no `.git`, no
  `installer/projects`) and cloned the Orders test version locally:
  `git clone <orders-pin08-a worktree> installer/projects/mays_order_builder`
  → clean detached `386d741`. No network, no write to the Orders worktree
  (read-only clone source; its own dirty files belong to Agent A and were
  left untouched).
- Pin override **only in the temp copy**:
  `installer/mays-orders-builder.pinned.json` = `386d741…` and the matching
  `PINNED_COMMIT` constant. Committed pin in the real worktree stays
  `016cdfd…` (`git status` clean, `git diff` empty).
- Ran the RIS wrapper end-to-end:
  `python3 -m installer.build_mays_orders_module --project-name ris-dev --force`.
  The wrapper's `ensure_repo()` checkout/fetch of the pinned commit succeeds
  inside the temp clone; the generated module is installed at
  `terraform/modules/mays_orders`.

## Result 1 — module build and RIS contract (PASS)

```
Build OK
Preset: orders-service; child modules: agent_transport, api, cognito, dynamodb,
        iam, lambda, sqs, sqs-worker
RIS transport outputs injected: results_queue_url, results_queue_arn,
        result_hmac_secret_arn
Inputs OK: 9 (enable_agent_transport, external_cognito, lambda_execution_boundary,
        log_retention_days, monitoring_enabled, order_dispatch_queue_url,
        project_name, ris_result_producer_role_arns, tags)
Outputs OK: 23 (incl. sqs_queue_name = module.sqs.queue_name)
IAM contract OK: sqs_enabled present, 2 gate-dependent counts
IAM SQS document OK: no wildcard, resources = [var.sqs_queue_arn]
```

- `module-builder.manifest.json` records
  `source.commit = 386d74169aa567a1e7c2f0aef4c602695d6e755d`, 42 written files.
- RIS dispatch env patch (`order_dispatch_queue_url` / `ORDER_DISPATCH_QUEUE_URL`)
  applied without marker mismatch against `386d741`.
- Independent contract audit:
  `validate_generated_contract(terraform/modules/mays_orders)` and
  `check_arn_id_contract(terraform)` → PASS.
- Root wiring audit: all 9 real `module.mays_orders[0].<output>` references in
  `terraform/main.tf` are declared by the module
  (`api_gateway_id`, `api_gateway_stage_name`, `dynamodb_table_arn`,
  `dynamodb_table_name`, `iam_handler_role_name`, `lambda_function_name`,
  `sqs_queue_arn`, `sqs_queue_name`, `sqs_queue_url`); the `moved` block
  reference is not an output. Root passes only declared inputs (plus native
  `source`/`count`); `external_cognito` and `lambda_execution_boundary` stay
  unused/default, unchanged.

## Result 2 — Terraform (PASS)

Generated module (temp copy):

| Check | Result |
| --- | --- |
| `terraform fmt -check -recursive` | PASS |
| `terraform init -backend=false -input=false -no-color` | PASS (aws 6.74.0, time 0.14.2) |
| `terraform validate -no-color` | `Success! The configuration is valid.` |

RIS root (`/tmp/opencode/ris-root08-c/terraform`):

| Check | Result |
| --- | --- |
| `terraform fmt -check -recursive` | PASS |
| `terraform init -backend=false -input=false -no-color` | PASS (all modules installed, incl. `modules/mays_orders`) |
| `terraform validate -no-color` | `Success! The configuration is valid, but there were some validation warnings` |

Root warnings are pre-existing style/deprecation notices (`hash_key` deprecated,
26 more); no errors. This is the first run in the current line where RIS root
validate passes with a real generated `mays_orders` module present; the earlier
root failure was the missing/incomplete gitignored module, not RIS wiring.

## Result 3 — tests (PASS)

RIS worktree, `PYTHONDONTWRITEBYTECODE=1`, no pytest cache:

```
tests/test_build_mays_orders_transport_outputs.py
tests/test_build_mays_orders_portability.py
tests/test_mo_contract_compat.py
tests/test_order_transport_contract.py
tests/test_terraform_agent_transport.py      -> 93 passed, 9 skipped
```

The 9 skips are `test_mo_contract_compat.py` (`MO_ORDERS_SRC not set`). Re-run
with `MO_ORDERS_SRC=<orders-pin08-a>/lambda/src` (the `386d741` sources):
**9 passed, 0 failed** → combined **102 passed / 0 failed**.

Additional:

```
tests/test_ris_installer.py                   -> 43 passed
transport/contract subset (69 tests)          -> 69 passed
```

## Result 4 — reproducibility

Two full builds in the same temp copy, source-file hash set (42 files, `.tf`,
`.json`, `.md`, `.py`, `.zip`; `.terraform` and lockfile excluded):

- 41 of 42 files byte-identical; only `module-builder.manifest.json` differs
  (`generated_at` timestamp).
- `lambda/dist/lambda.zip` rebuilt deterministically
  (`fa0dee9e2381e85ef897daa76635f15d9c7fc2c07592963a8c0cfca98818a983` in both
  builds). Note: this differs from the zip committed in the Orders clone
  (`48ddd5e5…`) because the builder regenerates it.
- Builder tooling side effect (pre-existing, not pin-specific): after a build
  the builder clone's `lambda/dist/lambda.zip` is modified, so an immediate
  second run fails `ensure_repo()`'s dirty-worktree guard until the clone is
  restored (`git checkout -- .`). Workaround documented, no code change made.

## Error classification

No builder, module or RIS-wiring error occurred: build, transport-output
injection, contract audit, module/root `fmt`/`init`/`validate` and the focused
test suites all pass at `386d741`. The only friction is the builder-clone
artifact side effect above, classified as **builder tooling behavior**
(pre-existing, cosmetic, no product impact).

## Open items — why the pin is not approved

1. **SQS queue policy (decisive).** `386d741` is a child of `016cdfd` and still
   emits `module.mays_orders[0].module.sqs.aws_sqs_queue_policy.orders`:
   `Principal = arn:aws:iam::<account>:root`, actions
   `SendMessage/ReceiveMessage/DeleteMessage/GetQueueAttributes`, no
   `aws:SourceArn`/`SourceAccount` condition. The main line (`a2fb385`) removes
   this resource and relies on IAM identity policies. Applying `386d741` would
   UPDATE the live wildcard policy
   (`ris-dev-mays-orders-orders-queue`) to an account-root principal instead of
   deleting it — better than the legacy wildcard, but still a broad queue
   policy and a policy decision, not a build defect. Forensics 11 classifies
   the live policy `LEGACY UNSAFE`; the remediation decision is pending.
2. **Result-queue principal.** `modules/agent_transport` sets
   `Principal = var.ris_result_producer_role_arns` (default `[]`). Enabling
   `enable_agent_transport` without a non-empty allowlist yields an empty
   principal. Pre-existing, unchanged by this verification.
3. **Lambda execution boundary** remains the account-specific
   `arn:aws:iam::240571105849:policy/Mays-Orders-Lambda-Execution-Boundary`
   (documented known limitation; unverified for other accounts).
4. Pre-existing items not re-verified here: gsi3 vs gsi4 ownership/PII,
   `apply_result` RESULT_WRITE_GUARD, HMAC envelope allowlist, live
   `agent_dispatch`/wildcard provenance.

None of these block technical integration; all are policy/security decisions
outside this build proof.

## Boundaries

- No AWS credentials used, no STS/discovery, no plan/apply, no state access or
  write, no SQS/IAM/API Gateway/Cognito/CloudFront mutation, no deployment.
- No generated module, `.terraform`, lockfile, or artifact was added to Git;
  the worktree tree is clean apart from this report and the audit-log entry.
- Committed builder pin and all RIS source files unchanged.
