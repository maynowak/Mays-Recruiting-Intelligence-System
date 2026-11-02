# R08-E2E-G1D-3B — OFFLINE BASELINE CLOSURE

**Status:** OFFLINE BASELINE CLOSED / INFRASTRUCTURE READINESS BLOCKED

## Scope and boundary

- HEAD at start: `1af975da9051d1cd96474d610dcc59b5bae76e45`
- No AWS or STS calls, installations, deployments or Terraform changes
- No Jobsearch/Orders production changes
- No tests removed, disabled, skipped or weakened
- The 39 pre-existing untracked files were preserved

## Baseline

The latest available full runs at this HEAD remain the G1D-3A results. The
RIS and Builder trees were executed separately; their counts are not added.

| Suite | Before G1D-3A | Current offline baseline |
|---|---:|---:|
| RIS regression | 2,197 passed / 34 failed / 56 skipped / 339 subtests | **2,197 / 34 / 56 / 339** |
| Builder available run | 256 passed / 68 failed / 30 subtests | **264 / 60 / 30** |
| Builder Lambda isolated gate | runtime import failures | **76 passed / 0 failed / 30 subtests** |
| Collection | — | **2,686 tests, 0 collection errors** |

An offline-safe targeted rerun passed **183 tests**, with **2 existing skips**
and **30 subtests**. It covered State Mirror, the repaired path assertions,
partner Terraform wiring, dry-run handoff, and the isolated Builder Lambda
tests. No external service was contacted.

## Root-cause overlap

There are no identical test nodes across the RIS and embedded Builder trees.
The following **9 RIS failure instances** are related to Builder/local fixture
causes, but remain counted only once in the RIS total:

| Related RIS group | Count | Related Builder group | Boundary |
|---|---:|---|---|
| Composite lifecycle / Orders subprocess fixture | 4 | Builder installer/generated-project fixture | Requires a coherent local Orders fixture and shell context |
| Lambda source-change copy fixture | 1 | Builder artifact/Lambda fixture | Requires a reproducible complete artifact tree |
| Installer lifecycle / identity | 2 | Builder installer/profile context | Requires valid local pin state and, for identity, AWS/STS |
| Dependency-check launcher | 2 | Builder installer/module-builder launcher failures | Requires a real `python3` executable alias or platform-neutral invocation |

The other **25 RIS failures** are RIS-only baseline blockers: preserved
tfvars, planned privacy routes, project-root assumptions, Windows credential
ACL/symlink capability, and the remaining composite/fixture portions. The
remaining **51 Builder failures** are Builder-only artifact, CI-tree, guide,
Lambda-service, and generated-project failures.

## Classification and release criteria

| Class | Remaining evidence | Required before release |
|---|---|---|
| Local fixture/artifact | Missing Builder `ci/` tree, stale generated ZIPs, incomplete archived-evidence copy tree, missing generated-project fixtures | Restore or regenerate the exact fixture/artifact from the authoritative source; rerun integrity and generated-layout tests without changing expected results |
| Windows capability | `WinError 1314`, ACL/mode rejection, shell environment and path assumptions | Run under a Windows account with symlink privilege and complete `ComSpec`/`SystemRoot`, or use a separately approved platform-portability change |
| Executables | Literal `python3` returns Windows app-alias `9009`; shell lookup also fails | Provide an approved `python3` launcher in PATH or update the affected test/tool contract deliberately; do not emulate it in production code |
| AWS/STS credentials | `aws` unavailable or STS output absent/unparsable; `mayaws` identity cannot be verified | AWS CLI plus the `mayaws` profile, valid credentials, region `eu-central-1`, and a read-only STS identity check in an explicitly permitted integration gate |
| DynamoDB/Orders runtime | Builder Lambda cases reach real `ResourceNotFoundException`; local Orders subprocess path is not available | Start only the approved local integration fixture/service and provision the expected test tables/configuration, then rerun the isolated integration gate |
| Planned Privacy | OpenAPI advertises `/v1/partner/me/privacy/export` and `/inspect` without implementation declarations | Implement and review the planned routes, or update the API contract through the normal product decision; neither is an offline test workaround |
| Preserved repository state | `terraform/ris-dev2.tfvars` remains present by boundary decision | Resolve the preservation-vs-clean-tree policy explicitly; do not delete the preserved file during this gate |

## Decision on further offline repairs

**Further Offline-Reparaturen: NEIN.** The remaining failures have no single
independent repair that can be made without either fabricating external
prerequisites, changing a security/platform contract, regenerating protected
Builder artifacts, or implementing planned product scope. The offline gate is
therefore closed at the documented baseline.

**Infrastruktur-Readiness: BLOCKED.** The next step is an explicitly approved
fixture/platform/AWS-IAM readiness gate, not another offline code change.

**Production: BLOCKED.** No production readiness is inferred from the green
targeted tests.

## Cleanup

- No test service was started.
- Port `18000` is not listening.
- Working tree contains only the preserved 39 untracked files after the report
  is committed.

## Commit

```text
test(ris): close offline baseline
```
