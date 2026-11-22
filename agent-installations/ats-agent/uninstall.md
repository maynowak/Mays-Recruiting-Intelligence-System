# ATS Agent — Uninstall

Two levers only. Both are data-plane and row-scoped; nothing is deleted from
the shared infrastructure.

## 1. Stop intake at the real producer

Since RIS-AGENT-LIFECYCLE-11 the reader enforces the agent entitlement:
with no valid entitlement `POST /orders` returns **403 AGENT_ORDER_REJECTED
before the order row is persisted**. The catalog is still not consulted, so a
catalog-only change does not stop intake.

- stop `agent.execution` orders for `ats-agent`/`analyze.job` at the external
  partner/producer as the earliest gate;
- `orders_agent_result_enabled=false` does **not** block intake — it only stops
  result forwarding and strands the order;
- `enable_agent_transport=false` destroys the shared dispatch queue/DLQ/ingress
  for **every** agent — never use it to disable one agent.

## 2. Withdraw agent entitlements, then set catalog INACTIVE

1. Withdraw only the entitlement rows where `agentId == ats-agent`
   (per-row evidence, reason required, audited).
2. Set the `agent-catalog` item for `ats-agent` to `INACTIVE` through a reviewed
   Terraform change of `local.agent_catalog_seed` (plan → review → apply).
3. Keep the API profile, credential, partner application and client
   reservation: they are shared with other agents.

## 3. Drain

- No `RUNNING`/`QUEUED` work row for the agent, queue and DLQ depth 0,
  `orderResultDelivery=SENT` where a result exists.
- Never delete `RUNNING`/`FAILED` rows. Stuck `RUNNING` recovery is a separate,
  approved `RUNNING→FAILED` operation.
- Do not `CANCEL` completed orders; a late result is permanently rejected.

## 4. Retain

Orders, work rows, results, audit and all shared resources. History is retained
by policy; TTL is the only cleanup mechanism.

## 5. Idempotency

A second UNINSTALL returns `already_uninstalled` and does not rewrite state or
reset the purge grace anchor. PURGE is separate, irreversible and never implicit.
