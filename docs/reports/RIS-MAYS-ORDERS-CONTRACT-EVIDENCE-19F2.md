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

The initial 19F3 RIS Native result was 3,278 passed / 3 failed / 142 skipped /
450 subtests. The three assertions identified the implemented APIProfile
binding operation missing from canonical OpenAPI. 19F4 documented the existing
operation (no runtime changes); its original three tests now pass, as does the
relevant API/OpenAPI group (87 passed + 322 subtests). See the 19F4 report.

Candidate-generated artifact validation reported undeclared
`privacy_secret_enabled`, `privacy_kms_key_arn`, `sqs_visibility_timeout_seconds`,
`sqs_message_retention_seconds`, `sqs_dlq_message_retention_seconds`,
`sqs_max_receive_count`, and `deployment_version`; plus undeclared
`module.privacy_secret` references. The Mays Builder/Generated Module owners
must correct these and write the full 40-character source SHA in a separate
Mays-Orders task.

### 19F4 addendum — contract closure, reproducible worker candidate, and RC4 ownership

- **OpenAPI:** Commit `06f9181` records the implemented `POST
  /v1/apiprofiles/{apiProfileId}/binding` operation in canonical OpenAPI. The
  original three route assertions pass; relevant API/OpenAPI tests: 87 passed,
  322 subtests passed. No handler/runtime behavior changed.
- **Bundle root cause:** The historical worker archive has 115 entries. All
  uncompressed entries match current Git sources after CRLF→LF normalization;
  order, fixed timestamps, modes, and compression method were stable. A mixed
  Windows checkout caused different source bytes, and platform-specific DEFLATE
  implementations (Windows zlib-ng vs Ubuntu zlib), plus platform-dependent
  ZIP `create_system` markers also changed archive bytes. Commits `2938021` and
  `f110f97` use stored entries and explicitly canonicalize ZIP metadata. Two
  independent clean Windows and Ubuntu builds match: worker
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`,
  analysis `370890d459488304481d99255cfa6a2891b5f19a8c5df2723556905195c7c621`,
  reader `bea4c3e59666bed8ad071ad4e405bcdfd57dafdac68096ce648667f0effb1b41`.
  Cross-platform hashes are recorded in evidence
  `bundle-reproducibility-ubuntu-45966656833.json` (final run).
  Historical worker SHA remains recorded and is not overwritten; new hash is
  review-only and requires separate pin approval.
- **Current XRepo:** exact reruns pass: contract 133 passed + 4 subtests; E2E 39
  passed. Candidate reruns reproduce the prior failures: contract 120/13 + 4
  subtests; E2E 3/36.
- **RC4 root cause:** group failures by source cause, not individual tests:
  (1) five required transport/consumer modules are missing in RC4 and cause
  import/contract/round-trip failures; (2) RC4 validation rejects
  `orderDescription`, causing four create-contract failures; (3) its generated
  Terraform has undeclared variables and `module.privacy_secret` references,
  the manifest truncates source SHA to seven characters, and backend-free
  validate fails; (4) four original builder policy-gate tests fail on Ubuntu
  because the runner lacked their required `/tmp/opencode` and fixed checkout
  aliases. QA workflow now provisions these ephemeral paths; current and RC4
  original builder/installer suites pass. This is resolved test-environment
  setup, not a candidate source blocker. RIS will not drop order data, bypass
  HMAC/idempotency/owner checks, or add an unversioned adapter. Executable task:
  `MO-RC4-RIS-COMPATIBILITY-FIX.md`.
- **Ubuntu evidence:** QA-only run `45965830933` verified cross-platform bundle
  hashes, current Mays originals (240 Lambda, 100 builder + 6 subtests, installer
  81, seed 28, Cognito 2), current XRepo, and current generated module/validate.
  RC4 original Mays suites pass (440 Lambda, 129 builder, installer 81, seed 28,
  Cognito 2); RC4 generated Terraform and XRepo remain failures. Final run
  `45966656833` adds the missing RIS native test alias; its current FULL and
  candidate UPGRADE_GATE results are recorded in the 19F4 report/results.
- **Worker regression:** `tests/test_lambda_packaging.py`, ecosystem bundle
  wiring, and fresh-plan regression: 26 passed, 2 credential-gated skips, 4
  subtests. New worker artifact is a review candidate only. No worker deployment
  pin was updated.

See `RIS-MAYS-ORDERS-COMPATIBILITY-RESOLUTION-19F4.md` and its machine-readable
results for release gates, run identities, safety counters, and final platform
classifications.
