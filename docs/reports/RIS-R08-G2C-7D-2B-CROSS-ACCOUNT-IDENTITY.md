# RIS-R08-G2C-7D-2B — Cross-Account External Identity

**Result:** CROSS-ACCOUNT CONTRACT VERIFIED / PLAN PREPARATION READY

The `ris-dev2` deployment account (`262370457690`) consumes the existing
`ris-dev` Jobsearch/Cognito identity by reference. The identity is not a
`ris-dev2` resource and is not migrated, imported, recreated or modified.

## Contract

External mode requires these separate inputs:

```text
RIS deployment account       = 262370457690
External Cognito account     = external_cognito_account_id
External Cognito pool ID     = external_cognito_user_pool_id
External Cognito pool ARN    = external_cognito_user_pool_arn
External Cognito issuer      = external_cognito_issuer
Human client                 = external_cognito_human_client_id
M2M client                   = external_cognito_m2m_client_id
```

`external_cognito_account_id` is independently validated as a 12-digit AWS
account ID. It is intentionally not compared with the RIS deployment account.
The pool ARN must use the declared external account, `eu-central-1`, and the
declared pool ID. The issuer must be the regional Cognito pool issuer for the
same pool ID. Human and M2M client IDs are required and remain distinct
audiences at the API Gateway JWT authorizers.

The M2M authorizer and `POST /v1/m2m/agents/{agentId}/execute` route remain
part of the current API contract and require the `ris-api/m2m/execute` scope.
Therefore M2M is **REQUIRED**, including when `orders_lifecycle=disabled`.

## Protected infrastructure boundary

The following existing `ris-dev` resources are **PROTECTED / EXTERNALLY
MANAGED** from `ris-dev2`:

- Cognito User Pool and existing users;
- Human and M2M app clients;
- Cognito Hosted UI/custom domain and OAuth configuration;
- CloudFront distribution/OAC;
- DNS, ACM and TLS associations.

External mode sets the Cognito module count to zero. The root Terraform
configuration contains no protected `ris-dev` Cognito, CloudFront, Route 53 or
ACM resource declarations. RIS-owned health/public infrastructure remains
separate and is not the protected Jobsearch distribution. No DNS change is
required while the existing
`auth.mays-job-matcher.app` CloudFront/Cognito mapping remains valid.

## `ris-dev` references and evidence

The retained `ris-dev` configuration/deployment evidence identifies:

| Reference | Value | Evidence quality |
|---|---|---|
| Pool | `eu-central-1_ojbmoiYGM` | `RIS_DEV_CONFIG_VERIFIED` |
| Pool ARN | `arn:aws:cognito-idp:eu-central-1:<ris-dev-owner-account>:userpool/eu-central-1_ojbmoiYGM` | `RIS_DEV_CONFIG_VERIFIED`; owner account confirmation required |
| Issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ojbmoiYGM` | `RIS_DEV_CONFIG_VERIFIED` |
| Human client | `7ldhihlpdgsgcl3puvu4oi7ksv` | `RIS_DEV_CONFIG_VERIFIED` |
| M2M client | `82ji073smu1b3fsvj96sonso` | `RIS_DEV_CONFIG_VERIFIED` |
| M2M scope | `ris-api/m2m:execute` | `RIS_DEV_CONFIG_VERIFIED` |
| OAuth/custom domain | `auth.mays-job-matcher.app` | `RIS_DEV_CONFIG_VERIFIED`; live owner confirmation required |
| CloudFront/DNS/ACM | existing `ris-dev` mapping | `RIS_DEV_CONFIG_VERIFIED`; no `ris-dev2` mutation |

The owning account may differ from `262370457690`. The authorized `default`
profile is guarded to `262370457690`; no profile switch or external-account
AWS query was performed. The remaining `RIS_DEV_LIVE_VERIFIED` step is an
owner-side, read-only confirmation before remote plan approval. It does not
block the code/configuration contract.

## Implemented changes

- Added `external_cognito_account_id` to Terraform variables and installer
  project-overlay allowlisting.
- Changed pool ARN validation to use the external Cognito account rather than
  the RIS deployment account.
- Added fail-closed bootstrap validation for the external account ID.
- Preserved issuer/pool consistency and required Human/M2M references.
- Added cross-account and protected-resource regression tests.
- Classified the existing `ris-dev` identity as protected and externally
  managed in architecture, runbook and plan-input documentation.

## Verification

- Relevant G2C-6/G2C-7 tests: **19 passed**.
- Python `py_compile` (`bootstrap_preflight.py`, `ris.py`): **PASS**.
- Terraform `fmt -check`: **PASS**.
- `terraform init -backend=false`: **BLOCKED** by the preserved deletion of
  generated `terraform/modules/mays_orders/variables.tf`; the generated module
  then has no declarations for `project_name`, `tags`, `monitoring_enabled` or
  `log_retention_days`.
- Terraform `validate`: **BLOCKED by the same pre-existing generated-module
  condition**. The deleted file was not restored or regenerated.
- No remote plan, apply, destroy, import, state mutation, push, merge or AWS
  resource change was performed.

## G2C-7D-3 gate

**Plan preparation:** READY after owner-side read-only confirmation of the
current pool ARN/account and client ownership, plus local generated-module
repair in the normal package/build workflow.

**Remote Terraform plan:** separately authorized only; not executed here.
**Apply:** NOT AUTHORIZED.
