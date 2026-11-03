# RIS-DEV2-TEST-IDENTITY-01 — Saved Terraform Plan (SUPERSEDED)

**Result:** **SUPERSEDED — DO NOT APPLY**

The plan in this report is superseded by the secret-free Human-only plan from
`RIS-DEV2-TEST-IDENTITY-02`. Do not apply the artifact below.

## 1. Plan artifact

The plan was created against the existing remote `ris-dev2` backend and
workspace with the verified `default` profile:

```text
Plan: C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-managed-identity-01.tfplan
SHA-256: CFF34F75049A479F2263CEB103C327618AEA5E0D5319028D9F49766729F9CA7C
```

The binary plan is outside the repository and is not committed. No apply was
run.

## 2. Guards

| Guard | Result |
|---|---|
| AWS profile | `default` |
| Account | `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| Backend bucket | `ris-dev2-tf-state-dev` |
| Backend state key | `env:/ris-dev2/dev/terraform.tfstate` |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| State serial observed before plan | `24` |
| Plan mode | managed identity, Orders disabled |
| Apply | **NOT EXECUTED** |

## 3. Action summary

```text
create: 12
update: 2
delete: 0
replace: 0
```

### Creates — only managed Cognito resources

- `module.cognito[0].aws_cognito_user_pool.users`
  (`ris-dev2-dev-users`);
- Human public app client `ris-dev2-dev-client`;
- M2M app client `ris-dev2-dev-m2m-client`;
- `ris-api` resource server with `m2m:execute` scope;
- seven existing-module user groups (`admins`, `candidates`, `recruiters`,
  `Admin`, `Staff`, `user-user`, `user-requier`);
- Cognito prefix domain `ris-dev2-dev`.

The external pool `eu-central-1_ojbmoiYGM` is not a resource in this plan and
has no action.

### Updates — expected JWT boundary changes

- `module.api.aws_apigatewayv2_authorizer.jwt` — Human issuer/audience changes
  from the external pool to the new managed pool/client;
- `module.api.aws_apigatewayv2_authorizer.jwt_m2m` — M2M issuer/audience changes
  from the external pool to the new managed pool/client.

These are in-place authorizer updates. They are security-boundary changes and
require explicit approval; they are not applied automatically.

## 4. Protected-resource review

Plan JSON inspection found no action for:

- CloudFront or OAC;
- Route 53/DNS;
- ACM;
- Lambda;
- DynamoDB;
- S3;
- SQS;
- Orders;
- external Cognito resources;
- `ris-dev` resources.

The plan contains no deletes or replacements.

## 5. Sensitive-state risk

The existing managed Cognito module creates an M2M client with
`generate_secret = true`. Terraform marks the client secret sensitive in the
plan, but a normal Terraform-managed Cognito client secret is still persisted
in Terraform state. No secret value was printed, copied, or added to Git or
this report.

This is a remaining approval risk against the requirement that secrets not be
stored in Terraform state. The exact plan must not be approved for apply until
the M2M secret/state handling is explicitly accepted or the module contract is
changed to use an approved external secret lifecycle. The Human public client
itself has `generate_secret = false`.

## 6. Apply gate

**STOP.** This report does not authorize apply. Before any apply approval,
resolve the M2M secret-state decision and separately approve the exact plan
hash plus both API authorizer updates. No Cognito user or partner/credential
binding may be created as an implicit side effect of this plan.
