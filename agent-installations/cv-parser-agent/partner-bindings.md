# CV Parser Agent — Partner Bindings

| Binding | Scope | Managed by | On DETACH |
|---|---|---|---|
| Entitlement (`agentId=cv-parser-agent`) | agent | ris | withdraw matching rows |
| API profile | shared | ris | retain |
| Credential | shared | ris | retain |
| Partner application | shared | ris | retain |

There is no external partner UI or allowlist for this agent. The only PENDING
external decision is whether the agent should become API-discoverable
(catalog seed), which is a separate reviewed change.
