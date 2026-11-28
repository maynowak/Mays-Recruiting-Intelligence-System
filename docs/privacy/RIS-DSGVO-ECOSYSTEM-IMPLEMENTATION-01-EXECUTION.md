# RIS-DSGVO-ECOSYSTEM-IMPLEMENTATION-01 — Execution

**Status:** `PARTIAL — A/B implemented for Addition reference capability; C–F pending/blocked`
**Branch:** `feature/ris-dsgvo-compliance-01`
**Baseline:** `db2e09419931fc64e9377aed8fdd35c720023045`
**Orders pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (unchanged)

## Checkpoint A — capability privacy contrac

Implemented the typed `RIS-CAPABILITY-PRIVACY/1` declaration and separate evidence record in `agents/ecosystem/privacy_contract.py`; added additive descriptor fields in `agents/ecosystem/registry.py`; and required supported version, complete declaration, capability/version/digest binding, exact source/artifact hashes, and complete non-skipped tests in Eligibility. The worker selection path already consumes Eligibility. The legacy direct `AgentExecutor` now resolves the descriptor from the Ecosystem registry and applies the same Eligibility decision; missing registration/evidence denies before invoking the handler.

Synthetic contract coverage: `tests/test_ecosystem_privacy_contract.py` — **7 passed**. Covered missing declaration/evidence, valid evidence, source mismatch, skipped evidence, unsupported version, declaration digest sensitivity, and direct execution authorization/denial.

Compatibility/regression checks expose an intentional migration block, not a green regression: `tests/test_agent_status_normalization.py` — **18 passed, 2 failed** (the old active-without-privacy-evidence expectation and an old reference execution fixture); `tests/test_multi_agent_ecosystem.py` + `tests/test_worker_entitlement_recheck.py` — **22 passed, 18 failed** because existing active agent descriptors contain no approved capability declaration/evidence and now fail before execution-time authorization. These failures must not be hidden with a bypass or fabricated policy approval. Existing agent package owners must provide policy-reviewed declarations and B-generated provenance before those execution suites can return green. `tests/test_agent_body.py` likewise has legacy direct-execution assumptions and is not a passing regression after fail-closed enforcement.

## Remaining work and blockers

- **B:** installer validates a typed capability policy, rebuilds the manifest-declared deterministic agent bundle itself, checks required Addition/privacy runtime entries, executes manifest-selected original/privacy tests, and binds a canonical report, contract hash, source-file digest, source commit, test selection and artifact SHA. Cached stage PASS is fingerprinted against package files, referenced source/test/build inputs and artifact bytes. Addition is the first package with a synthetic numeric-only declaration; local registry loading rejects evidence if source, contract/test report or built artifact no longer matches. Final evidence generation against the next committed tool source is pending.
- **C:** not started. No capability input/result enforcement; existing generic Order/WorkItem/result boundaries remain `PARTIAL`.
- **D:** not started. No late-result/fence lifecycle changes; terminal WorkItem retention remains unresolved.
- **E:** not started. No synthetic Orders JWT issuer/client/subject test or Provider original suite was run; no Provider/pin modifications made.
- **F:** not started. `RIS_PRIVACY` is not yet added; no ten-group profile or integrated regression result exists.
- All existing shipped capabilities lack the new declaration/evidence. They are blocked by design until policy and evidence are provided; do not treat this as authorization to execute them.

An initial local agent bundle was built while stabilizing B; its hash is provisional because source changed afterward. Regenerate the deterministic bundle and evidence against the committed B source checkpoint before treating either hash as final. No AWS/Terraform operation, deployment, installation, Provider modification, pin update, Main merge, real-data processing, retention-period decision, or legal/operational approval occurred.

## Resume order

Proceed B/C/E only against owner-approved synthetic capability policies; develop F with required groups represented as blocked until selectors/provenance exist; integrate D after C stabilizes; run `RIS_PRIVACY`, `FULL`, and XRepo only after profiles can distinguish intentional policy-blocked fixtures from regression defects without weakening Eligibility. Keep DSGVO-02C `PARTIAL`.
