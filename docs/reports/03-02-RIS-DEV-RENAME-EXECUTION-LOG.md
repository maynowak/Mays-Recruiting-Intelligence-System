# 03-02 — RIS-DEV RENAME + RIS-DEVELOPMENT TEARDOWN (EXECUTION LOG)

**Task:** Rename the permanent dev installation `ris-development` → `ris-dev`, verify the
new stack, then decommission the old stack. Treat as delete+create (destructive rebuild).

**Date:** 2026-10-20
**Account:** 240571105849, eu-central-1
**Operator:** OpenCode agent (Big Pickle)
**Approval:** explicit user approval for a clean rebuild ("kannst es clean machen und neu app").

---

## 0. Motivation

- Binding AWS name limits for the RIS core (`installer.ris.RIS_AWS_NAME_RULES`):
  - CloudTrail S3 bucket `{project}-cloudtrail-<account>` → max `project_name` **39**.
  - Cognito **backup** bucket (when `ORDERS_ENABLE_COGNITO_BACKUP=True`) → max `project_name` **23**.
- `ris-development` (14) → component `ris-development-mays-orders` (27) passes the 39
  core limit but **violates** the stricter 23 backup limit. The name must be known *before*
  resources are created — the project has to "know its name" up front.
- `ris-dev` (7) → component `ris-dev-mays-orders` (19) passes **both** limits with headroom.

| project | component | len | cloudtrail bucket | backup-limit 23 |
|---|---|---|---|---|
| ris-development | ris-development-mays-orders | 27 | 51 | ❌ |
| ris-dev | ris-dev-mays-orders | 19 | 43 | ✅ |

---

## 1. Pre-flight (read-only)

Verified before any mutation:

- Data holdings of the old `ris-development` stack: 10/11 DynamoDB tables had **0 items**;
  only `ris-development-dev-agent-catalog` held 1 item (`reference_agent`, a reproducible seed).
- Both old Cognito pools had **0 users**:
  `ris-development-dev-users` (`eu-central-1_7QCp09XEZ`) and
  `ris-development-mays-orders-users` (`eu-central-1_f53oRl4jy`).
- ⇒ No real data and no identities to lose.

---

## 2. Build the `ris-dev` stack

1. Lambda bundles:
   `python lambda/build_zip.py --bundle all` → `terraform/lambda.zip` (agent),
   `lambda/dist/orders-reader.zip` (reader). rc=0.
2. Module builder (preferred orders-integration path):
   `python -m installer.build_mays_orders_module --project-name ris-dev --force` → rc=0.
   `terraform/main.tf` `module.mays_orders` uses `project_name = "${var.project_name}-mays-orders"`.
3. Installer `validate` (`--project-name ris-dev --no-composite assumed`): only
   `terraform init -backend=false` + `terraform validate` → rc=0.
4. Installer `plan` / `install --no-composite`: the installer's composite path derives the
   backend from `project_name` (`ris-dev-tf-state-dev`, `ris-dev-tf-lock`) — a second state
   bucket we do not want — and the Orders clone checkout fails on the pinned SHA.
   ⇒ Used the proven direct-Terraform path (same as `parallel_tests.sh`).

### Terraform (direct, explicit backend)

```bash
cd terraform
export AWS_PROFILE=mayaws AWS_REGION=eu-central-1 TF_DATA_DIR=/tmp/tfris-dev
terraform init -reconfigure \
  -backend-config="bucket=mays-ris-tf-state-dev" \
  -backend-config="region=eu-central-1" \
  -backend-config="dynamodb_table=mays-ris-tf-lock" \
  -backend-config="key=dev/terraform.tfstate" \
  -backend-config="workspace_key_prefix=env:"
terraform workspace new ris-dev
terraform plan  -var="project_name=ris-dev" ... -out=/tmp/ris-dev.tfplan
terraform apply /tmp/ris-dev.tfplan
```

- **Plan:** 169 to add, 0 to change, 0 to destroy.
- **Apply:** `Apply complete! Resources: 169 added, 0 changed, 0 destroyed.`
- **Post-apply plan:** `No changes.` (no drift).
- **State key:** `env:/ris-dev/dev/terraform.tfstate` on `s3://mays-ris-tf-state-dev`
  (installer convention `{env}/terraform.tfstate` + `workspace_key_prefix=env:`).

### Live `ris-dev` resources (verified)

- Kernel API `ris-dev-dev-api` (`g6901and25`, stage `$default`, `/health` → 401 unauthenticated).
- Orders API `ris-dev-mays-orders-api` (`zf8tc0k2r2`).
- Pools: `ris-dev-dev-users` (`eu-central-1_ojbmoiYGM`), `ris-dev-mays-orders-users` (`eu-central-1_cmJWXujnb`).
- 11 DynamoDB tables (`ris-dev-dev-*` ×10 + `ris-dev-mays-orders`), 6 SQS queues,
  6 Lambdas (python3.14), 5 buckets, 1 trail `ris-dev-trail` (multi-region).

> **Note:** API IDs / pool IDs are **per-install random** — a rebuild issues new IDs.
> No tracked source hardcodes them (grep for `klklimekab`/`vdtv5in694` → empty).

---

## 3. Name-limit regression coverage

`tests/test_orders_aws_name_limits.py` gained `TestActiveDeploymentNames`:

- `orders_component_project_name("ris-dev") == "ris-dev-mays-orders"`.
- Real component fits both core (`enable_cognito_backup=False`) **and** backup
  (`True`) limits → `orders_name_limit_violations(...) == []`.
- CloudTrail bucket `ris-dev-mays-orders-cloudtrail-240571105849` ≤ 63.
- `validate_ris_aws_name_limits("ris-dev")` passes.

---

## 4. Stale live-contract tests fixed

The 8 hardcoded-`mays-ris` tests were made env-parametrizable, defaulting to the active install:

- `tests/test_observability_foundation.py`: `PROJECT = os.environ.get("RIS_PROJECT", "ris-dev")`;
  `test_project_isolation_no_mo_overlap` now asserts the *own* `{PROJECT}-mays-orders-overview`
  dashboard exists and the pre-rename `{PROJECT}-orders-overview` is gone; log-group checks use `PROJECT`.
- `tests/test_lambda_packaging.py`: `LIVE_PROJECT = os.environ.get("RIS_PROJECT", "ris-dev")`;
  FunctionName lookups `{LIVE_PROJECT}-dev-agent` / `{LIVE_PROJECT}-dev-orders-reader`.

Result: full pytest **1593 passed, 2 failed** (only the 2 documented baseline defects in
`tests/test_ris_installer.py`), 3 skipped.

---

## 5. Verifier suite adapted (`scripts/parallel_tests.sh`)

- Added `ris-dev` target; `ris-development` target now errors with a pointer to `ris-dev`.
- Prefix matching made **segment-safe** via `_seg()` (append `-`):
  `starts_with(Name, 'ris-dev-')` no longer matches `ris-development-*`.
  Applied to `LAMBDAS/RUNTIMES/TABLES/APIS/QUEUES/BUCKETS/POOLS/DASHES/LOGGRPS` and the
  CloudTrail queries.
- `S1.7` state-object check uses the installer convention
  `env:/<workspace>/dev/terraform.tfstate` with fallback to `env:/<workspace>/terraform.tfstate`.
- Removed the dead `MIGRATED`/`ris-development`-specific guard; kept the generic
  `<project>-orders` alt-name check.

**`./scripts/parallel_tests.sh ris-dev` → 64 PASS / 0 FAIL** (only the documented baseline
installer unit-test WARN remains).

---

## 6. Teardown of the old `ris-development` stack

Plan reviewed before apply:

- `terraform plan -destroy` (workspace `ris-development`, key `terraform.tfstate`):
  **169 deletes, nothing else** (no create/replace/no-op).
- Every address belonged to the old stack (RIS core modules + `module.mays_orders` + monitoring).
- Foreign e2e CloudFront `E1R3BHTJNMC6XW` **not** in the plan; the CloudFront being destroyed
  was `E1OFBSEH89Z8X2` (origin `ris-development-dev-health-public`).

Apply:

- `terraform apply` removed 167/169. Two `BucketNotEmpty` errors:
  `ris-development-cloudtrail-240571105849` (CloudTrail log objects) and
  `ris-development-dev-health-public` (`public-status.json`).
- Emptied and deleted both buckets manually; removed the residual state entries
  (`aws_s3_bucket`).
- Deleted the workspace `ris-development` and the stale state object
  `env:/ris-development/terraform.tfstate`.

### Post-teardown verification (must all be 0)

| service | count |
|---|---|
| DynamoDB (`ris-development*`) | 0 |
| Lambda | 0 |
| S3 buckets | 0 |
| Cognito pools | 0 |
| API Gateway v2 | 0 |
| CloudTrail | 0 |
| SQS queues | 0 |
| CloudWatch dashboards | 0 |
| CloudWatch alarms | 0 |
| `/aws/lambda/ris-development*` log groups | 0 |

`ris-dev` re-verified afterwards: **64 PASS / 0 FAIL**, no orphaned log groups.

---

## 7. Docs / config reconciled

- `AGENTS.md`: Deployments section rewritten for `ris-dev` (names, IDs, name-length rationale,
  per-install-random-ID note, destructive-rebuild note); architecture specifics updated;
  Jobsearch pool → `ris-dev-dev-users`.
- `README.md`: current install, verifier command, local `TF_DATA_DIR`, module-builder command,
  suite counts (1593 passed).
- `installer/README_MODULE_BUILDER.md`: example command → `ris-dev`.

---

## 8. Evidence files

- `/tmp/ris-dev.tfplan`, `/tmp/ris-dev-apply.log`, `/tmp/ris-dev-plan.log`
- `/tmp/ris-dev-postplan.log`
- `/tmp/ris-development-destroy.tfplan`, `/tmp/ris-development-destroy-apply.log`
- `/tmp/ris-dev-verify3.log`, `/tmp/ris-dev-final-verify.log`, `/tmp/ris-dev-verify-after-docs.log`
- `/tmp/old-risdev-state.json` (pre-destroy state snapshot, 185 resources)
- `/tmp/pytest-20261020.log`

## 9. Open

- Jobsearch Auth E2E Phase 2/3 (OAuth callback/PKCE `redirect_mismatch`, OIDC 404 on prefix
  domain, DNS `auth.mays-job-matcher.app` absent, API CORS `null`) — unaffected by the rename,
  but now runs against `ris-dev` IDs/pool.
- `installer.ris install --through` remains WIP; module builder stays the preferred path.
