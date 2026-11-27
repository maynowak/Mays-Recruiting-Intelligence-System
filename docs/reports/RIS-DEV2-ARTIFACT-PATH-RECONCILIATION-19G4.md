# RIS-DEV2 Artifact Path Reconciliation — 19G4

**Result:** **Filename root cause confirmed; preserved paths and ZIP identities restored locally; local Terraform validation PASS; full Ubuntu QA PASS; STOP before 19G5 plan approval.**

**Branch / final implementation HEAD:** `feature/ris-analysis-integration-07` / `41ebddae2c2aee1ff9677d4ec281dc4ff18e1d72`

## Scope and safety

This task only reconciled the Analysis and Orders-Reader Terraform `filename`
inputs. No ZIP was rebuilt or edited for deployment; the preserved archives
were copied byte-for-byte to their historical output locations. No runtime
source, worker or Mays pin, module installation, AWS access, Terraform plan,
apply, or state operation was performed. `MODE=true` was not changed.

Both prior plans remain blocked: the 19G plan and 19G3 plan
(`8daf05702d4e0ff27bd6668582f5e39162d0ab660935d52fdf1145703a722752`). The
19G3 saved plan was read locally only. Its digest was verified before
inspection. Its sole relevant unexpected updates were Analysis and Reader:
`filename` and computed `last_modified` changed, while each `source_code_hash`
was identical before and after. Agent-Worker and Dispatch-Ingress filenames
were already unchanged.

The 19G2 override file had replaced the old Analysis/Reader artifact inputs
with `terraform/artifacts/...` paths. That is the demonstrated root cause; it
was path wiring, not package bytes or runtime code. See
[`evidence/19G4/filename-matrix.json`](evidence/19G4/filename-matrix.json) for
all four resources, both 19G3 filename values, source hashes, current resolved
files, and local SHA-256s.

## Path and artifact reconciliation

The RIS-DEV2 overrides now point to the historical build outputs:

| Lambda | Historical configured input | Historical state filename on this Windows checkout | Local ZIP SHA-256 |
|---|---|---|---|
| Agent-Worker | `lambda.zip` | `lambda.zip` | `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d` |
| Dispatch-Ingress | `./lambda.zip` | `./lambda.zip` | `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d` |
| Analysis | `analysis-lambda.zip` | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/ris-mo-addition-e2e/terraform/analysis-lambda.zip` | `276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10` |
| Orders-Reader | `../lambda/dist/orders-reader.zip` | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-addition-e2e\lambda\dist\orders-reader.zip` | `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b` |

`terraform/main.tf` normalizes relative overrides against `path.root`, while
preserving absolute inputs. The reader additionally preserves the historical
Windows backslash form when running on Windows. On this checkout, the
configured Analysis/Reader filenames therefore resolve to the exact
state-recorded path strings and existing local files. Other platforms use
their native absolute paths; the portable expression and canonical builder
were not replaced. Any future plan must run its normal preflight on the
original Windows checkout/path identity; this task did not test or authorize
a plan on another host.

`scripts/stage_preserved_ris_dev2_artifact_paths.py` first verifies the source
archive hashes and expected current destinations, then copies bytes without
repacking. It is safe to re-run when the destinations already contain the
preserved bytes. It verified:

- `terraform/analysis-lambda.zip` = preserved Analysis archive, SHA-256
  `276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10`.
- `lambda/dist/orders-reader.zip` = preserved Reader archive, SHA-256
  `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b`.
- `terraform/lambda.zip` remained SHA-256
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.

The Ubuntu reproducibility check separately rebuilt the canonical bundles in
two clean clones and got identical hashes for both runs. Its canonical
Analysis/Reader hashes (`370890d4…` / `bea4c3e5…`) differ from the deployed
preserved archives. Those QA builds were disposable and do not replace the
preserved deployment artifacts. The canonical builder and runtime source were
not modified.

## Local verification

- Focused path, artifact, and Analysis wiring regressions: **29 passed**.
- Unified `RIS_NATIVE` on Windows with isolated QA dependencies and exact Mays
  source: **3,284 passed, 0 failed, 142 skipped, 450 subtests passed**.
- `terraform fmt -check`: PASS.
- `terraform init -backend=false -input=false -lockfile=readonly`: PASS with
  Terraform `1.17.0`, AWS provider `6.67.0`, time provider `0.14.2`.
- `terraform validate`: PASS, with existing AWS provider DynamoDB
  `hash_key`/`range_key` deprecation warnings only.
- Dependencies requested during QA were installed only in
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-19g4-qa-venv`; no
  project dependency file or global Python installation was changed.

The full original Mays tests are POSIX-specific and do not all run on this
Windows host. Their authoritative required run was the Ubuntu workflow below.

## Ubuntu reference QA

The established `.github/workflows/mays-compatibility-qa.yml` ran on Ubuntu
against commit `838e5be979ca6e595a449142830afbbb6f39fe8b`, Python `3.14.10`,
Terraform `1.17.0`, and exact Mays source
`db4f9e79980443de1cd3d5b688a33c0cf0eb771f`.

**Run 46015361867: SUCCESS on final HEAD `41ebdda…`.** The full profile passed every group, including
RIS_NATIVE (3,293), original Mays Lambda tests (240), original Mays module
builder (100), original Mays installer (81), seed tools (28), Cognito backup
(2), XRepo contract (133), XRepo E2E (39), builder contracts (57), and generated
module checks (9). Bundle reproducibility passed in two independent clean
clones. Raw JSON results, dependency freeze, and reproducibility evidence are
under [`evidence/19G4/ubuntu/`](evidence/19G4/ubuntu/).

The first CI attempt used an older static assertion for the Analysis input and
failed on that stale expectation. The regression was updated to assert the
normalized local wiring and distinguish the preserved Analysis ZIP from the
canonical review-build ZIP. A final workflow run after all implementation
commits passed. Two initial workflow attempts were consequently failures;
neither had AWS credentials or ran a Terraform plan.

## 19G5 request template — not plan authorization

> **Proposed follow-up:** after separate explicit approval, perform a fresh
> read-only preflight on the original Windows checkout/path identity and
> create exactly one complete normal-refresh RIS-DEV2 Terraform plan. Expected
> scope is `0 Add / 2 Change / 0 Destroy`, exclusively code updates for
> `module.lambda.aws_lambda_function.agent` and
> `module.agent_transport[0].aws_lambda_function.dispatch_ingress`, both using
> worker SHA `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
> Analysis must retain filename identity and SHA
> `276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10`;
> Orders-Reader must retain filename identity and SHA
> `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b`. Stop
> if any other resource changes or drift appears. No plan is authorized by
> this template; 19G and 19G3 plans remain blocked. Apply is not authorized.

## Final gates

| Gate | Result |
|---|---|
| `FILENAME_ROOT_CAUSE` | PASS — 19G2 Analysis/Reader override paths caused the extra filename updates |
| `ANALYSIS_FILENAME_PRESERVED` | PASS locally on the original Windows checkout |
| `READER_FILENAME_PRESERVED` | PASS locally on the original Windows checkout |
| `ANALYSIS_ARTIFACT_HASH_PRESERVED` | PASS — `276b4e44…` |
| `READER_ARTIFACT_HASH_PRESERVED` | PASS — `610004f6…` |
| `WORKER_ARTIFACT_UNCHANGED` | PASS — `507bc17…` |
| `TERRAFORM_LOCAL_VALIDATE` | PASS |
| `UNIFIED_FULL_QA` | PASS — Ubuntu run `46014102840` |
| `REPLAN_READINESS` | READY FOR SEPARATE EXPLICIT APPROVAL; no plan created |
| `PREVIOUS_PLANS` | BLOCKED — 19G and 19G3 |
| `AWS_MUTATIONS / TERRAFORM_PLANS / TERRAFORM_APPLIES / STATE_MUTATIONS` | `0 / 0 / 0 / 0` |

**STOP at the 19G5 replan-approval gate.**
