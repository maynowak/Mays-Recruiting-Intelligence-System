# RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01 — Execution

**Status:** `PARTIAL — A/B implemented for Addition reference capability; C–F pending/blocked`
**Branch:** `feature/ris-dsgvo-compliance-01`
**Baseline:** `db2e09419931fc64e9377aed8fdd35c720023045`
**Orders pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (unchanged)

## Checkpoint A — capability privacy contrac

Implemented the typed `RIS-CAPABILITY-PRIVACY/1` declaration and separate evidence record in `agents/ecosystem/privacy_contract.py`; added additive descriptor fields in `agents/ecosystem/registry.py`; and required supported version, complete declaration, capability/version/digest binding, exact source/artifact hashes, and complete non-skipped tests in Eligibility. The worker selection path already consumes Eligibility. The legacy direct `AgentExecutor` now resolves the descriptor from the Ecosystem registry and applies the same Eligibility decision; missing registration/evidence denies before invoking the handler.

Synthetic contract coverage: `tests/test_ecosystem_privacy_contract.py` — **7 passed**. Covered missing declaration/evidence, valid evidence, source mismatch, skipped evidence, unsupported version, declaration digest sensitivity, and direct execution authorization/denial.

Compatibility/regression checks expose exactly **25** legacy failures, not a green regression:

| Suite | Failures | Individual failing tests | Classification |
|---|---:|---|---|
| `test_agent_status_normalization.py` | 2 | `TestEligibilityStatus.test_active_eligible`; `TestActiveBehaviorIntact.test_reference_echo_still_runs` | ACTIVE fixture has no evidence; reference echo policy/evidence is not approved. |
| `test_multi_agent_ecosystem.py` | 6 | `TestMultiRouting.test_a_dummy_a`, `test_b_dummy_b`, `test_c_ats`, `test_d_reference`; `TestSharedQueueSimulation.test_duplicate_per_agent_no_new_run`, `test_four_items_each_gets_right_agent_isolated_results` | Dummy policies/evidence absent; ATS policy is owner-blocked; reference echo is unclassified. |
| `test_worker_entitlement_recheck.py` | 12 | `test_01_valid_runs`, `test_02_missing_denied_consumed`, `test_03_expired_denied`, `test_04_not_yet_valid_denied`, `test_05_wrong_user_denied`, `test_06_wrong_tenant_denied`, `test_07_wrong_agent_denied`, `test_09_tampered_tenant_denied`, `test_11_missing_user_denied_no_guess`, `test_12_revoked_before_retry_denied`, `test_16_transient_is_not_denied`, `test_17_duplicate_skips_recheck_keeps_idempotency` | All use reference.echo; Privacy Eligibility blocks before intended entitlement assertions. Authorization/idempotency regression remains unverified until a valid synthetic reference-agent package/evidence exists. |
| `test_agent_body.py` | 5 | `TestAgentBodyIntegrationHarness.test_happy_path_with_reference_agent`, `test_full_agent_body_with_reference_agent`; `TestAgentExecutor.test_executor_adds_metrics`; `TestAgentBody.test_execute_with_handler`; `TestReferenceAgentIntegration.test_echo_capability_workflow` | Two reference cases lack evidence; two generic work-type cases have no capability/descriptor; metrics case also lacks capability. No arbitrary injected-true callback is acceptable. |

No test was converted from success to denied to claim recovery. These 25 failures remain blockers; unknown capability policies/evidence are not fabricated. Addition's own original suite is recovered and passes with generated evidence.

## Remaining work and blockers

- **B:** complete for Addition only. Installer validates its typed policy, rebuilds the manifest-declared deterministic agent bundle, checks required runtime entries, executes the declared original/privacy test selection, and binds report, contract hash, source-file digest, source commit, test selection and artifact SHA. Cached PASS is fingerprinted against package files, referenced source/test/build inputs and artifact bytes. Registry loading checks current source, report and artifact bytes. Other packages have no owner-approved contracts/evidence and remain blocked.
- **C:** not started. No capability input/result enforcement; existing generic Order/WorkItem/result boundaries remain `PARTIAL`.
- **D:** not started. No late-result/fence lifecycle changes; terminal WorkItem retention remains unresolved.
- **E:** not started. No synthetic Orders JWT issuer/client/subject test or Provider original suite was run; no Provider/pin modifications made.
- **F:** not started. `RIS_PRIVACY` is not yet added; no ten-group profile or integrated regression result exists.
- All existing shipped capabilities lack the new declaration/evidence. They are blocked by design until policy and evidence are provided; do not treat this as authorization to execute them.

Final Addition build/evidence checkpoint: source commit `d4d802ab082c3fd559aea0cb15973aaac70195ed`; source digest `0e2052c60f2db7de6c4c0f4521f9b1b0107aed602baf104ee0ae68806344be73`; contract SHA-256 `342eec88ae32cf84531771fcd0d5b5485f82e9b9baff14dc635578c6059b2fe5`; test report SHA-256 `4ed9a92355a4bc6cb488de70fa9e795377336563dc284198a18f8287d7f03e06`; built `terraform/lambda.zip` SHA-256 `d039a5e82b3ed4a6484714ae3c25f9386140145d5c6215696dfdabbfe5487067`. Evidence-selected run: 29 passed, 2 deselected by its declared selector, 0 skipped; full `tests/test_addition_agent.py`: **29 passed**. Manifest validation: PASS; installer/A/privacy tests: **19 passed**. Direct smoke confirmed evidence loaded → Eligibility eligible → AgentBody execution success, `17 + 25 = 42`. ZIP is local build evidence only, not installed/deployed. No AWS/Terraform operation, installation, Provider modification, pin update, Main merge, real-data processing, retention-period decision, or legal/operational approval occurred.

## Resume order

Proceed B/C/E only against owner-approved synthetic capability policies; develop F with required groups represented as blocked until selectors/provenance exist; integrate D after C stabilizes; run `RIS_PRIVACY`, `FULL`, and XRepo only after profiles can distinguish intentional policy-blocked fixtures from regression defects without weakening Eligibility. Keep DSGVO-02C `PARTIAL`.
