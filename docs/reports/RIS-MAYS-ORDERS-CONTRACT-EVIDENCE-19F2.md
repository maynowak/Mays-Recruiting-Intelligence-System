# RIS / Mays-Orders Contract Evidence Index — 19F2 / 19F3 Update

**Original evidence baseline:** RIS `253e929e635bc4b79fe25773dd09e3f68c329af5`; Mays-Orders
generated-module source `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`. The original
19F2 statement that RC4 had not been checked out/tested records the state at that
checkpoint. 19F3 separately verified and tested exact candidate
`v0.6.0-rc.1` / `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`.

Test IDs below refer to source test files/classes/method families; current and
candidate JSON contain per-group counts and output tails. Module contracts
already proven by Mays originals are reused, not reimplemented as duplicate RIS
tests.

| Contract / group | Owner and source | Original test evidence (Mays) | RIS integration gate / evidence | Result and remaining RIS-specific proof |
|---|---|---|---|---|
| RC4 create request, validation, order description | Mays `lambda/src/validation.py`, `order_service.py`, `order_types.py` | `lambda/tests/test_validation.py`; `test_order_description.py`; `test_agent_order.py` | `XREPO_CONTRACT`: `tests/test_cross_repo_mo_contract.py`, `test_agent_order_body.py`, `test_agent_order_order_description.py` | Mays Lambda PASS; XRepo 133 passed + 4 subtests. RIS adapter body/translation remains RIS-owned. |
| Order ownership, tenant/owner isolation | Mays `lambda/src/identity.py`, `order_service.py` | `lambda/tests/test_ownership.py`; `test_agent_order_projection.py` | `XREPO_CONTRACT`; RIS `tests/test_orders_adapter.py`, `test_mo_contract_compat.py` | Mays Lambda PASS; XRepo PASS. Deployment identity/pool wiring is not inferred from unit tests. |
| Idempotency key, duplicate delivery, concurrency | Mays `lambda/src/order_service.py`, `dispatch.py`, `result_consumer.py` | `lambda/tests/test_dispatch.py` (`TestDispatchBinding`, `TestSendState`); `test_result_handoff.py` (`TestResultIngestion`) | `XREPO_CONTRACT`; `XREPO_E2E` and RIS adapter tests | Mays Lambda PASS; XRepo E2E 39 passed. Live contention/operational behavior NOT RUN. |
| Dispatch envelope, ContextRef, processing attempt | Mays `lambda/src/dispatch.py`, `agent_order.py` | `lambda/tests/test_dispatch.py`; `test_agent_order.py` | `XREPO_CONTRACT`: `test_order_transport_contract.py`, `test_mo_contract_compat.py`; `XREPO_E2E`: `test_mo_dispatch_handoff.py`, `test_agent_order_dispatch_e2e.py` | Contract 133+4; E2E 39 passed. RIS queue/IAM/deployment configuration remains separately gated. |
| Delivery, retry, `ORDER_RESULT`, error behavior | Mays `lambda/src/result_envelope.py`, `result_consumer.py`, `result_handler.py` | `lambda/tests/test_result_handoff.py` (`TestResultContract`, `TestResultIngestion`, `TestConsumerBoundary`); `test_result_consumer_lambda.py` | `XREPO_CONTRACT`; `XREPO_E2E`; generated module tests | XRepo PASS; generated artifact 9 passed. Real queue delivery/retry not executed. |
| HMAC signing and verification | Mays `lambda/src/result_envelope.py`, `result_consumer.py` | `lambda/tests/test_result_handoff.py` (`TestConsumerBoundary`); `test_result_consumer_lambda.py` (`TestRejections`) | RIS `tests/test_order_transport_contract.py`, `test_cross_repo_mo_contract.py` | Cross-repo contracts PASS. Secret provisioning/rotation in AWS not tested. |
| Lifecycle transitions and completion | Mays `lambda/src/order_service.py`, `state_machine.py` | `lambda/tests/test_state_machine.py`; `test_order_service.py` (`TestUpdateOrderStatus`); `test_dispatch.py`; `test_result_handoff.py` | XRepo E2E + RIS `tests/test_mo_dispatch_handoff.py` | Synthetic local roundtrip PASS; no live lifecycle invocations. |
| Privacy/erasure, owner-only projection | Mays `lambda/src/order_service.py`, `agent_order.py` | `lambda/tests/test_ownership.py`; `test_agent_order_projection.py`; `test_order_description.py` | RIS privacy/erasure and adapter suites in `RIS_NATIVE`; XRepo contracts | Current Mays Lambda PASS. After A1/A2, RIS Native has 3 remaining OpenAPI-route failures; candidate integration failures are in the 19F3 addendum. |
| Generated-module inputs/outputs and artifact | Mays `module_builder/`, `terraform/` | `module_builder/tests/` | `MODULE_BUILD`: RIS `tests/test_build_mays_orders_transport_outputs.py`, `test_generated_module_artifact.py` | Current artifact: RIS builder 57 PASS, generated contract 9 PASS; Mays builder 86/14 Windows results. Candidate generated module: Terraform validate fails and manifest uses abbreviated `5bc154e`; current RIS artifact expectations are incompatible. |
| Installer and upgrade contracts | Mays `installer/`, `Mays-Order-AWS-installer` | `installer/tests/test_installer.py` (81 tests) | `MODULE_BUILD`; version map + fail-closed `UPGRADE_GATE` | Current 69 pass / 11 errors / 1 skip; candidate 71 pass / 9 errors / 1 skip on Windows. Linux reference run unavailable locally; results are not extrapolated. |
| Seed tools | Mays `scripts/seed_orders.py`, import/cleanup scripts | `scripts/tests/` | `MAYS_MODULE` | 28 passed. No production data or AWS endpoint used. |
| Module-builder QA | Mays `module_builder/` | Original `module_builder/tests/` | `MODULE_BUILD` / `UPGRADE_GATE` | Current: 86 pass / 14 Windows failures. Candidate after rebuilding its Lambda ZIP in an isolated exact-commit clone: 111 pass / 18 Windows failures (POSIX path and symlink assumptions). Neither is a Linux result. |
| Terraform validation / live harnesses | Mays `terraform/`, `tests/` and documented E2E harness | Terraform/module-builder validations; Mays `tests/test_e2e_async_order.py` requires deployed infrastructure and credentials | `LIVE` locked; local generated artifact only | Live harness inventory only; NOT_RUN. No Terraform plan/apply/init or AWS calls. |

## Provenance and reuse rules

- Current test version is the generated module's source commit `db4f9e7`, cross-checked
  against `installer/mays-orders-builder.pinned.json`, the builder constant, and the
  generated manifest. `installer/mays-orders-clone.pinned.json` (`5cf50a0`) is a
  distinct legacy clone pin and is not substituted for builder provenance.
- Mays original tests run from a temporary detached local clone at the exact SHA;
  this preserves `.git`-based source discovery and isolates test side effects from
  the ignored source clone. RIS and Mays use separate child processes.
- A module upgrade requires candidate original tests, generated module contracts,
  RIS XRepo contract and synthetic E2E profiles, and verified candidate artifact
  provenance. A module PASS does not establish deployment readiness.

## 19F3 addendum — current versus RC4 candidate

| Contract | Current integrated `db4f9e7` | Candidate RC4 `5bc154e` | 19F3 interpretation |
|---|---|---|---|
| Candidate remote/tag provenance | N/A | Remote `https://github.com/maynowak/mays-order-aws.git`; tag object `79628819717e4609d828581dff53055f2b32f8ec`; peeled commit `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` | Verified; separate clean detached checkout; no main-HEAD substitution |
| Order Core / Lambda | 240 pass | 440 pass after isolated runner included both `lambda/` and `lambda/src` in Python path | Candidate Lambda originals pass on Windows |
| Builder / Installer | Builder 86/14; installer 69/11/1 | Builder 111/18; installer 71/9/1 | Windows-only results; documented Linux reference unavailable locally |
| RIS Cross-Repository Contract | 133 pass + 4 subtests | 120 pass / 13 fail + 4 subtests | Candidate fails current RIS transport/schema compatibility, including `orderDescription` rejected as an unknown create field |
| RIS synthetic E2E | 39 pass | 3 pass / 36 fail | Candidate lacks expected result-consumer imports and round-trip behaviors |
| Candidate-generated module | N/A | Terraform fmt PASS; `init -backend=false` PASS; validate FAIL; Generated Module Contract 2 pass / 7 fail | Candidate module contract blocked; exact source SHA is abbreviated in builder manifest and generated Terraform has unresolved references |

The current RIS Native result is now 3,278 passed / 3 failed / 142 skipped /
450 subtests; A1's historical-hash failure and A2's AWS-profile fixture failure
are resolved. The three remaining assertions identify one discrepancy:
`POST /v1/apiprofiles/{apiProfileId}/binding` is in Terraform, the dispatcher,
and `docs/API/API-STANDARD.md`, but absent from canonical
`docs/api/openapi-platform.yaml`. The assertions are correct. This belongs to
the RIS API/OpenAPI contract and is tracked in a separate fix request; 19F3 does
not change runtime, API contract, or security behavior.

Candidate-generated artifact validation reported undeclared
`privacy_secret_enabled`, `privacy_kms_key_arn`, `sqs_visibility_timeout_seconds`,
`sqs_message_retention_seconds`, `sqs_dlq_message_retention_seconds`,
`sqs_max_receive_count`, and `deployment_version`; plus undeclared
`module.privacy_secret` references. The Mays Builder/Generated Module owners
must correct these and write the full 40-character source SHA in a separate
Mays-Orders task.

### Worker bundle reproducibility (independent deployment gate)

The required/current worker ZIP is `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`.
A disposable checkout with `core.autocrlf=false` rebuilt it as
`4d880b4856067b7d8b9d17e8a0257abf49d6208f9fb1743b711f516091ce928a`; a
disposable CRLF checkout rebuilt it as
`747b749ed674aad40954b85a2d628631131684230d4145e52e627e4ed58bd7b5`. Neither
reproduced the required digest. ZIP member line endings differ (LF in the
controlled LF rebuild, CRLF in the existing artifact). The cause is unresolved;
`WORKER_DEPLOYMENT_READINESS=BLOCKED` pending reproducibility/provenance review.
No tracked source or bundle was changed by these checks.
