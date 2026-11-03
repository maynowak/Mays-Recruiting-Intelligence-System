# RIS-APPLICATION-DEPLOY-03L — Authorized Apply & Synthetic AWS E2E

**Result:** **APPLY PASS / PROTECTED INFRASTRUCTURE UNCHANGED**

## 1. Pre-Apply guards

All required guards passed before Apply:

- repository root: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1`;
- branch: `feature/ris-application-persistence-v1`;
- HEAD: `554d37a14d3e5ad0fc38fd094678c4efd31cc3a0`;
- existing uncommitted `AGENTS.md` change preserved and not staged;
- AWS profile `default`, account `262370457690`, region `eu-central-1`;
- workspace `ris-dev2`;
- backend bucket `ris-dev2-tf-state-dev`;
- state key `env:/ris-dev2/dev/terraform.tfstate`;
- lock table `ris-dev2-tf-lock`;
- lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- state serial before Apply: `23`;
- Terraform `1.17.0`, Windows `amd64`;
- lockfile provider: AWS `6.67.0` only;
- approved plan SHA-256 matched:
  `587E02FC61DE16BD74BFDDDF1B02625C411EFE6F9CD9903DD7CA9925AC243078`;
- `terraform show -json` succeeded;
- plan drift and active actions matched 03K exactly: 85 drift entries and
  11 creates / 1 update / 0 deletes / 0 replacements;
- no active protected-resource action.

## 2. Apply result

Only the approved binary plan was applied:

```text
terraform -chdir=terraform apply -input=false -no-color \
  C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-03j.tfplan
```

Terraform exit code: **0**

Terraform reported:

```text
Apply complete! Resources: 11 added, 1 changed, 0 destroyed.
```

No new plan, target, replace, destroy, unlock, import, migration or rollback
was used.

### Actual actions

- 11 creates: ApplicationV1 DynamoDB table, ApplicationV1 IAM policy, and nine
  ApplicationV1 API routes;
- 1 update: existing agent Lambda bundle/environment;
- 0 deletes;
- 0 replacements.

## 3. State after Apply

| Check | Result |
|---|---|
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` — unchanged |
| State serial before | `23` |
| State serial after | `24` |
| State SHA-256 after | `53db809eb781fe8ff071aabd9925699db936ed4f3bfe32cf9014a94fa35b0dc9` |
| Orders lifecycle | `disabled` |
| Privacy/Erasure/Freeze/Cutover flags | remain `false` |

## 4. ApplicationV1 deployment verification

- DynamoDB table `ris-dev2-dev-applications`: **ACTIVE**;
- billing: `PAY_PER_REQUEST`;
- keys: `applicationId` / `entityKey`;
- GSI `gsi-owner`: **ACTIVE**, `ownerKey` / `updatedAt`;
- all nine ApplicationV1 routes exist on API `8apxb6fgne`;
- all routes target existing integration `oybmena`;
- all routes use JWT authorizer `9i4w8r` and `authorization_type=JWT`;
- agent Lambda `ris-dev2-dev-agent`: `State=Active`;
- Lambda `LastUpdateStatus=Successful`;
- Lambda environment contains `APPLICATIONS_TABLE=ris-dev2-dev-applications`;
- ApplicationV1 IAM policy contains only `PutItem`, `GetItem`, `Query`,
  `DeleteItem`, and `TransactWriteItems` on the application table and GSI.

## 5. Protected infrastructure

**Result: `PROTECTED INFRASTRUCTURE UNCHANGED`**

| Area | Verification |
|---|---|
| Cognito pool/clients/domain/OAuth | No active Terraform action; existing JWT issuer/audience on authorizer unchanged. Direct pool read is cross-account and returned `ResourceNotFound` under target account, as expected for the external pool account. |
| JWT authorizer | ID `9i4w8r`, type JWT, issuer `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM`, audience unchanged |
| CloudFront `E1IZKHFPZ5X7SN` | `Deployed`, enabled, same ETag `E23ZP02F085DFQ`, origin and OAC unchanged |
| CloudFront OAC | `E30BLRTMAWVYN1`, unchanged |
| Route53 / DNS | No active plan action or state resource in scope |
| ACM | No active plan action or state resource in scope |
| Existing RIS resources/data | No deletes/replacements; only approved ApplicationV1 actions occurred |

## 6. Read-only smoke tests

- CloudFront health page: HTTP `200`;
- unauthenticated `/health`: HTTP `401`, consistent with the JWT contract;
- unauthenticated existing `/me/profile`: HTTP `401`;
- unauthenticated existing `/v1/partner/me/cvs`: HTTP `401`;
- CloudFront configuration remained deployed/enabled after Apply.

## 7. E2E gate

The negative authentication tests were executed against all nine ApplicationV1
routes with synthetic request data only:

- missing JWT: 9/9 returned `401`;
- invalid JWT: 9/9 returned `401`;
- credential without JWT: 9/9 returned `401`.

No authentication boundary was bypassed and no real application data was sent.

Positive CRUD, pagination, version conflict, idempotency, status transition,
history, cover-letter, export and delete tests require an authorized Cognito
identity plus an active partner credential. No such approved test credentials
were available in this session. These tests are therefore **BLOCKED**, not
passed by assumption.

Privacy inspect/export, cross-user/tenant/partner/issuer isolation and
resumable erasure are likewise **BLOCKED** without authorized identities and
synthetic ownership fixtures. All global erasure/freeze/cutover flags remain
disabled. Jobsearch integration was not exercised and remains out of scope.

## 8. Final status

| Area | Result |
|---|---|
| Pre-Apply guards | PASS |
| Saved plan | HASH MATCH |
| Terraform Apply | PASS, exit `0` |
| Actual creates | `11` |
| Actual updates | `1` |
| Deletes/replacements | `0 / 0` |
| State lineage | UNCHANGED |
| State serial | `23 -> 24` |
| ApplicationV1 infrastructure | VERIFIED |
| ApplicationV1 CRUD E2E | BLOCKED — credentials unavailable |
| Auth negative tests | PASS — 27/27 expected `401` |
| Auth/isolation positive tests | BLOCKED — credentials unavailable |
| Privacy Inspect/Export | BLOCKED |
| Erasure E2E | BLOCKED; execution flags false |
| Protected infrastructure | UNCHANGED |
| Jobsearch integration | NOT IN SCOPE |
| DSGVO production approval | NOT GRANTED |

No production/privacy approval is implied by this report.
