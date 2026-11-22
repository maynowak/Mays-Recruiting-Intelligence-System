# CV Parser Agent — Retention

| Artifact | Retention | Lifecycle action |
|---|---|---|
| Orders | Mays-Orders policy | never deleted by UNINSTALL/PURGE |
| Work items / results | shared table policy | retained |
| Agent audit | append-only JSONL | retained |
| Parsed CV result | caller-owned (agent keeps no state) | caller retention applies |

The agent itself stores nothing. CV text and parsed PII are returned to the
caller and are subject to the caller's retention and consent rules. PURGE is
blocked until retention approval and an agent deletion ledger exist.
