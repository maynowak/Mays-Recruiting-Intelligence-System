# RIS-R08-SECURITY-06G — Regression

The targeted integrated security/application suite completed with **300 passed
and 308 subtests passed** after the review corrections. Python compilation and
`git diff --check` passed. The complete repository run produced **2317 passed,
31 failed, 56 skipped, 400 subtests**; the failures are documented as
environment/legacy-contract issues (missing `mayaws` profile, Windows symlink
privileges, unavailable subprocess executable, stale entitlement expectation,
and local handler fixtures without production WorkItems configuration), not
silently treated as PASS.

No AWS-backed test, deployment, queue mutation, or Terraform Apply was run.
