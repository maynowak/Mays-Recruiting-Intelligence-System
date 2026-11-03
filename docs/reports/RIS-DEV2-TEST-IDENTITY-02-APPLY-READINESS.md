# RIS-DEV2-TEST-IDENTITY-02 — Apply Readiness

**Decision:** **STRUCTURALLY READY FOR EXPLICIT REVIEW / STOP BEFORE APPLY**

No AWS mutation was performed in this phase. The report does not authorize an
Apply.

## 1. Secret-risk assessment

The DEV2 overlay sets `identity_m2m_enabled = false`. The new plan contains no
managed M2M client, resource server or generated M2M client secret. The Human
client is public with `generate_secret = false` and uses Authorization Code +
PKCE.

No secret, password, token or client-secret value was read, printed, stored in
Git or placed in a report. The preserved M2M authorizer uses only existing
non-secret external issuer/audience references and is not changed.

## 2. Human client configuration

| Setting | Value |
|---|---|
| Pool name | `ris-dev2-dev-users` |
| Human client name | `ris-dev2-dev-client` |
| Client secret | **Disabled** (`generate_secret=false`) |
| OAuth flow | Authorization Code (`code`) + PKCE for public client |
| Scopes | `openid`, `email`, `profile` |
| Callback | `http://localhost:5173/auth/callback` |
| Logout | `http://localhost:5173/` |
| Custom domain | Disabled |

## 3. Authorizer impact

- Human authorizer `9i4w8r`: one in-place issuer/audience update to the new
  managed DEV2 pool/client;
- M2M authorizer `9eli0a`: unchanged, still external issuer/audience;
- 64 Human routes remain attached, including Profile, CV, ApplicationV1 and
  privacy routes;
- the single M2M route remains attached to the existing M2M authorizer;
- no public route or authentication bypass is introduced.

## 4. Test results

- Identity/configuration tests: **9 passed**;
- selected API/ApplicationV1/privacy/erasure/APIProfile/CV/partner regressions:
  **244 passed, 297 subtests passed**;
- Terraform fmt: **PASS**;
- Terraform init without backend: **PASS**;
- Terraform validate: **PASS** with existing provider deprecation warnings;
- live positive JWT/user test: **NOT PERFORMED**;
- AWS mutation: **NOT PERFORMED**.

## 5. Old versus new plan

| Artifact | Result |
|---|---|
| `ris-dev2-managed-identity-01.tfplan` | **SUPERSEDED — DO NOT APPLY**; contained managed M2M client/resource server |
| `ris-dev2-managed-identity-02.tfplan` | Current candidate; 10 creates, 1 update, 0 deletes, 0 replacements |

Current candidate:

```text
Path: C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-managed-identity-02.tfplan
SHA-256: 35EE37C10CF190A0DD1A80714734C2DD9A567CF191186693B9952B9C2ED64CE6
```

## 6. Resource action matrix

| Category | Result |
|---|---:|
| Managed Human Cognito pool/client/domain/groups | 10 creates |
| Human API JWT authorizer | 1 in-place update |
| Managed M2M client/resource server | 0 |
| M2M authorizer/route | 0 changes |
| Deletes | 0 |
| Replacements | 0 |
| Lambda/DynamoDB/S3/SQS | 0 |
| CloudFront/OAC/DNS/ACM | 0 |
| External Cognito pool | 0 |

## 7. Protected infrastructure

The plan is scoped to the verified `ris-dev2` state in account `262370457690`.
The external pool `eu-central-1_ojbmoiYGM` in account `240571105849` remains
reference-only. No CloudFront, DNS, ACM, Orders, `ris-dev` or Jobsearch action
is present.

## 8. Rollback and recovery concept

Rollback is a separately reviewed operation, not an automatic destroy:

1. stop on any unexpected action or runtime failure;
2. preserve the exact plan, state serial, CloudTrail evidence and apply output;
3. inspect the remote state and live Cognito/API resources read-only;
4. if reversal is approved, generate a new plan restoring the explicit
   external identity tuple and Human authorizer contract;
5. review that reverse plan for managed-pool/resource cleanup and authorizer
   restoration;
6. apply only that separately approved reverse plan.

Never use `terraform destroy`, `state rm`, manual state edits or an unreviewed
old plan as recovery.

## 9. Next step after a separately approved Apply

Only after approval and successful Apply:

1. verify the new pool/client/issuer and Human authorizer read-only;
2. create one synthetic test user through the approved Cognito procedure;
3. obtain a valid Authorization Code + PKCE token without logging it;
4. execute authenticated Profile/CV/ApplicationV1 HTTP tests;
5. perform separately approved RIS partner/APIProfile/credential provisioning
   if partner routes are included;
6. test privacy export/erasure and cross-user isolation;
7. revoke/disable and delete only synthetic test resources.

No user or credential is created by this phase.

## 10. Final gate

```text
PLAN STRUCTURE: PASS
SECRET-FREE HUMAN PATH: PASS
APPLY AUTHORIZATION: NOT GRANTED
STATUS: STOP BEFORE APPLY
```
