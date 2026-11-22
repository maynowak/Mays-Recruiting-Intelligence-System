# RIS-ANALYSIS-ORDER-BOUNDARY-AUDIT-12A — Ownership · Ecosystem Contracts · No Apply

**Date:** 2026-11-21
**Repositories:** RIS `5e8df80` (`feature/ris-analysis-integration-07`),
Mays-Orders read-only `9627eb2`, Jobsearch `e77ee94`
**Status:** **CORRECTION REQUIRED** — one latent boundary gap was found and
minimally fixed; the stored 12 plan is invalid and needs a new approval.
**No apply, no main merge, no production change, no real data.**

---

## 1. Ownership matrix

| Responsibility | Owner | Code reference |
|---|---|---|
| Order creation, validation, totals/pricing | Mays-Orders | `lambda/src/order_service.py:125` (`create_order`), `:131-144` (line/total calculation), `lambda/src/validation.py:40` (`validate_create_order`) |
| Order status transitions | Mays-Orders | `lambda/src/state_machine.py:15` (`can_transition`), `order_service.py:201` (`update_order_status`, conditional write at `:211`) |
| Order persistence / erasure | Mays-Orders | `order_service.py:159` (`put_item`), `:347` (`erase_subject`) |
| HTTP order API | Mays-Orders | `lambda/src/index.py:128` (`handler`) |
| ORDER_DISPATCH envelope construction | Mays-Orders (code shipped via the generated module, pin `5cf50a0`) | `terraform/modules/mays_orders/lambda/src/dispatch.py:39` (`build_dispatch_envelope`), `:20` (`ORDER_DISPATCH`) |
| Dispatch receipt, context verification, WorkItem creation | RIS ecosystem | `lambda/dispatch_ingress.py` (`handler`, `resolve_context`), `agents/transport/order_transport.py` (`dispatch_to_work_item`) |
| WorkItem lifecycle, idempotency, retry/attempts | RIS ecosystem | `agents/runtime/pipeline.py:482` (`process_record`), `:306/:349` (conditional WorkItems write) |
| Result sending (ORDER_RESULT) | RIS ecosystem | `agents/transport/order_result_sender.py` (`make_sender`, `send_message`), `pipeline.py:852` (`_forward_order_result`) |
| Result consumption/ack | Mays-Orders | `terraform/modules/mays_orders/lambda/src/result_consumer.py`, `result_envelope.py` (HMAC verify, order/work/correlation match) |
| Analysis execution | RIS internal partner | `lambda/analysis_runner.py`, `agents/analysis_agent/agent.py`, `agents/analysis/orchestrator.py` |

The analysis agent is not an owner of any order row in this matrix.

## 2. Analysis call path

```
analysis_runner.handler
  → gate: _is_analysis_work (type/capability/agentId)
  → process_record (WorkItems, entitlement re-check, attempt/idempotency)
  → AgentBody (analysis agent instance)
  → AnalysisAgent → AnalysisOrchestrator
  → parser Lambda (RIS_PARSER_MODE=lambda) / CV / job store
  → WorkItems result (existing persistence)
```

Verified:

1. **No order creation/status mutation** — analysis files contain no
   `create_order`, `update_order_status`, `validate_create_order`,
   `ORDER_DISPATCH` or `ORDER_RESULT`; no `agents.orders` import.
2. **No pricing/billing** — no `totalAmount`, `lineTotal`, `unitPrice`,
   `pricing` or `billing` reference.
3. **No direct delivery/ack** — the analysis env has no `ORDER_RESULT_QUEUE_URL`
   / secret / `ORDERS_*` / token; the role has no SQS/Secrets permission.
   The result path returns `order_result_delivery: NOT_ORDER` and never resolves
   the result sender (test-pinned).
4. **No own dispatch queue or routing** — no SQS client, no queue Terraform,
   no second router; the existing `process_record` is reused.
5. **No duplicated order idempotency** — idempotency remains WorkItem-level
   (`workId` conditional write), not order-level.
6. **WorkItem idempotency** — replay is a duplicate without re-execution
   (`test_analysis_order_boundary`, runner integration tests).
7. **Results only via existing RIS contracts** — persisted in WorkItems with
   `CVParserResultBody 1.0` / `JobParserResultBody 1.0` /
   `ATSAnalysisResultBody 2.0` / `ComparisonResultBody 1.0`.
8. **No foreign tenant/partner/order mutation** — analysis only writes its own
   WorkItem; owner/tenant checks remain in `cv_bridge`/`partner`.

## 3. Boundary violation found and corrected

**Finding:** `analysis_runner` previously accepted any WorkItem. Because
`process_record` → `ensure_reference_agent` registers the whole ecosystem
(including `agents.orders.function`), an invocation with
`type=agent_orders` / `capability=orders.create` could have routed order work
through the analysis Lambda and its role. No analysis Lambda is deployed, so
there was no live exposure, but the boundary was not enforced in code.

**Minimal fix:** `lambda/analysis_runner.py` now rejects any WorkItem unless
`type == "agent_analysis_agent"`, `capability == "analysis.run"` and
`agentId in (None, "", "analysis-agent")`, before `process_record`
(`_is_analysis_work`, `work_type_not_allowed`). No order architecture was
added or changed; no new transport component.

The fix changes `analysis_runner.py`, therefore the analysis bundle hash and the
stored 12 plan are **stale** (section 7).

## 4. Historical changes (CANARY-10B)

| Change | Owner | Part of existing integration? | Required for analysis? | Duplication? |
|---|---|---|---|---|
| `dispatch_ingress` WorkItems `index/*` | RIS agent transport | Yes — dispatch/entitlement WorkItem queries; commit `5438256` | No (baseline integration) | No |
| Mays-Orders `ORDER_DISPATCH_QUEUE_URL` | Mays-Orders generated module | Yes — Orders→RIS dispatch; commit `5438256`, builder `installer/build_mays_orders_module.py` | No | No |
| `orders_agent_dispatch` policy | RIS root/integration | Yes — Mays-Orders handler role → RIS dispatch queue; commit `7146d24` | No | No |
| `order_result_transport` policy | RIS Lambda role | Yes — existing RIS→Orders result transport; commit `7146d24`, additive update `c24f734` | No | No |

No existing order routine was removed. These are pre-existing ecosystem
mechanisms and were approved as part of the additive 10B plan; the analysis
runtime uses none of them (no queue/secret/env, result path `NOT_ORDER`).

## 5. IAM / environment evidence

- Analysis role policies: logs, documents `tenant/*` read, jobs `jobs/*` RW,
  parser invoke. The new data policy adds WorkItems RW,
  Entitlements/PartnerProfiles read. No SQS, Secrets Manager, Orders table or
  Orders API.
- Analysis Lambda env: `RIS_PARSER_MODE=lambda`, parser function, WorkItems/
  Entitlements/PartnerProfiles/Documents/Jobs. No `ORDER_*`, `ORDERS_*` or
  token.
- Order transport modules (`order_transport`, `order_result_sender`,
  `dispatch_ingress`, `agents.orders`) are not imported by analysis code.

## 6. Regression results

| Check | Result |
|---|---|
| Boundary/static/runtime tests | 10 passed |
| Runner/unit + integration | 17 passed |
| Full focused set (21 files) | **314 passed + 13 subtests** |
| Terraform fmt / validate | PASS (unchanged) |

## 7. Terraform plan validity

The stored 12 plan is **invalid for apply**:

| | Old (12) | New (12A) |
|---|---|---|
| Plan SHA-256 | `b892d17a…f700d` | `7258bd8b1f0f00936dcb5ff4a2851dc0e1832ab20437486523e14b3b73468b81` |
| Plan JSON SHA-256 | `0a1bb40c…68861` | `f33c27aa9ea215155ce5d486e4e9ddbc7321f53684329378146459461820554d` |
| Bundle SHA-256 | `f3c2f1a2…a2314` | `fff25f1e2b80ecbd216746cc37fa98567295347710283ce1d64b04705686d0b6` |
| Bundle size | 287 919 | 288 213 |
| Adds/changes/destroys | 2/0/0 | **2/0/0** |
| Guard | `NO_SHARED_DESTROY` | **`NO_SHARED_DESTROY`** |
| State | serial 67 / lineage `a0bd361d…` | unchanged |

Only the same two resources remain: analysis Lambda and the dedicated data
policy. Parser Lambda untouched. The old plan must not be applied; the new plan
requires a new explicit approval.

## 8. Verdict and next step

**CORRECTION REQUIRED.** The ownership boundary is confirmed and the latent
gate is fixed and tested, but the pre-fix plan/bundle is invalid. No apply was
performed. A new approval must reference the new 2/0/0 plan and bundle above.
