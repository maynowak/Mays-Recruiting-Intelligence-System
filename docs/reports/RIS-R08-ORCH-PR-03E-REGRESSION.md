# RIS-R08-ORCH-PR-03E — Regression Results

- Recovery/ledger/worker/erasure focused tests: **20 passed**.
- Combined selected Recovery/Erasure/Application/API/Privacy/Worker suite:
  **224 passed, 301 API subtests**.
- Python compilation for reviewed recovery/ledger modules: **PASS**.
- `git diff --check`: **PASS**.
- AWS live tests: **NOT RUN / prohibited**.
- Terraform validate: **ENVIRONMENT BLOCKED** by Windows Application Control;
  prior Terraform PASS remains historical only.
- OpenAPI parse and the earlier 222-pass/301-subtest baseline remain historical;
  this review did not change API/OpenAPI files after that run.

The focused rerun confirms the schema/order/CAS review fix but does not override
the active messaging and ApplicationV1 findings.
