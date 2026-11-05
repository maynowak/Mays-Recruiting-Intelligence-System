# RIS-R08-DEV2-12B — PITR Configuration

`r08_pitr_enabled` is a root and DynamoDB-module boolean with default
`false`. It is not a legal retention policy and does not imply restore or
erasure compliance.

## Scope decision

PITR is proposed for the five R08 recovery/deletion coordination tables:

1. `privacy_receipts`
2. `erasure_operations`
3. `s3_erasure_phases`
4. `upload_ticket_ledger`
5. `upload_cutover`

The new `deletion_ledger` table also has an opt-in PITR block. The remaining
11 of the 17 existing RIS tables are deliberately excluded from this minimal
R08 integration scope. They may require PITR for a later full recovery
acceptance, but that is a separate inventory and cost decision.

The excluded set means an R08 restore cannot claim complete application
recovery. Applications, WorkItems, identity/profile, credentials, jobsearch,
partner and other data domains remain outside this PITR proposal. Promotion
must therefore remain blocked unless the restore scope and missing-domain
handling are explicitly approved.

## Terraform change

The module adds `point_in_time_recovery { enabled = var.r08_pitr_enabled }`
to the five named tables and the ledger. Existing keys, GSIs, billing mode,
streams and event-source mappings are unchanged. Default `false` preserves
existing workspaces. No retention period is asserted as policy.

Local checks: `terraform fmt -check -recursive`, `terraform validate` and
`git diff --check` pass; validate reports only existing provider deprecation
warnings. No PITR activation or restore was performed.

Status: **READY FOR SEPARATE REVIEW / LIVE ACTIVATION NOT EXECUTED**.
