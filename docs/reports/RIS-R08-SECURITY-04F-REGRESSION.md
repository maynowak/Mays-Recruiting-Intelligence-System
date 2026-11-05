# RIS-R08-SECURITY-04F — Regression

## Current focused evidence

- Worker/cache/erasure/recovery focused slice: **37 passed**.
- Worker-only suite after terminal-failure tests: **10 passed**.
- Combined selected R08/Application/API/Privacy/Worker suite: **230 passed,
  301 API subtests**.
- Python compilation of changed modules: **PASS**.
- OpenAPI parse: **PASS** in the prior combined run; no OpenAPI files changed.
- `git diff --check`: **PASS**.

The full selected regression suite must be rerun after final documentation and
auditlog commits. Terraform remains **ENVIRONMENT BLOCKED** by Windows
Application Control; no current Terraform PASS is claimed. AWS live, race and
conditional-write integration tests were not run by policy.

## Remaining negative tests

The durable missing-row resurrection test and a real concurrent DynamoDB claim
test remain blocked until a durable RIS fence/integration seam is approved.
