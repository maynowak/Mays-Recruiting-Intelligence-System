# R08-E2E-G1D-3 — REMAINING REGRESSION BASELINE RECONCILIATION

**Status:** BASELINE RECONCILED / G1D-4 BLOCKED

## Baseline and execution boundary

- Starting HEAD: `8c7a573e5e6448827cf45cd9b853d2e8a7679870`
- Compared against G1C and G1D-2 reports.
- No AWS calls, installations, deployments or Terraform changes.
- No Jobsearch or Orders production changes.
- HTTP deployed E2E remained excluded as required by the local boundary.

Current collection is **2,686 tests, 0 collection errors**. The one-test
increase from the earlier 2,685 count is the G1D-1 freeze-key regression test;
it is not a new failure.

## Reconciliation: 42 before → 34 after

Eight failures were corrected with evidence-based, test-only portability
changes:

| Cause | Before | After | Correction |
|---|---:|---:|---|
| Windows path spelling | 3 | 0 | Static test comparisons now normalize `\\` to `/`; semantic path checks are unchanged. |
| Git unavailable to Python subprocesses | 5 | 0 | Root pytest configuration exposes the already-installed `C:\Program Files\Git\cmd` to child processes; no Git was installed or emulated. |

These are not test relaxations: the path normalization compares equivalent
paths, and the Git change makes the existing offline subprocess fixtures use
the real installed executable.

The G1D-1 boundary regression and the two G1D-2 State-Mirror defects remain
green and are not included in the 42→34 delta.

## Remaining 34 failures

| Group | Count | Classification / evidence | Priority |
|---|---:|---|---|
| Preserved `terraform/ris-dev2.tfvars` | 1 | Environment-preservation conflict. The file is required to remain; the test expects a clean absence. | P3 baseline fixture |
| Composite lifecycle subprocess capture | 4 | Builder/local Orders fixture and AWS CLI context do not reach the mocked command path; no productive operation occurred. | P2 Builder/infrastructure |
| Lambda source-change copy fixture | 1 | `shutil.copytree` cannot reproduce the large archived-evidence tree in the current temporary Windows fixture (`WinError 3`). | P2 fixture |
| Planned privacy routes | 1 | OpenAPI lists `/privacy/export` and `/privacy/inspect`, but implementation is explicitly planned, not present. | P3 planned scope |
| Project pinning local-root assumptions | 2 | Git now runs; failures are assertions against a custom temporary `repo_root` while `discover_project()` resolves the process repository root. | P2 existing test/fixture defect |
| Credential output/security tests | 21 | Five symlink cases fail with `WinError 1314`; the remaining issuance/revoke/list/CLI cases fail earlier because Windows temporary-directory ACL/mode checks reject the fixture. | P2 Windows capability/fixture |
| Installer lifecycle/identity | 2 | Orders pin state remains unavailable (`HEAD None`/pin mismatch); mocked STS output is empty and not JSON. | P2 Builder/AWS fixture |
| Dependency-check launcher | 2 | Tests invoke literal `python3`; Windows returns launcher/app-alias code 9009 and no JSON. | P2 executable alias |

**Total remaining: 34.** No remaining failure was proven to be a new RIS
production regression in this gate. The planned privacy route finding remains
an explicit capability gap, not a hidden pass.

## Builder separation

The available Builder run was kept separate from the RIS count:

- **256 passed**
- **68 failed**
- **30 subtests passed**

The Builder failures are not added to the 34 RIS failures. They concern the
embedded generated Orders project, SARIF adapter, Lambda test assumptions and
module-builder generated artifacts. The four RIS composite lifecycle failures,
two installer pin/identity failures, and the Lambda copy-fixture failure are
reported in both scopes only as related environment/baseline causes; they are
counted once in the RIS total and not double-counted as Builder failures.

## Skips

The existing **56 skips** remain unchanged and justified:

- 39 DynamoDB Local endpoint absent
- 2 captured real-plan fixtures absent
- 1 CloudFront/OAC capability finding
- 2 missing AWS credentials
- 6 live observability contracts
- 6 explicitly planned privacy capabilities

No test was disabled, weakened or converted from failure to skip.

## Cleanup and working tree

- No background test service was started.
- Port `18000` is not listening.
- The 39 pre-existing untracked files were preserved.
- Changes are limited to root test configuration, three portable test
  assertions, and this report; no Jobsearch/Orders production files changed.

## G1D-4 readiness

**BLOCKED.** The baseline is reconciled and eight legitimate portability
failures are fixed, but 34 known failures remain. The highest-priority gates
are the Builder/local Orders fixture, Windows credential security fixture,
installer identity/pinning fixture, and literal executable assumptions.

## Commit

```text
test(ris): reconcile remaining regression baseline
```
