# CV Parser Agent — Uninstall

1. Stop new `parse.cv` orders at the producer.
2. Withdraw only the agent-scoped entitlement (`scope: agent`). The reader
   rejects new orders with 403; the worker denies execution.
3. There is no catalog row to change (`visibility: ABSENT`).
4. Drain in-flight work; never delete RUNNING/FAILED rows.
5. Retain orders, work items, results, audit and all shared resources.
6. Record the result manifest and audit entry.

UNINSTALL is idempotent. PURGE stays blocked
(`purge_blocked_no_deletion_ledger`).
