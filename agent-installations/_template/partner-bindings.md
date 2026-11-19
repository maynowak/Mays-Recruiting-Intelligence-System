# <agent-id> — Partner Bindings

| Binding | Scope | Managed by | On DETACH |
|---|---|---|---|
| Entitlement (`agentId=<agent-id>`) | agent | ris | withdraw matching rows |
| API profile | shared | ris | retain |
| Credential | shared | ris | retain |
| Partner application / client reservation | shared | ris | retain |
| External partner UI/API | partner | external | PENDING change request |

Only bindings with `scope: agent` are removable. Shared profile, credential,
application and reservation rows must survive a detach.

External references (partner credential, allowlist, static UI, quota/consent,
partner Cognito) are change requests outside this repository and stay PENDING.
