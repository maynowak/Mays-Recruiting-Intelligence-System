# RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01 — Execution

**Status:** `PARTIAL — A/B implemented for Addition; C boundary implemented; D–F pending/blocked`
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
- **C:** partial implementation: declarations carry exact typed input, internal-result, and capability-specific ORDER_RESULT field allowlists. Runtime rejects undeclared/mistyped payloads before WorkItem admission, rejects successful results before completion persistence, and refuses ORDER_RESULT fields outside policy. Addition has synthetic tests including extra-field/type rejection and transport validation. Evidence was regenerated against the C commit. Generic Order/WorkItem storage retention and unreviewed capability policies remain open.
- **D:** not started. No late-result/fence lifecycle changes; terminal WorkItem retention remains unresolved.
- **E:** partial. Synthetic RIS-side tests sign/verify local HS256 JWTs and confirm outer WorkItem `auth.idToken` precedes engine-wrapped payload and environment fallback while preserving synthetic `sub`, `custom:tenant_id`, `aud`, and `token_use` claims. This checks token selection, not Provider acceptance/authorization. Pinned checkout `installer/projects/mays_order_builder` is absent; Provider originals/JWT verifier are explicitly BLOCKED. No Provider/pin modifications.
- **F:** `RIS_PRIVACY` added without changing existing profiles. Local capability/addition group passed **42**, application/lifecycle group **76**, synthetic Orders JWT group **2**. Provider original and verifier groups explicitly BLOCKED, so profile status is BLOCKED; Mays provenance records the missing checkout.
- All existing shipped capabilities lack the new declaration/evidence. They are blocked by design until policy and evidence are provided; do not treat this as authorization to execute them.

Current Addition evidence checkpoint: source commit `ee6055acd1856e9fdaf09fe09c7a30a698a0da58`; source SHA-256 `20b488916e770dae84594c714663ee582104aae5b125505235f1c2b189924f53`; contract SHA-256 `b6ab1d98ab2659bc2fa25eea82f751ae536d7c908850d64d0c428b87cb9fbeb4`; selected test-report SHA-256 `5dd8caddac2f95ad14c2745bde2186f66bf9cfd22b093349c97e4f68d8b38937`; built `terraform/lambda.zip` SHA-256 `7f082ccf7b47195e712d968eecac81ca785f9030211da8d77b5e639aaa50478f`. Declared evidence suite: **32 passed, 2 deselected, 0 skipped**; complete original `tests/test_addition_agent.py`: **29 passed**; installer/contract/boundary suites: **23 passed**. Synthetic registry→Eligibility→AgentBody smoke: eligible, successful, result 42. The deselected original integration tests were subsequently executed with freshly generated valid evidence; no test bypass is used to claim their result. No AWS/Terraform operation, installation, Provider modification, pin update, Main merge, real-data processing, retention-period decision, or legal/operational approval occurred.

`RIS_PRIVACY` run report was written outside the repository. Groups: capability/addition 42 passed; application/lifecycle 76 passed; synthetic JWT 2 passed; Provider originals and Provider JWT verifier BLOCKED. Runner/JWT tests: **10 passed**. Broader `tests/test_ats_result_link.py`: **26 passed, 5 failed** at ATS Eligibility before result-link assertions because ATS has no approved privacy declaration/evidence; these remain unverified.

## Resume order

Proceed B/C/E only against owner-approved synthetic capability policies; develop F with required groups represented as blocked until selectors/provenance exist; integrate D after C stabilizes; run `RIS_PRIVACY`, `FULL`, and XRepo only after profiles can distinguish intentional policy-blocked fixtures from regression defects without weakening Eligibility. Keep DSGVO-02C `PARTIAL`.
