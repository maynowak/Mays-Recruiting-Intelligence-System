# RIS-DEV2-TEST-IDENTITY-04G — Cleanup and Regression

**Run ID:** `RIS-DEV2-04-20261103T111714Z`

## Cleanup result

**COMPLETE** for all resources created by this run.

- Synthetic Cognito user `ris-dev2-e2e-04-111714` deleted;
- read-only verification confirmed the user no longer exists;
- temporary password, access-token, PKCE and callback files deleted;
- local callback server stopped;
- no ApplicationV1 record, APIProfile, Credential, PartnerApplication or
  entitlement was created, so no database cleanup was required;
- the Cognito test pool, Human client and authorizer were intentionally kept.

No Terraform destroy or table deletion was used.

## Read-only regression

- Account: `262370457690`; region: `eu-central-1`;
- State serial: `25`; lineage unchanged;
- Pool `eu-central-1_K3dkdSipZ` and public client remain present;
- Human authorizer points to the DEV2 pool/client;
- external M2M authorizer remains on the external issuer/audience;
- Cognito pool has zero users after cleanup and no managed resource server;
- Agent Lambda: `Active` / `Successful`;
- ApplicationV1 and User Profile DynamoDB tables: `ACTIVE`, expected GSI present;
- Health CloudFront `E1IZKHFPZ5X7SN`: enabled and `Deployed`;
- public Health CloudFront HTTP status: `200`;
- no Terraform or infrastructure mutation occurred in this phase.

DNS/ACM/CloudFront/OAC and external Cognito remained outside the phase's
authorized mutation scope. No valid token or secret remains in the temporary
handoff area.
