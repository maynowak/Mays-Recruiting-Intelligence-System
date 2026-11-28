# RIS–Mays-Orders Integration — Current Status

**Status at 2026-11-28:** local Addition roundtrip **PASS**; live completion
**BLOCKED pending explicit mutation and live-order approvals**. No AWS call,
Terraform plan/apply, Cognito/entitlement/catalog mutation, or live order was
performed for this checkpoint.

| Work package | Soll | Ist / mode | Implementation / deployment | Test result | Offene Abweichung | Nächster Schritt | Commit / Evidenz |
|---|---|---|---|---|---|---|---|
| A — Historical ATS deactivation | Deactivate `ats-agent` through existing lifecycle; retain results and shared infrastructure | **BLOCKED at approval gate**; local lifecycle `DISABLE` dry-run only | Existing lifecycle requires withdrawing agent-scoped entitlement(s) and Terraform catalog `INACTIVE`; no uninstall/purge. No live change. `agent-catalog` INACTIVE alone does not block worker execution. | Dry-run returned `inventory_required_for_impact`; inventory was not supplied, so its default `entitlementStatus=absent` is **not live evidence**. | Latest read-only 20A2 check found zero ATS entitlements for the exact synthetic test owner only; it does not establish all current ATS grants or queue/in-flight state. | Approve fresh read-only inventory; then present a plan limited to exact ATS entitlement withdrawal(s) and ATS catalog row status update. Preserve shared queues, worker, dispatch, result consumer, HMAC, orders, work and results. | Lifecycle package `agent-installations/ats-agent/lifecycle.yaml`; prior lifecycle evidence `docs/reports/RIS-AGENT-LIFECYCLE-12.md`; 20A2 `docs/reports/evidence/20A2/read-only-findings.json`; local dry-run output under Temp `ris-addition-final-e2e/ats-disable-impact.json`. |
| B — Addition local order roundtrip | Reuse `addition_agent` / `math.add`; check order through signed result and owner readback | **LOCAL TESTED**; external Mays source read-only at integrated pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` | Existing addition runtime and shared transport unchanged; addition catalog remains intentionally ABSENT/dispatch-only. No AWS deployment. | New focused Addition roundtrip **1 passed**; `tests/test_mo_dispatch_handoff.py` plus the focused roundtrip **11 passed**; Addition/auth/lifecycle suites **70 passed**. | No live proof at current deployed target. | Reuse this test; after approval, run at most one live synthetic order, no manual retry. | `tests/test_agent_order_dispatch_e2e.py`; Mays source checkout `installer/projects/mays_order_builder`; source identity verified read-only. |
| C — Addition live authorization | One authenticated synthetic order with `orderDescription` + `agentOrder`, `math.add(19,23)=42`; signed result, consumer persistence, completed state, owner GET; preserve idempotency/privacy | **NOT RUN**; no live order authorized | Current source supports deterministic addition without ATS/AI provider. Existing dispatch/result infrastructure is reused. | Local tests pass; no live test. Existing 19F8 and Mays-original evidence remains reused, not repeated. | Current addition entitlement and test identity/profile state have not been freshly inventoried. A temporary entitlement may require an approved Terraform mutation. | Freshly verify existing synthetic Cognito identity, ACTIVE owner profile, tenant binding, relevant entitlement rows and in-flight/queue state. Present the exact entitlement plan and one-order payload/hash for approval. | Prior local test evidence: `docs/reports/RIS-AGENT-INSTALLATION-09-ADDITION-PILOT.md`; prior integration evidence: 19F8; current tests above. |
| D — Shared contracts/security | Keep `ORDER_DISPATCH`, WorkItem, worker, HMAC `ORDER_RESULT`, Mays result consumer, idempotency and owner-only result projection | **LOCAL TESTED / HISTORICAL LIVE EVIDENCE REUSED** | No contract or shared infrastructure change. | The new test verifies same order/work correlation, signed result acceptance, `processing=COMPLETED`, exact result 42, unchanged `orderDescription`, no public `agentOrder`, and foreign-owner GET 404. Existing suites cover stable dispatch/result idempotency and auth/privacy negatives. | Live repeat of these assertions remains unverified at current state. | Recheck only within the one approved live order/readback; do not replay or redrive. | New test `test_addition_order_round_trip_and_authorized_read_back`; prior local and live evidence cited above. |
| E — ATS/API scope | Exclude HTTP ATS canary; preserve historical source/tests/results | **SCOPE EXCLUDED**, not erased | No ATS source, AnalysisAgent, JS parser, historical result, or test was deleted or modified. | No ATS integration test or ATS provider call was executed in this Addition-only checkpoint. | Actual ATS deactivation is still pending Phase A lifecycle approvals; excluding ATS from the test scope alone does not disable it. | Complete Phase A before claiming deactivation; leave historical evidence intact. | Prior history retained in existing ATS reports and tests. |

## Local execution record

- Baseline branch `feature/ris-analysis-integration-07`, starting HEAD
  `b915f5731a76fb9f024acda7d8afa390d2c87be4`.
- Addition/authorization/lifecycle command:
  `python -m pytest tests/test_addition_agent.py tests/test_mo_addition_authorization_matrix.py tests/test_agent_lifecycle.py -q`
  → **70 passed**.
- Cross-repository command used only the read-only integrated Mays checkout:
  `MO_ORDERS_SRC=installer/projects/mays_order_builder/lambda/src python -m pytest tests/test_agent_order_dispatch_e2e.py::TestAgentOrderDispatchE2E::test_addition_order_round_trip_and_authorized_read_back tests/test_mo_dispatch_handoff.py -q`
  → **11 passed**.
- The new test uses synthetic identity/table/queue boundaries and the actual
  RIS reader, dispatch ingress, pipeline, AdditionAgent, Transport V1, Mays
  signed-result validation/consumer and owner projection. No AWS or external
  HTTP/ATS endpoint is contacted.
- Local lifecycle dry-run command for `ats-agent` returned `DRY_RUN` with
  blocker `inventory_required_for_impact`; it did not mutate state or AWS.
  Output is outside the repository at
  `%TEMP%\ris-addition-final-e2e\ats-disable-impact.json`.
- No code/runtime defect was established. The only implementation change is a
  focused regression test; no Build/QA/Plan/Apply/deployment step is needed.

## Approval packet — no approvals granted

Target scope from existing evidence (must be re-verified read-only before any
plan): account `262370457690`, region `eu-central-1`, workspace `ris-dev2`,
historical state serial `76`, lineage
`a0bd361d-5cd1-a207-a8c0-e6888f0be082`. The serial/lineage are historical, not
fresh state verification.

### A. Disable historical ATS agent

1. Review fresh, read-only inventory for ATS agent-scoped entitlements, open
   orders/results and in-flight queue state. Existing 20A2 evidence confirms
   zero `ats-agent` entitlement rows only for one synthetic identity; it is not
   sufficient to define the global withdrawal set.
2. Use `installer.agent_lifecycle` **DISABLE** only. No UNINSTALL, DETACH,
   PURGE, deletion of orders/work/results, or shared-resource changes.
3. Plan exact withdrawal of any still-valid `ats-agent`-only entitlement(s)
   using the established provisioning plane, plus the agent-catalog row update
   `ats-agent: ACTIVE → INACTIVE` if it is still active. Any unexpected plan
   action, shared-resource change, or unreviewed entitlement is a stop.
4. Approval needed: exact inventory digest/entitlement IDs (redacted in report),
   reviewed plan hash, actor/authority, and explicit Apply authorization.
   Catalog INACTIVE is not treated as the worker gate; entitlement withdrawal
   is required to stop authorized dispatch/worker execution. Keep all shared
   transport and historical data.

### B. One Addition order

1. Freshly verify the existing synthetic Cognito subject is enabled, its
   ACTIVE API profile is owner/tenant-bound, and the tenant matches. Do not
   create a user/profile unless separately listed and approved.
2. Freshly check only the exact test owner's `addition_agent` entitlements and
   open/queued work. If missing, request exactly one short-lived row using the
   existing Terraform foundation-entitlement mechanism:
   `userId=<verified synthetic sub>`, `tenantId=<matching tenant>`,
   `agentId=addition_agent`, `validFrom=T0-1m`, `validUntil=T0+15m`.
   That seed is user/tenant/agent-wide (no `apiProfileId` binding) and does not
   populate TTL; it must be explicitly removed through the same IaC lifecycle
   after the test. Do not activate an Addition catalog row; it remains
   dispatch-only.
3. Request permission for **at most one initial** authenticated `POST /orders`
   at the verified RIS-DEV2 Orders endpoint. Payload: synthetic customer
   `Addition QA`, `customer@example.invalid`; one item `ADD`, quantity 1,
   unitPrice 1 EUR; `orderType=agent.execution`; `agentOrder.target` is
   `addition_agent/math.add`; inputs `left=19`, `right=23`; a unique fixed
   requestId/idempotency key and exact payload SHA-256 must be filled into the
   approval after final serialization. No ATS/API/AI provider execution.
4. Permit only the single matching owner GET and, if a second existing
   synthetic identity is available and separately approved, one foreign-owner
   GET. Otherwise retain the existing local 404 evidence and report that
   foreign-owner denial was not live-tested. No second order, manual POST
   retry, direct Lambda invocation, queue receive/redrive, recovery or cleanup
   outside the exact approved entitlement cleanup.
5. Accept existing SQS automatic retry behavior (`maxReceiveCount=3`) for this
   one logical work item; no queue configuration changes. Stop on any failed,
   ambiguous or mismatched status; do not retry the order.
6. Cleanup is a separate IaC mutation: remove only the temporary
   `addition_agent` entitlement seed, retaining order/work/result evidence and
   all shared infrastructure. Its exact cleanup plan requires review/approval.

Approver/authority/date; fresh inventory/state digest; ATS lifecycle plan hash
and exact scope; Addition entitlement add/cleanup plan hashes; final request
payload SHA-256 and idempotency key; one-order approval; retry acceptance;
owner-read permission: **not supplied**. Gate A Apply: **NOT APPROVED**. Gate B
entitlement Apply: **NOT APPROVED**. Gate C initial order: **NOT APPROVED**.

No further live action is taken until those approvals are explicit. Main merge
was not performed. The protected
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` was not used
as output, staged or changed.
