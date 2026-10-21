# ADR: Partner User Dual Authentication Contract

## Status
ACCEPTED (implementiert) — Tenant-Auflösung L03 umgesetzt und live
verifiziert (`docs/reports/RIS-JOBSEARCH-CONSUMER-OFFER-03.md`).
Offen bleibt die Quota-Durchsetzung (siehe Open Decisions).

## Context
Mays-Job-Matcher hosted on Vercel needs to call Mays-RIS on behalf of authenticated users. Existing M2M flow uses Cognito client credentials + RIS API Credential. User-initiated flows require both user identity and partner application identity.

## Decision
Canonical request:
POST /v1/partner/agents/{agentId}/execute
Authorization: Bearer <COGNITO_USER_ACCESS_JWT>
X-Api-Credential: ris_...
Content-Type: application/json

No additional Cognito M2M token required.

## Authentication Flow
1. Browser authenticates via Cognito User Pool eu-central-1_IfucuxPC1
2. Vercel server-side route receives user session, obtains Access Token
3. Vercel server-side holds RIS API Credential in environment secret
4. Vercel proxies request to RIS with both credentials
5. RIS validates JWT signature, issuer, expiration, token_use=access, client_id
6. RIS validates RIS API Credential via existing verify_api_credential
7. RIS enforces user + partner binding, tenant isolation, entitlements

## User Authentication
- Validate JWT signature via JWKS
- iss = https://cognito-idp.eu-central-1.amazonaws.com/<pool-id>
- aud = human login client id
- exp valid
- token_use = access
- Extract sub, custom:tenant_id, email
- Never trust userId/tenantId from request body

## Tenant Resolution (L03 — implemented)
The tenant is a **server-side state**, never a caller-supplied value:

| Source | Role |
|---|---|
| `custom:tenant_id` claim | authoritative **when present** |
| Partner Registry (`client_id` / authorizer-validated `aud` → Application → `tenantId`) | server-side resolution when the claim is absent |
| Credential `tenantId` | the tenant in the partner route (cross-checked against the registry) |

Rules:
- A claim that **contradicts** the server-side resolution is a cross-tenant
  attempt → **403**.
- A **missing** claim is not a failure: self-signup users of a partner
  application carry no tenant claim. Refusing them would make the partner
  route unusable without protecting anything.
- An **unresolvable** tenant is refused (**403** `Tenant not resolvable`).
  There is **no** `default` tenant — a silent default would merge the profiles
  of different partners into one bucket.
- `DELETE /me/profile` stays **without** a tenant requirement (privacy right).

## Partner Application Identity
- RIS API Credential identifies partner application via APIProfile
- Credential stored server-side in Vercel env vars
- Never exposed to browser
- Credential rotation/revocation supported

## User + Partner Authorization
Authoritative checks:
- User JWT tenant matches credential APIProfile tenant — **refined by L03**:
  the tenant must match the *server-side* resolution (credential/registry);
  the JWT claim is authoritative when present and must not contradict it
- User exists in RIS user profile and is ACTIVE
- User has entitlement for requested agent
- APIProfile status ACTIVE
- Application status ACTIVE in Partner Application Registry
- No cross-tenant, no cross-application reuse

## API Gateway
Reuse human JWT authorizer for this route. Credential validated in Lambda.
Existing M2M routes remain separate with jwt_m2m authorizer + scope.

## Vercel Integration
Server-side API route proxies request, forwards JWT, adds X-Api-Credential.
CSRF protection via same-site cookies, rate limiting per tenant.
Credential rotation via Vercel secret update.

## Usage Accounting
Metrics per applicationId, apiProfileId, tenantId, agentId with server-side counters.

## GDPR
Minimal logging, no JWT or credential in logs, user deletion invalidates access, partner offboarding revokes credentials.

## Open Decisions
- Scopes for partner user tokens
- Quota enforcement mechanism
- Grant path for self-signup consumers: today an administrative grant per
  consumer (the entitlement model is user-wide, there is no app-wide offer)

## Consequences
+ Strong dual-auth without M2M token
+ Server-side secret protection
+ Tenant isolation without depending on a browser-supplied claim
- Requires Vercel server-side proxy
