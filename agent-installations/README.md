# Agent Installation Packages

Versioned installation and lifecycle contracts for RIS agents. A package is a
reviewable contract, not executable third-party software.

## Layout per agent

```
agent-installations/<agent-id>/
  manifest.yaml          # identity, capability, source pin, contract versions
  offers.yaml            # optional: offers for a composite agent
  lifecycle.yaml         # discovery, shared/exclusive resources, bindings,
                         # uninstall and retention rules, purge boundaries
  contracts/             # wire contracts owned by this agent
  tests/                 # package-level tests
  risks.md
  operations.md
  handoff.md
  uninstall.md           # two-lever procedure, drain, retention, idempotency
  partner-bindings.md    # binding matrix, P1/P2/P3, external PENDING items
  retention.md           # per-artifact retention and purge boundaries
```

`_template/` is the starting point for a new agent. It contains **all** of the
files above and is excluded from discovery. It is never a deployable package;
the installer rejects template status and placeholder pins (`<...>`).

## Composite agents (plug-and-play reference)

A composite agent is **one** installable agent that exposes **one or more
offers**. It is not a bundle of separately ordered agents. The reference is
`analysis-agent` (`analysis.run`, work type `agent_analysis_agent`) with three
DRAFT offers: `analysis.cv`, `analysis.job`, `analysis.match`.

Rules:

1. **One outer order/WorkItem.** A paid or API-initiated `analysis.run` is one
   order and one WorkItem. Internal parser calls (`parse.cv`, `parse.job`,
   `parse.ats`) are technical subfunctions of that WorkItem. They are not
   separately orderable, do not create orders, and are not billed separately.
2. **One execution pipeline.** Reuse the existing registry/Discovery/
   Eligibility, AgentBody, WorkItems, `ORDER_DISPATCH`, shared work queue,
   shared worker, `ORDER_RESULT`/`ORDER_FAILED` and result consumer. Do not add
   a per-offer queue, table, order state machine or result transport.
3. **Offers map outcomes, not orders.** `offers.yaml` maps `offerId` ->
   requested results -> external entitlements -> internal capabilities ->
   result bodies. Pricing/billing stays with Mays-Orders; RIS defines no price.
4. **Verified identity and consent.** Tenant/user/partner/issuer come from the
   verified runtime context, never from the request body. APIProfile,
   entitlement, consent and subject/CV-owner fences are checked server-side and
   fail closed. A test/synthetic profile is not real consent.
5. **Unified contracts.** Keep WorkItem 1.0, AgentOrder 1.0, Transport V1,
   result bodies and the shared lifecycle/status/retrieval contracts. Result
   retrieval remains the existing order view (Mays-Orders
   `GET /orders/{orderId}` -> `processing.status/result/error`; RIS reader
   owner-scoped equivalent).
6. **No silent activation.** Offers stay `DRAFT`, `activation: false`, catalog
   `ABSENT`, entitlements `PENDING_APPROVAL` until legal, entitlement, catalog
   and apply approvals exist.
7. **No implied agent-to-agent resume.** `ORDER_RESULT`/`ORDER_FAILED` update
   the order. A `WAITING` state, parent correlation propagation and automatic
   re-activation of a parent agent are a separate platform track.

Manifest fields for a composite package:

```yaml
agent:
  composite: true
  offers: offers.yaml
  internalCapabilities: [parse.cv, parse.job, parse.ats]
  externalEntitlements: [parse.cv, parse.job, compare.tags, analyze.job]
```

The template ships an `offers.yaml` scaffold. Adding offers does not change the
installer's discovery or validation rules; a package is still validated through
its `manifest.yaml`, required files and lifecycle contract.

## Install stages (contract validation only)

```
python -m installer.agent_install --root agent-installations
python -m installer.agent_install --agent <id> --stage validate --status-file <path>
```

Stages: DISCOVER → ANALYZE → COMPATIBILITY → RISK REVIEW → PACKAGE → VALIDATE →
PLAN → APPLY → E2E → HANDOFF. Status is idempotent and resumable; `APPLY`
refuses without `--execute --allow-apply --yes`. `APPLY` records `executed:
false` — it is an approval record, not a Terraform run.

## Lifecycle actions (local state, no AWS)

```
python -m installer.agent_lifecycle --agent <id> --action <action> \
  --inventory <inventory.json> --state-file <state.json> \
  --audit-log <audit.jsonl> [--execute] [--actor <id>] [--approval <ref>] \
  [--reason "<text>"] [--impact-report <path>]
```

Actions: INSTALL, UPDATE, DISABLE, ENABLE, DETACH_PARTNER, UNINSTALL, PURGE,
STATUS, VERIFY. Every action has dry-run, impact, dependency check,
idempotency, audit and a result manifest.

Rules:

- DISABLE must withdraw the agent-scoped entitlement; catalog status alone does
  not stop the worker or the order reader.
- DETACH_PARTNER removes only `scope: agent` bindings and keeps shared
  profile/credential/application; external references stay PENDING.
- UNINSTALL blocks on open orders **and** open results, and is idempotent.
- **PURGE is blocked** until retention approval and an agent deletion ledger
  exist (`purge_blocked_no_deletion_ledger`).
- Shared queues, Lambdas, tables, Cognito and the HMAC secret are never removed
  for one agent.

## Infrastructure safety

The installer refuses a plan that deletes/replaces/forgets shared
infrastructure unless an explicit `--shared-teardown-intent <reference>` is
provided. Missing `enable_agent_transport` / `orders_agent_result_enabled` /
`orders_lifecycle` are reported as the cause, never as a teardown request.
Plans are hash-checked before apply; unreadable or incomplete plans stop.

## Live baselines

- `ats-agent` 1.0.0 — live E2E PASS on ris-dev2, catalog ACTIVE.
- `addition-agent` 1.0.0 — live E2E PASS, catalog ABSENT (dispatch-only).
- `cv-parser-agent` 1.0.0 — LOCAL VERIFIED (`parse.cv`), catalog ABSENT.
  Live enablement PENDING: the Python Lambda has no node runtime.
- `job-parser-agent` 1.0.0 — LOCAL VERIFIED (`parse.job`), catalog ABSENT.
  Live enablement PENDING (same runtime gap).
- `analysis-agent` 1.0.0 — LOCAL VERIFIED composite agent (`analysis.run`:
  cv/job/ats/comparison orchestration). Three DRAFT offers, no catalog row, no
  activation. Not deployed; AWS canary PENDING (technical apply A, synthetic
  profile B). The Mays `apiProfileRef` ownership binding (C) and automatic
  agent resume remain open/blocked.

All five use the same dispatch/work/result transport; there are no per-agent
queues. Correction-14 dispatch -> work-queue -> worker is prepared but not
applied; the existing addition/ATS live baselines are unchanged.

## Adding an agent

> „Agent `<agent-id>` aufnehmen, Paket validieren, Risiken und Partnerwirkungen
> analysieren, vorhandene Runtime/Transport nutzen, in ris-dev2 testen und
> ris-dev-Handoff erzeugen."

Copy `_template/`, replace every placeholder, declare the capability and
workType that the runtime actually registers, add the entitlement binding with
`scope: agent`, and follow the runbook. No new queue, Lambda, table, Cognito
client or agent framework without proven necessity.

For a composite agent, additionally fill `offers.yaml`, set
`agent.composite: true` / `agent.offers`, and list internal capabilities and
external entitlements separately. Prove with a negative test that an internal
parser call cannot create an order, and with a positive test that one outer
request produces only one WorkItem and one order result.
