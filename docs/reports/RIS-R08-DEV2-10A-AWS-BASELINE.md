# RIS-R08-DEV2-10A — AWS Baseline

## Identity

| Field | Verified value |
|---|---|
| AWS profile | `default` |
| Account | `262370457690` |
| Caller | IAM user `devnemo` (no credentials recorded) |
| Region | `eu-central-1` |
| AWS CLI | 2.38.5 |
| Terraform | 1.17.0 |
| Branch/HEAD | `feature/ris-privacy-r08-gate-b-orchestration-01` / `b511819` |
| PR | #5, open, no checks reported yet |

## State

Read-only S3 evidence confirms:

- Bucket: `ris-dev2-tf-state-dev`;
- effective key: `env:/ris-dev2/dev/terraform.tfstate`;
- workspace: `ris-dev2`;
- state serial: `25`;
- state lineage: `a0bd361d-5cd1-a207-a8c0-e6888f0be082`;
- state resource count: `181`;
- last modified: `2026-11-03T10:59:47Z`.

The correct current lock table is `ris-dev2-tf-lock`, not the historical
`mays-ris-tf-lock`. It is ACTIVE, but contains two lock-ID records:

```text
ris-dev2-tf-state-dev/env:/ris-dev2/dev/terraform.tfstate-md5
ris-dev2-tf-state-dev/env/ris-dev2/dev/terraform.tfstate-md5
```

The second key is a legacy/malformed variant. No lock cleanup or state
mutation was performed. The diagnostic plan therefore used `-lock=false` and
must not be treated as proof that a normally locked plan is operationally
ready.

AWS identity and state ownership match `ris-dev2`; no account/profile
mismatch was found.
