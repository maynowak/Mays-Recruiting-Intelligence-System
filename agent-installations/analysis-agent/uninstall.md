# Analysis Agent — Uninstall

1. Stop new `analysis.run` orders at the producer and withdraw the agent-scoped
   entitlement. No catalog row exists (`visibility: ABSENT`).
2. Drain in-flight work; never delete `RUNNING`/`FAILED` rows or shared
   transport.
3. Remove only the agent-specific compute/data (`ris-dev2-dev-analysis`,
   `ris-dev2-dev-analysis-parser`, `ris-dev2-dev-analysis-jobs`) through a
   reviewed Terraform change **after** drain. The analysis Lambda is not
   deployed yet; the parser Lambda is Terraform-gated.
4. Retain orders, work items, results, audit and all shared resources.
5. PURGE stays blocked (`purge_blocked_no_deletion_ledger`).
