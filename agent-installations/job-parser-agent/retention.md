# Job Parser Agent — Retention

| Artifact | Retention | Lifecycle action |
|---|---|---|
| Orders | Mays-Orders policy | never deleted by UNINSTALL/PURGE |
| Work items / results | shared table policy | retained |
| Agent audit | append-only JSONL | retained |
| Parsed job result | caller-owned (agent keeps no state) | caller retention applies |

The agent stores nothing. The parsed posting is returned to the caller and is
subject to the caller's retention rules. PURGE is blocked until retention
approval and an agent deletion ledger exist.
