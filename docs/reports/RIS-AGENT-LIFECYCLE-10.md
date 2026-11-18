# RIS Agent Lifecycle 10 — INSTALL / DISABLE / DETACH / UNINSTALL

**Project:** ris-dev2 · account 262370457690 · workspace ris-dev2 · Orders lifecycle `managed`
**Baseline:** RIS-AGENT-INSTALLATION-08/-09/-10 and RIS-AGENT-OPERATIONS-HANDOFF-10
**Mode:** local implementation, tests, test-environment verification, audit, commits
**Date:** 2026-11-18
**Status:** IMPLEMENTED + TESTED (local) · LIVE GATE NOT WIRED · PARTNER TRAFFIC NO-GO

---

## 1. Scope and constraints

Reused, not rebuilt: agent runtime, catalog, partner registry, offers/grants,
WorkItem, Orders and Transport V1. No second orchestration platform, no new
queue, no per-agent Lambda, table, Cognito client or secret.

Hard constraints honoured:

- no destructive AWS action, no `terraform destroy`/`-target`/`-replace`;
- no PURGE executed, no secret or user mutation;
- no ris-dev or production change, no main merge, no unrequested push;
- HARD STOP before destructive AWS actions and PURGE.

---

## 2. Implemented lifecycle contract

`installer/agent_lifecycle.py` (new) + delegation from `installer/agent_install.py`
(`--action`). Actions: `INSTALL`, `UPDATE`, `DISABLE`, `ENABLE`,
`DETACH_PARTNER`, `UNINSTALL`, `PURGE`, `STATUS`, `VERIFY`.

Every action produces:

| Requirement | Implementation |
|---|---|
| Dry-run / plan | `--execute` absent → `DRY_RUN`; state is never written |
| Impact report | `impact`: catalog before/after, bindings to remove, pending external, open orders, retained shared resources, retail unaffected |
| Dependency check | package identity vs manifest, required `lifecycle.yaml` sections, inventory mandatory for destructive actions |
| Resume / idempotency proof | second UNINSTALL → `already_uninstalled`, no state rewrite, grace anchor preserved |
| Audit entry | append-only JSONL with actor, approval, reason, inventory digest, blockers |
| Result manifest | `<state>.result.json` with plan + state |

Safety design:

- the module **never calls AWS**; it mutates only local JSON state;
- PURGE requires the exact `agentId`, prior `uninstalled` state, and is blocked
  while the catalog is active or an inventory reports open orders;
- `--purge-grace-days` enforces a minimum window between UNINSTALL and PURGE;
- `_template` is rejected as non-deployable;
- inventory must contain an explicit `openOrders` list — otherwise it is
  "missing evidence", not "nothing open".

---

## 3. Reality check: where the contract is not yet enforced

Four independent reviews (runtime, partner, operations, security) found the
same structural fact:

**There are only two agent-scoped levers: the `agent-catalog` row and the
entitlement row. Everything else is shared or owner data.**

| Boundary | Reads catalog? | Reads entitlement? | Consequence |
|---|---|---|---|
| Worker / SQS (`agents/runtime/pipeline.py`) | **no** | yes (re-check before run) | DISABLE via catalog does **not** stop execution |
| Order dispatch (`lambda/orders_reader.py` → `dispatch_ingress.py`) | **no** | yes | new orders keep arriving; only entitlement removal stops them |
| API ingress (`lambda/handler.py` partner/m2m) | yes | yes | 403 after DISABLE |
| `GET /agents`, `/v1/introspection` | yes | yes | agent disappears after DISABLE |

So `catalog` alone is **not** a kill switch. The lifecycle documents and the
ATS manifest are corrected accordingly: DISABLE = withdraw entitlements **and**
set catalog `INACTIVE` through a reviewed Terraform change.

Additional verified facts:

- `addition_agent` has **no catalog seed** and is dispatch-only; its
  `lifecycle.yaml` now declares `visibility: ABSENT`, `apiReachable: false`.
- The runtime registers both agents unconditionally; there is no
  de-registration path (`AgentRegistry.unregister` is unused).
- API-route admission with a pre-written `QUEUED` row currently trips
  `WORK_ADMISSION_STATE_UNSAFE`; the dispatch path is the working path.
- A warm Lambda container can carry a catalog-mutated registry state, so
  catalog-based disable is container-history dependent.

These are recorded as open blockers, not implemented around.

---

## 4. Agent and partner dependency matrix

| Layer | ats-agent | addition_agent | Scope | Lifecycle action |
|---|---|---|---|---|
| Runtime descriptor + body routes | ACTIVE (code) | ACTIVE (code) | shared bundle | UPDATE only via shared redeploy |
| Catalog row | seeded ACTIVE | absent | shared table, agent row | DISABLE/ENABLE via Terraform |
| Entitlement rows | per user | per user | shared table, agent row | **the detach/uninstall lever** |
| API profile | shared | shared | owner-bound | retain |
| Credential | shared | shared | profile-bound | retain |
| Partner application + client reservation | shared | shared | tenant-bound | retain |
| Offer (`agentIds[]`) | shared package | n/a | shared | never edit for one agent |
| `GET /agents`, introspection | derived | not listed | derived | automatic |
| Work items / results | shared table | shared table | retained | never deleted |
| Orders (`processing`) | Mays-Orders | Mays-Orders | owner data | never deleted |
| Dispatch/result queues, DLQs, ingress, consumer, worker, reader | shared | shared | shared | never touched |
| HMAC secret | shared | shared | shared | retain |

Entitlement detachment classification (required before any withdraw):

- **P1 profile-bound** — safe to withdraw.
- **P2 user-wide** — also authorizes other consumers; explicit per-row confirmation.
- **P3 provisioning** (`createdBy.role == provisioning`) — Terraform-managed;
  convert to an IaC change, do not withdraw.

---

## 5. Package extension (Phase G)

Per agent (`ats-agent`, `addition-agent`):

- `lifecycle.yaml` — discovery, shared vs exclusive resources, partner bindings,
  uninstall and retention rules, purge boundaries;
- `uninstall.md` — two-lever procedure, drain, retention, idempotency;
- `partner-bindings.md` — binding matrix, P1/P2/P3 classification, share
  firewalls, verification, external PENDING items;
- `retention.md` — per-artifact retention, TTL gaps, purge boundaries.

Corrected unsafe legacy guidance in `ats-agent/manifest.yaml`:
`enable_agent_transport=false` / `orders_agent_result_enabled=false` are shared
switches that remove transport for **every** agent and must not be used to
decommission one agent.

---

## 6. Test evidence

| Suite | Result |
|---|---|
| `tests/test_agent_lifecycle.py` | **17 passed** |
| Lifecycle + orchestrator + installer | 59 passed |
| Agent/orders/partner regression (10 files) | **201 passed, 15 subtests passed** |
| YAML parse of all `agent-installations/*/*.yaml` | 5 files OK |

Covered contract cases:

- addition UNINSTALL removes only `ent-add`, never `dispatch` and never ATS;
- ATS DISABLE keeps retail orders and all shared resources;
- DETACH removes only the agent entitlement, marks the external UI PENDING,
  keeps the shared profile;
- open orders block UNINSTALL and no state is written;
- no secret, `ris_` credential or owner key appears in evidence/audit;
- DISABLE→ENABLE→DETACH→INSTALL→UNINSTALL→UNINSTALL recovery is idempotent;
- PURGE needs confirmation, prior UNINSTALL, inactive catalog **and** the grace
  window;
- destructive actions are blocked without an inventory;
- package identity mismatch is rejected; `_template` is not deployable;
- audit records actor/approval/reason and a 64-hex inventory digest;
- UTF-8 BOM inventories are accepted (PowerShell `Set-Content` fix).

---

## 7. Local verification performed

```
python -m installer.agent_lifecycle --root agent-installations --agent ats-agent \
  --action status --inventory <file>
python -m installer.agent_install --root agent-installations \
  --agent addition-agent --action uninstall --inventory <file>
```

Observed: `STATUS`/`VERIFY` → `REPORTED`; `UNINSTALL` → `DRY_RUN`; result
manifests and audit JSONL written; addition impact lists exactly one binding,
zero open orders, shared dispatch/results/consumer retained. No AWS call.

Live install/uninstall was **not** executed. The earlier live INSTALL/E2E
evidence for both agents (RIS-AGENT-INSTALLATION-09) still stands.

---

## 8. Protected resources (never removed by one agent's lifecycle)

`agent-dispatch` + DLQ + ingress Lambda, `orders-agent-results` + DLQ + result
consumer, worker Lambda, reader Lambda, `work-items`, `mays-orders`,
`agent-catalog`, `entitlements`, `api-profiles`, `credentials`,
`partner-applications`, Cognito pools/clients/domain, HMAC result secret,
application cursor secret, documents bucket, IAM roles.

Only agent-scoped rows change: the catalog row status (via Terraform) and the
entitlement rows for that `agentId`.

---

## 9. Open partner hand-offs (PENDING, never automatic)

External, outside this repository:

- partner `RIS_API_CREDENTIAL` / `RIS_API_BASE_URL` and any hard-coded agent
  allowlist;
- partner UI elements bound to a specific `agentId` (dynamic lists from
  `GET /agents` self-update; static ones do not);
- quota, consent and privacy text tied to the agent purpose;
- partner Cognito pool/client/domain (never part of an agent detach).

Internal PENDING IaC change: add the `addition_agent` catalog seed **only if** it
should become API-discoverable. Until then it stays dispatch-only.

---

## 10. Remaining blockers before partner traffic / production

1. Catalog is not a worker execution gate; DISABLE needs entitlement withdrawal.
2. Order creation is ungated; "block new orders" is only enforceable at the
   producer or by removing the entitlement.
3. API-route admission (`QUEUED` pre-write) is unsafe → `WORK_ADMISSION_STATE_UNSAFE`.
4. No alarm notification path; permanent rejects are dropped without artifact.
5. Batch 5 × ATS 30 s inside a 60 s Lambda can leave a permanent `RUNNING` row.
6. No `ORDER_FAILED` / failure projection for stranded orders.
7. Reader POST lacks request-level idempotency; profile expiry is ignored.
8. Work-item TTL: code 30 days vs matrix 90 days; order-correlated worker rows
   omit `expiresAt` and are retained indefinitely — **REVIEW REQUIRED**.
9. Warm-container catalog registry nondeterminism.
10. Entitlement `DELETE` permission is table-wide; withdrawals need per-row
    evidence and audit.

---

## 11. Recommendations for ris-dev operations takeover

1. Adopt the two-lever rule: catalog status (Terraform) + entitlement (data).
2. Never use `enable_agent_transport` / `orders_agent_result_enabled` to
   decommission a single agent.
3. Require an inventory produced by a read-only order/work scan before every
   destructive action; keep the digest in the change record.
4. Keep PURGE disabled until retention is approved and a deletion-ledger type
   for agent resources exists.
5. Run `VERIFY` after every action and store the result manifest with the change.
6. Add a per-agent catalog status variable only after the worker consults the
   catalog — otherwise DISABLE remains cosmetic.

---

## 12. Artifacts

- `installer/agent_lifecycle.py`
- `installer/agent_install.py` (`--action` delegation)
- `tests/test_agent_lifecycle.py`
- `agent-installations/ats-agent/{lifecycle.yaml,uninstall.md,partner-bindings.md,retention.md}`
- `agent-installations/addition-agent/{lifecycle.yaml,uninstall.md,partner-bindings.md,retention.md}`
- `agent-installations/ats-agent/manifest.yaml` (deactivation/rollback corrected)
- `docs/releases/ris-agent-lifecycle-10.json`
- this report; `docs/AI_AUDITLOG.md`; `.gitignore` lifecycle-evidence rules
