# RIS Agent Factory — Release 13

**System:** ris-dev2 · account 262370457690 · eu-central-1 · workspace ris-dev2
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Baseline commit:** `fd38288ddffc36ee7380cd36bc5a63f9501ac78a`
**Date:** 2026-11-19
**Status:** BASELINE CONSOLIDATED · **PARTNER TRAFFIC NO-GO**

This release consolidates the agent factory baseline. It does not deploy, does
not touch ris-dev/production and performs no AWS mutation. Historical reports
are evidence, not the current runtime state; every current claim below was
re-verified against code and read-only AWS calls.

---

## 1. Agent inventory and contracts

| Agent | Capability | Work type | Version | Catalog row | Status |
|---|---|---|---|---|---|
| `ats-agent` | `analyze.job` | `ats_process` | 1.0.0 | ACTIVE | **LIVE VERIFIED** |
| `addition_agent` | `math.add` | `agent_addition_agent` | 1.0.0 | ABSENT (dispatch-only) | **LIVE VERIFIED** |
| `reference_agent` | `reference.echo` | — | 1.0.0 | ACTIVE | catalog only, no package |
| `jobsearch-agent` | `jobsearch.*` | — | 1.0.0 | ACTIVE | catalog only, no package |

Contracts as implemented: WorkItem `1.0`, AgentOrder `1.0`, Transport `1`,
agent runtime `1.0.0`, ATS upstream contract `1.2`, ATS result body `2.0`.
The addition agent emits no `bodyType`/`bodyVersion`; its manifest's
`resultBody: "1"` has no code counterpart (documented drift, OPTIONAL).

`addition_agent` declares `visibility: ABSENT`; the catalog seed must not be
read as "both agents are API-reachable".

## 2. Effective gates

| Path | Catalog | Entitlement | Notes |
|---|---|---|---|
| `GET /agents`, introspection, partner/m2m execute | yes | yes | catalog = discovery/API only |
| `POST /orders` (agent order) | **no** | **yes, before persist** | 403 on missing entitlement, 503 if store unavailable |
| Dispatch ingress → worker | **no** | **yes** | fails closed when `ENTITLEMENTS_TABLE` missing |
| Retail `POST /orders` | no | no | unaffected |
| Worker execution | **no** | **yes** | catalog `INACTIVE` alone does not stop a queued item |

`executionGates.catalogAloneBlocksExecution = false`. A DISABLE must withdraw
the entitlement; the catalog change is for discovery correctness.

## 3. Lifecycle and shared-infrastructure safety

**Lifecycle contract:** `installer/agent_lifecycle.py` — INSTALL, UPDATE,
DISABLE, ENABLE, DETACH_PARTNER, UNINSTALL, PURGE, STATUS, VERIFY. Local state
only; dry-run/impact/dependency/idempotency/audit/result manifest.

This release hardened the following, each with tests:

- PURGE is **unconditionally blocked** (`purge_blocked_no_deletion_ledger`):
  no retention approval and no agent deletion ledger exist.
- UNINSTALL now also blocks on open **results**, not only open orders.
- DETACH_PARTNER no longer changes the catalog; INSTALL/UNINSTALL respect
  `visibility: ABSENT` (no phantom catalog state).
- Binding removal requires `scope: agent`; shared-scope rows are never listed
  as removable.
- The install validator now requires `lifecycle.yaml`, `uninstall.md`,
  `partner-bindings.md`, `retention.md`; placeholders (`<…>`) and
  `_template` are rejected; the `apply` stage records `executed: false`
  because it runs no Terraform.
- Commands are printed with `-var` values redacted.
- `--through` is refused (it was silently ignored and would run a full install).
- Composite destroy requires `--shared-teardown-intent`.
- `is_plan_safe` rejects plan documents without a list-shaped
  `resource_changes`.

**Guard proofs (read-only, live plan in ris-dev2):**

| Scenario | Result |
|---|---|
| Plan without `enable_agent_transport` | exit 1, `MISSING_OR_FALSE_TRANSPORT_FLAG`, names the flag, lists the 11 dispatch resources |
| Correct flags | exit 0, `NO_SHARED_DESTROY`, **0 changes** |

The intent is validated (length/charset), bound to the plan SHA-256 and
re-checked before apply (TOCTOU). A missing/unreadable plan is refused.
`destroy` requires the intent. The remaining gap: direct `terraform`/`state
push` outside `installer.ris` and Terraform-native `prevent_destroy` are not
covered (REQUIRED BEFORE PRODUCTION).

## 4. Live state (read-only, 2026-11-19)

| Fact | Value |
|---|---|
| State serial / lineage | **64** / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Resources | 266 |
| Worker / ingress code SHA | `UljJnuYr…` (unchanged) |
| Orders reader code SHA | `RkuZH3hP…` (LIFECYCLE-11 gate) |
| Timeouts | worker 60 s, ingress 60 s, reader 10 s, result consumer 30 s |
| Catalog | ats-agent ACTIVE, reference_agent ACTIVE, jobsearch-agent ACTIVE |
| Entitlements / profiles / offers | 2 / 4 / 0 |
| Orders / work items | 10 / 12 |
| Queues | all agent/orders queues and DLQs **0 visible / 0 in-flight** |
| Alarms | **20 total, 0 with actions**; 0 SNS topics |
| HMAC secret | one version, `AWSCURRENT` |

## 5. Independent reviews

Five read-only reviews were run (runtime, installer, security, operations, QA).
Their confirmed findings are reflected in the risk classes below. The most
important corrections that came out of them are already in this release:
redaction, `--through`, composite-destroy intent, plan-shape fail-closed,
PURGE block, open-results block, catalog semantics, template completeness and
placeholder validation.

Not fixed here (documented, not silently accepted):

- `ris apply --out <reviewed.tfplan>` re-plans before applying: the reviewed
  file is overwritten. Always review the **new** plan hash printed by apply.
- Preflight can clone/checkout the Orders component before the dry-run gate.
- The Orders component destroy is guarded only by the intent requirement, not
  by inspecting its plan JSON.
- `state push` mutates state with `--yes` but no plan/guard.
- `is_plan_safe` still uses the historical `PRODUCTION_RESOURCE_PREFIXES`
  including `mays-ris-dev-`; default project name `mays-ris` cannot pass it.
- Monitoring has no notification path; the result consumer and ingress have no
  alarms.

## 6. Risk classification

### BLOCKER (before any partner traffic)

1. **No notification path:** 20 alarms, none with actions, no SNS topic.
   Dispatch/result queues and DLQs are unmonitored.
2. **Permanent rejects are deleted:** dispatch ingress and the result handler
   consume invalid records without DLQ copy or metric.
3. **Timeout budget:** batch 5 × ATS 30 s in a 60 s Lambda can leave a
   `RUNNING` work row permanently unprocessable; no worker partial-batch.
4. **No `ORDER_FAILED`:** a failed execution leaves the order `PENDING` with no
   `processing` and no error.
5. **No partner result retrieval:** `POST …/execute` returns 202 with a workId,
   but `GET /work/{workId}` has no route; results cannot be reconciled.

### REQUIRED BEFORE PRODUCTION

- Reader POST idempotency; profile `expiresAt` enforcement.
- Monitoring calibration (8 s duration threshold vs 60 s timeout; only the
  worker is covered).
- API-enqueued work (`QUEUED` pre-write) is not executable
  (`WORK_ADMISSION_STATE_UNSAFE`).
- Eligibility fails open on body/runtime mismatch.
- Entitlement rows without `tenantId` are tenant-global; unparsable validity
  bounds fail open.
- No Terraform `prevent_destroy`/`deletion_protection`; protection is
  installer-only and bypassable outside it.
- Composite Orders destroy is not plan-inspected; `state push` is unguarded.
- PURGE lacks a retention-approval gate and an agent deletion ledger.
- Partner execution context can lose `partnerApplicationId`/issuer.

### OPTIONAL

- Work-item TTL 30 d vs matrix 90 d; order-correlated rows omit `expiresAt`.
- ATS `workType ats_process` vs canonical `agent_ats-agent` (routing is by
  agentId/capability).
- Manifest env lists are informational and incomplete.
- Line-based lifecycle YAML parsing; mirror project-name charset.
- Catalog seed `version` vs API `agentVersion` inconsistency.

## 7. Tests

```
456 passed, 18 subtests
```

Key suites: shared-infra guard 31, lifecycle 25, orchestrator 9, reader agent
gate 10, dispatch env 3, plus ATS/addition/reader/worker/partner/catalog
regression. The agent-order E2E suite requires `MO_ORDERS_SRC` and is skipped
without the Orders source checkout; no new live deployment was performed
because the LIFECYCLE-11 live evidence (order IDs, work states, delivery) is
current and the state serial is unchanged at 64.

## 8. Artifacts

- `docs/releases/ris-agent-factory-13.json` — machine-readable baseline
- `docs/reports/RIS-AGENT-FACTORY-RELEASE-13.md` — this report
- `docs/operations/RIS-AGENT-FACTORY-RUNBOOK.md` — operating procedures
- `docs/handoffs/RIS-DEV-AGENT-FACTORY-13.md` — standalone ris-dev handoff
- `agent-installations/README.md` — package standard (updated)

## 9. Onboarding the next agent

> „Agent `<agent-id>` aufnehmen, Paket validieren, Risiken und Partnerwirkungen
> analysieren, vorhandene Runtime/Transport nutzen, in ris-dev2 testen und
> ris-dev-Handoff erzeugen."

Use `agent-installations/_template`, the lifecycle CLI and the shared guard.
No new queue, Lambda, table, Cognito client or agent framework without proven
necessity. The template now contains all lifecycle artifacts, and the
installer rejects placeholder pins and template status.

## 10. Decision

The factory baseline is **consolidated and reproducible** in ris-dev2.
**Partner traffic remains NO-GO** until the five BLOCKERs are closed.
No ris-dev/production change was made; the handoff in
`docs/handoffs/RIS-DEV-AGENT-FACTORY-13.md` is the entry point for the
operating team.
