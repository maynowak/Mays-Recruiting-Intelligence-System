# RIS-R08-DEV2-12C — Durable Deletion Ledger

`DurableDeletionLedger` is a disabled-by-default, injected DynamoDB
repository. It stores opaque resource-reference digests, verified
user/tenant/partner/issuer scope, operation identity, expected state and a
version. It does not store CV contents or sensitive payloads, delete ledger
history, or reactivate restored records.

Persistence uses a separate `deletion-ledger` table with `ledgerId` as the
primary key and `gsi-operation` for reconciliation reads. Capture is
idempotent through a conditional put. Completion is a conditional CAS on
version and state; divergent retries fail closed. Missing, malformed or
unavailable evidence blocks reconciliation.

Terraform supplies least-privilege `GetItem`, `PutItem`, and `Query` access
only to this table and its index. Runtime bindings are present but
`DELETION_LEDGER_ENABLED=false` by default. The table is not the upload-ticket
ledger and is not claimed to be isolated from account-level administrative or
regional failures.

Evidence: `tests/test_durable_deletion_ledger.py` plus
`tests/test_r08_orch02_recovery_and_ledger.py`: **8 passed**. Live deployment
and durable production writes were not performed.

Status: **VERIFIED LOCAL / BLOCKED FOR LIVE USE**.
