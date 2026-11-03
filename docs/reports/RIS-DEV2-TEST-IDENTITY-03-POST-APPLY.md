# RIS-DEV2-TEST-IDENTITY-03 — Post-Apply Verification

**Result:** **POST-APPLY PASS**

All checks below were read-only. No user, password, token or credential was
created or retrieved.

## Cognito

| Check | Result |
|---|---|
| Pool | `eu-central-1_K3dkdSipZ`, `ris-dev2-dev-users` present |
| Region/account | `eu-central-1` / `262370457690` |
| Human client | `21j28p71vogg0m41tcue0ib3l4`, `ris-dev2-dev-client` |
| Client secret | Not present (`generate_secret=false`) |
| OAuth flow | `code` |
| Callback/logout | `http://localhost:5173/auth/callback` / `http://localhost:5173/` |
| Prefix domain | `ris-dev2-dev`, ACTIVE |
| Groups | Seven expected groups present |
| Users | 0 |
| Managed resource servers | 0 |

## API Gateway

Human authorizer `9i4w8r` now uses:

```text
issuer:   https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ
audience: 21j28p71vogg0m41tcue0ib3l4
```

M2M authorizer `9eli0a` is unchanged:

```text
issuer:   https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM
audience: 82ji073smu1b3fsvj96sonso
```

All 64 Human routes remain attached to `9i4w8r`; the single M2M route remains
`POST /v1/m2m/agents/{agentId}/execute`. ApplicationV1, Profile and CV routes
are present. The live route inventory contains 65 JWT routes and no newly
unauthorized route.

## Infrastructure regression

- Agent Lambda: `Active`, last update `Successful`, Python 3.14;
- ApplicationV1, User Profile, Agent Catalog and Agent State DynamoDB tables:
  `ACTIVE`, with expected GSI presence;
- Health CloudFront: `E1IZKHFPZ5X7SN`, `d3axlsioawbq92.cloudfront.net`,
  enabled and `Deployed`; public GET returned HTTP 200;
- API `GET /health` without a JWT returned HTTP 401, consistent with the
  current API contract and live JWT route configuration;
- missing JWT, invalid JWT, malformed Authorization header and unauthenticated
  ApplicationV1 request all returned HTTP 401;
- no plan/apply action touched CloudFront/OAC, DNS/Route53, ACM, DynamoDB,
  S3, Lambda, SQS or the external Cognito pool;
- external M2M issuer/audience remained unchanged.

## Terraform state

```text
serial: 25
lineage: a0bd361d-5cd1-a207-a8c0-e6888f0be082
```

The plan is consumed and must not be reapplied.
