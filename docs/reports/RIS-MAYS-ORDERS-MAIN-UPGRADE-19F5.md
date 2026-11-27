# RIS-MAYS-ORDERS-MAIN-UPGRADE-19F5 — Candidate Gate Blocker

**Status:** BLOCKED BEFORE MODULE BUILD / INSTALLATION  
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

The mandatory original builder/installer and RIS XRepo gates failed. In
accordance with the task's fail-closed instruction, execution stopped here:

- Original module Builder was **not** invoked to generate a candidate module;
  Generated Module Validation and `UPGRADE_GATE` therefore remain NOT RUN.
- Existing installer was **not** run; module directory, active builder pin,
  generated manifest and installed module were not changed.
- Backend-free Terraform init/validate were **not** run because no candidate
  module was generated or installed.
- `FULL` was **not** run after the prerequisite upgrade gates failed.
- `MODE=true` unchanged; `LIVE=false`; AWS mutations 0; Terraform plans 0;
  applies 0; Main merges 0.

The new version-map checkpoint is the only RIS code/configuration change. No
forced installation or workaround was attempted. Resume only after the Mays
candidate supplies the missing result-consumer/transport compatibility and the
original Builder/Installer gates are green in the supported test environment.
