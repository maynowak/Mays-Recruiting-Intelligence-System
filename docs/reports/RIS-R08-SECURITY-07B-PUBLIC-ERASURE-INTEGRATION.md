# RIS-R08-SECURITY-07B — Public Erasure Integration

The handler now requires `APPLICATIONS_TABLE` and verified partner/issuer
context. It constructs the existing `ApplicationRepository` and
`ApplicationErasureExecutor`, then injects both into `PrivacyErasure`.

`PrivacyErasure` consumes executor pages until the cursor is exhausted. A
non-advancing cursor or executor/store exception produces a failed
`erase-applications` step and therefore `complete=false` / HTTP 207. Empty
ApplicationV1 results complete successfully after an authorized zero-row
query. Missing infrastructure fails closed with HTTP 503. No client-selected
category or reduced scope is accepted.

This is local source/runtime evidence only; it does not prove deployed tables,
IAM, PITR, or cross-service atomicity.
