# RIS-ANALYSIS-16C2-QA2 — Generated Module Contract Alignment

**Date:** 2026-11-22
**Base:** `eac2a98` on `feature/ris-analysis-integration-07`
**Scope:** builder/contract correction and isolated module verification.
**No Terraform apply, AWS mutation, target-module replacement, main merge or
production deployment.**

**Verdict:** **Builder/contract drift fixed.** The isolated module has 23
outputs and passes fmt/init/validate. The applied target module remains
untouched (20 outputs) and now intentionally fails the stricter builder check
until a future reviewed rebuild. **No immediate infrastructure change is
required**; a later rebuild would change outputs only.

---

## 1. Cause analysis

`installer/build_mays_orders_module.py` contained
`inject_transport_outputs()`, but the active `build_module()` never called it.
The contract validator required only the 20 Orders-Service outputs. The test
`test_generated_module_artifact` expected three additional outputs:

- `results_queue_url`
- `results_queue_arn`
- `result_hmac_secret_arn`

### Ownership decision

The result queue, DLQ and HMAC secret are created by
`modules/agent_transport` **inside the generated Mays module**. The generated
module therefore owns those resources and should re-export their identifiers.
The RIS root consumes the identifiers through its own
`order_result_queue_url` / `order_result_queue_arn` /
`order_result_secret_arn` variables; it does not own a second queue.

The outputs are **references only**:

```hcl
output "results_queue_url" {
  value = try(module.agent_transport[0].results_queue_url, "")
}
output "results_queue_arn" {
  value = try(module.agent_transport[0].results_queue_arn, "")
}
output "result_hmac_secret_arn" {
  value = try(module.agent_transport[0].result_hmac_secret_arn, "")
}
```

No resource, IAM permission, queue, table or secret value is added.

### Version/ownership contract

| Artifact | Pin/identity |
|---|---|
| Builder checkout | `016cdfd` (clean) |
| Builder pin file | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Generated target source | `016cdfd6ac62565dcec9a2fee78cb898fb919e59` |
| Composite clone pin | `5cf50a0` (separate fixture) |

The builder and generated target are on `016cdfd`; `5cf50a0` remains the
composite/clone fixture. No version was silently upgraded.

## 2. Minimal builder fix

- `build_module()` now calls `inject_transport_outputs(TEMP_MODULE_DIR)`
  **before** `validate_generated_contract()`.
- The contract requires **23** outputs and includes the three names.
- `validate_transport_outputs()` verifies each output exists exactly once and
  references the correct `module.agent_transport[0]` identifier.
- Duplicate/upstream collisions fail closed before any write.
- The applied `terraform/modules/mays_orders` target was **not edited and not
  replaced**.

New negative tests (`tests/test_build_mays_orders_transport_outputs.py`,
**8 passed**):

- three outputs injected exactly once and deterministically;
- duplicate injection fails closed;
- upstream output collision fails closed;
- missing output rejected;
- duplicate output rejected;
- wrong reference rejected;
- output block contains no resource/data/IAM/secret-value construct;
- active build calls injection before validation and requires 23 outputs.

## 3. Isolated generation and Terraform validation

Generated in:
`C:/Users/DCI-Student/AppData/Local/Temp/opencode/qa2-temp-module`

| Check | Result |
|---|---|
| `module_builder build --preset orders-service` | PASS |
| RIS transport output injection | PASS |
| Generated contract (23 outputs) | PASS |
| `terraform fmt -recursive` / `fmt -check` | PASS |
| `terraform init -backend=false` | PASS |
| `terraform validate` | PASS |

### Before/after hashes

| File | Applied target | Isolated temp |
|---|---|---|
| `outputs.tf` | `6f9b88b5…` (20 outputs) | `88483db4…` (23 outputs) |
| Tree hash | `1cb135ad…` | `73c2ec6d…` |
| `main.tf` | `adc6d2be…` | `adc6d2be…` |
| `variables.tf` | `ca45056f…` | `ca45056f…` |
| `lambda/dist/lambda.zip` | `48ddd5e5…` | `48ddd5e5…` |

The only meaningful module-file difference is the additive `outputs.tf`
block; `module-builder.manifest.json` differs only in `generated_at`. The
target has pre-existing `__pycache__` files from local imports; they are not
generated-module content. `main.tf`, `variables.tf` and the Lambda zip are
byte-identical.

## 4. Test acceptance

| Suite | Result |
|---|---|
| QA2 contract tests | **8 passed** |
| Isolated module + Mays extended fixture | **55 passed** |
| Default full `tests/` suite | **3193 passed, 134 skipped, 0 failed, 441 subtests** |
| Full suite with all local fixtures + fixed temp module | **3259 passed, 68 skipped, 0 failed, 441 subtests** |
| Five agent packages | **all VALIDATED** |
| Builder `--check` on isolated fixed module | **PASS** |
| Builder `--check` on applied target | **FAIL_EXPECTED** (target still has 20 outputs) |

The previously failing
`test_generated_module_artifact::test_ris_transport_outputs_are_exposed_additively`
now passes against the isolated fixed module; the fixture suite has **0
failures**.

### Python 3.14 runtime regression

The full suite was repeated with the Lambda runtime version:

`C:/Users/DCI-Student/AppData/Local/Temp/opencode/ris-qa2-venv314`
(Python **3.14.10**, pytest 9.2.0, pytest-subtests 0.15.0, requests 2.34.2,
moto 5.2.5, boto3/botocore 1.44.9).

| Suite | Result |
|---|---|
| Default full suite | **3193 passed, 134 skipped, 0 failed, 441 subtests** |
| Fixture full suite | **3259 passed, 68 skipped, 0 failed, 441 subtests** |

The 3.14 results are identical to the 3.15 run; no runtime-specific failure.

Comparison with QA1:

- QA1 default: 3185 passed / 134 skipped / 0 failed.
- QA1 fixture: 3250 passed / 68 skipped / **1 failed**.
- QA2: 3193 / 134 / 0 and 3259 / 68 / 0, on both Python 3.15 and 3.14.

## 5. Compatibility and whether infrastructure must change

**No immediate infrastructure change is required for QA2.**

- The applied target module is intentionally unchanged.
- The current RIS root does **not** consume these module outputs; it receives
  the queue/ARN/secret through its own variables.
- A future reviewed module rebuild/apply would add the three outputs to state
  only. It would **not** create, delete, replace or re-permission a queue,
  table, secret, Lambda or Cognito resource.
- If the RIS root later switches to consuming the module outputs, that is a
  separate reviewed plan; it is not required for the current runtime.

The target `--check` failure is the expected signal that the deployed/generated
module files are older than the new builder contract. It must **not** be fixed
by hand-editing or automatically replacing the target.

## 6. Boundaries

- No Terraform apply, AWS mutation, module deployment or target replacement.
- No synthetic activation B, no Mays transport C, no main merge or production
  deployment.
- The module was generated only in an isolated temp directory.

Machine-readable evidence:
`docs/reports/RIS-ANALYSIS-16C2-QA2-MODULE-CONTRACT.json`.
