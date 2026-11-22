# RIS-ANALYSIS-ECOSYSTEM-INTEGRATION-13 — Shared SQS Worker · Ecosystem · Analysis Agent

**Date:** 2026-11-21
**Base:** RIS `2f11da2` (`feature/ris-analysis-integration-07`), Jobsearch
`e77ee94` (parser code `c40bf78`), Mays-Orders read-only `9627eb2`
**Status:** **CORRECTION REQUIRED** — worker/ecosystem integration implemented
and tested, but two pre-existing runtime gaps block a "full ecosystem canary".
**No apply, no merge, no production change, no real data.**

---

## 1. Actual SQS topology (code + Terraform)

| Queue | Name | Producer | Consumer |
|---|---|---|---|
| Dispatch | `ris-dev2-dev-agent-dispatch` | Mays-Orders handler (`ORDER_DISPATCH`) | `dispatch_ingress` via event source mapping |
| Dispatch DLQ | `ris-dev2-dev-agent-dispatch-dlq` | dispatch redrive | operator |
| Work | `ris-dev2-dev-work-queue` | RIS API execute path (`lambda/handler.py`, `WORK_QUEUE_URL`) | shared worker `ris-dev2-dev-agent` via event source mapping |
| Work DLQ | `ris-dev2-dev-dlq` | work-queue redrive (`maxReceiveCount`) | operator |
| Result | `ris-dev2-mays-orders-agent-results` | RIS worker/ingress (`ORDER_RESULT`) | Mays-Orders result consumer |
| Result DLQ | `ris-dev2-mays-orders-agent-results-dlq` | result redrive | Mays-Orders operator |

Additional domain queues (`cv`, `ats`, `match`) exist but are not part of the
analysis path.

**Historical-vs-code divergence (documented, not changed):** the architecture
document describes `WorkItem persistieren → gemeinsame SQS Work Queue →
Worker`. In the current code the **ORDER_DISPATCH** ingress calls
`process_record` **directly** in the ingress Lambda (`dispatch_ingress.py:105/131`);
only the API execute path enqueues to the work queue. Both paths share
`process_record`, registry, entitlement, fence and AgentBody. This divergence
predates the analysis work and is not changed here.

## 2. Responsibilities

| Responsibility | Owner |
|---|---|
| Order lifecycle, owner, pricing, persistence, result retrieval | **Mays-Orders** |
| ORDER_DISPATCH construction | Mays-Orders (`dispatch.py`) |
| Transport validation, context resolution, WorkItem creation | RIS (`order_transport`, `dispatch_ingress`) |
| WorkItem state, attempts, retry, idempotency, subject fence | RIS runtime (`pipeline`) |
| Registry/discovery/eligibility/routing, AgentBody, entitlement re-check | RIS ecosystem |
| Agent domain logic | Agent (addition / analysis / …) |
| ORDER_RESULT / ORDER_FAILED envelope + delivery | RIS transport (`order_result_sender`) |
| Result consumption / order mutation | Mays-Orders (`result_consumer`) |

## 3. Addition Agent reference path

```
ORDER_DISPATCH → dispatch queue → dispatch_ingress
  → process_record → registry selects addition_agent
  → AgentBody → AdditionAgent.process_work
  → WorkItem COMPLETED → ORDER_RESULT via existing sender
```

The addition agent has no own compute, queue, retry or transport
(`agents/addition_agent/agent.py`, registry in `agents/runtime/pipeline.py:154`).
The API execute path reaches the same agent via the work queue and shared
worker.

## 4. Analysis Agent integration (new)

```
dispatch_ingress / shared worker
  → process_record (unchanged WorkItem/attempt/entitlement/fence)
  → registry selects analysis-agent
  → AgentBody route = LambdaAgentHandler (remote)
  → invoke ris-dev2-dev-analysis {"executionMode":"agent","workItem":…}
  → analysis_runner executes only AnalysisAgent.process_work (no WorkItem state)
  → result returned to process_record
  → WorkItems persistence + existing ORDER_RESULT sender
```

- **No new queue**, **no direct Mays→Analysis call**, **no second dispatcher**,
  **no second WorkItem/retry/DLQ** and **no new result transport**.
- `dispatch_ingress` and the shared worker both build the remote handler from
  `ANALYSIS_FUNCTION_NAME`; without it, behavior is unchanged.
- `_is_analysis_work` remains defense-in-depth in the analysis Lambda
  execution mode (rejects order work).
- The analysis Lambda's standalone runner path (`analysis_runner.handler`
  without `executionMode`) remains for internal/synthetic use, but the worker
  path uses execution-only mode.

### AgentInvoker / adapter change

`agents/runtime/remote_agent.py` adds a **generic** `LambdaAgentHandler`
implementing the existing Agent Body contract `process_work(work_item)`; it is
not analysis-specific. It invokes synchronously with:
- 60 s connect/read timeout, zero SDK retries,
- 512 KiB payload limit,
- controlled `RemoteAgentError` for `FunctionError`, non-200, invalid JSON,
- error payload → error code.

`build_analysis_executor()` reads `ANALYSIS_FUNCTION_NAME` and caches one
handler per function/timeout. No change to AgentInvoker, ExecutionEngine or
routing; the handler is passed through `process_record(analysis_agent=…)`.

## 5. Result / retry / DLQ / idempotency

- WorkItem state, attempts and retries stay in `pipeline` (conditional writes,
  same attempt semantics).
- The analysis Lambda returns only the agent result; the worker/ingress owns
  persistence and ORDER_RESULT.
- ORDER_RESULT uses `result_from_work_item` with a **stable message id**
  (`msg_<workId>_order_result`) and idempotency key per (order, work, type).
  A duplicate replay re-emits the same deterministic id; Mays-Orders
  deduplicates.
- **No exactly-once claim:** delivery is at-least-once between DynamoDB, SQS and
  Lambda. The guarantee is idempotent work execution plus deduplicated
  delivery, not distributed exactly-once.
- **Gap — ORDER_FAILED:** the transport supports `ORDER_FAILED` and Mays
  consumes it, but the runtime never emits it on terminal failure
  (no `_forward_order_failure`). This predates the analysis work and blocks a
  full "all result paths" canary.
- DLQ remains the existing redrive policy (`maxReceiveCount`); no new DLQ.

## 6. Tests

| Area | Result |
|---|---|
| Remote adapter (success/errors/timeout/payload) | 7 passed |
| Analysis runner execution mode (agent-only, order reject) | 3 passed |
| Worker/ecosystem wiring + two agents + revoke + duplicate | 8 passed |
| Pipeline result path (ORDER_RESULT stable id, no double execution) | 3 passed |
| Existing worker/dispatch/fence/entitlement/transport | 96 passed |
| Broad focused set (23 files) | **339 passed, 9 skipped** |

`ORDER_FAILED` is covered only at the **transport contract** level
(`test_order_transport_contract.py`); the runtime gap above is documented, not
papered over.

## 7. Terraform plan (new, replaces the retired 2/0/0)

| Item | Value |
|---|---|
| Adds / changes / destroys / replacements | **4 / 2 / 0 / 0** |
| Plan SHA-256 | `78d6c5ec3a42fa177f5e25aafe5dd89720ab2016eda864d3ed2ea9fc68af18c7` |
| Plan JSON SHA-256 | `ec77372c6adda5ec05241b344397730fb4df581d18583c56a2bcd89207c37a0b` |
| State serial / lineage | 67 / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `e51b175711ee7e3d919253767cebf9b632124821e2f2e612fbd1f1de387781ed` (114 files) |
| Analysis bundle | `b0538e71e89cec33f52ef6c865a99aaa19a300ec29e300c0307d5580bc79bc6a` (112 files) |

Adds:
1. `aws_lambda_permission.analysis_invoke_worker[0]`
2. `aws_lambda_permission.analysis_invoke_ingress[0]`
3. `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]`
4. `module.analysis_runtime.aws_lambda_function.analysis[0]`

Changes (both in place, no replacement):
- `module.agent_transport[0].aws_lambda_function.dispatch_ingress`:
  env `ANALYSIS_FUNCTION_NAME`, `ANALYSIS_REMOTE_TIMEOUT_SECONDS` + new bundle hash.
- `module.lambda.aws_lambda_function.agent`: same two env values + new bundle hash.

No queue, IAM policy, table, secret or Cognito/CloudFront/DNS change. The two
invoke permissions are **resource-based Lambda permissions** (no shared IAM
policy edit). The analysis role stays least-privilege; the worker/ingress roles
need no new identity policy.

## 8. Open corrections / approvals

1. **ORDER_FAILED emission** on terminal failure (separate reviewed change;
   uses the existing `result_from_work_item(..., message_type=ORDER_FAILED)`
   contract; no new transport).
2. **ORDER_DISPATCH → work-queue handoff** divergence (existing behavior;
   decide whether to align with the document or document the direct ingress
   path as authoritative).
3. Apply approval for the new 4/2/0 plan; the old 2/0/0 plan is retired.
4. Synthetic environment approval (`ANALYSIS_ENTITLEMENTS` / consent are still
   deny-by-default).
5. Legal/entitlement/catalog approvals remain unchanged; no real data.

## 9. Verdict

**CORRECTION REQUIRED.** The analysis agent now runs through the existing
worker/ecosystem/AgentBody contract with a generic remote adapter, no new
queue/dispatcher/state machine and no order ownership. A full ecosystem canary
cannot be claimed until ORDER_FAILED is emitted (and the dispatch/work-queue
divergence is decided). No apply has been performed.
