# Analysis Agent — Partner Bindings

| Binding | Scope | Managed by | On DETACH |
|---|---|---|---|
| Entitlement (`agentId=analysis-agent`) | agent | ris | withdraw |
| API profile | shared | ris | retain |
| Credential | shared | ris | retain |
| Partner application | shared | ris | retain |

## Identity boundary

- Caller partner: `ris-internal`; executor application:
  `ris-internal-analysis`; agent: `analysis-agent`. These are logical partner
  identifiers, not a technical Cognito user.
- No technical Cognito service user exists in the repository. The optional M2M
  app client (`client_credentials`, scope `ris-api/m2m:execute`) has no
  server-side APIProfile/entitlement binding in the repo.
- The RIS API path requires a Cognito access JWT plus `X-Api-Credential` and
  re-checks profile/tenant/entitlement/catalog server-side.
- Mays-Orders `agentOrder.metadata.apiProfileRef` is client-supplied. Mays
  verifies order ownership but not that the profile belongs to the order
  owner/partner; this is an open Mays-owned finding and blocks real
  order-driven traffic.

No external partner UI or allowlist. Adding a catalog seed is a separate
reviewed Terraform change.
