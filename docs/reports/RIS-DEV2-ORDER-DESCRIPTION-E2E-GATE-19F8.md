# RIS-DEV2-ORDER-DESCRIPTION-E2E-GATE-19F8

**Outcome:** OrderDescription end-to-end readback gap closed in the existing
synthetic test. Local final QA passed; deployment remains stopped at the
separate approval gate. No runtime source, deployment pin, Mays module, or
infrastructure configuration was changed.

## Identity and change boundary

- Branch: `feature/ris-analysis-integration-07`.
- Starting HEAD: `f7ff573cd3049ac6fbb45575be0f27b66a62a400` (clean and matched
  origin at preflight).
- Test-only RIS commit used for final Ubuntu QA / proposed 19G source identity:
  `fba2721cb4f051d7a049c853a962acf8b34ae185`.
- Mays module source: `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; clean detached
  local checkout and CI provenance both verified.
- Only test change: `tests/test_agent_order_dispatch_e2e.py`. No runtime source
  changes, Mays source changes, pin changes, installation, Terraform changes,
  live call, new order, AWS mutation, plan/apply, recovery, redrive, or Main
  merge.
- Test change commit: `fba2721`; evidence commit: `a15cea6`; documentation and
  Auditlog commit is recorded in branch history after this report.

## Step 1 — OrderDescription roundtrip

Extended existing `test_agent_order_round_trip_and_authorized_read_back`; did
not add a new harness. It submits the existing opaque description and now
asserts exact equality at these boundaries:

1. Order Create responds `201` and returns the expected `orderDescription`.
2. The created in-memory persistence row stores the exact same value.
3. Existing queued initial-claim / agent execution still completes.
4. The signed `ORDER_RESULT` is accepted by the result consumer.
5. Persisted `processing.status` is `COMPLETED`.
6. Owner GET responds `200` and returns the exact original description,
   unchanged.

The contract follows Mays' original `lambda/tests/test_order_description.py`:
`orderDescription` is optional opaque text, stored verbatim and publicly
projected; internal `agentOrder` remains private. The exact integrated Mays
source was used, without installing or changing the module. All new assertions
passed; no runtime discrepancy was exposed, so no runtime fix was attempted.

## Step 2 — Regression results

| Gate | Result | Evidence |
|---|---|---|
| Mays original OrderDescription tests | PASS — 15 passed | `evidence/19F8/mays-order-description-original-windows.json`; exact source SHA verified |
| RIS–Mays `XREPO_CONTRACT` | PASS — 133 passed + 4 subtests | Windows local JSON and Ubuntu CI JSON |
| RIS–Mays `XREPO_E2E` | PASS — 39 passed | Includes the extended roundtrip; Windows local JSON and Ubuntu CI JSON |
| Ubuntu Unified `FULL` | PASS | Run `45996079592`, all groups passed, zero failures/collection errors |
| Ubuntu Mays provenance | VERIFIED | Exact `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` |
| Worker bundle | PASS / unchanged candidate | Built locally; CI built twice; exact SHA below |

Ubuntu run `45996079592` executed on the test commit above (Python 3.14.10,
Linux). Per-group `FULL` results: RIS Native 3,291 passed / 133 skipped / 450
subtests; Mays Lambda 240; Mays Builder 100 + 6 subtests; Mays Installer 81;
Mays Seed 28; Cognito backup 2; XRepo Contract 133 + 4 subtests; XRepo E2E 39;
RIS Builder contract 57; generated-module artifact 9. No failures or collection
errors. Machine-readable run results and dependency freeze are in
`docs/reports/evidence/19F8/ubuntu/`.

The 15 original Mays tests were run directly against a clean detached checkout
at the exact integrated commit; all passed. Local Windows XRepo profiles also
passed and their JSON results are retained under `evidence/19F8/`.

## Worker artifact provenance

- Historical worker pin: `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`.
- New review candidate (not pinned):
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
- Local `python lambda/build_zip.py --bundle agent` produced the candidate
  SHA-256 exactly. Ubuntu CI independently built all bundles twice; both Agent
  hashes matched the candidate. CI provenance and reproducibility record are
  retained in `evidence/19F8/ubuntu/`.
- No worker pin update. Analysis and Reader bundle identities were not changed
  by this test-only task.

## Step 3 — Prepared follow-up 19G (no plan)

Suggested next ticket: `RIS-DEV2-WORKER-DEPLOYMENT-PLAN-19G`, requiring fresh,
explicit authorization before any state/backend access or Terraform plan.

- Exact source identity for a future plan review: RIS test commit
  `fba2721cb4f051d7a049c853a962acf8b34ae185`; this 19F8 delta is test-only.
  Re-verify the branch/worktree and candidate artifact before acting.
- Worker pin transition under review only: historical
  `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7` →
  candidate `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
  Pin update requires its own explicit approval and is not included here.
- Target: account `262370457690`, region `eu-central-1`, workspace `RIS-DEV2`.
- Last known Terraform state serial: `75`, historical only. Verify live account,
  workspace, backend, state lineage and current serial immediately before any
  separately approved plan; stop on mismatch.
- Expected minimal scope: in-place artifact/code-hash update for the Agent
  worker and Dispatch-Ingress that share the agent bundle. Analysis and Reader
  must remain unchanged. No create/delete/replacement, unrelated drift
  remediation, Mays module/source changes, IAM broadening, queue/DLQ changes,
  or any other resource modifications are acceptable.
- Drift/STOP conditions: unexpected identity, backend, workspace, lineage or
  serial; unexplained drift; bundle hash mismatch; any replacement or
  out-of-scope proposed change; `MODE` not `true` or live mode not disabled.
  Do not auto-correct drift. No plan or apply is authorized by 19F8.
- Rollback reference: historical worker pin
  `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7` and
  prior worker configuration documented in
  `RIS-DEV2-WORKER-QA-COMPLETION-19F.md`. Rollback requires its own approval
  and a fresh, separately reviewed plan; no rollback is authorized here.

## Final gates

| Gate | Result |
|---|---|
| `ORDER_DESCRIPTION_CREATE` | PASS — 201 and exact response value |
| `ORDER_DESCRIPTION_PERSISTENCE` | PASS — exact verbatim value in created row |
| `ORDER_DESCRIPTION_OWNER_GET` | PASS — owner GET 200 and exact value |
| `LOCAL_E2E` | PASS — existing integrated synthetic roundtrip |
| `UNIFIED_FULL_QA` | PASS — Ubuntu run `45996079592` |
| `WORKER_BUNDLE_PROVENANCE` | PASS — two CI builds and local build match candidate SHA |
| `DEPLOYMENT_READINESS` | READY FOR SEPARATELY AUTHORIZED 19G PLAN REVIEW ONLY; no pin/plan/apply approval |
| `LIVE_CANARY_READINESS` | Harness contract PASS; live execution NOT AUTHORIZED; entitlement/configuration must be verified under a future authorization |
| `AWS_MUTATIONS` | 0 |
| `TERRAFORM_PLANS` | 0 |
| `TERRAFORM_APPLIES` | 0 |

**STOP at the approval gate.** No pin update, Terraform plan/apply, live
canary, new order, AWS mutation, recovery/redrive, or Main merge.
