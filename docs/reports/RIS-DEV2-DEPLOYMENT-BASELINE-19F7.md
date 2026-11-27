# RIS-DEV2-DEPLOYMENT-BASELINE-19F7

**Status:** LOCAL CANDIDATE PREPARED — STOP AT EXPLICIT APPROVAL GATE  
**Branch:** `feature/ris-analysis-integration-07`  
**Baseline HEAD:** `95c9a90a9c237ecdfe3bb0f7ea723dc09cee7597`  
**QA workflow commit:** `d0a5bdecddbcc35ded6f62ff51bd5dc4f1bc76e1`  
**Evidence/report commits:** `4bf8014`, `c1a45c6` (see final commit section).

## Phase 1 — Baseline consolidation

- Current Mays module source verified as
  `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` in both builder pin and generated
  module manifest. Existing module remains unchanged.
- `orderDescription` is already implemented in the integrated Mays module;
  19F6 verified focused original tests and current RIS cross-repository tests.
  No description-specific module upgrade is required.
- Historical worker digest: `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`.
  Review-only worker candidate: `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
  No worker deployment pin changed.
- Historical Canary-Recovery/Redrive is not on the release-critical path. 19G
  is a separate read-only deployment-plan request; historical recovery remains
  unexecuted, separately authorized/optional, and is not a prerequisite for
  bundle QA or deployment planning.
- Prior evidence: `RIS-MAYS-ORDERS-COMPATIBILITY-RESOLUTION-19F4.md`,
  `RIS-MAYS-ORDERS-MAIN-UPGRADE-19F5.md`, and
  `RIS-MAYS-ORDERS-DESCRIPTION-PATCH-19F6.md`.

## Phase 2 — Unified QA

The integrated-source Ubuntu reference workflow completed successfully on
`d0a5bdecddbcc35ded6f62ff51bd5dc4f1bc76e1` in GitHub Actions run
`45993779301` (Python 3.14.10, Linux). Mays provenance was `VERIFIED` against
the exact integrated SHA. All six required profiles passed:

| Profile | Result | Key counts |
|---|---|---|
| `RIS_NATIVE` | PASS | 3,291 passed; 133 skipped; 450 subtests; 0 failures/collection errors |
| `MAYS_MODULE` | PASS | Lambda 240; builder 100 + 6 subtests; installer 81; seed 28; Cognito backup 2 |
| `MODULE_BUILD` | PASS | Builder 100 + 6 subtests; installer 81; RIS builder contract 57; generated artifact 9 |
| `XREPO_CONTRACT` | PASS | 133 passed + 4 subtests |
| `XREPO_E2E` | PASS | 39 passed |
| `FULL` | PASS | All above groups; per-group counts are intentionally not summed across overlapping profiles |

Ubuntu run artifacts and dependency freeze are committed under
`docs/reports/evidence/19F7/ubuntu/`. The worker ZIP built in CI is the
candidate `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`;
the workflow's historical-bundle comparison reports mismatch with the retired
`78eb6e...` worker pin, as expected for a candidate review—not a build failure.

Windows results are separately retained under
`docs/reports/evidence/19F7/windows/`: `RIS_NATIVE` PASS (3,282/142 skipped),
both XRepo profiles PASS (133 + 4 subtests; 39), while `MAYS_MODULE`,
`MODULE_BUILD`, and consequently Windows `FULL` are BLOCKED. Mays original
Lambda (240), seed (28), Cognito backup (2), RIS builder contract (57), and
generated artifact (9) passed. Mays Builder had 86 passed/14 platform failures
(POSIX path assumptions); Installer had 69 passed/11 `FileNotFoundError`
errors/1 skip (`python3` and `/home/...` assumptions). No tests were skipped to
manufacture a pass and no source/test was altered. Ubuntu is the successful
reference; Windows failures remain visible and environment-specific.

## Phase 3 — Worker artifact and wiring review

- Rebuilt `python lambda/build_zip.py --bundle all` twice locally. Both builds
  were byte-reproducible. Agent SHA-256 is
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`, exactly
  the 19F4 candidate. Analysis remains
  `370890d459488304481d99255cfa6a2891b5f19a8c5df2723556905195c7c621`; Reader
  remains `bea4c3e59666bed8ad071ad4e405bcdfd57dafdac68096ce648667f0effb1b41`.
- Claim-fix evidence: `tests/test_worker_pipeline.py`, especially
  `test_existing_queued_item_claim_executes_without_retry_claim`,
  `test_lost_initial_claim_suppresses_execution`, and
  `test_preexisting_running_item_remains_suppressed`. Ubuntu `RIS_NATIVE`/`FULL`
  passed these tests. The focused 19F worker regression and local RIS–Mays
  handoff evidence are additionally documented in
  `RIS-DEV2-WORKER-QA-COMPLETION-19F.md`.
- `terraform/main.tf` and `terraform/modules/agent_transport/lambda.tf` wire the
  same `terraform/lambda.zip` to the Agent worker and Dispatch-Ingress
  (`dispatch_ingress.handler`). `terraform/modules/analysis_runtime` receives
  its distinct analysis ZIP path. Thus the candidate scope is the shared Agent
  worker + Dispatch-Ingress artifact only; Analysis and Reader hashes remain
  unchanged. No pin was updated.

## Phase 4 — Local Terraform validation

Root Terraform `init -backend=false`, `validate`, and `fmt -check -recursive`
completed successfully with an external `TF_DATA_DIR`, empty AWS config and
credential files, and EC2 metadata disabled. Existing provider deprecation
warnings are non-blocking. No backend/state access, AWS credentials, plan, or
apply was used. The generated-module fmt/init/validate checks also passed in
the Ubuntu QA job.

## Phase 5 — 19G follow-up request (prepared, not executed)

Proposed next authorized task: `RIS-DEV2-WORKER-DEPLOYMENT-PLAN-19G`.

- Target identity: AWS account `262370457690`, region `eu-central-1`, workspace
  `RIS-DEV2`.
- Last known state serial: `75`. The later plan operator must live-verify
  account/region/workspace, backend, state lineage and serial immediately
  before planning; serial 75 is not asserted as current.
- Candidate artifact: exact Agent bundle SHA-256
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
- Expected plan scope: in-place code/hash update of the Agent worker and
  Dispatch-Ingress that consume the shared bundle. Analysis and Reader must
  remain unchanged. No create/delete/replacement, unrelated drift remediation,
  Mays module/source/pin change, IAM broadening, queue/DLQ operation, or other
  resource change is within scope.
- Stop if identity/state/serial differs unexpectedly, drift is unexplained,
  the bundle hash differs, any replacement or out-of-scope resource change is
  proposed, or `MODE` is not `true` / live execution is not disabled.
- A new explicit approval is required both to update the worker pin and to
  create a Terraform plan. Plan approval is not apply approval; apply requires
  a separate explicit authorization. No plan has been run for 19G.
- Rollback reference: historical worker digest
  `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`,
  with prior worker configuration/source as recorded in
  `RIS-DEV2-WORKER-QA-COMPLETION-19F.md`. Rollback itself requires a distinct
  authorization and a fresh reviewed plan; do not auto-rollback.

## Phase 6 — Synthetic Canary preparation (not live-ready)

Existing local harness: `tests/test_agent_order_dispatch_e2e.py` exercises a
synthetic Order, dispatch, WorkItem, queued initial claim, Agent execution,
signed `ORDER_RESULT`, result consumer, `processing.status=COMPLETED`, and
Owner-GET `200`. It passes in Ubuntu `XREPO_E2E`/`FULL`. The request includes
`orderDescription`, and the created row preserves it; however the final GET
assertions do **not** assert the returned `orderDescription` value. Therefore
`ORDER_DESCRIPTION=VERIFIED` is verified for integrated-source support and
create/storage, but the requested end-to-end GET readback remains an OPEN
integration requirement. Do not call the live Canary ready until a harness
assertion/readback contract is reviewed and passes.

Before any separately authorized canary, require an isolated synthetic owner,
API profile and agent entitlement bound to the intended tenant/capability;
confirm owner/profile binding, active entitlement, dispatch/result queue
permissions, result HMAC secret access, and the required analysis endpoint
configuration. No grants are made here. Use a unique synthetic order only
after separate approval. Do not inspect/change historical orders, WorkItems,
or DLQs; no recovery or redrive is part of this canary.

## Final gates and action boundary

| Gate | 19F7 result |
|---|---|
| `ORDER_DESCRIPTION` | INTEGRATED / CREATE-STORAGE VERIFIED; final GET value readback OPEN |
| `MAYS_MODULE_UPGRADE_REQUIRED_FOR_DESCRIPTION` | NO |
| `RIS_NATIVE_QA` | PASS (Ubuntu reference; Windows also PASS) |
| `MAYS_ORIGINAL_QA` | PASS (Ubuntu); Windows platform failures separately recorded |
| `UNIFIED_FULL_QA` | PASS (Ubuntu); Windows FULL BLOCKED by original platform assumptions |
| `XREPO_QA` | PASS (Ubuntu and Windows) |
| `BUNDLE_PROVENANCE` | VERIFIED; source and workflow evidence retained |
| `BUNDLE_REPRODUCIBILITY` | PASS; two local builds and Ubuntu two-build check match candidate hash |
| `TERRAFORM_VALIDATE` | PASS; backend disabled, credentials absent |
| `WORKER_PIN_APPROVAL_REQUIRED` | YES — no pin update performed |
| `DEPLOYMENT_READINESS` | CANDIDATE READY FOR SEPARATELY APPROVED 19G PLAN ONLY; not apply-ready |
| `LIVE_CANARY_READINESS` | OPEN / NOT READY — explicit description GET readback missing; entitlements must be confirmed |
| `AWS_MUTATIONS` | 0 |
| `TERRAFORM_PLANS` | 0 |
| `TERRAFORM_APPLIES` | 0 |
| New order / recovery / redrive / Main merge | 0 / 0 / 0 / 0 |

**STOP at the approval gate.** No automatic continuation to AWS, Terraform
planning/apply, pin change, live canary, recovery/redrive, or Main merge.

## Commits

- `4bf8014` — baseline report and Auditlog Phase 1, pushed.
- `d0a5bde` — integrated-only Ubuntu QA workflow, pushed; run `45993779301`
  succeeded.
- `c1a45c6` — machine-readable Ubuntu and Windows QA evidence, pushed.
- Final report/Auditlog completion commit: recorded after this report update.
