# RIS-DSGVO-ECOSYSTEM-ORCHESTRATION-01 — V2

**Status:** `RIS ECOSYSTEM PRIVACY CONTRACT & UNIFIED QA READY FOR IMPLEMENTATION REVIEW` — STOP before implementation.
**Baseline:** RIS `a1837f5169b0c40c354daef4de84d3a25caa3967`, branch `feature/ris-dsgvo-compliance-01`.
**Integrated Mays-Orders pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (unchanged).
**Foundation:** [`DSGVO-02C-ORDER-DATA-BOUNDARY-AND-LIFECYCLE.md`](DSGVO-02C-ORDER-DATA-BOUNDARY-AND-LIFECYCLE.md), status `PARTIAL`.
**Scope:** implementation design and acceptance plan only. No runtime/Provider/pin/CI/AWS/Terraform changes, tests, deployment, legal or operational approval.

## Executive design

Add a capability-level privacy contract to the existing `AgentDescriptor`/agent-installation/build path; make missing, invalid, stale, or evidence-incomplete declarations a fail-closed Eligibility decision. Evidence must be generated from the capability's original tests/build and bound to source, contracts and artifact hashes—not accepted because the agent declares itself compliant. Preserve current registry, discovery, routing, `AgentBody`, WorkItem, Order and Transport V1 interfaces additively; do not introduce another registry, queue, order lifecycle, identity map or erasure engine.

`DSGVO-02C` is binding: generic `input.data` and result JSON can contain personal/derived data; WorkItems persist both; configured `ORDER_RESULT` forwards results. A capability contract must decide field-level input/output rules before an order is created or a result is transported. Existing `cvId`, `jobRef`, Profile and Document resolvers remain the only approved routes for resolving their corresponding stored resources. Privacy inspect/export/erase remains a direct, authorized RIS/provider operation, never an AgentOrder.

## Existing surfaces and design gaps

| Existing surface | Verified role | Gap this work addresses |
|---|---|---|
| `agents/ecosystem/registry.py::AgentDescriptor` | Runtime identity/version, capability list, status, runtime/body compatibility, metadata | No typed privacy declaration or evidence reference; current `metadata` is untyped and not an eligibility gate. |
| `discovery.py`, `eligibility.py`, `routing.py`, `runtime/pipeline.py` | Candidate discovery → eligibility → selection → execution | Eligibility checks status/capability/body/runtime, not privacy contract/evidence. Privacy block must happen before selection/execution and be visible as a stable reason, without exposing policy details to untrusted clients. |
| `agent-installations/*/manifest.yaml`, `installer/agent_install.py` | Versioned install packages; manifest requires agent/capability/source SHA/transport/resultBody/Orders pin; package includes contracts/tests/retention/lifecycle docs | No capability privacy contract/evidence validation. `run_stage()` can return `SKIPPED` for prior `PASSED` without comparing current source/package fingerprint; stale privacy evidence must never pass this shortcut. |
| `lambda/build_zip.py` | Deterministic shared, analysis and reader bundles | Shared bundle build returns artifact metadata, but no per-capability privacy evidence binding exists. Do not equate a ZIP build/hash with a privacy test result. |
| `scripts/unified_tests.py` | Isolated `RIS_NATIVE`, `MAYS_MODULE`, `XREPO_CONTRACT`, `XREPO_E2E`, `MODULE_BUILD`, `FULL`; exact Mays SHA verification, scrubbed child environment, artifact hash reporting; `LIVE` locked | No `RIS_PRIVACY` profile or privacy-specific source/evidence provenance checks. Extend this runner rather than create a second harness. |
| Existing consent/privacy implementations | Analysis checks consent boolean + purpose + notice + capabilities; CV resolution uses existing repository/S3 ownership checks; RIS inspect/export/erasure and fenced document S3 erasure exist | These are purpose/domain components, not generic agent declarations; they do not prove terminal WorkItem payload erasure or provider-wide completeness. Reuse and expose their result as evidence. |

## A. Ecosystem Privacy Contrac

### Proposed contract (design; version `RIS-CAPABILITY-PRIVACY/1`)

Represent one declaration per **agent version × capability**, referenced by the runtime descriptor and package manifest. Minimum fields:

```yaml
privacyContract:
  contractVersion: "1"
  capabilities:
    - capability: analysis.run
      processingPurpose: analysis-processing
      input:
        technical: [schemaVersion, requestedResults, idempotencyKey]
        business: [cvRef, jobRef, profileRef]
        prohibitedInlineCategories: [cv_document, special_category_data, personal_free_text]
      identity:
        actor: verified-runtime-contex
        requester: verified-user-or-api-profile-owner
        tenant: verified-runtime-contex
      authorization: [consent:analysis-processing, entitlement:per-requested-result]
      storage: [ris-workitem:payload, ris-workitem:result, ris-document-s3:referenced-input]
      recipients: [ris-parser]
      result:
        categories: [derived-cv-tags, job-tags, comparison]
        orderResult: forbidden
      lifecycle:
        phases: [create, dispatch, execution, completion, failure, cancellation]
        cleanupMechanism: existing-ris-owner-policy
```

The example is illustrative, not an approved Analysis contract. Use controlled enums/IDs for purposes, categories, resolver names, recipient IDs, storage owner/region references, lifecycle phases and result destinations. No retention duration is declared here; name the existing mechanism/policy and leave duration to the approved retention source. Distinguish agent identity, requesting actor, authorized owner context and business payload. A manifest's claim is a requirement declaration only, never proof that behavior conforms.

### Enforcement design

- Add a typed, immutable optional descriptor field with a compatibility default that is **not executable** for privacy-sensitive capabilities. The privacy gate evaluates every invoked capability against the registered declaration and evidence.
- Discovery may return candidates for catalog/UI visibility, but Eligibility marks a missing/invalid/stale declaration or evidence `INELIGIBLE` with stable internal reason codes. Routing must only receive privacy-eligible candidates. Direct AgentBody/runtime execution paths must share the same gate; no route can bypass it.
- Compare requested tenant, actor, user/owner and API-profile context to verified runtime identity; reject cross-tenant/profile mismatches before resolver or provider calls. A declaration does not grant access or replace consent, entitlement, JWT/APIProfile, subject fence or worker recheck.
- Do not surface internal evidence hashes, partner IDs, or rejection details as an authorization oracle. Operational diagnostics contain codes/opaque references only; never payloads, CV text, bearer tokens or provider export bodies.

### RED/GREEN tests

- **RED** `tests/test_ecosystem_privacy_contract.py`: absent contract/evidence, unsupported contract version, unknown capability/category/resolver, duplicate capability declaration and stale evidence are all blocked; valid versioned declaration is accepted.
- **RED** `tests/test_eligibility_privacy_gate.py`: ensure candidate is rejected before routing; all-active-but-privacy-invalid candidate set yields no selection; direct execution path cannot bypass the same gate.
- **GREEN** preserve current status/capability/body/runtime and entitlement behavior for a valid non-sensitive fixture declaration; existing `tests/test_routing.py`, `test_multi_agent_ecosystem.py`, `test_agent_body.py`, `test_worker_entitlement_recheck.py` remain regression suites.

## B. Agent Factory, package and build evidence

### Contract and provenance

Extend the existing `agent-installations/<agent>/manifest.yaml` and `installer/agent_install.py` validator. Require the privacy declaration for each shipped capability, link its contract file and original test entrypoints, and validate the schema and completeness. Do not use `manifest.yaml` alone as evidence.

Evidence record generated by the build/QA tooling should bind: `agentId`, semantic agent version, capability, privacy-contract version/hash, RIS source commit, relevant source-file digest set, original test selection and test report digest/status, build tool/version, artifact path/SHA-256, and evidence creation time. Test results must come from actual isolated test execution; package declarations only select tests. Missing/skipped/failed required tests are BLOCKED/FAIL, not pass. Keep reproducibility/provenance separate from any legal or live-system approval.

Invalidate evidence whenever any bound source, capability declaration, contract, original test, dependency/build input, build tool contract or artifact bytes change. `installer/agent_install.py::run_stage()` must fingerprint inputs before reusing `PASSED`; stale evidence triggers revalidation/rebuild. Preserve explicit install lifecycle gates—this task must not enable or deploy agents.

### RED/GREEN tests

- **RED** extend `tests/test_agent_install_orchestrator.py`: missing/invalid per-capability contract fails validation; declared-but-missing test, skipped test, mismatched source SHA, contract hash or artifact hash cannot produce evidence; changing a bound input invalidates a previously passed validation stage.
- **GREEN** exact source+contract+test+artifact evidence validates and is recorded; unrelated agent package changes do not invalidate another agent's evidence. Existing package discovery, status, compatibility, risk and lifecycle tests remain intact.
- **RED/GREEN** extend `tests/test_lambda_packaging.py` or add `tests/test_agent_privacy_build_evidence.py`: deterministic build hash is bound to evidence, changed bytes fail; building alone does not assert privacy-test success.

## C. AgentOrder, capability payload and result boundaries

Each capability declaration must provide two field-level policies:

1. **Order/WorkItem input:** allowed technical parameters, allowed non-sensitive business parameters, prohibited categories/inline fields, and named resolver references. For stored CV, job text, profile or documents, resolve through existing `cvId`, `jobRef`, Profile and Document adapters with existing tenant/user/owner checks; WorkItem carries the minimum opaque reference and needed execution context, not source document bytes. No universal AgentOrder/ResultContract schema rewrite is proposed.
2. **Result/destinations:** output categories and an explicit `ORDER_RESULT` disposition (`forbidden`, `reference-only`, or a specifically allowlisted minimized result). Only capability-approved fields cross result transport; sensitive result bodies stay in their existing designated RIS store and return opaque references where the existing contract supports this. Unknown/unclassified result fields fail closed for external transport. Local WorkItem result persistence remains a separate lifecycle/retention decision, not authorization to forward it.

The shared transport currently checks schema, size and credential-shaped data, not PII. Preserve its V1 envelope/idempotency/correlation contract; apply per-capability policy before persistence/dispatch and before result send. Do not log rejected content. Do not silently strip/truncate input/output; return typed rejection or use an explicitly versioned capability contract. Preserve legacy callers only when their capability contract explicitly permits the legacy shape and has current evidence.

### Current capability inventory to seed the contract review (not approvals)

| Capability | Existing code/source to assess | Boundary questions for its owner |
|---|---|---|
| `analysis.run` | `agents/analysis/contracts.py`, `orchestrator.py`, `cv_bridge.py`, `job_store.py`, `analysis_agent/agent.py` | Restrict inline structured CV/personal free text; decide which derived result categories may be returned to a WorkItem caller and prohibit Orders transport unless explicitly approved. Reuse `cvId`/`jobRef` and purpose/entitlement gates. |
| `parse.cv` | `agents/cv_parser_agent/agent.py`, `agents/parsers/node_adapter.py` | CV text currently appears as work input; define storage/reference path, whether source text can reach WorkItem and output handling. Existing no-own-state statement is not enough if runtime stores result. |
| `parse.job` | `agents/job_parser_agent/registry.py`, parser adapters/original tests | Define job text/reference handling and derived output boundary. |
| `analyze.job` | `agents/ats_agent/agent.py`, `contract.py`, `result_body.py`, existing Jobsearch API contract | External recipient is Mays-Jobsearch API; disclose fields to that recipient in the technical declaration; define response categories and prevent unapproved ORDER_RESULT fields. |
| `orders.create`, `orders.status`, `orders.cancel` | `agents/orders/function.py`, `agents/orders/real.py`, `tests/test_real_orders_adapter.py` | Orders wrapper chooses customer/order fields and result contract. Confirm exact ID token source and verified principal; no customer/CV payload passthrough by default. |
| `math.add` / reference and test capabilities | original addition/reference agents and tests | Use as low-risk fixture capabilities; still require declared inputs, outputs, storage and test evidence, but no broad sensitive-data policy is inferred. |

### RED/GREEN tests

- **RED** add capability-policy tests for inline CV/free text and foreign tenant/profile references; no request may smuggle user/tenant identity in business payload.
- **RED** add `ORDER_RESULT` negative tests: unapproved result category, CV/PII marker and unknown fields are not sent; `forbidden` capability sends no result; reference-only mode sends only an authorized opaque ref.
- **GREEN** approved synthetic request uses existing resolvers, verifies only selected minimum fields are dispatched, and preserves existing Transport V1 envelope, stable idempotency key, correlation IDs and result duplicate behavior. Extend `tests/test_agent_order_body.py`, `test_order_transport_contract.py`, `test_analysis_order_boundary.py`, `test_analysis_pipeline.py` and original agent result tests rather than replacing them.

## D. Order and WorkItem lifecycle

| Phase | Minimum technical data | Payload/result rule | Existing contract to preserve |
|---|---|---|---|
| Create | capability, schema/version, correlation/idempotency, verified identity/profile refs, resolver refs | validate capability allowlist before OrderV1 persistence; no privacy operation order | owner-bound create; OrderV1 fields; no client-supplied identity |
| Dispatch | order/work ID, capability, profile context ref, attempt/idempotency, minimum allowed input | only approved fields/refs in dispatch; never raw CV PDF | Transport V1 and `contextRef` resolution |
| Execution | verified tenant/user/actor, capability, work ID, authorized resolved data | resolver fetches only after current entitlement/consent/fence; avoid logging | WorkItem idempotency, worker entitlement recheck, existing subject fence |
| Result delivery | correlation/work/attempt, result contract, status, minimized result/ref | per-capability result policy gate before sender; default deny for unclassified | deterministic result ID/idempotency, retry/re-emit and duplicate suppression |
| Completion/failure | terminal status, timestamp, error code/type, result reference | payload/result retention follows approved existing policy; errors must not echo data | COMPLETED/FAILED/DEAD_LETTER semantics; no new state machine |
| Cancellation/erasure | work/order refs and fence/version; action outcome | reject or suppress late result before persist/re-emit; do not resurrect erased payload | G5 cancels non-terminal work; terminal duplicate suppression; conditional writes |

Reuse existing `result_reference`, WorkItem version/conditional updates, duplicate suppression and `subject_fence`/erasure admission. Before extending, prove their scope includes result send/replay and terminal stored payload. A delayed message after erase must be checked against the current fence at the last mutation/forwarding boundary; stale delivery is rejected without restoring payload. If existing fence cannot cover it, extend the same fence/conditional contract after review—do not add a separate global identity/erasure ledger. Define cleanup triggers and use current TTL/retention mechanisms; duration and legal holds remain owner decisions. No automatic purge may break idempotency/replay semantics.

### RED/GREEN tests

- **RED** extend `tests/test_worker_pipeline.py` and `test_subject_fence.py`: erase/fence between execution and result persistence/send blocks stale result; duplicate/replay does not restore erased content; same-work retries keep existing idempotency.
- **GREEN** each lifecycle phase retains only fields declared for that phase; cancellation and terminal suppression still work; existing `test_work_queue.py`, `test_worker_entitlement_recheck.py`, `test_order_transport_contract.py` pass.
- **RED** inject result transport failure/late replay and verify no payload in logs or status markers; **GREEN** stable message/correlation semantics remain unchanged for permitted results.

## E. Mays-Orders provider boundary and CR disposition

- Reuse provider `privacy/inspect`, `privacy/export`, `privacy/erase` through its direct authorized privacy invocation; these are control-plane calls, not AgentOrders. Keep provider order lifecycle/erasure implementation in Mays-Orders and RIS-owned orchestration/status mapping in existing RIS privacy flow.
- **JWT/subject gate:** `agents/orders/function.py::_token()` accepts `work_item.auth.idToken`, payload auth `idToken`, then `ORDERS_ID_TOKEN`; `RealMaysOrdersAdapter` sends the selected token as Bearer. Current source therefore does not establish one deployment-independent JWT subject. Before requiring provider subject delegation, document/test which source wins in the authorized path, verify the token issuer/client/sub against Orders API identity, and compare to the intended RIS subject. No body `subjectId` workaround.
- Reduce **CR-MO-PRIVACY-RIS-SUBJECT-DELEGATION-01** to `CONDITIONAL / NOT REQUIRED unless proven`: if the provider-indexed JWT subject already is the data subject for orders, reuse provider identity/privacy; if it is a service principal and the existing provider API cannot bind the intended subject, request only the smallest authenticated, tenant/consumer-scoped binding needed. No global subject map and no generalized delegation by default.
- Keep **CR-MO-PRIVACY-ANONYMIZE-COVERAGE-02** as provider-owned conditional review. The RIS pin is `db4f9e...`; separate provider Main `716a...` is not evidence of pin behavior. First enumerate the actual persisted fields and enforce capability minimization; then require provider residual-field/AgentOrder tests only for personal-bearing Orders and only if the selected provider policy is ANONYMIZE. Do not reimplement provider anonymization or claim legal anonymization.
- Reuse provider response/original tests/reports cited in `DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md` and `MO-PRIVACY-PROVIDER-CONTRACT-REVIEW-01.md`; preserve operation status, limitations and timeout ambiguity. Existing returned operation IDs are not a durable reconciliation ledger. No pin upgrade, provider change or assumption of live provider configuration.

### RED/GREEN tests

- **RED** synthetic adapter test proves token precedence/source, issuer/client/subject and fail-closed missing/ambiguous identity; provider privacy invoke never derives subject from an untrusted order body.
- **GREEN** exact integrated pin original suite plus existing RIS XRepo contract tests run in isolated processes; inspect/export/preview only after verified identity; assert no Order is created for inspect/export/erase.
- Provider invocation failure, partial result, timeout and stale/unknown operation outcome stay BLOCKED/PARTIAL/UNKNOWN; never convert to success or blind EXECUTE retry.

## F. Unified RIS Privacy QA profile

Add one `RIS_PRIVACY` profile to `scripts/unified_tests.py::PROFILES` and `profile_jobs()`; keep existing jobs, report schema, process isolation, credential scrubbing and exact-pin verification. Reuse the present runner; no second test framework. The profile should be deterministic, offline/synthetic, fail closed on omitted/skipped groups, and report the RIS commit, provider pin, contract/evidence hashes, artifact hashes, per-group status and source/test provenance.

| Group | Existing tests to reuse / planned additions |
|---|---|
| 1 Ecosystem contract | `test_routing.py`, `test_multi_agent_ecosystem.py`, new `test_ecosystem_privacy_contract.py` |
| 2 Manifest/build evidence | `test_agent_install_orchestrator.py`, `test_lambda_packaging.py`, new `test_agent_privacy_build_evidence.py` |
| 3 Eligibility/authorization | `test_worker_entitlement_recheck.py`, `test_authorization_context.py`, new `test_eligibility_privacy_gate.py` |
| 4 Consent/purpose | `test_consent_gate.py`, `test_consent_notice_lifecycle.py`, `test_analysis_entitlements.py` |
| 5 Input boundary | `test_analysis_order_boundary.py`, `test_agent_order_body.py`, `test_cv_storage_consent_gate.py` |
| 6 Result boundary | `test_order_transport_contract.py`, `test_analysis_pipeline.py`, existing ATS/analysis result tests |
| 7 RIS storage privacy | `test_partner_privacy_inspection.py`, `test_r08_c1b_document_erasure_integration.py`, `test_privacy_lifecycle_evidence.py` |
| 8 WorkItem lifecycle/retention | `test_worker_pipeline.py`, `test_subject_fence.py`, `test_work_queue.py` |
| 9 Provider privacy contract | exact provider original privacy tests from verified pin, in isolated provider process; do not reuse Main response-branch tests as pin proof |
| 10 XRepo/regression | `test_cross_repo_mo_contract.py`, `test_mo_contract_compat.py`, `test_mo_dispatch_handoff.py`, `test_agent_order_dispatch_e2e.py`; synthetic only |

Required negative cases: missing/stale evidence; foreign tenant/user/profile; absent purpose-specific consent or entitlement; inline CV/free text where prohibited; sensitive/unclassified result in forbidden transport; no Order on privacy request; stale result after erasure; missing provider source/pin/evidence; partial provider outcome; skipped required test. `RIS_PRIVACY` must not invoke `LIVE`, AWS, deployed APIs or real user data. Record skipped as a blocked group, not green. Existing `FULL`/`XREPO_*` profiles and provider original tests remain unchanged.

## G. Implementation sequence, ownership, and stop criteria

Work may proceed in independent design/implementation branches only after this review gate. Dependency DAG:

```tex
A contract/schema ─┬─> B manifest/build evidence ─┬─> F RIS_PRIVACY profile
                   ├─> C capability input/result ─┤
                   └─> D lifecycle/fence ─────────┤
E provider identity/CR disposition ────────────────┘
                 -> exact-SHA implementation review -> separate approval
```

| Work package | Concrete first files | Dependencies | RED/GREEN completion gate |
|---|---|---|---|
| A Contract | `agents/ecosystem/registry.py`, `eligibility.py`, `discovery.py`, `routing.py`, `runtime/pipeline.py`; focused tests above | none | Missing/stale evidence cannot reach selection or direct execution; compatible valid descriptor retains existing routing. |
| B Factory/build | `agent-installations/*/manifest.yaml`, `installer/agent_install.py`, `lambda/build_zip.py`, package-specific `contracts/` and `tests/` | A schema | Test/build evidence binds exact inputs and artifact; changed input invalidates cached PASS; no apply/deploy. |
| C Boundaries | `agents/orders/agent_order.py`, `agents/transport/order_transport.py`, `agents/runtime/pipeline.py`, `agents/analysis/{contracts,cv_bridge,job_store,orchestrator}.py`, domain agent tests | A contract; B evidence for shipped capabilities | No prohibited field persists or transports; allowed resolver/reference flows and V1 correlation/idempotency remain compatible. |
| D Lifecycle | `agents/runtime/pipeline.py`, `subject_fence.py`, `runtime/work_item.py`, `privacy_erasure.py`, lifecycle tests | A and C policy decisions | stale result after erasure cannot persist/replay; no idempotency, retry, duplicate-suppression regression. |
| E Provider | `agents/orders/function.py`, `agents/orders/real.py`, existing Orders privacy docs/tests, RIS privacy orchestration docs/tests | identity owner decision; A/C data matrix | Actual JWT subject proven; exact pin original tests; provider CR reduced to evidence-backed need; no Orders created for DSAR. |
| F Unified QA | `scripts/unified_tests.py`, `tests/test_unified_test_orchestrator.py`, privacy tests and report schema | A–E stable test selectors and provenance | All ten groups run in process isolation; exact source/artifact hashes; skipped/missing group blocks; no live/AWS access. |

**First implementation-review deliverables:** reviewed JSON/YAML schema for contract/evidence; capability inventory with owner-approved input/output matrix; written decision on Orders JWT principal and DSAR subject; per-package test selectors; exact artifact/provenance format; gap/risk list for retained terminal WorkItems and delayed results. Then request a separate implementation authorization. No legal retention periods, legal bases, consent validity, production readiness, or release approval are inferred.

## Master orchestration alignmen

- **DSGVO-03** becomes “Ecosystem privacy contract and provider identity disposition” (A + E); provider reports and originals are evidence inputs, not duplicated capability implementations.
- **DSGVO-04** becomes “Capability payload/result boundary and existing privacy-flow adapters” (C + D); use current RIS resolvers, fences, ledgers and provider-owned privacy operations.
- **DSGVO-05** becomes “Agent privacy evidence and build binding” (B); package-specific original tests remain owned by each agent.
- **DSGVO-06** becomes “Unified `RIS_PRIVACY` profile” (F); extend current isolated runner, preserve all existing profiles.
- **DSGVO-07** becomes exact-SHA implementation evidence review, before separate operational/legal approvals; it is not live acceptance.

**Final status:** `RIS ECOSYSTEM PRIVACY CONTRACT & UNIFIED QA READY FOR IMPLEMENTATION REVIEW` — design and RED/GREEN gates are ready; implementation is not authorized. `DSGVO-02C` remains `PARTIAL` until the capability policies are enforced and the result/terminal WorkItem/provider data boundary is demonstrated. No tests were run for this documentation task.
