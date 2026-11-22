# Addition Agent — Partner Bindings

| Binding | Scope | Managed by | On DETACH |
|---|---|---|---|
| Entitlement (`agentId=addition_agent`) | agent + user + tenant | ris | withdraw matching rows only |
| API profile | shared, owner-bound | ris | retain |
| Credential | shared | ris | retain |
| Partner application / client reservation | shared | ris | retain |
| Catalog row | **none exists** | — | nothing to change; dispatch-only |

DETACH removes only the entitlement rows for `addition_agent`. It must not
touch `ats-agent` rows, retail orders, the shared profile, credential or
application.

Because there is no catalog row and no API route, partner discovery never lists
this agent; the entitlement is the only runtime gate. If the agent should become
API-discoverable, adding a catalog seed row is a separate reviewed INSTALL
change request (Terraform `local.agent_catalog_seed`).
