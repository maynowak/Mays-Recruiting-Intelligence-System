# RIS-R08-PR-08C — API/Infrastructure Review

The public erasure path requires `APPLICATIONS_TABLE`, constructs the existing
ApplicationRepository/ApplicationErasureExecutor, and binds partner scope to
an ACTIVE registry entry. Missing partner context fails the application phase
closed and returns an honest partial result. Personal responses receive
`Cache-Control: no-store, private`.

WorkItems uses `workId` as the primary key; transactional IAM and `/index/*`
authorization are present. No new table was introduced. Terraform source
fmt/validate was checked offline; no Apply, state operation, or deployment was
performed. Runtime rollout still requires the existing table/schema/IAM
cutover and fail-closed deployment gate.
