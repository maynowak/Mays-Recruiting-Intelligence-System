# <agent-id> — Uninstall

1. Stop new orders at the external producer.
2. Withdraw only the agent-scoped entitlement (`scope: agent`); the reader
   rejects new agent orders with 403 before persisting and the worker denies
   execution.
3. Set the catalog status INACTIVE via a reviewed Terraform change **only if**
   a catalog row exists.
4. Drain in-flight work; never delete RUNNING/FAILED rows.
5. Retain orders, work items, results, audit and all shared resources.
6. Record the result manifest and audit entry; external references stay PENDING.

UNINSTALL is idempotent. PURGE is separate, irreversible and blocked until
retention approval and a deletion ledger exist.
