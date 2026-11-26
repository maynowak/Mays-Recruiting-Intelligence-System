# RIS-MODULE-BUILDER-PORTABILITY-07D — Report

Status: **IMPLEMENTED / VERIFIED LOCAL** — the Mays-Orders module builder now
runs on Linux against the unchanged builder pin `016cdfd`.

Branch: `fix/ris-module-builder-portability-07d` (base `d76fb99`)
No main merge, no force-push, no pin change, no AWS/Terraform plan/apply, no
deployment.

## Problem

`installer/build_mays_orders_module.py` resolved external tools Windows-only:

- `_terraform_exe()` shelled out to `where terraform` (raises
  `FileNotFoundError` on Linux) and otherwise guessed `terraform.exe`.
- `run()` and `ensure_repo()` hardcoded
  `C:\Program Files\Git\bin\git.exe`.

In addition, a code fragment from an earlier portability report had leaked into
`build_module()` after the target adoption: it referenced the undefined names
`hashlib` and `manifest_sha` and would raise `NameError` whenever the generated
module contained `lambda.zip`.

## Changes

`installer/build_mays_orders_module.py`

- `_resolve_tool()` resolves executables in this order:
  1. explicit override (`TERRAFORM_EXE`, new `GIT_EXE`; a set-but-missing
     override fails closed),
  2. PATH via `shutil.which`,
  3. Windows-only Git install candidates (`Program Files` bin/cmd, x86 bin).
- `_terraform_exe()` and new `_git_exe()` wrap that resolver and raise an
  actionable `RuntimeError` instead of guessing `.exe` names:
  install/PATH hint + the matching override variable.
- `run()` maps `git` / `terraform` command tokens to the resolved executable;
  other commands pass through unchanged. `TF_DATA_DIR` isolation is unchanged.
- `ensure_repo()` uses the portable `git` token and the resolver for the status
  check; the malformed `Warnung` format string was fixed.
- Removed the unreachable artifact-hash fragment (undefined
  `hashlib`/`manifest_sha`). The B5 account-boundary note is kept, now as a
  plain documentation print inside `build_module()`; no artifact or boundary
  behaviour was invented.
- CLI parameters and defaults (`--project-name ris-dev2`, `--force`, `--check`,
  `--clean`), name derivation, generated-module contract validation, transport
  injection and pin loading are untouched.

Tests

- New `tests/test_build_mays_orders_portability.py` (16 tests): PATH discovery
  for git/terraform, env overrides, missing override, Windows Git fallback and
  absence (no invented `git.exe`), `run()` resolution/cwd/`TF_DATA_DIR`,
  pass-through commands, `ensure_repo()` git token, missing-tool fail-closed in
  `post_run_checks`, unchanged CLI parameters/defaults.
- `test_wrapper_regression.py`: `mock.patch` string targets now bind to the
  imported module object. The repository `conftest.py` drops `installer.*` from
  `sys.modules` during builder collection, so the old string targets patched a
  second module instance and never reached the imported functions.

## Verification (all local)

| Check | Result |
| --- | --- |
| `pytest tests/test_build_mays_orders_portability.py` | 16 PASS |
| `pytest tests/test_build_mays_orders_transport_outputs.py` | 8 PASS |
| `pytest tests/test_ris_installer.py` | 43 PASS |
| `pytest tests/test_terraform_consent_deployment_unblock.py` | 8 PASS |
| `pytest test_wrapper_regression.py` | 43 PASS / 6 pre-existing failures (baseline `d76fb99`: 35 PASS / 14) |
| `git diff --check` | PASS |
| Secret scan of diff | PASS (no keys, tokens, allowlist values or account credentials) |

Real build, `/tmp/opencode/ris07d` copy of the worktree (no committed module or
pin touched), builder clone at pinned `016cdfd`:

```
python3 -m installer.build_mays_orders_module --project-name ris-dev --force
  module_builder orders-service build: OK
  Inputs OK: 9 (required 5)      Outputs OK: 23
  IAM contract OK, no wildcard SQS statement
  terraform fmt -recursive / fmt -check / init -backend=false / validate: OK
  Module installed at .../terraform/modules/mays_orders
```

The installed module was re-initialised and validated locally (`Success! The
configuration is valid.`). No `.terraform` data, lockfile or state was written
to the RIS worktree; the temporary build tree was removed.

## Remaining integration blocker

Not introduced here and out of this task's scope: the Mays-Orders module/pin
reconciliation (`016cdfd` vs reviewed `1dbb0cb`, including the SQS queue-policy
DELETE risk) from RIS-P0-PLAN-BASELINE-RECONCILIATION-06 still needs an explicit
owner decision. This change only makes the pinned builder executable on
Linux/macOS/Windows; it does not validate a plan.

The 6 remaining `test_wrapper_regression.py` failures are stale fixtures from
before the transport-output and dispatch-env features (they mock a generated
module without `variables.tf`/transport outputs); they are unchanged in nature
from the baseline run.
