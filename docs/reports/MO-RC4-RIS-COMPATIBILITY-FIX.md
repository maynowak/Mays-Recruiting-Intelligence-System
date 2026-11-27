# MO-RC4-RIS-COMPATIBILITY-FIX

**Owner:** Mays-Orders repository (`maynowak/mays-order-aws`)  
**Priority:** Blocking for RIS integration of `v0.6.0-rc.1`  
**Candidate under review:** tag `v0.6.0-rc.1`, peeled commit
`5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` (do not move or rewrite this tag)

## Problem statement

The exact RC4 source passes its own Lambda unit suite, but does not provide the
Orders transport and result-consumer contract exercised by RIS. RIS XRepo tests
against this candidate reproduce 13 contract failures and 36 synthetic E2E
failures. The current integrated source `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
passes those same RIS profiles (133 contract tests + 4 subtests; 39 E2E tests).

The candidate also rejects the existing RIS agent-order representation: the
real `validation.validate_create_order` raises `Unknown field 'orderDescription'
at body`. This is a confirmed source-contract mismatch, not a reason for RIS to
discard required order data, weaken validation, or introduce a candidate-only
workaround.

## Required Mays-Orders changes

1. **Restore/implement the versioned RIS transport contract** in candidate-owned
   `lambda/src/dispatch.py` and the corresponding consumer-side modules
   `lambda/src/result_envelope.py`, `lambda/src/result_handler.py`, and
   `lambda/src/result_consumer.py`. Those files exist in current `db4f9e7` and
   are absent from RC4. Preserve strict schema validation and the documented
   `ORDER_DISPATCH` / `ORDER_RESULT` / `ORDER_FAILED` direction and fields.
2. **Restore the agent-order contract** in `lambda/src/agent_order.py` and the
   create-order validation path. Either accept the supported `orderDescription`
   field with the current documented semantics, or publish a versioned
   replacement contract plus a reviewed cross-repository adapter design before
   changing the field. Unknown-field validation must remain strict for other
   fields; do not silently drop the agent order.
3. **Retain security and lifecycle guarantees:** HMAC-SHA256 verification must
   fail closed; identity/context references remain server-derived and bound to
   the order owner/tenant; dispatch must use stable idempotent work identity;
   duplicate and stale results must not mutate an order; wrong owner, work ID,
   correlation ID, attempt, or signature must be rejected.
4. **Repair the generated `orders-service` module and manifest** at this same
   source identity. The exact RC4 generation reports undeclared variables
   `privacy_secret_enabled`, `privacy_kms_key_arn`,
   `sqs_visibility_timeout_seconds`, `sqs_message_retention_seconds`,
   `sqs_dlq_message_retention_seconds`, `sqs_max_receive_count`, and
   `deployment_version`, and undeclared `module.privacy_secret` references.
   Declare valid inputs/modules or remove stale references consistently; do
   not add undocumented RIS-side Terraform shims. `module-builder.manifest.json`
   must record the full 40-character source commit, not `5bc154e`.

## Existing source tests and RIS acceptance evidence

Run the candidate's original tests, without copying or modifying them:

- `lambda/tests/test_validation.py`, `test_order_processing_component.py`,
  `test_order_service.py`, `test_processing_result.py`, `test_sqs_handler.py`,
  `test_hmac_contract.py`, and the remaining Lambda suite.
- Add/restore Mays-owned originals for dispatch, result handoff/consumer,
  agent-order serialization/projection, and `orderDescription` validation if
  the candidate branch currently lacks those test modules. Required scenarios
  include valid and invalid HMAC, unknown fields/schema versions, stable work
  ID, duplicate delivery, stale attempts, owner/tenant isolation, context
  reference, and full create→dispatch→signed result→owner read-back.
- Run original `module_builder/tests/`, `installer/tests/`, seed-tool, Cognito
  backup, and generated Terraform validation tests on Ubuntu.

**Verified test result:** Ubuntu run `45965830933` passed the exact RC4 original
Lambda (440), builder (129), installer (81), seed-tool (28), and Cognito backup
(2) tests after the RIS QA workflow provisioned the legacy fixed-path aliases.
The aliases are ephemeral runner setup, not candidate-source edits or a reason
to skip tests. Making those original tests portable without aliases may be
handled separately; it is not a blocking source defect for this candidate.

Then provide RIS with a **new immutable commit and release identity** (do not
retag RC4). RIS will rerun the existing Unified Testsuite profiles
`XREPO_CONTRACT`, `XREPO_E2E`, `MODULE_BUILD`, and `UPGRADE_GATE` against that
exact new SHA. Expected RIS gates: contract **133 passed + 4 subtests, 0 failed**;
synthetic E2E **39 passed, 0 failed**; generated-module contract all tests pass;
backend-free `terraform init` and `terraform validate` pass. These are acceptance
criteria, not claims that the present RC4 candidate passes.

## Ownership boundary

All listed source and builder defects belong to Mays-Orders. No RIS compatibility
adapter is justified by the verified evidence: the candidate lacks the
producer/consumer modules needed for a safe adapter, and moving/dropping order
data would violate the create contract. No RIS runtime workaround, HMAC bypass,
idempotency bypass, owner/tenant exception, module pin change, or module
installation is requested by this issue.

Evidence: `docs/reports/RIS-MAYS-ORDERS-COMPATIBILITY-RESOLUTION-19F4.md` and
`docs/reports/RIS-MAYS-ORDERS-COMPATIBILITY-RESOLUTION-19F4.results.json`.
