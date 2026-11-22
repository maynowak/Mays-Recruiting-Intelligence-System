# Addition Agent — Retention

| Artifact | Retention | Lifecycle action |
|---|---|---|
| Orders | Mays-Orders retention, owner-bound | never deleted by UNINSTALL/PURGE |
| Work items | 30-day `expiresAt`; matrix says 90 days — **REVIEW REQUIRED** | retained |
| Order-correlated work rows | no `expiresAt` → retained indefinitely | retained; TTL gap open |
| Results | retained on the work row | retained |
| Audit / lifecycle manifest | append-only local JSONL | retained |

The addition agent owns no AWS resource and no bundle. UNINSTALL deletes
nothing; PURGE may delete only local lifecycle state. The HMAC secret, queues,
Lambdas and tables are shared with `ats-agent` and must be retained.
