# RIS-DEV2-TEST-IDENTITY-04 — Abschlussbericht

**Run ID:** `RIS-DEV2-04-20261103T111714Z`

## Final decision

```text
PARTIAL VERIFIED — REMAINING GATES DOCUMENTED
```

The dedicated Cognito Human identity was exercised with a real Authorization
Code + PKCE login and a cryptographically verified access JWT. The RIS
PartnerApplication/APIProfile/Credential binding could not be provisioned
because the required principal-bound RIS admin authorization was unavailable.
No ApplicationV1 CRUD success is claimed.

## Test matrix

| Prüfung | Status |
|---|---|
| Cognito-Pool-Verifikation | PASS |
| Synthetischer Testbenutzer | PASS; created and cleaned up |
| Authorization Code + PKCE | PASS |
| Gültiges Access JWT | PASS; signature/JWKS/claims verified |
| API Gateway Human Authorizer | PASS |
| RIS-Partner-Binding | BLOCKED; no authorized RIS admin mapping |
| ApplicationV1 CRUD | BLOCKED |
| Versionierung/Idempotenz | BLOCKED |
| Pagination | BLOCKED |
| Cross-User-Isolation | BLOCKED; no second authorized identity |
| Cross-Tenant/Partner-Isolation | BLOCKED |
| Privacy Inspect/Export | BLOCKED |
| Application-Erasure | BLOCKED |
| Cleanup | COMPLETE |
| Protected Infrastructure | UNCHANGED |

## Evidence

- Account/region: `262370457690` / `eu-central-1`;
- pool: `eu-central-1_K3dkdSipZ`;
- Human client: `21j28p71vogg0m41tcue0ib3l4`, no secret;
- state serial/lineage: `25` / `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- Human authorizer points to the new pool/client;
- external M2M authorizer remains unchanged;
- valid access JWT signature verified against the pool JWKS;
- unauthenticated, invalid, expired and wrong-issuer requests returned 401;
- valid JWT without partner context returned 403 for Profile and 500 for
  ApplicationV1 list requests, exposing a missing-binding runtime error;
- public Health CloudFront returned 200; Lambda and core DynamoDB regression
  checks passed;
- synthetic user and all temporary secret/token/PKCE files were removed.

## Blocking reason

`tools/ris_admin` requires an owner-only `RIS_ADMIN_AUTHORIZATION_FILE` mapping
the exact STS principal to an authorized RIS role and tenant. None exists for
`arn:aws:iam::262370457690:user/devnemo`. AWS AdministratorAccess is not treated
as an RIS application authorization, and direct DynamoDB writes were correctly
not used.

## Remaining gate

Provide an explicit, tenant-scoped RIS admin authorization and secure credential
handoff. Then repeat only the partner-binding and authenticated ApplicationV1
E2E phases with a new run manifest. Do not modify the deployed Cognito pool,
client or authorizer as part of that follow-up.
