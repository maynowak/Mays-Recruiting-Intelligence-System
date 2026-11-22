# ATS Agent — Partner Bindings

## Binding matrix

| Binding | Scope | Managed by | On DETACH |
|---|---|---|---|
| Agent entitlement (`agentId=ats-agent`) | agent + user + tenant | ris | withdraw matching rows only |
| API profile (`apiProfileId`) | shared, owner-bound | ris | retain (ACTIVE) |
| Credential (`credentialId` → profile) | shared | ris | retain (ACTIVE) |
| Partner application (`cognitoClientId`) | shared | ris | retain |
| Client reservation (`CLIENT#<clientId>`) | shared | ris | retain |
| Offer (`agentIds[]`) | shared package | ris | do **not** edit (future grants) |
| External partner UI/API references | partner | external | PENDING change request |
| `GET /agents`, `/v1/introspection` | derived from entitlements | ris | updates automatically |

## Entitlement classification (withdraw only P1/P2)

- **P1 profile-bound** (`apiProfileId == registry profile`) — partner-exclusive;
  safe to withdraw.
- **P2 user-wide** (`apiProfileId` absent, e.g. `--scope USER` grants) — also
  authorizes other consumers of that user; requires explicit per-row
  confirmation.
- **P3 provisioning** (`createdBy.role == provisioning`) — Terraform-managed;
  withdrawing is reverted by the next apply → convert to a TF change request.

## Share firewalls

- If another ACTIVE application shares the profile → profile and credential are
  shared; detach may only withdraw entitlements.
- If the profile has ACTIVE credentials used elsewhere → the credential stays
  ACTIVE (revoking it would kill every agent).
- A multi-agent offer's `agentIds` is product data; never edit it for one
  partner.

## Verification after detach

- `GET /agents` no longer lists `ats-agent`.
- `POST /v1/partner/agents/ats-agent/execute` → 403, while another entitled agent
  still returns 202 (proves application/credential/profile survived).
- Registry and credential remain ACTIVE.

## External, PENDING

Partner-side `RIS_API_CREDENTIAL`/`RIS_API_BASE_URL`, hard-coded agent
allowlists, UI buttons bound to a specific agent, quota/consent text and the
partner Cognito pool/client. These are change requests, never automatic edits.
