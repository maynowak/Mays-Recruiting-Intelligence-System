# Analysis Agent vs. Addition Agent — Ecosystem/Transport Integration

**Date:** 2026-11-21
**Scope:** read-only comparison against the documented architecture.
**Status:** **INTEGRATION GAP — CORRECTION REQUIRED** (no apply, no code change
in this report).

The Addition Agent is the reference for "an agent that is already integrated
through the existing SQS → ecosystem → AgentBody path". The Analysis Agent
reuses the same runtime contracts, but its compute is **not** wired into that
transport path.

---

## 1. Binding architecture (from the documents)

| Level | Responsibility | Binding rule |
|---|---|---|
| Mays-Orders | generic order, owner, lifecycle, persistence, result retrieval | authoritative order store |
| RIS agentOrder V1 | business instruction (`target`, `input`, `metadata`, `processing`, `resultContract`) | nested inside the Mays order |
| Transport V1 | decoupled messaging `ORDER_DISPATCH` → RIS, `ORDER_RESULT`/`ORDER_FAILED` → Orders | no parallel contracts |
| RIS Runtime | registry, discovery, eligibility, entitlement, WorkItem, AgentBody | reuse the existing runtime |
| Partner boundary | identity, RIS key, API profile, tenant isolation | key server-side; metadata is not authorization |

## 2. Addition Agent (reference: fully integrated)

| Level | Addition Agent | Evidence |
|---|---|---|
| Mays-Orders | order contains an `agentOrder` targeting `addition_agent` | `mays_orders/.../dispatch.py:39` builds `ORDER_DISPATCH` from the stored order |
| agentOrder V1 | target/input/metadata carried unchanged | `agents/transport/order_transport.py` (`dispatch_to_work_item`) |
| Transport V1 | `ORDER_DISPATCH` arrives on `ris-dev2-dev-agent-dispatch` | `terraform/modules/agent_transport` (queue + event source mapping) |
| RIS Runtime | `dispatch_ingress.handler` → `process_record` → registry → AgentBody | `lambda/dispatch_ingress.py:105,131`; `pipeline.py:154-155` |
| Result | same pipeline forwards `ORDER_RESULT` using the existing queue/secret | worker/ingress env: `ORDER_RESULT_QUEUE_URL`, `ORDER_RESULT_SECRET_ARN` (`terraform/modules/agent_transport/lambda.tf`, `modules/lambda/main.tf`) |
| Agent code | no infrastructure knowledge | `agents/addition_agent/agent.py` (no SQS/DynamoDB/HTTP) |

The addition agent runs **inside** the existing dispatch/execution function; it
does not get its own compute, queue or transport. Its WorkItem is
`type=agent_addition_agent`, `capability=math.add`, `agentId=addition_agent`.

## 3. Analysis Agent (actual state)

| Level | Analysis Agent | Evidence |
|---|---|---|
| Mays-Orders | no order integration; direct internal WorkItem only | dedicated Lambda is invoked directly |
| agentOrder V1 | compatible in principle (reuses `process_record`) | `lambda/analysis_runner.py` |
| Transport V1 | **not bound**: the analysis Lambda is not an event source and is not called by `dispatch_ingress` | `terraform/modules/analysis_runtime` has no SQS mapping; `dispatch_ingress.py` calls `process_record` locally |
| RIS Runtime | registered in the same registry/AgentBody; WorkItems/idempotency reused | `pipeline.py:163-164`; runner integration tests |
| Compute | **separate Lambda** with parser/env, direct invoke | `ris-dev2-dev-analysis` (planned) |
| Result | **no result transport config** on the dedicated Lambda | env has no `ORDER_RESULT_*`; `_forward_order_result` returns `NOT_ORDER` and never resolves a sender |
| Partner boundary | WorkItem tenant/user/partner + entitlement re-check | same pipeline; analysis-specific consent gate |

The `_is_analysis_work` gate ensures the dedicated function cannot execute order
work, but it also means an `ORDER_DISPATCH` that targets `analysis-agent` is
handled by `dispatch_ingress`, not by the dedicated function.

## 4. Gap matrix

| Question | Addition Agent | Analysis Agent |
|---|---|---|
| Reaches the agent through the shared dispatch queue? | Yes | No |
| Executes in the existing dispatch/runtime function? | Yes (dispatch ingress) | No (direct invoke) |
| Has WorkItem idempotency/persistence? | Yes | Yes (when invoked) |
| Sends results back via existing Transport V1? | Yes | No (no env/secret/queue permission) |
| Has its own queue/transport? | No | No (good) — but also no binding |
| Owns order data? | No | No (verified) |
| Fails closed on missing consent/entitlement? | n/a | Yes |

**Practical consequence:** a Mays order whose `agentOrder.target` is
`analysis-agent` would send `ORDER_DISPATCH`; `dispatch_ingress` would select the
analysis agent, but its env lacks `ANALYSIS_ENTITLEMENTS`/`ANALYSIS_CONSENT` and
`RIS_PARSER_*`, so the WorkItem ends as a controlled rejection/DEAD_LETTER.
Conversely, the deployed analysis Lambda has the parser but no `ORDER_RESULT`
transport. Neither path completes the documented order → analysis → result flow.

## 5. No order-boundary violation

The earlier audit holds: the analysis code has no order creation, status,
pricing, delivery or acknowledgement. It does not import the orders agents,
does not own a queue and does not duplicate idempotency. The gap is **transport
integration**, not ownership: the analysis agent is a correctly isolated agent
whose compute is not connected to the existing dispatch/result path.

## 6. Minimal integration options (approval required, not implemented)

**Option A — route through the existing dispatch path (recommended if Mays
orders should target analysis).**
`dispatch_ingress` detects an analysis WorkItem and synchronously invokes the
dedicated analysis Lambda; the dedicated function keeps WorkItem persistence.
For the result, either (a) give the analysis role the existing
`ORDER_RESULT_QUEUE_URL`/secret and let the existing `_forward_order_result`
send it (no new contract, copied permission), or (b) return the result to the
ingress and let the ingress forward it with its existing sender. Adds one
invoke permission and a routing branch; no new queue, no duplicate order
lifecycle.

**Option B — execute analysis in the existing dispatch function (exact
addition-agent pattern).**
Add `RIS_PARSER_MODE=lambda`, `RIS_PARSER_FUNCTION` and the analysis env to the
dispatch function, grant parser invoke to the dispatch role, and do not use the
dedicated Lambda. Reuses the path one-to-one, but loses the dedicated role and
puts analysis load into the transport function.

**Option C — keep direct invoke only (internal tooling/synthetic).**
Document that analysis is intentionally not reachable from Mays orders; do not
add `ORDER_RESULT` and do not claim order-driven E2E. The dedicated 2/0/0 plan
then remains an internal compute, not an order agent.

Recommended: decide the product intent first. If analysis is an agentOrder
target, take Option A (smallest change, existing transport). If it is only an
internal service, take Option C and remove the "order E2E" expectation.

## 7. Plan impact

This report changes no code or Terraform. The current state remains:

- analysis bundle `fff25f1e…` (after the boundary gate),
- read-only plan `7258bd8b…` (2/0/0), JSON `f33c27aa…`, guard
  `NO_SHARED_DESTROY`, state serial 67,
- **not approved, not applied**; the older `b892d17a…` plan is invalid.

A transport integration (Option A/B) would require a new plan/approval.

## 8. Verdict

**INTEGRATION GAP — CORRECTION REQUIRED.** The Addition Agent demonstrates the
intended SQS/ecosystem path and the Analysis Agent reuses the same runtime
contracts, but it is not connected to the dispatch/result transport. The
analysis agent itself remains within its order boundary; the missing piece is
the approved routing/result wiring, not order logic.
