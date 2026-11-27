# RIS-DEV2-WORKER-CONTROLLED-REPLAN-19G3

**Date:** 2026-11-27 | **Result:** **PREFLIGHT PASS — ONE FULL PLAN CREATED — PLAN_SCOPE FAIL — APPLY BLOCKED**

**Plan source commit:** `7ccc34c3da3fbe4a686dd34fca7d7d2439c480cb`

**Plan SHA-256:** `8daf05702d4e0ff27bd6668582f5e39162d0ab660935d52fdf1145703a722752`

## Decision

One complete, normally refreshing Terraform plan was created for the approved
RIS-DEV2 account/region and the `ris-dev2` workspace. It found **0 Add / 4
Change / 0 Destroy**, not the authorized 0/2/0. The two extra in-place updates
are Analysis and Orders-Reader. Their `source_code_hash` values remain exactly
equal to the deployed hashes, but Terraform detects a change to each Lambda's
`filename` input and plans an update. This is a scope violation.

`PLAN_SCOPE=FAIL`; `APPLY_READINESS=BLOCKED`. Do not apply this plan. No second
plan was created. The earlier 19G plan remains blocked and was not used.

## Preflight evidence

- Git branch `feature/ris-analysis-integration-07`; local and remote HEAD both
  matched `7ccc34c3da3fbe4a686dd34fca7d7d2439c480cb` before planning.
- The sole pre-existing unstaged path was
  `docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json`. It was not
  edited, staged, stashed, or reset. It remains unstaged after this task.
- STS identity: account `262370457690`, principal
  `arn:aws:iam::262370457690:user/devnemo`; configured region `eu-central-1`.
- Terraform `1.17.0`; AWS provider `6.67.0`, time provider `0.14.2` from the
  committed lock file. Workspace `ris-dev2`, supplied by the existing
  `TF_WORKSPACE=ris-dev2` environment.
- Backend: bucket `ris-dev2-tf-state-dev`, key
  `env:/ris-dev2/dev/terraform.tfstate`, region `eu-central-1`, lock table
  `ris-dev2-tf-lock`. The regular temporary plan lock was allowed.
- Before plan: state serial **75**, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 VersionId
  `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ`. Read-only state inspection and direct
  Lambda reads agreed. After plan, the S3 VersionId, size, and LastModified
  remained unchanged; state-content mutations: **0**.
- Current live Lambda `CodeSha256` values matched the state for all four
  functions. Project/Environment ownership tags matched RIS-DEV2; Analysis
  retained `Purpose=internal-analysis`. Analysis still has
  `ANALYSIS_SYNTHETIC_MODE=true`; the reviewed var file has
  `analysis_synthetic_mode=true`, `project_name=ris-dev2`, `environment=dev`,
  `aws_region=eu-central-1`, and `orders_lifecycle=managed`.
- Local artefacts were not changed: worker ZIP SHA-256
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`, preserved
  Analysis `276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10`,
  preserved Reader
  `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b`. Mays pin
  remains `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`. Successful 19G2 QA run
  `46005456362` was reused; no tests or builds were run for this replan.
- Terraform init used a separate `TF_DATA_DIR`, the existing backend config,
  and `-lockfile=readonly`. It reported the pre-existing deprecated S3 backend
  `dynamodb_table` parameter; no lock/config files in the repository changed.

## Plan artifact and exact changes

- Plan file, outside the repository:
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-worker-19g3.tfplan`
- SHA-256: `8daf05702d4e0ff27bd6668582f5e39162d0ab660935d52fdf1145703a722752`
- Size: 252,941 bytes; Terraform `1.17.0`.
- One regular full plan, normal refresh, no `-target`, `-refresh=false`,
  `-replace`, or artificial suppression. The plan was saved once, moved from
  Terraform's literal `$plan` output path to the external path above, and
  verified by SHA-256 and `terraform show -json`. It is not committed.
- Machine-readable plan summary reports `resource_drift_count=0` and 270 no-op
  resources.

| Resource | Action | Changed attributes | Source-code-hash result |
|---|---|---|---|
| `module.lambda.aws_lambda_function.agent` | in-place update | `source_code_hash`, computed `last_modified` | deployed `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` → candidate `UHvBfbny7gky5C3gOaUIqz8B47srVRDqefLlT5WzpY0=` (worker SHA `507bc17…`) |
| `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | in-place update | `source_code_hash`, computed `last_modified` | deployed `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` → candidate `UHvBfbny7gky5C3gOaUIqz8B47srVRDqefLlT5WzpY0=` (worker SHA `507bc17…`) |
| `module.analysis_runtime.aws_lambda_function.analysis[0]` | **unexpected** in-place update | `filename`, computed `last_modified` | unchanged at deployed Analysis hash `J2tORCAnIWfdMsWQ1tur7UAIckpwkeTYZQTVRE/iaxA=`; filename changes from the state-recorded absolute `terraform/analysis-lambda.zip` path to the new preserved-artifact path |
| `module.orders_reader[0].aws_lambda_function.reader` | **unexpected** in-place update | `filename`, computed `last_modified` | unchanged at deployed Reader hash `YQAE9urjUx5MhyNkOeSRvL8MEC6ikWH+8kfCcTyBrms=`; filename changes from the state-recorded absolute `lambda/dist/orders-reader.zip` path to the new preserved-artifact path |

The Analysis/Reader package bytes and SHA-256s are preserved. The remaining
scope problem is the Terraform `filename` attribute identity, not a ZIP-content
or code-hash mismatch. This replan task forbids artifact changes and a second
plan; therefore no attempt was made to alter the artifact paths or replace the
canonical build outputs. Any further correction needs a separate scoped task
and a separately authorized new plan.

## Gates

| Gate | Result |
|---|---|
| `PREFLIGHT` | PASS |
| `ARTIFACT_SCOPE` | PASS for bundle identities and deployed hashes |
| `TERRAFORM_PLAN` | One complete plan successfully created and saved |
| `PLAN_SCOPE` | **FAIL — 4 changes rather than 2** |
| `RESOURCE_DRIFT` | PASS — 0 detected |
| `APPLY_READINESS` | **BLOCKED** |
| `PREVIOUS_PLAN` | BLOCKED — prior 19G plan not used |
| `TERRAFORM_APPLIES` | 0 |
| `AWS_RESOURCE_MUTATIONS` | 0 |
| `STATE_CONTENT_MUTATIONS` | 0 |
| `LIVE_INVOCATIONS / NEW_ORDERS / REDRIVES` | 0 / 0 / 0 |

## 19H Apply gate — not approved

The following record is **not an apply request and grants no authority**. The
current plan must not be applied because it violates the approved scope.

> **19H status: BLOCKED — DO NOT APPLY.** Candidate plan path:
> `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-worker-19g3.tfplan`,
> SHA-256 `8daf05702d4e0ff27bd6668582f5e39162d0ab660935d52fdf1145703a722752`,
> source commit `7ccc34c3da3fbe4a686dd34fca7d7d2439c480cb`. Actual scope is
> 0 Add / 4 Change / 0 Destroy and includes unexpected Analysis/Reader
> `filename` updates. This is outside approval. No approver signature can
> authorize applying this artifact under the current request.
>
> A future apply approval requires a new separately authorized task, a fresh
> preflight, and a newly reviewed plan that meets the exact approved scope.
> Approver: **NONE**. Apply authorization: **NOT GRANTED**.

**STOP. No automatic deployment.**
