# RIS Agent Lifecycle 11 — Runtime Enforcement & Live Verification

**Project:** ris-dev2 · account 262370457690 · region eu-central-1 · workspace ris-dev2
**Baseline:** RIS-AGENT-LIFECYCLE-10
**Date:** 2026-11-18
**Status:** ENFORCEMENT LIVE IN RIS-DEV2 · PARTNER TRAFFIC STILL NO-GO

---

## 1. Delta to Lifecycle-10

Lifecycle-10 delivered the contract but left one decisive gap: `POST /orders`
persisted an agent order **before** any authorization, and the reader never
read the catalog. A DISABLED agent therefore kept receiving orders; only the
worker rejected them later, leaving an order with no `processing`.

Lifecycle-11 closes that gap with one minimal change and proves it live.

---

## 2. Actual runtime gates (before → after)

| Entry point | Before | After |
|---|---|---|
| `POST /orders` (agent.execution) | persists, no agent check | **403 before persist** when entitlement invalid/absent; 503 if store unavailable |
| Dispatch ingress → worker | entitlement re-check (was already wired) | unchanged; still terminal `DEAD_LETTER` on denial |
| API execute (partner/m2m) | catalog + entitlement | unchanged |
| `GET /agents`, introspection | catalog + entitlement | unchanged |
| Retail `POST /orders` | no agent gate | unchanged (no gate needed) |
| Catalog status | discovery only, not execution | unchanged — catalog is still **not** a worker gate |

The enforced rule: **a valid agent entitlement is required to create and to
execute an agent order.** The catalog remains a discovery/API surface.

---

## 3. Implementation

`lambda/orders_reader.py`

- new `_require_agent_entitlement(...)` runs after profile resolution and
  before the order row is written;
- it calls the **same** `check_worker_entitlement` used by the worker, with the
  profile's `ownerUserId`, `tenantId`, `apiProfileId` and the order's `agentId`;
- denials map to `403 AGENT_ORDER_REJECTED`; a missing/unreachable store maps
  to `503 SERVICE_UNAVAILABLE` (fail-closed, never silent allow);
- the detailed reason stays in the log, the client gets a stable code.

`lambda/build_zip.py`

- the flat reader bundle now includes `agents/ecosystem/worker_authorization.py`
  (stdlib only), with a repo/flat import fallback.

`terraform/modules/orders_reader`

- new `ENTITLEMENTS_TABLE` env;
- read-only `dynamodb:Query` on the entitlements table and `index/*`;
- root module passes the existing DynamoDB outputs.

No new catalog/registry architecture, no second permission world.

---

## 4. Live canary (synthetic data, ris-dev2 only)

Plan (reviewed): **2 updates, 0 add, 0 destroy, 0 replace**
`reader_agent_dispatch` IAM policy + `orders_reader` Lambda.
Plan SHA-256 `47862CF869763E20734969595915ECACFF7A44F837E2BFB1761595F561BA5E0B`.
Post-apply plan: **no changes**. State serial 63 → **64**, lineage
`a0bd361d-…` unchanged, 266 resources.

Synthetic identity: profile `aprof_lc11canary`, subject `lifecycle11-canary-sub`,
tenant `ris-dev2-lifecycle11` (both entitlements removed after the run).

| Step | Result |
|---|---|
| ENABLED → agent order | **201**, order `ord_dce286fa42aa192773f67276`, dispatch `SENT`, work `work-def684e6d16c0d11` **COMPLETED**, result `sum=42`, delivery `SENT`, Orders `processing COMPLETED` |
| DISABLED (entitlement removed) → same order | **403 `AGENT_ORDER_REJECTED`**; no order row persisted; only the enabled order exists for the synthetic owner |
| DISABLED → direct work item (`work-lc11-direct`) | worker **`DEAD_LETTER`**, `ENTITLEMENT_DENIED / no-entitlement`, no result |
| Other agent while addition disabled | ATS order `ord_120536c300e188f7c0a244dd` **201**, work `work-3226944b7be8ecfa` **COMPLETED**, bodyVersion 2.0, delivery `SENT` |
| Retail order | `ord_8945fb4ee8d7e65b820c381e` **201** (`orderType=retail`), no dispatch |
| ENABLED again | order `ord_e79d7cc716b61af254bc8577` **201**, work **COMPLETED**, `sum=42`, delivery `SENT`, Orders `processing COMPLETED` |
| Orphan check | every created row is accounted for and terminal; no `QUEUED`/`RUNNING` left |

Queues after the run: dispatch, dispatch DLQ, work queue, result queue and
result DLQ all **0 visible / 0 in-flight**. The Orders queue is 0.

---

## 5. Shared resources — unchanged

| Resource | Evidence |
|---|---|
| Worker `ris-dev2-dev-agent` | code SHA `UljJnuYr…` unchanged |
| Dispatch ingress | code SHA `UljJnuYr…` unchanged |
| Dispatch/result queues + DLQs | present, empty, no policy change |
| Orders reader | only intended update (new code + `ENTITLEMENTS_TABLE` + Query) |
| Tables | all 21 `ris-dev2` tables present, nothing destroyed |
| HMAC secret | one version, `AWSCURRENT` |
| Catalog / offers / partner applications | unchanged (`ats-agent` ACTIVE, offers 0, no partner row changes) |

Applied change set: exactly 2 updates, no delete, no replace.

---

## 6. Partner reconciliation

- Synthetic entitlements and the synthetic profile were removed after the run:
  entitlements back to 2, api-profiles back to 4, offers 0.
- No offer, grant, partner application, credential or client reservation was
  modified.
- External partner references remain **PENDING** (see Lifecycle-10
  `partner-bindings.md`); nothing outside this repository was touched.
- `addition_agent` stays dispatch-only; a catalog seed is still an explicit
  INSTALL change request.

---

## 7. Tests

| Suite | Result |
|---|---|
| `tests/test_orders_reader_agent_gate.py` | 10 passed, 7 subtests |
| Reader + dispatch e2e + result transport + packaging + lifecycle + orchestrator + catalog + multi-agent + partner boundary | **180 passed, 8 skipped, 13 subtests** |
| Reader bundle flat import (`worker_authorization` + `orders_reader`) | PASS (4-file bundle, stdlib only) |

Gate cases covered: enabled, disabled-before-persist, other agent unaffected,
tenant mismatch, profile-bound mismatch, expiry, missing store (503), resolver
outage (503), parity with the worker decision, retail unaffected.

---

## 8. Known limitations / open risks

1. **Catalog is still not an execution gate.** DISABLE must remove the
   entitlement; a catalog-only change does not stop new orders. Documented in
   both packages.
2. **No `ORDER_FAILED`.** A denied *pre-existing* dispatch ends as
   `DEAD_LETTER` with no result; Orders cannot distinguish failed from running.
   The new reader gate prevents *new* stranded orders but not historical ones.
3. **Reader POST idempotency** is still per-order-row only; a client retry
   without the same request can create a second order.
4. **Work-item TTL** remains 30 days in code vs 90 days in the matrix; order
   rows omit `expiresAt`.
5. **PURGE** stays blocked until retention/legal approval and an agent
   deletion-ledger type exist.
6. **Operational dependency:** the reader now fails closed (503) if
   `ENTITLEMENTS_TABLE` or the entitlement store is unavailable. That is
   intentional but must be in the runbook.

---

## 9. Operations decisions required

1. Treat entitlement withdrawal as the DISABLE primitive; pair it with a
   catalog `INACTIVE` change via Terraform for discovery correctness.
2. Never decommission a single agent with `enable_agent_transport` or
   `orders_agent_result_enabled` (shared switches).
3. Decide whether `addition_agent` should become API-discoverable (catalog
   seed) or remain dispatch-only.
4. Approve retention and a deletion-ledger type before enabling PURGE.
5. Keep the reader gate in the alarm/runbook path: a 503 spike means the
   entitlement store is unreachable, not that agents were disabled.

---

## 10. Commits

- `f80a1f3` — reader entitlement gate, bundle, Terraform, gate tests.
- this report + release manifest + package/doc alignment (see audit log).
