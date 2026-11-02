# RIS-R08-G2C-7C — Safe RIS-DEV2 State Bootstrap Contract

**Status:** GO / OFFLINE PREFLIGHT VERIFIED / REMOTE PLAN NOT AUTHORIZED

## Decision boundary

### A. Reuse existing State

Permitted only after a separate approval proves State lineage, complete
resource ownership, protected-resource mapping and a safe bootstrap procedure.
The current serial-17 State is empty, while historical versions represent
staged installation/teardown. It is not an upgrade baseline by itself.

No historical object version may be restored, pushed, imported, migrated or
used as an implicit plan source.

### B. New isolated bootstrap State — preferred construction

Use a separately approved State tuple if ownership cannot be recovered. The
historical `ris-dev2` object remains unchanged. The new tuple must have an
explicit project/workspace/key, distinct resource naming, an approved backend
owner, and a recorded recovery/backup decision. No new State is initialized by
G2C-7C.

## Exact target contract

The offline preflight requires these exact values:

```text
project_name=ris-dev2
environment=dev
account_id=262370457690
region=eu-central-1
aws_profile=default
backend_bucket=ris-dev2-tf-state-dev
backend_lock_table=ris-dev2-tf-lock
workspace=ris-dev2
state_key=env:/ris-dev2/dev/terraform.tfstate
```

It also requires explicit `identity_mode` and `orders_lifecycle` values. In
external identity mode, pool/ARN/issuer/human-client/M2M-client references are
mandatory and structurally cross-checked. In external Orders mode, table and
queue references are mandatory. Disabled Orders mode requires no dummy
references.

All known privacy/erasure/receipt/freeze/cutover/S3 execution flags are
rejected when true.

## Local mechanism

Run without AWS access:

```text
python -m installer.bootstrap_preflight --config <non-secret-config.json>
```

The validator is pure configuration logic, returns all violations, and fails
closed on missing identity, foreign project/profile/backend/state, malformed
external references or enabled privacy execution flags. It does not inspect
live resource ownership; that remains a mandatory later read-only gate.

## Protection and later G2C-7D plan preparation

Before any plan, independently verify live Cognito pool/clients/users,
Jobsearch domain, CloudFront/OAC, DNS/ACM, external Orders references, IAM and
state lineage. The future plan must be saved outside Git, hashed, reviewed for
all creates/updates/deletes/replacements and rejected on any protected-resource
change, foreign state address, implicit Cognito/Orders installation, state
migration or privacy flag activation.

Required recovery evidence includes backend version/backup posture, lock
recovery owner, data backups and rollback criteria. Apply requires a separate
written approval of the exact plan hash.

## Verification

- G2C-7 bootstrap tests: **5 passed**.
- G2C-6 protection tests: **6 passed**.
- AWS calls from the preflight: **none**.
- Remote Terraform plan/apply/state mutation: **not performed**.
