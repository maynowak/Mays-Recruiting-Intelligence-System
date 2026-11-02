# RIS-DEV-UPGRADE-01 — Controlled Upgrade Execution

**Result:** STOPPED AT VALIDATE / NO PLAN / NO APPLY

The upgrade was not executed because the authorized `ris-dev` AWS identity
could not be established. No Terraform state, AWS resource, DNS, Cognito,
CloudFront, ACM or backend mutation was performed.

## Baseline

| Item | Observed |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD | `f6b14901084e175078324f38071490b2e4aa9726` |
| Expected `ris-dev` account | `240571105849` |
| Expected region | `eu-central-1` |
| Expected profile | `mayaws` (per repository deployment contract) |
| Working tree | 39 pre-existing untracked files; pre-existing deletion of `terraform/modules/mays_orders/variables.tf` |

## Execution matrix

| Step | Status | Evidence |
|---|---|---|
| Validate | **BLOCKED** | `mayaws` profile is unavailable; default STS guard resolves to the wrong account |
| Plan | **NOT RUN** | State ownership and target account were not verified |
| Apply Gate | **BLOCKED** | No approved saved plan or verified `ris-dev` identity |
| Apply | **NOT RUN** | No apply command executed |
| Verify | **NOT RUN** | No apply occurred |
| Clean | **NOT RUN** | Existing untracked files and changes were preserved |

## Account and profile guard

The available boto3 profiles are only:

```text
default
```

The documented `mayaws` profile could not be loaded. A read-only STS check
against `default` returned:

```text
Account: 262370457690
Arn: arn:aws:iam::262370457690:user/devnemo
Region: eu-central-1
```

This is the `ris-dev2` target account, not the `ris-dev` owner account
`240571105849`. The account guard therefore failed closed. No `ris-dev` state
bucket, lock table, workspace, state lineage or resource inventory was queried
under the wrong identity.

## Local validation

- G2C-6/G2C-7 identity and contract regressions: **19 passed**.
- Python `py_compile` for installer, backend, runner and Orders builder:
  **PASS**.
- Recursive Terraform `fmt -check`: **BLOCKED** by the pre-existing
  unformatted `terraform/ris-dev2.tfvars` file.
- Orders builder `--project-name ris-dev --check`: **FAIL** because the
  pre-existing deletion of generated
  `terraform/modules/mays_orders/variables.tf` is still present.
- Terraform `init -backend=false` / `validate`: **NOT RUN for `ris-dev`**;
  the local module contract is already known to fail for the same missing
  generated input declarations.

## Protected infrastructure decision

Because the `ris-dev` account and state could not be verified, no plan was
created. Consequently no action classification exists for Cognito, app
clients, Cognito domains/OAuth, CloudFront/OAC, DNS, ACM, IAM, Lambda, API
Gateway, DynamoDB, SQS or Orders. The protected-infrastructure invariant was
preserved by stopping before initialization against the remote backend.

The existing `ris-dev` Identity remains the owner of its Cognito and auth
resources. No `ris-dev2` values were used as a replacement.

## Required recovery inputs

1. Restore/provide the authorized `mayaws` profile or an equivalent explicitly
   authorized read-only/write identity for account `240571105849`.
2. Resolve the generated Orders module validation issue through the pinned
   builder workflow without overwriting unrelated working-tree changes.
3. Re-run validate against workspace `ris-dev` and backend path
   `env:/ris-dev/dev/terraform.tfstate`.
4. Create and machine-check one saved plan without `-target`, `-replace`,
   `-destroy` or `-refresh=false`.
5. Obtain explicit approval of that exact plan hash before any apply.

## Git safety

Only this execution report was added and committed. The 39 untracked files and
the existing deletion of `terraform/modules/mays_orders/variables.tf` were not
cleaned, restored or overwritten. No push or merge was performed.
