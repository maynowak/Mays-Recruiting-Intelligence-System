# RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2

**Status: `BLOCKED` (local integration implemented; required platform/baseline gates fail).**
No runtime, Mays source, or generated module was changed. No module upgrade,
deployment, Terraform plan/apply, live invocation, AWS mutation, redrive, or
recovery was performed.

## Identity and execution

| Item | Evidence |
|---|---|
| RIS baseline / branch | `253e929e635bc4b79fe25773dd09e3f68c329af5` / `feature/ris-analysis-integration-07` |
| Integrated generated-module source | `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; verified against builder pin, builder constant, generated manifest and clean detached test checkout |
| Legacy clone pin | `5cf50a0...`; distinct and not used as integrated builder identity |
| Upgrade candidate | `v0.6.0-rc.1` / `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`; candidate-only, unavailable as an exact local checkout, NOT_RUN |
| Platform | Windows `win32`, Python 3.14.10 |
| Worker bundle | `terraform/lambda.zip` SHA-256 `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`, matches supplied baseline |
| Generated Mays artifact | ZIP SHA-256 `aa70eaaa1cb6e01b972dba05893573559e8aa0d945eb5691ce31e079e2521c89`; source commit matches integrated pin |
| Result detail | [`RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json`](RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json) |
| Contract index | [`RIS-MAYS-ORDERS-CONTRACT-EVIDENCE-19F2.md`](RIS-MAYS-ORDERS-CONTRACT-EVIDENCE-19F2.md) |

## Unified `FULL` run

Each group runs in its own process. Counts below are group results, not additive
unique-test totals; overlapping groups are intentional. The Mays groups ran from
temporary detached Git clones at the verified SHA. The original ignored Mays clone
was clean after the run.

| Group | Status | Passed | Failed/errors | Skipped | Subtests | Duration / classification |
|---|---:|---:|---:|---:|---:|---|
| RIS Native | FAIL | 3,276 | 5 | 142 | 446 | about 2 minutes; baseline/platform failures detailed below |
| Mays Lambda | PASS | 240 | 0 | 0 | 0 | 0.07s |
| Mays Module Builder | FAIL | 86 | 14 | 0 | 6 | 9.74s; Windows path separator incompatibility |
| Mays Installer | FAIL | 69 | 11 | 1 | 0 | about 2 minutes; Windows missing `python3` and hard-coded Linux paths |
| Mays Seed Tools | PASS | 28 | 0 | 0 | 0 | 0.10s |
| Mays Cognito Backup | PASS | 2 | 0 | 0 | 0 | 0.03s |
| XRepo Contract | PASS | 133 | 0 | 0 | 4 | 0.77s |
| XRepo E2E | PASS | 39 | 0 | 0 | 0 | 0.78s |
| RIS Builder Contracts | PASS | 57 | 0 | 0 | 0 | 0.34s |
| Generated Module Artifact | PASS | 9 | 0 | 0 | 0 | 0.72s |

`FULL` is **BLOCKED**, not PASS, because required RIS Native, Mays Builder and
Mays Installer groups fail on this Windows run. The Mays original suites have not
been altered or skipped to manufacture a pass.

### Failure classification

- **RIS baseline (3):** three missing OpenAPI assertions in
  `tests/test_platform_openapi_contract.py` for documented Terraform routes,
  imperative-route classification, and reachable dispatcher branches.
- **RIS test-environment (1):** `test_composite_lifecycle.py::TestStateCommandBackend::test_discover_subprocess_env_keeps_path` fails because its read-only STS context test requires the `mayaws` profile, which is unavailable. Orchestrator child processes are isolated from host AWS profiles and credentials; this is not reported as a live PASS.
- **RIS historical artifact/baseline (1):** `test_analysis_fresh_plan_16c1.py::FreshPlan16C1Test::test_bundles_match_local_artifacts_when_present` verifies a historical bundle hash; current worker bundle independently matches the 19F supplied SHA.
- **Mays platform (14):** module-builder output-path assertions compare POSIX slash paths with Windows backslash paths. No source/test was changed; do not claim Linux success from Windows evidence. Re-run the unchanged original suite on its supported Linux platform.
- **Mays platform/environment (11):** installer tests invoke `python3` and use `/home/dci-student/...` paths, unavailable on Windows. Not a demonstrated module runtime defect and not a Linux PASS.
- **Unresolved candidate:** no clean exact RC4 checkout was available; candidate QA and `UPGRADE_GATE` remain BLOCKED/NOT_RUN.

## Profile and gate disposition

- `RIS_NATIVE`, `MAYS_MODULE`, `XREPO_CONTRACT`, `XREPO_E2E`, `MODULE_BUILD`,
  `UPGRADE_GATE`, `FULL`, `LIVE` are centralized in `scripts/unified_tests.py`.
- `LIVE` returns `BLOCKED / LOCKED_NOT_EXECUTED` and does not launch tests.
- `UPGRADE_GATE` requires candidate version selection plus exact clean candidate
  checkout; it cannot implicitly turn integrated-source QA into upgrade approval.
- Original Mays tests are not copied into RIS. Cross-repo-only `MO_ORDERS_SRC`
  is set only for XRepo jobs; native RIS and Mays namespaces remain separate.
- Existing CI workflows were reviewed but not modified: the current source
  checkout and platform-specific failing tests are not yet a portable, reliable
  required CI gate. No new pipeline architecture was added.

## Final gates

| Gate | Result |
|---|---|
| `UNIFIED_TESTSUITE` | BLOCKED |
| `MAYS_TEST_INTEGRATION` | PARTIAL |
| `MODULE_PROVENANCE` | VERIFIED (integrated artifact); candidate BLOCKED |
| `PROCESS_ISOLATION` | PASS |
| `CONTRACT_EVIDENCE_REUSE` | VERIFIED for listed module contracts; remaining RIS integration tests separate |
| `RIS_NATIVE_QA` | FAIL: 3,276 passed, 5 failed, 142 skipped, 446 subtests |
| `MAYS_MODULE_QA` | PARTIAL: Lambda 240 PASS; Builder 86/14 FAIL; Seed 28 PASS; Backup 2 PASS |
| `XREPO_QA` | PASS: contract 133 + 4 subtests; synthetic E2E 39 |
| `MODULE_BUILDER_QA` | PARTIAL / Windows FAIL: RIS builder 57 PASS, generated artifact 9 PASS, Mays source builder 86/14 FAIL |
| `INSTALLER_QA` | FAIL / Windows: 69 passed, 11 errors, 1 skipped |
| `WORKER_DEPLOYMENT_READINESS` | READY_FOR_PLAN baseline retained; this task did not authorize or run a plan |
| `MAYS_ORDERS_UPGRADE_READINESS` | BLOCKED: candidate not checked out/tested; required platform gates incomplete |
| AWS mutations / live invocations / redrives | 0 / 0 / 0 |
| Runtime source changes | 0 |

No follow-on 19G, Terraform, deployment, recovery, or Mays upgrade was started.
