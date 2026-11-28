# RIS–Mays-Orders Integration — Current Status

**Status at 2026-11-28:** local Addition roundtrip **PASS**; shared read-only
preflight **COMPLETE**; live completion **BLOCKED pending explicit mutation and
live-order approvals**. Read-only AWS calls were performed. No AWS write,
Terraform plan/apply, Cognito/entitlement/catalog mutation, queue receive or
redrive, or live order was performed.

| Work package | Soll | Ist / mode | Implementation / deployment | Test result | Offene Abweichung | Nächster Schritt | Commit / Evidenz |
|---|---|---|---|---|---|---|---|
| A — Historical ATS deactivation | Deactivate `ats-agent` through existing lifecycle; retain results and shared infrastructure | **Read-only inventory complete; live disable NOT APPLIED**. Local `DISABLE` dry-run returned `DRY_RUN`, zero blockers. | Catalog is `ACTIVE`; global ATS entitlement query found one expired-only historical row and no currently valid row. `INACTIVE` is a discovery gate, not the worker execution gate. No uninstall/purge. | All 4 ATS orders in the live Orders index have `processing=COMPLETED`; no open ATS order/result. Dispatch, work and result queues are 0. Shared worker DLQ has 1 approximate visible message; its body was not read/received. | Expired entitlement is not represented in current Terraform state and has no `createdBy`; do not delete it manually. DLQ message remains unclassified and untouched. | Prepare a tightly scoped plan for ATS catalog `ACTIVE→INACTIVE` and the temporary Addition grant only. Preserve all shared resources and historical data; stop if plan includes anything else. | Lifecycle `installer/agent-installations/ats-agent/lifecycle.yaml`; dry-run inventory digest `38fd2c0f…`; read-only checks 2026-11-28; Terraform workspace `ris-dev2`, state serial `76`, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`. |
| B — Addition identity and local roundtrip | Reuse existing identity/profile and `addition_agent` / `math.add`; signed result and owner readback | **Read-only identity check complete; local evidence reused**, not rerun. Mays source pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`. | One enabled Cognito test user and one ACTIVE owner/tenant-matched profile exist. The identity has no entitlements; global Addition query found one expired-only row. Addition catalog remains ABSENT/dispatch-only. | Prior local suites: 70 and 11 passed. | One temporary `addition_agent` entitlement is necessary. A live foreign-owner 404 requires a second valid Cognito principal; pool currently has one user. | Include only the short-lived Addition grant in the combined plan; request separate explicit approval for a temporary second principal, or report foreign-owner 404 as local-only. | `tests/test_agent_order_dispatch_e2e.py`; read-only Cognito/profile/entitlement checks; integrated Mays source. |
| C — Addition live authorization | One synthetic order `19 + 23 = 42`; signed result, consumer persistence, `COMPLETED`, owner GET; preserve idempotency/privacy | **NOT RUN**; no live order authorized | Deterministic Addition runtime; no ATS/AI provider. Shared transport reused. | Local evidence retained; no live test. | No valid test entitlement or execution-time token available in repository. Existing Analysis-agent has two unrelated PENDING orders; untouched. | After explicit gates, use one authenticated POST only, no retry; verify exact WorkItem/result/owner readback. Prepare exact serialized payload hash for approval. | Prior local evidence `RIS-AGENT-INSTALLATION-09-ADDITION-PILOT.md`; current checkpoint baseline `21aa96a`. |
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
- Read-only AWS preflight 2026-11-28 verified account `262370457690`, region
  `eu-central-1`, identity pool with one enabled synthetic user, one ACTIVE
  tenant-matched profile, zero current test-owner entitlements, and one
  expired-only global row each for ATS and Addition. The four ATS and four
  Addition historical orders are all `processing=COMPLETED`; no open relevant
  work or results. Shared worker DLQ approximate visible count is 1; not
  received or inspected.
- Lifecycle `DISABLE` dry-run used a fresh redacted inventory and returned
  `DRY_RUN`, zero blockers, `ACTIVE→INACTIVE`, `expired_only`, and no
  entitlement withdrawals. Inventory digest starts `38fd2c0f`; output remains
  outside the repo at `%TEMP%\ris-addition-final-e2e\ats-disable-impact-current.json`.
- Terraform context was verified read-only: workspace `ris-dev2`, state serial
  `76`, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`; only the catalog seed
  is managed in state, no foundation-entitlement resources. No plan or apply has
  yet been made.
- No code/runtime defect was established. Phase 2 changes the Terraform ATS
  catalog seed to `INACTIVE` and updates its seed regression. The targeted seed
  regression passed (**26 passed**); no existing Addition/live test suite was
  repeated. The required deployment bundle build completed; agent bundle SHA
  prefix `507bc17d`, analysis bundle `370890d4`, reader bundle `bea4c3e5`.

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

1. Current read-only check found one enabled user in the target pool and one
   ACTIVE profile with matching tenant claim. Do not create a user/profile
   unless separately listed and approved.
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

No further live action is taken until those approvals are explicit. A combined
backend Terraform plan is **not yet prepared**: the active configuration declares
an S3 backend lock table `mays-ris-tf-lock`, while the prior verified RIS-DEV2
installation evidence identifies `ris-dev2-tf-lock`; backend/state-key inputs
must be re-established from the actual installation context rather than guessed.
The planned entitlement window also needs a fresh T0 immediately before plan
creation. No plan/apply was run. Main merge was not performed. The protected
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` was not used
as output, staged or changed.
