# RIS-DEV2-TEST-IDENTITY-01 — Offline Validation

**Result:** **PASS — OFFLINE CONTRACT VALIDATED / APPLY BLOCKED**

## 1. Configuration

Added the dedicated non-secret overlay:

```text
installer/project-configs/ris-dev2.json
```

It explicitly selects `managed` identity mode, disables Orders, enables OAuth
authorization code + PKCE with one localhost callback/logout URL, disables
custom Cognito domains, and permits only the localhost API origin.

No external pool ID, client secret, password, token, certificate ARN, DNS name
or production callback was added.

## 2. Offline checks

| Check | Result |
|---|---|
| Dedicated overlay contract tests | **PASS** — 2 passed |
| Existing G2C identity/orders tests | **PASS** — 6 passed |
| Combined identity selection | **PASS** — 8 passed |
| Terraform format check | **PASS** |
| Terraform init `-backend=false` | **PASS** |
| Terraform validate | **PASS** with existing provider deprecation warnings |
| Mays-Orders module builder | **PASS**; generated locally only |
| AWS mutation | **NOT PERFORMED** |

The generated Orders module was required for root Terraform validation, but
`orders_lifecycle=disabled` keeps the Orders modules out of the planned resource
graph for this overlay. No Orders deployment or AWS call was performed.

## 3. Contract findings

- Managed mode creates a new pool named `ris-dev2-dev-users` through the
  existing module naming contract.
- The Human client is public and has no client secret.
- OAuth uses the existing module's `code` flow and explicit callback lists;
  there is no implicit grant.
- The M2M client/resource server remains part of the existing managed module
  contract; its generated secret must remain confined to sensitive Terraform
  state and must never appear in Git, reports or output.
- API Gateway receives the managed issuer and Human/M2M audiences from module
  outputs.
- The overlay does not create users, groups, partner bindings, APIProfiles,
  credentials or entitlements.

## 4. Regression boundary

This validation proves configuration and Terraform syntax only. It does not
prove that the remote `ris-dev2` state can safely transition from external to
managed identity. That requires the saved remote plan and explicit review of
every action.

## 5. Stop condition

No apply is authorized by this report. The next step is one guarded saved plan
against the existing `ris-dev2` backend/state, followed by a hard stop before
apply.
