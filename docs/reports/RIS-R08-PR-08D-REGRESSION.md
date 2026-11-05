# RIS-R08-PR-08D — Regression

Current targeted RIS/R08/Application/API suite: **304 passed, 308 subtests**.
Re-run on current HEAD `27575f5` passed. Python compile, `git diff --check`,
and Terraform fmt passed. Terraform validate passed with the existing
deprecated DynamoDB `hash_key`/`range_key` warnings; no validation error.

Current full repository run: **2323 passed, 29 failed, 56 skipped, 400
subtests**. The 29 failures are classified as independent environment or
legacy-fixture issues: missing `mayaws` AWS profile, Windows symlink privilege
denials, secret-output permission assumptions, missing subprocess executable,
installer/composite legacy tests, and one stale entitlement expectation. No
new security failure was introduced by SECURITY-07; the four conditional-table
fixture failures observed during this review were corrected and retested.

The red full suite is not represented as fully passed.
