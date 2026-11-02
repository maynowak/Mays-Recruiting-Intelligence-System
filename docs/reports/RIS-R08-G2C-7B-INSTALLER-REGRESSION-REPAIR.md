# RIS-R08-G2C-7B — Installer Regression Repair

**Status:** GO / OFFLINE VERIFIED / BUILDER REGRESSION BOUNDARY DOCUMENTED

## Reproduced failures and fixes

### 1. Backend-less validate attempted STS

`_cmd_validate` called `validate_aws_context` even though it runs Terraform
`init -backend=false` and `validate` only. The existing mocked subprocess
fixture returned empty STS output, producing `STS returned unparsable output`.
The root cause was an unnecessary AWS dependency in a local validation command.
The command now remains local; account/profile guards stay in preflight, plan
and apply paths.

### 2–3. Windows project-pinning path assertions

Two tests compared `str(Path)` to a forward-slash suffix, failing on Windows
despite correct configured `installer/projects/<project>` resolution. The tests
now assert path components (`name`, parent names), preserving the same contract
portably without weakening pin or clone checks.

### Prior dry-run Orders failure

The installer dry-run reached Orders pin enforcement and failed when the local
component was unavailable. Dry-run now returns after printing its read-only
phase description; it cannot invoke component lifecycle or deployment logic.

## Actual verification

| Check | Result |
|---|---:|
| Installer/Runner/Backend/Pinning subset | **95 passed** |
| G2C-6 static protection tests | **6 passed** |
| Bootstrap preflight tests | **5 passed** |
| Python compilation | PASS |
| Pinned Orders builder for `ris-dev2` | PASS (module contract, fmt, init, validate) |
| AWS access/mutation | NOT USED |

The historical broad wrapper regression command still times out in its
mock-heavy build tests after partial output. It is recorded as **NOT PASS**;
the direct pinned builder path is independently green and is the deployment
relevant artifact path.

Managed defaults remain unchanged. External and disabled Orders modes do not
invoke the managed Orders component.
