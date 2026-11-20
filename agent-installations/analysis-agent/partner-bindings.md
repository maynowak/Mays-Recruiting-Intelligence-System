# Analysis Agent — Partner Bindings

| Binding | Scope | Managed by | On DETACH |
|---|---|---|---|
| Entitlement (`agentId=analysis-agent`) | agent | ris | withdraw |
| API profile | shared | ris | retain |
| Credential | shared | ris | retain |
| Partner application | shared | ris | retain |

No external partner UI or allowlist. Adding a catalog seed is a separate
reviewed Terraform change.
