# RIS-R08-DEV2-11A — Terraform Lock Reconciliation

## Verified context

| Field | Evidence |
|---|---|
| AWS profile/account | `default` / `262370457690` |
| Region | `eu-central-1` |
| Workspace | `ris-dev2` |
| Bucket | `ris-dev2-tf-state-dev` |
| Canonical state key | `env:/ris-dev2/dev/terraform.tfstate` |
| Lock table | `ris-dev2-tf-lock` |
| State serial/lineage | `25` / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |

## Records

The lock table contains two records, both ending in `-md5`:

```text
ris-dev2-tf-state-dev/env:/ris-dev2/dev/terraform.tfstate-md5
  Digest: b91442a166f33991c2f21a472ac1a242

ris-dev2-tf-state-dev/env/ris-dev2/dev/terraform.tfstate-md5
  Digest: b7cf3f92b131e668838e1af6ac622e33
```

Read-only S3 evidence maps the first digest to the canonical state object
`env:/ris-dev2/dev/terraform.tfstate` (539650 bytes). The second maps to the
legacy object `env/ris-dev2/dev/terraform.tfstate` (3088 bytes, serial 13,
zero resources). Both are digest-cache entries, not active lock records.

No base `LockID` item, `Info`/owner metadata, or running local Terraform
process was found. The canonical backend key is unambiguous.

## Status and recommendation

**LOCK STATE: VERIFIED — no active Terraform lock.**

The legacy digest/state object was not deleted, and no lock cleanup or
force-unlock was attempted. A later normally locked Terraform operation is
operationally possible using the canonical backend contract, subject to a
fresh identity and protected-resource check. Legacy artifacts require
separately approved maintenance.
