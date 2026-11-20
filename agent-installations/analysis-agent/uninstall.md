# Analysis Agent — Uninstall

1. Stop new `analysis.run` orders at the producer.
2. Withdraw the agent-scoped entitlement. No catalog row exists
   (`visibility: ABSENT`).
3. Drain in-flight work; never delete RUNNING/FAILED rows.
4. Retain orders, work items, results, audit and all shared resources.
5. PURGE stays blocked (`purge_blocked_no_deletion_ledger`).
