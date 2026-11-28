# RIS-MAYS-ORDERS-MAIN-UPGRADE-19F5 — Candidate Gate Blocker

**Status:** BLOCKED — CANDIDATE CONTRACT CANNOT PRESERVE INTEGRATED RIS FEATURES
**RIS branch:** `feature/ris-analysis-integration-07`  
**Initial RIS HEAD:** `9e1cff4f392410de887ddef10e86edc9008d2bdb`  
**Candidate-pin checkpoint:** `6d0b6ba5d865f4f78968154f89a8d847462188ce`

## Source verification

- RC4 `v0.6.0-rc.1`: `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`.
- Direct command in the Mays-Orders worktree:
  `git -C <MAYS_WORKTREE> rev-parse --verify "80a84ca^{commit}"`.
- Resolved SHA: `80a84ca2f146d5efaa31d41ba425359283333f21`.
- Title: `feat(orders): add optional orderDescription field`.
- `git merge-base --is-ancestor <SHA> origin/main`: exit 0.
- Separate detached source checkout was clean at that exact SHA. No Mays files
  or refs were changed.
- RIS QA version map was updated to this exact full SHA and pushed in commit
  `6d0b6ba5d865f4f78968154f89a8d847462188ce`.

## Required gates executed

All runs used the existing Unified Testsuite with the detached candidate source;
the runner reported candidate provenance `VERIFIED`. Host: Windows, Python
3.15.0. Results are in the temporary JSON files named below; those files are
outside the repository.

| Profile / group | Result | Detail |
|---|---|---|
| `MAYS_MODULE` / Lambda originals | PASS | 456 passed |
| `MAYS_MODULE` / module-builder originals | FAIL | 113 passed, 16 failed. Failing groups include builder apply/manifest/layout, generated project/policy gates, module selection, and Orders-Service layout. |
| `MAYS_MODULE` / installer originals | FAIL | 71 passed, 9 errors, 1 skipped. Errors include `FileNotFoundError [WinError 2]` launching `python3` in `test_sarif_no_native_top_level_fields`. |
| `MAYS_MODULE` / seed originals | PASS | 28 passed |
| `MAYS_MODULE` / Cognito backup originals | PASS | 2 passed |
| `XREPO_CONTRACT` | FAIL | 124 passed, 9 failed, 4 subtests passed. All nine failures in `test_mo_contract_compat.py` cannot import candidate `result_envelope` (`ModuleNotFoundError`). |
| `XREPO_E2E` | FAIL | 3 passed, 36 failed. E2E handoff/dispatch requirements fail; bridge tests cannot import candidate `result_consumer` (`ModuleNotFoundError`). |

Result files:

- `C:\Users\DCI-Student\AppData\Local\Temp\opencode\19f5-mays-module-results.json`
- `C:\Users\DCI-Student\AppData\Local\Temp\opencode\19f5-xrepo-contract-results.json`
- `C:\Users\DCI-Student\AppData\Local\Temp\opencode\19f5-xrepo-e2e-results.json`

## Stop decision and safety

### Builder/installer preservation analysis

The existing Module Builder cannot compose a module from the candidate's
OrderDescription change while retaining the current RIS integration:

- Candidate Builder `module_builder/builder.py` copies each `lambda/src/*.py`
  from its own pinned checkout into the generated module and records that
  checkout SHA in `module-builder.manifest.json`.
- RIS's existing Builder does not overlay current RIS/Mays transport or consumer
  source. It applies only its documented compatibility Terraform wiring and
  validates the generated contract.
- The existing Installer takes the validated generated module and replaces the
  target `terraform/modules/mays_orders` directory (with backup/restore on
  failure); it does not merge or preserve files from the old generated module.
- Compared to current integrated source `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`,
  candidate `80a84ca2f146d5efaa31d41ba425359283333f21` deletes
  `lambda/src/dispatch.py`, `result_envelope.py`, `result_handler.py`,
  `result_consumer.py`, `agent_order.py`, and
  `terraform/modules/agent_transport/{main.tf,lambda.tf}`. Those are material
  pieces of the RIS transport/consumer integration.

So a candidate-built module would record the correct candidate provenance but
would omit existing RIS functionality. Keeping those files by manual copying,
patching the Builder to substitute a different source, or installing only a
partial generated tree is not an approved path and would fail provenance and/or
generated-module gates. No such workaround was attempted.

### Unified profile results

The existing Unified runner was used with the exact detached candidate and the
candidate-specific QA version-map entry:

| Profile | Result | Material gates |
|---|---|---|
| `MAYS_MODULE` | BLOCKED | Lambda 456 PASS; Builder 113 PASS / 16 FAIL; Installer 71 PASS / 9 errors / 1 skipped; Seed 28 PASS; Cognito backup 2 PASS |
| `XREPO_CONTRACT` | BLOCKED | 124 PASS / 9 FAIL / 4 subtests; missing `result_envelope` |
| `XREPO_E2E` | BLOCKED | 3 PASS / 36 FAIL; missing `result_consumer` and required dispatch/handoff behavior |
| `UPGRADE_GATE` | BLOCKED | Candidate tests as above; RIS builder contract 57 PASS; generated module artifact 8 PASS / 1 FAIL because its manifest still identifies integrated source `db4f9e7`, not candidate SHA |
| `FULL` | BLOCKED | Same candidate failures; RIS Native collection additionally has 2 collection errors due unavailable `moto` and `requests` in this Windows environment (3 tests skipped) |

The Mays Installer errors include `FileNotFoundError [WinError 2]` when its
original test launches `python3` on Windows. This environment issue is recorded
separately from the source/module incompatibility; it does not make the failed
gate green.

Result JSONs (outside the repository):

- `C:\Users\DCI-Student\AppData\Local\Temp\opencode\19f5-upgrade-gate-results.json`
- `C:\Users\DCI-Student\AppData\Local\Temp\opencode\19f5-full-results.json`

In accordance with the task's fail-closed instruction, execution stopped here:

- Original module Builder was **not** invoked to generate a candidate module;
  Generated Module Validation and `UPGRADE_GATE` therefore remain NOT RUN.
- Existing installer was **not** run; module directory, active builder pin,
  generated manifest and installed module were not changed.
- Backend-free Terraform init/validate were **not** run because no candidate
  module was generated or installed.
- `FULL` ran and is **BLOCKED**; it is not an acceptance pass.
- `MODE=true` unchanged; `LIVE=false`; AWS mutations 0; Terraform plans 0;
  applies 0; Main merges 0.

The new version-map checkpoint is the only RIS code/configuration change. No
forced installation or workaround was attempted. Resume only after the Mays
candidate supplies the missing result-consumer/transport compatibility and the
original Builder/Installer gates are green in the supported test environment.
