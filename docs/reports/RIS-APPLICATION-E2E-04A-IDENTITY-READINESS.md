# RIS-APPLICATION-E2E-04A — Identity Readiness

**Result:** **POSITIVE AUTH E2E BLOCKED — TEST IDENTITY REQUIRED**

## Scope and safety

This checkpoint was read-only. No Terraform command, AWS mutation, Cognito
user creation, credential issuance, token acquisition, API mutation, secret
read, or Jobsearch connection was performed. `AGENTS.md` was preserved as the
only pre-existing working-tree modification.

## A1 — Repository and AWS baseline

| Check | Result |
|---|---|
| Repository root | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1` |
| Branch | `feature/ris-application-persistence-v1` |
| HEAD | `d66ddcedd8e3bd7d8a1bb79cd8a9700dc6e484b0` |
| Working tree | Only pre-existing `AGENTS.md` modified; preserved unchanged |
| AWS profile | `default` |
| AWS account | `262370457690` — PASS |
| Region | `eu-central-1` — PASS |
| Terraform workspace | `ris-dev2` — PASS (read-only) |
| State backend | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` — unchanged |
| State serial | `24` — expected |

Current deployment metadata also passed the checkpoint baseline:

- ApplicationV1 table `ris-dev2-dev-applications`: `ACTIVE`;
- GSI `gsi-owner`: `ACTIVE`;
- all 9 ApplicationV1 routes are present, target `integrations/oybmena`,
  authorization type `JWT`, authorizer `9i4w8r`;
- agent Lambda: `Active`, `LastUpdateStatus=Successful`.

## A2 — Authentication contract

The deployed contract is dual authentication:

1. `Authorization: Bearer <Cognito access JWT>` is validated by API Gateway;
2. `X-Api-Credential` carries the opaque RIS partner credential and is validated
   by Lambda;
3. server-side identity is derived from verified `iss + sub`;
4. tenant resolution uses the verified `custom:tenant_id` claim and/or the
   server-side partner registry, never caller-supplied owner or tenant fields;
5. partner application, API profile, credential, status and entitlement
   bindings must all resolve to the same authorized boundary.

The live JWT authorizer references the external Cognito issuer:

`https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM`

This external identity system is separate from the `ris-dev2` Foundation AWS
account (`262370457690`). The configured Cognito pool is not treated as a pool
owned by the Foundation account.

## A3/A4 — Authorized test identity discovery

No explicitly authorized synthetic Cognito test identity was found.

Evidence collected without reading secret values:

- no local environment variable names indicated a test token, partner
  credential, or E2E credential handoff;
- no dedicated E2E credential file was present;
- historical reports explicitly state that test-user creation was not approved
  for the relevant deployment and do not constitute current authorization;
- live metadata-only DynamoDB counts returned zero `ACTIVE` rows for:
  `ris-dev2-dev-partner-applications`, `ris-dev2-dev-api-profiles`,
  `ris-dev2-dev-credentials`, and `ris-dev2-dev-entitlements`;
- no credential or token value was read from DynamoDB, Terraform state, logs,
  browser sessions, or unrelated files.

The presence of empty or production-oriented infrastructure tables is not
authorization to create identities or credentials. Existing historical users,
if any existed in another account or pool, were not reused.

## Identity permission matrix

| Identity/reference | Environment | Issuer/client | Partner/tenant binding | Auth method | Scope | Result |
|---|---|---|---|---|---|---|
| Authorized synthetic human test user | `ris-dev2` | Not provided | Not established | Cognito access JWT | ApplicationV1 synthetic E2E | **BLOCKED** |
| Authorized partner application credential | `ris-dev2` | Not provided | No active binding found | `X-Api-Credential` | ApplicationV1 synthetic E2E | **BLOCKED** |
| Second authorized identity for isolation | `ris-dev2` | Not provided | Not established | Cognito access JWT + partner credential | Cross-identity tests | **BLOCKED** |

## Gate decision

```text
POSITIVE AUTH E2E BLOCKED — TEST IDENTITY REQUIRED
```

Phases 04B–04E are not started: no positive API call or mutation is safe or
authorized. Phase 04F may proceed with read-only regression verification only.
