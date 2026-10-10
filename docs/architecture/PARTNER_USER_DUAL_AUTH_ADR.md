# ADR: Partner User Dual Authentication Contract

## Status
PROPOSED – Awaiting orchestration review

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

## Partner Application Identity
- RIS API Credential identifies partner application via APIProfile
- Credential stored server-side in Vercel env vars
- Never exposed to browser
- Credential rotation/revocation supported

## User + Partner Authorization
Authoritative checks:
- User JWT tenant matches credential APIProfile tenant
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
- Exact route path: new /v1/partner/agents/... vs reuse /v1/m2m/agents/...
- Scopes for partner user tokens
- Quota enforcement mechanism

## Consequences
+ Strong dual-auth without M2M token
+ Server-side secret protection
- Requires Vercel server-side proxy
