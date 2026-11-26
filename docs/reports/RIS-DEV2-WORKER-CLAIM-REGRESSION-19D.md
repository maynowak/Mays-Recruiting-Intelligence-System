# RIS-DEV2-WORKER-CLAIM-REGRESSION-19D

**Datum:** 2026-11-26

**Branch:** `feature/ris-analysis-integration-07`

**Execution:** local tests/build only. AWS mutation, live invocation, Terraform plan/apply, recovery and Mays-Orders upgrade are prohibited and were not performed.

## Final gates

| Gate | Status | Evidence / limitation |
|---|---|---|
| `ROOT_CAUSE` | `VERIFIED` | 19B deployed artifact + exact runtime trace + WorkItem state |
| `LOCAL_FIX` | `VERIFIED` | c6e996a separates successful initial claim from FAILED-only retry claim |
| `REGRESSION` | `PASS` for worker/agent/result scope | Focused, relevant and broad filtered local test results below; the unfiltered repository suite is not clean/collectable in this environment |
| `LOCAL_E2E` | `PASS` | Local synthetic Order→dispatch→worker→result consumer round-trip with Mays-Orders source fixture; 22 passed, no real AWS endpoints |
| `BUNDLE_BUILD` | `PASS` | Deterministic 115-file agent bundle, rebuilt twice with identical SHA-256 |
| `DEPLOYMENT_READINESS` | `READY_FOR_PLAN` (candidate only) | Static wiring identifies two consumers of shared artifact. No plan was run; an independently approved future deployment task must revalidate baseline and exact plan |
| `LIVE_RECOVERY_READINESS` | `BLOCKED` / `RECOVERY_PATH=NOT_AVAILABLE` | No safe RUNNING recovery interface; requires separate 19E design/review |
| `MAYS_ORDERS_UPGRADE` | `NOT_AUTHORIZED` | No module change/install/upgrade |
| `AWS_MUTATIONS` | `0` | Read-only work in 19B preceded this task; no writes in this task |
| `LIVE_INVOCATIONS` | `0` | No Lambda invokes or live test endpoint calls |
| `REDRIVES` | `0` | The earlier one-time redrive remains consumed; not repeated |

## 1. Regression matrix R01–R20

| ID | Result | Local evidence |
|---|---|---|
| R01 QUEUED initial claim executes once | PASS | New pre-existing QUEUED regression test; real pipeline and registry, one attempt, one handler call |
| R02 No retry claim after initial claim | PASS | New test asserts only the QUEUED conditional update; RED previously observed extra FAILED condition |
| R03 Lost initial claim suppresses duplicate execution | PASS | New competing-claim table seam atomically makes competing claim win; loser makes zero agent calls |
| R04 Existing RUNNING stays suppressed | PASS | New test checks no re-execution and no status reset |
| R05 FAILED retry allowed | PASS | Existing `test_retry_after_failure_is_new_attempt`; failure then attempt 2 succeeds, handler called exactly twice total |
| R06 FAILED retry not allowed | NOT_APPLICABLE as a distinct policy | Current contract has no separate attempt-eligibility policy beyond status/attempt CAS and SQS `maxReceiveCount`; conditional claim loss is tested and suppresses execution |
| R07 Competing FAILED retries | PASS | New two-thread CAS test produces exactly one successful `_start_retry_attempt`, attempt becomes 2 |
| R08 Terminal item | PASS | Existing DEAD_LETTER/COMPLETED duplicate tests; no second execution |
| R09 Agent resolution failure | PASS | Existing no-eligible-agent test; no WorkItem registration/execution |
| R10 Agent success | PASS | Existing worker happy path and new pre-existing QUEUED case |
| R11 Agent failure | PASS | Existing permanent and transient failure/retry contract tests |
| R12 Analysis invocation/result contract | PASS locally | `test_analysis_runner_pipeline.py`, remote adapter tests, plus local bridge suite; no production invocation |
| R13 Serialization/HMAC | PASS locally | Result transport signature/envelope tests and local consumer verification |
| R14 Result publication | PASS locally | Worker result sender tests and local SQS/consumer bridge |
| R15 Publication failure semantics | PASS locally | Existing sender-failure/retry-marker assertions |
| R16 Consumer/Order lifecycle | PASS locally | Mays-Orders consumer source fixture; 22 bridge/contract tests passed |
| R17 Tenant/Owner isolation | PASS | Existing analysis cross-tenant and partner/security/result-reader tests in focused/broad run |
| R18 MODE unchanged | PASS | No runtime env changes; existing synthetic-mode/profile contract tests pass |
| R19 Shared worker agent types | PASS | Ecosystem/ATS/analysis/worker tests; common `process_record` remains shared |
| R20 Existing synthetic RUNNING not reset/re-run | PASS | New test verifies duplicate suppression and unchanged RUNNING state |

NOT_APPLICABLE is limited to a separate FAILED-attempt eligibility policy that does not exist in the current contract. It is not a skipped test for the claim control-flow fix.

## 2. Test execution

### RED → GREEN

- Before source fix: focused regression **1 failed**. Observed update guards were QUEUED claim then FAILED retry claim; agent call list remained empty.
- After fix: `tests/test_worker_pipeline.py` **25 passed**.

### Focused worker/analysis/security/transport regression

`test_worker_pipeline.py`, `test_worker_entitlement_recheck.py`, `test_dispatch_ingress_lambda.py`, `test_analysis_runner_pipeline.py`, `test_analysis_ecosystem_wiring.py`, `test_analysis_runner.py`, `test_remote_agent.py`, `test_order_transport_contract.py`, `test_lambda_bridge_e2e.py`, `test_mo_contract_compat.py`, `test_ats_domain_agent.py`, `test_api_profile_propagation.py`, `test_partner_security_boundary.py`, `test_analysis_synthetic_profile.py`, `test_agent_order_dispatch_e2e.py`:

**257 passed, 22 skipped, 6 subtests passed.** Optional Mays-Orders source-dependent tests were then rerun with the available local clone fixture configured for that process only.

### Local cross-repository E2E

`test_lambda_bridge_e2e.py`, `test_agent_order_dispatch_e2e.py`, `test_mo_contract_compat.py`, with `MO_ORDERS_SRC` set only for the test process to the local clone's `lambda/src`:

**22 passed.** This is a synthetic local/mock round-trip; it is not a live AWS or production E2E.

### Bundle/package-focused suite

`test_lambda_packaging.py`, `test_ats_built_bundle.py`, worker/analysis pipeline, remote agent, lambda bridge, transport and Mays contract suites:

**119 passed, 16 skipped.**

### Broad repository regression

After the current-worker bundle pin was updated, broad local run excluding six known environment/pre-existing suites:

**3,077 passed, 169 skipped, 446 subtests passed, 1 existing timestamp deprecation warning.** The excluded files were `test_durable_deletion_ledger.py`, `test_http_e2e_integration.py`, `test_analysis_fresh_plan_16c1.py`, `test_composite_lifecycle.py`, `test_consent_special_categories.py`, and `test_platform_openapi_contract.py`.

Unfiltered `pytest tests/ -q` cannot collect in this environment: `moto` is missing (`mock_aws` is `None`) and `requests` is not installed. An earlier collection-unblocked run showed additional unrelated baseline/environment failures: stale historical bundle pin in `test_analysis_fresh_plan_16c1`, missing `mayaws` profile, NameErrors in `test_consent_special_categories`, and an undocumented API route in `test_platform_openapi_contract`. These are outside this worker-fix scope and were not changed. No dependency was installed and no unrelated test was altered or weakened.

`python -m compileall -q agents lambda tests/test_worker_pipeline.py`: PASS.

## 3. Local end-to-end and contract boundary

The local bridge tests exercise synthetic Order/dispatch input, RIS dispatch ingress, the common worker, agent execution, result envelope/signature, Mays-Orders result consumer and owner read-back using local test doubles plus the available Mays-Orders source. No real endpoint, AWS SDK network call, credential, or deployed environment was used. Cross-tenant and owner isolation tests are separate assertions in the focused suites.

The test harness does not demonstrate a live recovery of the historic Canary. It deliberately does not load or mutate the old WorkItem.

## 4. Bundle and build provenance

| Property | Value |
|---|---|
| Baseline deployed Fix-16B worker ZIP SHA-256 | `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383` (verified deployed artifact in 19B) |
| New local agent bundle | `terraform/lambda.zip`; 115 Python entries; 354,138 bytes |
| New local SHA-256 | `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7` |
| Lambda CodeSha256 form | `eOtu2u0ZAm1BSaenPg7yI3jnP+Pv92G59Wsx/lS1G/c=` |
| Builder | `python lambda/build_zip.py --bundle agent` |
| Build source commit | `c6e996a8f22afe9b248094cf278a0c2f31846782` (worker fix commit) |
| Reproducibility | Two consecutive builds yielded identical 354,138-byte output and identical hash |
| Contents | Shared agent/dispatch bundle contains `handler.py`, `dispatch_ingress.py`, `agents/runtime/pipeline.py`, remote adapter and agent packages. It does not contain `analysis_runner.py`; Analysis uses its separate artifact. |

### Deployment wiring / minimal later scope

- `module.lambda.aws_lambda_function.agent` uses the shared agent ZIP and handler `handler.lambda_handler`.
- `module.agent_transport[0].aws_lambda_function.dispatch_ingress` also uses that same ZIP and handler `dispatch_ingress.handler`. Its code path does not invoke the worker pipeline, but Terraform's current shared artifact path/hash means a later bundle update also changes this function's code hash.
- `module.analysis_runtime.aws_lambda_function.analysis` uses a separate Analysis ZIP and is **not** changed by this fix. The Mays-Orders handler/worker and Orders reader use separate artifacts and are not in scope.
- Minimal future deployment candidate: in-place source-code updates to Agent worker and Dispatch ingress only, subject to a newly authorized Terraform plan proving exactly that scope. No plan was run here. Do not upload a ZIP or deploy automatically.

The test pin in `tests/test_analysis_ecosystem_wiring.py` now distinguishes this reviewed local candidate from the deployed Fix-16B baseline; it does not claim the new artifact is deployed.

## 5. Recovery analysis and next assignment

**`RECOVERY_PATH=NOT_AVAILABLE`.** Local source has no supported lease expiry, claim owner, stale-RUNNING takeover, or RUNNING-to-next-attempt recovery interface. Retry starts only from FAILED with CAS. Replaying or resetting the historic item would risk duplicate Analysis/ORDER_RESULT and is explicitly outside the fix.

Recommended next task: **`RIS-DEV2-WORKITEM-RECOVERY-DESIGN-19E`**, design/review only. Define operator authorization, stale ownership proof, a fenced/CAS recovery transition, attempt and idempotency semantics, single-execution guarantees, ORDER_RESULT dedupe, audit evidence and rollback/abort criteria. Any live recovery must be a later separately approved task naming the exact Canary objects and execution modes.

## 6. Commit and final safety evidence

Feature branch: `feature/ris-analysis-integration-07`.

Commit order:

1. `d7dfe455a5715e47d8acf34458c362c79af05d76` — 19A docs, prior checkpoint.
2. `3bddf6dafaae4551fbfffcffad0ac622775c8d35` — 19B evidence docs/audit.
3. `c6e996a8f22afe9b248094cf278a0c2f31846782` — fix and lifecycle regression tests.
4. `46e98c30a07eca53d91646429e5fc78e36fdc02f` — local worker bundle pin.

All are pushed on the feature branch. Documentation changes in this report/audit append remain local until the final documentation commit. No source changes exist outside the files listed in 19C. No commit was made to main; no Mays-Orders repository change occurred.
