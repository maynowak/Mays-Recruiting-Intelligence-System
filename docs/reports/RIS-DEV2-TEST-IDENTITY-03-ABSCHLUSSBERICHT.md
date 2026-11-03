# RIS-DEV2-TEST-IDENTITY-03 — Abschlussbericht

## Final decision

```text
RIS-DEV2-TEST-IDENTITY-03 — APPLY PASS
```

The explicitly approved saved Terraform plan was applied once to the guarded
`ris-dev2` workspace. Terraform exited successfully with exactly 10 creates, 1
in-place Human-authorizer update and 0 destroys.

## Identity outcome

The dedicated managed Cognito Human identity is installed in account
`262370457690`, region `eu-central-1`:

- Pool `eu-central-1_K3dkdSipZ`;
- public Human client `21j28p71vogg0m41tcue0ib3l4`;
- Authorization Code flow with localhost PKCE callback;
- no client secret, users, tokens or credentials;
- no managed M2M client or resource server.

## Authorization outcome

Human authorizer `9i4w8r` points to the new pool/client. External M2M authorizer
`9eli0a` and its machine route remain unchanged. Profile, CV and ApplicationV1
routes remain Human-authorized; no bypass route was introduced.

## Verification outcome

- State serial `24` → `25`; lineage unchanged;
- Cognito pool/client/domain/groups verified read-only;
- Lambda Active/Successful and core DynamoDB tables ACTIVE;
- public Health CloudFront returned 200;
- negative unauthenticated/invalid-header tests returned 401;
- API `/health` returned 401 without JWT by design, matching the current API
  contract; no valid JWT test was performed;
- no protected-resource action or unexpected deletion/replacement.

## Protected resources and next boundary

External Cognito owner pool, CloudFront/OAC, DNS/Route53, ACM, Lambda,
DynamoDB, S3 and SQS infrastructure remained outside the approved action set.
The consumed plan is marked **APPLIED — DO NOT REAPPLY**.

The next authorized operation is `RIS-DEV2-TEST-IDENTITY-04 — Synthetic User &
Authenticated API E2E`. No synthetic user or RIS partner credential is created
by this phase.
