# Addition Agent — Uninstall

The addition agent is a **dispatch-only** agent: it has no catalog row and no
API route, so its only runtime gate is the entitlement row.

## 1. Stop intake

Stop `math.add` / `addition_agent` orders at the producer. The reader does not
gate on catalog status, so this step is not optional.

## 2. Withdraw the agent entitlement

Remove only rows where `agentId == addition_agent`, with a reason and audit
entry. Removing the addition entitlement must not touch `ats-agent`, retail
orders, or any shared profile/credential/application.

## 3. Drain

No `RUNNING`/`QUEUED` work for the agent; queues and DLQs empty. Never delete
`RUNNING`/`FAILED` rows.

## 4. Retain

Orders, work rows, results, audit and every shared resource. The HMAC secret and
the result consumer are shared with `ats-agent`.

## 5. Idempotency

A second UNINSTALL returns `already_uninstalled`. PURGE is separate and
irreversible. Re-INSTALL requires a fresh reviewed grant, not a state flip.
