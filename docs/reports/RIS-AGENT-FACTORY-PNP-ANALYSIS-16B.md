# RIS-AGENT-FACTORY-PNP-ANALYSIS-16B — Order Status / Result Contract

**Date:** 2026-11-22
**Basis:** `6080b5f` on `feature/ris-analysis-integration-07`
**Fix commit:** `5de8da2`
**Mode:** minimal RIS OrdersPort correction + local contract tests; no AWS
mutation, no Terraform apply, no deployment, no new credential or agent
identity.
**Status:** **FIXED / LOCAL TESTED. AWS VERIFICATION PENDING.**

---

## 1. Scope

Goal: use the existing Mays-Orders result functions correctly through the
existing RIS `OrdersPort`. KISS: no new orders system, queue, result consumer
or Mays-Orders lifecycle change.

Confirmed defect: `RealMaysOrdersAdapter.get_order_status()` treated every
HTTP 2xx response with an `orderId` as `OrdersResultType.APPROVED`. An order
that was accepted but still pending therefore looked completed.

## 2. Contract review (STEP 1)

### 2.1 Code inspected

| Area | File |
|---|---|
| RIS port contract | `agents/orders/adapter.py` |
| RIS real adapter | `agents/orders/real.py` |
| RIS orders function | `agents/orders/function.py` |
| RIS orders reader | `lambda/orders_reader.py` |
| RIS tests | `tests/test_real_orders_adapter.py`, `tests/test_orders_reader.py`, `tests/test_orders_reader_agent_gate.py` |
| Mays generated module | `terraform/modules/mays_orders/lambda/src/{order_service,result_handler,result_envelope,dispatch,identity}.py` at source `016cdfd` |

### 2.2 Mays pin boundary

| State | Value | Use |
|---|---|---|
| RIS pin file | `5cf50a0` (v0.5.0-rc.2) | pin metadata |
| Generated module | source `016cdfd6ac62565dcec9a2fee78cb898fb919e59` | behavior inspected for this report |
| Local Mays checkout | `9627eb2` | review reference only; its `lambda/src` lacks dispatch/identity/result consumer |

The local RC line is **not** the generated module source. The dispatch/result
claims below are based on the generated module `016cdfd`.

### 2.3 `GET /orders/{orderId}` and projection

- Mays `order_service.apply_result` writes `processing.status` as
  `COMPLETED` (ORDER_RESULT) or `FAILED` (ORDER_FAILED), plus
  `processing.result` or `processing.error`.
- `to_public_processing` releases `status`, `attempt`, `completedAt`,
  the fachliche `result` and a sanitised `error.message`; it withholds
  `workId`, `messageId`, `idempotencyKey` and execution internals.
- RIS `orders_reader._public_processing` mirrors this owner-facing projection
  and scans for credential-shaped data before release.
- HTTP GET is owner-scoped: the owner key is `sha256(iss + NUL + sub)`;
  foreign/missing/legacy-unbound orders return 404, invalid identity returns
  401.

### 2.4 `apiProfileRef` at the real entry points

| Entry point | Binding behavior | Status |
|---|---|---|
| RIS `orders_reader._create_agent_order` | Requires `apiProfileRef`; `_load_profile` requires ACTIVE profile, `ownerUserId == verified subject`, tenant; `_require_agent_entitlement` re-checks entitlement | **IMPLEMENTED / TESTED** on the RIS path |
| RIS dispatch ingress | Resolves any ACTIVE `contextRef`; cannot prove it belongs to the Mays order owner | **CANNOT PROVE** the Mays binding |
| Mays generated module `prepare_dispatch` | Checks `identity.can_read(item)` (order ownership) only; `apiProfileRef` is client-supplied metadata | **OPEN, Mays-owned (C)** |
| RIS `RealMaysOrdersAdapter.submit_order` | `orders.create` builds a retail body only; no agent-order create | **MISSING by design** for agent orders; unchanged |

No cross-repo Mays correction was made. The Mays `apiProfileRef` ownership
binding remains a real blocker for secure order-driven traffic.

## 3. Minimal fix (STEP 3)

`RealMaysOrdersAdapter` now separates:

- `OrderResult.success` — technical port/API success (valid HTTP 2xx).
- `OrderResult.result_type` — business state.

For `orders.status`:

| Condition | result_type | success |
|---|---|---|
| `processing.status=COMPLETED` with object `processing.result` | `APPROVED` | true |
| `processing.status=COMPLETED` without result body | `ERROR` + `contract_error=missing_processing_result` | true |
| `processing.status=FAILED` with/without error | `REJECTED` | true |
| `order.status=CANCELLED` | `REJECTED` | true |
| `order.status=DELIVERED` | `APPROVED` | true |
| accepted, no terminal processing | `PENDING` | true |
| 2xx without `orderId` | `ERROR` | false |
| 4xx controlled error | `ERROR` | false |
| 5xx / transport | `TransientOrdersError` (retry) | — |

Additional changes:

- `orders_function` forwards `processing`, `processing_status`,
  `order_status`, `http_status` and `contract_error`; the top-level `success`
  remains technical success, the business state is `result_type`.
- Unexpected response bodies are no longer echoed into `OrderResult.data`
  (avoids leaking foreign/credential-shaped payloads).
- No Mays-Orders code, order lifecycle, queue, result consumer or Terraform
  resource was changed.

## 4. Contract tests (STEP 2)

| # | Synthetic case | Evidence |
|---|---|---|
| 1 | Order accepted, processing open | `TestOrderStatusSemantics.test_accepted_order_without_processing_stays_pending` → PENDING, not APPROVED |
| 2 | `processing.status=COMPLETED` with `processing.result` | `test_completed_processing_is_approved_with_result` → APPROVED, result preserved |
| 3 | `processing.status=FAILED` with `processing.error` | `test_failed_processing_is_rejected_with_error` → REJECTED, sanitized message |
| 4 | HTTP 200 GET must not mean completed | Pending test above; reader test `test_pending_order_has_no_fabricated_processing_result` → no `processing` fabricated |
| 5 | Foreign owner / invalid identity | Existing reader tests: foreign owner 404, missing/wrong issuer 401, wrong client 401, invalid token_use 401; new `test_profile_owned_by_another_user_is_rejected` and `test_inactive_profile_is_rejected` → 403, no persist/dispatch |
| 6 | Transient errors and missing results | `test_transient_status_raises` (503 → TransientOrdersError); `test_success_without_order_id_is_controlled_error`; `test_completed_without_result_is_a_contract_error` |
| 7 | No RIS key/JWT in results/logs | `test_status_result_contains_no_transport_credentials`; `test_status_output_contains_no_token`; existing reader `test_secret_shaped_result_returns_500_without_leak` |

Test results:

- Adapter/reader/agent-gate suite: **86 passed + 7 subtests**.
- Broader factory/analysis/auth regression: **533 passed, 30 skipped,
  13 subtests passed**.

## 5. Evidence matrix

### IMPLEMENTED

- Technical vs business status separation in `OrderResult` and the real
  adapter.
- `processing.status/result/error` projection through Mays and RIS reader.
- RIS reader owner/profile/entitlement admission for agent orders.
- `orders_function` passthrough of processing and HTTP metadata.
- Existing 404/401/500 leak-safe behavior.

### LOCAL TESTED

- New and existing adapter/reader/agent-gate tests: 86 passed + 7 subtests.
- Broad focused regression: 533 passed, 30 skipped, 13 subtests.
- No network and no AWS calls in these tests.

### AWS VERIFIED

- **NONE.** No live GET, no Mays order, no analysis/deployment change. The
  analysis Lambda remains undeployed; plan `9a0324a0…` is not applied.

### BLOCKED

1. **Mays `apiProfileRef` ownership binding (C):** the Mays direct path still
   uses client-supplied metadata without proving it belongs to the order
   owner/partner. Real order-driven traffic must wait.
2. **DLQ exhaustion without `ORDER_FAILED`:** unchanged, separate decision.
3. **Automatic agent resume:** out of scope; still not implemented. Result
   retrieval remains the supported polling path.
4. **Live AWS proof of the corrected status mapping:** pending an approved
   canary.

## 6. Verdict

**DEFECT CONFIRMED AND FIXED IN THE EXISTING RIS ORDERSPORT.** A successful
HTTP GET is no longer reported as a completed order; only terminal
`processing.status` with a result body is APPROVED. The change is local,
KISS-compatible and covered by synthetic contract tests. AWS verification and
the Mays cross-repo `apiProfileRef` binding remain open and explicitly
separate.
