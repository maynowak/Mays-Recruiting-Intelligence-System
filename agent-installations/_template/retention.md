# <agent-id> — Retention

| Artifact | Retention | Lifecycle action |
|---|---|---|
| Orders | Mays-Orders retention, owner-bound | never deleted by UNINSTALL/PURGE |
| Work items | 30-day `expiresAt` in code; matrix 90 days — REVIEW REQUIRED | retained |
| Order-correlated work rows | no `expiresAt` today | retained |
| Results | retained on the work row | retained |
| Audit / lifecycle manifest | append-only local JSONL | retained |
| HMAC secret | shared container | deleted only by separate review |

UNINSTALL deletes nothing. PURGE may delete only lifecycle-local state and is
not a physical-deletion certificate (PITR, backups and Orders remain). PURGE is
blocked until retention is approved and a deletion-ledger type exists.
