# ATS Agent — Retention

| Artifact | Retention | Lifecycle action |
|---|---|---|
| Orders (`agent.execution`) | Mays-Orders retention, owner-bound | never deleted by UNINSTALL/PURGE |
| Work items | 30-day `expiresAt` in code; matrix says 90 days — **REVIEW REQUIRED** | retained |
| Order-correlated work rows | worker rows omit `expiresAt` → currently retained indefinitely | retained; TTL gap open |
| Results (`result`, `result_reference`) | retained on the work row | retained |
| Orders `processing` result | Mays-Orders, PITR/backup | retained |
| Audit / lifecycle manifest | append-only local JSONL | retained |
| HMAC secret | one shared container | deleted only by a separate reviewed procedure |

UNINSTALL never deletes data. PURGE may delete only lifecycle-local state and
markers; it is **not** a physical-deletion certificate because PITR backups,
S3 versions and the Orders table remain. No retention period is legally
approved (`docs/privacy/DATA_RETENTION_MATRIX.md` — REVIEW REQUIRED).
