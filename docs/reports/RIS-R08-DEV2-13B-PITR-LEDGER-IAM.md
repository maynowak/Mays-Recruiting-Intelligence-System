# RIS-R08-DEV2-13B — PITR, Ledger and IAM Review

## PITR

The selected five existing tables are:

* `privacy_receipts`
* `erasure_operations`
* `s3_erasure_phases`
* `upload_ticket_ledger`
* `upload_cutover`

The new `deletion_ledger` table also has the same opt-in PITR block. The
Terraform variable is `r08_pitr_enabled`, default `false`; the review plan
overrides it to `true`. No `recovery_period_in_days` or legal retention
window is configured. The plan reports the recovery period as provider-known
after apply. No 24-hour, 35-day or other policy value may be inferred from
this configuration.

All five existing tables are in-place updates. Keys, GSIs, billing mode,
streams and event-source mappings are unchanged. PITR activation would be a
write against existing tables and is therefore a separate authorization gate;
it is not live evidence of restore or erasure compliance.

## Ledger

`ris-dev2-dev-deletion-ledger` is a separate PAY_PER_REQUEST table with
`ledgerId` as primary key and `gsi-operation` on `operationId`/`ledgerId`.
Entries contain scoped identity fields, operation/version/state and opaque
resource digests; no CV or sensitive payload is intended. The repository
uses conditional idempotent capture and version/state CAS completion.

The Lambda policy grants only `dynamodb:GetItem`, `dynamodb:PutItem` and
`dynamodb:Query` on the table and its indexes. Runtime environment wiring is
explicitly `DELETION_LEDGER_ENABLED=false`. Missing table, disabled runtime,
unavailable store or malformed evidence fails closed; no automatic
reactivation or promotion is implemented.

RecoveryPlanV1 and existing reconciliation contracts are reused. Restore
promotion remains separate and requires current authoritative ledger evidence.

Status: **LOCAL CONFIGURATION PASS / LIVE ACTIVATION AND RESTORE BLOCKED**.
