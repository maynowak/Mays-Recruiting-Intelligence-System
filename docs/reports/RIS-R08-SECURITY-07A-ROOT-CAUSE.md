# RIS-R08-SECURITY-07A — Root Cause

`POST /me/erasure` previously constructed only the legacy `PrivacyErasure`
collaborators. `ApplicationErasureExecutor` existed and was tested, but no
public route supplied it, so ApplicationV1 records were outside the reported
erasure lifecycle.

The corrected path is:

`JWT claims -> verified user/tenant/partner/issuer context ->
ApplicationRepository -> ApplicationErasureExecutor -> PrivacyErasure
application phase -> honest complete/partial response`.

The existing WorkItem subject fence remains activated before cancellation and
the ApplicationV1 phase runs before document/profile finalization. No second
erasure engine was introduced.
