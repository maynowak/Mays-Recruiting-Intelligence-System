# RIS-MAYS-ORDERS-QA-BLOCKER-RESOLUTION-19F3

**Outcome: current RIS QA improved; RC4 candidate identified and tested; Mays
upgrade remains BLOCKED.** All work is local test/orchestration/documentation
only. No RIS runtime, Mays source repository, generated installed module, or
module pin was changed.

## Identity and evidence

| Item | 19F3 evidence |
|---|---|
| RIS branch / baseline | `feature/ris-analysis-integration-07`; requested HEAD `83711470af9a1a6a464bef5e58f58ce99925033a` |
| Final RIS HEAD | Recorded after final checkpoint below; test result JSONs identify the commit used for each run |
| Current integrated Mays source | `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; unchanged |
| RC4 source remote | `https://github.com/maynowak/mays-order-aws.git` |
| RC4 tag | `v0.6.0-rc.1`; remote tag object `79628819717e4609d828581dff53055f2b32f8ec` |
| RC4 peeled commit | `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` |
| Candidate checkout | Separate clean detached checkout at exact SHA; original integrated clone remains at db4f9e7 and clean |
| Worker bundle | SHA-256 `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`; baseline unchanged |
| Platform | Windows `win32`, Python 3.14.10, Terraform 1.17.0 |
| Machine results | [`19F3 current results`](RIS-MAYS-ORDERS-QA-BLOCKER-RESOLUTION-19F3.current.results.json); [`RC4 candidate UPGRADE_GATE results`](RIS-MAYS-ORDERS-QA-BLOCKER-RESOLUTION-19F3.candidate.results.json) |
| Contract index | [`Updated 19F2 / 19F3 evidence index`](RIS-MAYS-ORDERS-CONTRACT-EVIDENCE-19F2.md) |
| Separate RIS API fix request | [`APIProfile binding OpenAPI fix`](RIS-API-OPENAPI-APIPROFILE-BINDING-FIX-REQUEST.md) |

## Track A — RIS Native blockers

### A1 — Historical bundle hash: resolved

The 16C1 manifest itself says its old plan pins pre-change bundles and is
`STALE_SUPERSEDED`. The test incorrectly compared those historical hashes with
present-day files. It now verifies the immutable historical SHA values and
provenance fields. Current artifacts remain independently checked by
`test_analysis_ecosystem_wiring.ManifestPinTest`, including current worker and
analysis bundle SHA contracts. Targeted validation: **18 passed, 4 subtests**.
No historical report or manifest was rewritten and no hash assertion was
removed.

### A2 — `mayaws` fixture: resolved

`test_discover_subprocess_env_keeps_path` is an environment-composition test,
not an STS integration test. It now injects a local `_run_sts` identity fixture
and asserts the requested profile/timeout. No real AWS profile, credentials,
endpoint, or STS request is used. Targeted test **1 passed**; the complete
`test_composite_lifecycle.py` suite **43 passed**. Runner children continue to
receive scrubbed AWS variables and isolated empty AWS config/credentials files.

### A3 — OpenAPI route: remains a separately owned contract fix

The three remaining failures are not bad assertions: the actual
`POST /v1/apiprofiles/{apiProfileId}/binding` route is in Terraform and the
dispatcher and is documented in `docs/API/API-STANDARD.md` as a JWT-admin
operation, but is absent from canonical `docs/api/openapi-platform.yaml`.
The same missing route explains all three failures. No runtime, security, or
OpenAPI change was made in 19F3; a concrete RIS-owned follow-up is recorded in
the separate fix request.

### A4 — Current RIS verification

Final current `FULL` execution: RIS Native **3,278 passed, 3 failed, 142
skipped, 450 subtests**. The three failures are the A3 OpenAPI discrepancy.
Current Mays/XRepo groups are below. The worker bundle SHA still exactly matches
the requested baseline.

## Track B — reference platform and Mays suites

Mays `docs/TEST-STRATEGY.md` documents Ubuntu `ubuntu-latest` for unit tests and
gives `python3` test commands. The checked-in `.github/workflows` directory has
security/dependency/CodeQL workflows, but no executable unit-test workflow
matching that documentation. This host has neither WSL nor Docker; no Linux
container or external CI infrastructure was started. Thus **Ubuntu is the
documented reference, but it was not locally verified in 19F3**.

Current integrated source, from isolated exact-commit test clones:

| Group | Result on Windows | Classification |
|---|---:|---|
| Mays Lambda | 240 passed | PASS |
| Mays Module Builder | 86 passed / 14 failed / 6 subtests | Windows POSIX path separator assertions; not classified as Linux/module failure |
| Mays Installer | 69 passed / 11 errors / 1 skipped | `python3` and hard-coded Linux paths unavailable on Windows |
| Seed tools | 28 passed | PASS |
| Cognito Backup | 2 passed | PASS |
| RIS builder contracts | 57 passed | PASS |
| Current generated module artifact contracts | 9 passed | PASS; source `db4f9e7` and artifact SHA verified |

The unified runner rebuilds `lambda/dist/lambda.zip` only inside a disposable
exact-commit Mays clone before Module Builder tests. This fixed candidate
test-environment failures caused by the release's stale committed ZIP, without
changing the clean candidate checkout or original tests.

## Track C — RC4 candidate results

Original candidate test suites ran at exact `5bc154e…`; the candidate clone
remained clean. A separate temporary build-source clone had only its generated
`lambda/dist/lambda.zip` rebuilt (SHA-256
`f1031a86da0083ad034075598f89e0c4b178cbb20ce93743a1bd28ab56678e86`). The
candidate checkout itself was not modified.

| Candidate group | Result | Meaning |
|---|---:|---|
| Mays Lambda | 440 passed | PASS on this Windows/Python run |
| Mays Module Builder | 111 passed / 18 failed | Windows path and symlink assumptions; reference-platform rerun unavailable |
| Mays Installer | 71 passed / 9 errors / 1 skipped | Windows `python3`/Linux-path failures; not Linux evidence |
| Seed tools | 28 passed | PASS |
| Cognito Backup | 2 passed | PASS |
| RIS XRepo Contract | 120 passed / 13 failed / 4 subtests | Candidate compatibility failures; `orderDescription` sent by the RIS adapter is rejected as unknown by RC4 create validation |
| RIS synthetic XRepo E2E | 3 passed / 36 failed | Candidate does not expose expected result-consumer module/imports and fails current RIS round-trip contracts |
| RIS generated module contracts against temp RC4 build | 2 passed / 7 failed | Current integration contract expects full source SHA and db4f9e7 module/input/output set; RC4 artifact does not satisfy it |
| RC4 generated Terraform | `fmt -check` PASS; `init -backend=false` PASS; `validate` FAIL | Candidate-generated configuration has undeclared variables/modules listed below |

Terraform validation failures include references to undeclared
`privacy_secret_enabled`, `privacy_secret` module, `privacy_kms_key_arn`,
`sqs_visibility_timeout_seconds`, `sqs_message_retention_seconds`,
`sqs_dlq_message_retention_seconds`, `sqs_max_receive_count`, and
`deployment_version`. The generated manifest reports source commit `5bc154e`
(7-character abbreviation), while the existing RIS Generated Module Contract
requires the full 40-character SHA. These are candidate builder/generated
module issues requiring Mays-Orders ownership; no fix was applied in RIS.

The candidate originals establish **candidate QA evidence, not an upgrade
authorization**. XRepo tests did run and failed. The existing RIS module pin and
installed generated artifact remain unchanged.

## Platform/dependency disposition

- Documented reference platform: Ubuntu `ubuntu-latest` per Mays
  `docs/TEST-STRATEGY.md`; no matching active unit-test workflow was found.
- Local Linux availability: WSL not installed; Docker executable/daemon absent.
- Terraform dependency validation: candidate module `terraform init
  -backend=false` succeeded with Terraform 1.17.0; `terraform fmt -check
  -recursive` succeeded; `terraform validate` failed as above. No backend,
  workspace, state, plan, or apply was used.
- Candidate artifact `lambda.zip` was rebuilt only in a disposable local clone;
  full candidate SHA remains verifiable from the clean detached checkout.
- Worker bundles were also rebuilt in a disposable LF checkout (`core.autocrlf=false`):
  worker SHA-256 `4d880b4856067b7d8b9d17e8a0257abf49d6208f9fb1743b711f516091ce928a`,
  not the required/current artifact SHA
  `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`.
  ZIP members are LF in the controlled rebuild and CRLF in the existing artifact.
  The earlier disposable `core.autocrlf=true` rebuild produced a third SHA,
  `747b749ed674aad40954b85a2d628631131684230d4145e52e627e4ed58bd7b5`.
  Cause is unresolved, so worker deployment readiness is BLOCKED pending
  artifact provenance/reproducibility investigation; no tracked source or
  artifact was changed by these disposable builds.

## Independent release gates

| Gate | Result |
|---|---|
| `RIS_NATIVE_QA` | FAIL: 3,278 passed / 3 failed / 142 skipped / 450 subtests; A3 OpenAPI contract |
| `CURRENT_MODULE_QA` | PARTIAL: Lambda/Seed/Backup PASS; Windows Builder and Installer failures remain unverified on Ubuntu |
| `MODULE_BUILDER_QA` | PARTIAL: current artifact contracts pass; source suites have Windows-only failures; candidate generated Terraform has real validation errors |
| `INSTALLER_QA` | BLOCKED on local Windows reference mismatch; current 11 and candidate 9 errors, not represented as Linux results |
| `REFERENCE_PLATFORM_VERIFIED` | NOT_VERIFIED: documented Ubuntu reference unavailable locally |
| `RC4_CANDIDATE_PROVENANCE` | VERIFIED: exact remote release tag and full commit; clean detached checkout |
| `RC4_CANDIDATE_MODULE_QA` | BLOCKED: original Lambda/seed suites pass, but reference platform missing and candidate generated Terraform/manifest contract fails |
| `RC4_CANDIDATE_INTEGRATION_QA` | FAIL: XRepo Contract 13 failed; XRepo E2E 36 failed |
| `XREPO_QA` | Current integrated version PASS: contract 133 + 4 subtests; E2E 39 |
| `WORKER_DEPLOYMENT_READINESS` | BLOCKED: neither controlled rebuild reproduced the required worker ZIP SHA; no plan executed |
| `MAYS_ORDERS_UPGRADE_READINESS` | BLOCKED: candidate/module/generated-contract/XRepo gates do not pass |

## Safety, commits, and stop

- `AWS_MUTATIONS=0`; `LIVE_INVOCATIONS=0`; `REDRIVES=0`.
- `RUNTIME_SOURCE_CHANGES=0`; `MAYS_ORDERS_REPOSITORY_CHANGES=0`;
  `MODULE_PIN_CHANGES=0`.
- No module installation/replacement, Terraform plan/apply, deployment, recovery,
  or canary occurred. `MODE=true` was not changed.
- Commits pushed in order: `47f1d0a` (A1 historical bundle evidence),
  `c19f0dd` (A2 isolated AWS fixture), `8825fb7` (isolated Mays import path),
  `7f7f3af` (rebuild ZIP only in test clone), `5881806` (candidate artifact
  diagnostic handling), followed by the 19F3 report/evidence checkpoint.
- Final remote HEAD and clean/dirty state are included in the completion
  message. Original integrated clone and exact candidate clone are clean; the
  disposable candidate build-source has only the regenerated ZIP.

## Recommended next task

**19F4 should be a combined blocker-closure task, not an upgrade/install task:**
1. RIS API owner adds the missing OpenAPI binding operation and closes A3.
2. Mays-Orders owner fixes RC4 candidate orderDescription compatibility, builder
   manifest full-SHA provenance, missing generated Terraform declarations/module
   wiring, and reruns unchanged originals on Ubuntu `ubuntu-latest`.
3. Re-run candidate Generated Module Contracts and XRepo Contract/E2E against a
   new immutable exact candidate commit. Only if all pass should a later,
   separately authorized local integration task evaluate pin/install changes.

19G remains separate worker planning scope. No automatic follow-on, module
installation, Terraform plan, deployment, recovery, or canary is started here.
