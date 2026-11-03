# RIS-DEV2-TEST-IDENTITY-04C — PKCE Authentication

**Run ID:** `RIS-DEV2-04-20261103T111714Z`

## Result

**PASS — VALID ACCESS JWT / PARTNER AUTHORIZATION NOT ESTABLISHED**

## OAuth configuration

- Prefix domain: `ris-dev2-dev.auth.eu-central-1.amazoncognito.com`
- Public client: `21j28p71vogg0m41tcue0ib3l4`
- Redirect URI: `http://localhost:5173/auth/callback`
- Response type: `code`
- PKCE method: `S256`
- Scopes: `openid profile email`
- Issuer: `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ`

No client secret or alternative OAuth flow was used.

## Authorization Code flow

The existing managed-login page was used with the synthetic user. A fresh
`state` and PKCE verifier/challenge were generated locally, the redirect was
received on the localhost callback, and the code was exchanged once at
`/oauth2/token`. The verifier, code and token were never written to Git,
reports or the audit log.

The access JWT was validated locally against the actual pool JWKS:

- signature: valid;
- issuer: correct DEV2 pool;
- `token_use`: `access`;
- `client_id`: `21j28p71vogg0m41tcue0ib3l4`;
- subject: present;
- requested scopes: present;
- expiry: valid at test time.

## HTTP smoke results

| Request | Result |
|---|---:|
| Missing JWT, ApplicationV1 list | 401 |
| Invalid JWT | 401 |
| Expired/modified JWT | 401 |
| Wrong-issuer/modified JWT | 401 |
| Valid JWT, `GET /me/profile` | 403 — `Tenant not resolvable` |
| Valid JWT, ApplicationV1 without credential | 500 — `Internal Server Error` |
| Valid JWT, ApplicationV1 invalid credential | 500 — `Internal Server Error` |

The valid JWT proves API Gateway Human-authorizer authentication, but not RIS
partner authorization. The 500 responses are recorded as an application-side
error under the missing partner-binding condition; no CRUD mutation was sent.

## Secret handling

The password and access token were held only in restricted temporary local
files during the test and were not printed. They are scheduled for deletion in
04G cleanup. No refresh token was used or retained for testing.
