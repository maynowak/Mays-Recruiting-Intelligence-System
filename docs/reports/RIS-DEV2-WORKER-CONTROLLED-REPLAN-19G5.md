# RIS-DEV2 Worker Controlled Replan — 19G5

**Result:** **Preflight PASS; exactly one full-refresh plan created; scope PASS; APPLY BLOCKED pending separate approval.**

**Plan source commit:** `8f610939dcc2fd7402430e2830a1fad095f6dd3a`
**Branch:** `feature/ris-analysis-integration-07`
**Plan SHA-256:** `d78c0fcfaee991c774895c583604f0ea270dee600f59af7e37c9cf1e804985c3`

## Decision and boundaries

One complete Terraform plan with normal refresh was created after all preflight
and artifact gates passed. Its exact scope is **0 Add / 2 Change / 0 Destroy**:
in-place Lambda code updates to Agent-Worker and Dispatch-Ingress only.
Analysis and Orders-Reader are no-op, including exact state `filename` values
and deployed package hashes. Resource drift detected by the plan: **0**.

The binary plan is for review only. **Do not apply it without separate explicit
approval.** Both previous plans (19G and 19G3) remain blocked and were not used.
No second plan was run. No state content or AWS resource was mutated.

## Preflight

- Local and remote HEAD matched baseline `8f610939dcc2fd7402430e2830a1fad095f6dd3a`
  on branch `feature/ris-analysis-integration-07` before planning.
- The sole worktree change was the pre-existing unstaged
  `docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json`. It was not
  read for content, edited, staged, stashed, or reset; it remains unstaged.
- STS: account `262370457690`, principal
  `arn:aws:iam::262370457690:user/devnemo`; region `eu-central-1`.
- Backend: bucket `ris-dev2-tf-state-dev`, key
  `env:/ris-dev2/dev/terraform.tfstate`, workspace `ris-dev2`, lock table
  `ris-dev2-tf-lock`.
- State before and after plan: serial **75**, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 VersionId
  `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ`, size 891,609 bytes. Version, size, and
  LastModified were unchanged after planning.
- Terraform `1.17.0`; state Terraform version `1.17.0`. Existing Ubuntu QA
  evidence was reused: run `46015361867` SUCCESS. Mays source pin remains
  `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`.
- `analysis_synthetic_mode=true` in the approved var file; State and live
  Analysis Lambda both still report `ANALYSIS_SYNTHETIC_MODE=true`.
- Read-only Lambda configuration and tag checks passed. All four deployed
  `CodeSha256` values matched State; all four functions were Active with
  successful last updates and RIS-DEV2 ownership tags. Analysis additionally
  retained `Purpose=internal-analysis`.
- The actual Terraform-evaluated Analysis filename was
  `C:/Users/DCI-Student/AppData/Local/Temp/opencode/ris-mo-addition-e2e/terraform/analysis-lambda.zip`;
  the actual Reader filename was
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-addition-e2e\lambda\dist\orders-reader.zip`.
  Both exactly matched their State values, including Reader backslashes.
- All local package hashes matched the 19G5 artifact gate. No ZIP was built or
  overwritten. Detailed preflight and four-Lambda matrix are in
  `docs/reports/evidence/19G5/`.

## Plan artifact and exact scope

- Binary plan, outside the repository:
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-worker-19g5.tfplan`
- SHA-256: `d78c0fcfaee991c774895c583604f0ea270dee600f59af7e37c9cf1e804985c3`
- Size: 252,144 bytes; Terraform `1.17.0`; created once with normal refresh,
  full resource scope, and regular backend locking. No `-target`,
  `-refresh=false`, `ignore_changes`, or State manipulation.
- Summary: 274 resource changes examined; **272 no-op**, 2 in-place updates,
  0 add, 0 destroy, 0 replace, 0 detected resource drift.

| Terraform address | Action | Changed attributes | Filename before → after | Source-code hash before → after |
|---|---|---|---|---|
| `module.lambda.aws_lambda_function.agent` | In-place update | `source_code_hash`, computed `last_modified` | `lambda.zip` → `lambda.zip` | `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` → `UHvBfbny7gky5C3gOaUIqz8B47srVRDqefLlT5WzpY0=` (artifact SHA `507bc17…`) |
| `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | In-place update | `source_code_hash`, computed `last_modified` | `./lambda.zip` → `./lambda.zip` | `jsUKYUCNKO+yuF/2yDsF3Q7mB1ubRgge8W1kl5PMY4M=` → `UHvBfbny7gky5C3gOaUIqz8B47srVRDqefLlT5WzpY0=` (artifact SHA `507bc17…`) |

Analysis remained no-op at filename
`C:/Users/DCI-Student/AppData/Local/Temp/opencode/ris-mo-addition-e2e/terraform/analysis-lambda.zip`
and source-code hash
`J2tORCAnIWfdMsWQ1tur7UAIckpwkeTYZQTVRE/iaxA=` (ZIP SHA
`276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10`).
Orders-Reader remained no-op at filename
`C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-addition-e2e\lambda\dist\orders-reader.zip`
and source-code hash `YQAE9urjUx5MhyNkOeSRvL8MEC6ikWH+8kfCcTyBrms=` (ZIP SHA
`610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b`).

The plan's encoded new Worker/Ingress source-code hash decodes to exactly
`507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
The existing deployed Worker/Ingress hash is different, which is the approved
code-only update. No other resource is planned to change.

## Apply gate — blocked pending explicit approval

This section is a review record, **not** authorization to apply.

> **19H status: PLAN_SCOPE PASS; APPLY NOT AUTHORIZED.** Review only the binary
> at `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-worker-19g5.tfplan`
> with SHA-256
> `d78c0fcfaee991c774895c583604f0ea270dee600f59af7e37c9cf1e804985c3`.
> Source commit: `8f610939dcc2fd7402430e2830a1fad095f6dd3a`. Scope: exactly the
> two Worker/Ingress code updates above; Analysis/Reader unchanged; zero drift.
> Apply authorization: **NOT GRANTED**. Approver: **NONE**. No automatic
> deployment.

Any later Apply needs a separate explicit approval after verifying the same
plan file, source commit, State identity, and resource scope. Do not re-plan as
a substitute for reviewing this plan.

## Final gates

| Gate | Result |
|---|---|
| `PREFLIGHT` | PASS |
| `ARTIFACT_IDENTITY` | PASS — all four target ZIP hashes and both preserved paths match |
| `TERRAFORM_PLAN` | PASS — exactly one complete normal-refresh plan |
| `PLAN_SCOPE` | PASS — 0 Add / 2 Change / 0 Destroy; only Worker and Ingress code |
| `ANALYSIS_FILENAME / HASH` | PASS — exact state filename and `276b4e44…` |
| `READER_FILENAME / HASH` | PASS — exact state filename and `610004f6…` |
| `RESOURCE_DRIFT` | PASS — 0 |
| `PREVIOUS_PLANS` | BLOCKED — 19G and 19G3 not used |
| `TERRAFORM_APPLIES` | 0 |
| `AWS_RESOURCE_MUTATIONS` | 0 |
| `STATE_CONTENT_MUTATIONS` | 0 |
| `APPLY_READINESS` | REVIEWABLE; approval still required |

**STOP at the Apply approval gate.**
