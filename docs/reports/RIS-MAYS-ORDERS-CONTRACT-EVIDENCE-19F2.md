# RIS / Mays-Orders Contract Evidence Index — 19F2

**Evidence baseline:** RIS `253e929e635bc4b79fe25773dd09e3f68c329af5`; Mays-Orders
generated-module source `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`.
RC4 `v0.6.0-rc.1` (`5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`) is only a
candidate and was not checked out or tested. Test IDs below refer to source
test files/classes/method families; the runner's JSON contains per-group counts
and output tails. Module contracts already proven by Mays originals are reused,
not reimplemented as duplicate RIS tests.

| Contract / group | Owner and source | Original test evidence (Mays) | RIS integration gate / evidence | Result and remaining RIS-specific proof |
|---|---|---|---|---|
| RC4 create request, validation, order description | Mays `lambda/src/validation.py`, `order_service.py`, `order_types.py` | `lambda/tests/test_validation.py`; `test_order_description.py`; `test_agent_order.py` | `XREPO_CONTRACT`: `tests/test_cross_repo_mo_contract.py`, `test_agent_order_body.py`, `test_agent_order_order_description.py` | Mays Lambda PASS; XRepo 133 passed + 4 subtests. RIS adapter body/translation remains RIS-owned. |
| Order ownership, tenant/owner isolation | Mays `lambda/src/identity.py`, `order_service.py` | `lambda/tests/test_ownership.py`; `test_agent_order_projection.py` | `XREPO_CONTRACT`; RIS `tests/test_orders_adapter.py`, `test_mo_contract_compat.py` | Mays Lambda PASS; XRepo PASS. Deployment identity/pool wiring is not inferred from unit tests. |
| Idempotency key, duplicate delivery, concurrency | Mays `lambda/src/order_service.py`, `dispatch.py`, `result_consumer.py` | `lambda/tests/test_dispatch.py` (`TestDispatchBinding`, `TestSendState`); `test_result_handoff.py` (`TestResultIngestion`) | `XREPO_CONTRACT`; `XREPO_E2E` and RIS adapter tests | Mays Lambda PASS; XRepo E2E 39 passed. Live contention/operational behavior NOT RUN. |
| Dispatch envelope, ContextRef, processing attempt | Mays `lambda/src/dispatch.py`, `agent_order.py` | `lambda/tests/test_dispatch.py`; `test_agent_order.py` | `XREPO_CONTRACT`: `test_order_transport_contract.py`, `test_mo_contract_compat.py`; `XREPO_E2E`: `test_mo_dispatch_handoff.py`, `test_agent_order_dispatch_e2e.py` | Contract 133+4; E2E 39 passed. RIS queue/IAM/deployment configuration remains separately gated. |
| Delivery, retry, `ORDER_RESULT`, error behavior | Mays `lambda/src/result_envelope.py`, `result_consumer.py`, `result_handler.py` | `lambda/tests/test_result_handoff.py` (`TestResultContract`, `TestResultIngestion`, `TestConsumerBoundary`); `test_result_consumer_lambda.py` | `XREPO_CONTRACT`; `XREPO_E2E`; generated module tests | XRepo PASS; generated artifact 9 passed. Real queue delivery/retry not executed. |
| HMAC signing and verification | Mays `lambda/src/result_envelope.py`, `result_consumer.py` | `lambda/tests/test_result_handoff.py` (`TestConsumerBoundary`); `test_result_consumer_lambda.py` (`TestRejections`) | RIS `tests/test_order_transport_contract.py`, `test_cross_repo_mo_contract.py` | Cross-repo contracts PASS. Secret provisioning/rotation in AWS not tested. |
| Lifecycle transitions and completion | Mays `lambda/src/order_service.py`, `state_machine.py` | `lambda/tests/test_state_machine.py`; `test_order_service.py` (`TestUpdateOrderStatus`); `test_dispatch.py`; `test_result_handoff.py` | XRepo E2E + RIS `tests/test_mo_dispatch_handoff.py` | Synthetic local roundtrip PASS; no live lifecycle invocations. |
| Privacy/erasure, owner-only projection | Mays `lambda/src/order_service.py`, `agent_order.py` | `lambda/tests/test_ownership.py`; `test_agent_order_projection.py`; `test_order_description.py` | RIS privacy/erasure and adapter suites in `RIS_NATIVE`; XRepo contracts | Mays Lambda PASS. RIS Native includes five independent baseline failures listed in QA report. |
| Generated-module inputs/outputs and artifact | Mays `module_builder/`, `terraform/` | `module_builder/tests/test_module_builder.py`; `module_builder/tests/test_orders_service.py` (suite selection is `module_builder/tests`) | `MODULE_BUILD`: RIS `tests/test_build_mays_orders_transport_outputs.py`, `test_generated_module_artifact.py` | RIS builder contracts 57 passed; artifact 9 passed and manifest/ZIP provenance verified. Mays builder 86 passed, 14 Windows failures; no Linux PASS inferred. |
| Installer and upgrade contracts | Mays `installer/`, `Mays-Order-AWS-installer` | `installer/tests/test_installer.py` (81 tests) | `MODULE_BUILD`; version map + fail-closed `UPGRADE_GATE` | 70 passed, 11 errors on Windows due to Linux paths/`python3`. Candidate tests not run; upgrade gate BLOCKED. |
| Seed tools | Mays `scripts/seed_orders.py`, import/cleanup scripts | `scripts/tests/` | `MAYS_MODULE` | 28 passed. No production data or AWS endpoint used. |
| Module-builder QA | Mays `module_builder/` | Original `module_builder/tests/` | `MODULE_BUILD` / `UPGRADE_GATE` | 86 passed, 14 failed on Windows path representation (`\\` vs `/`); test suite remains intact. Re-run on project-supported Linux before calling platform status resolved. |
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
