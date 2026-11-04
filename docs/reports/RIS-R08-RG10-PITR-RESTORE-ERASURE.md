# RIS-R08-RG10 — PITR, Backup, Restore and Erasure

## Result: RED / BLOCKED — LOCAL ORCH-02 CONTRACTS ADDED

No AWS access was performed. This assessment compares executable Terraform and
local contracts only.

## Findings

1. `terraform/modules/dynamodb/main.tf` declares the RIS DynamoDB tables but
   no `point_in_time_recovery` block was found for the relevant tables,
   including profiles, work items, credentials, applications, receipt and
   erasure tables. The backup contract's “PITR enabled per table” is a
   requirement/design statement, not current executable evidence.
2. No executable `deletion-ledger` table, repository, restore executor or
   replay/reconciliation test was found.
3. `BACKUP_RESTORE_PRIVACY_CONTRACT.md` requires restore to staging, deletion
   ledger replay, revoked-credential verification and promotion only after
   deletion application. These acceptance steps are not implemented.
4. S3 version/delete-marker purge is covered by synthetic Fake-S3 tests only;
   versioning is enabled and no lifecycle rule was observed in the documents
   module. Distributed fencing, legacy upload-ticket cutover, IAM/Object Lock
   and live purge remain open.
5. The seven-year deletion-ledger statement is a contract proposal for a
   distinct future ledger. It is not an approved PrivacyReceipt retention
   period. Receipt retention remains `BLOCKED / REVIEW_REQUIRED` with journal
   writes disabled.
6. ORCH-02 adds local-only `RecoveryPlanV1`, CAS checkpoints, opaque deletion
   evidence and restore detection. These components do not claim PITR, durable
   ledger persistence or live restore readiness.

## Local evidence

- R08-C1A/C1B synthetic profile/document erasure: local PASS, including
  pagination, version/delete-marker fake handling, partial and resume behavior.
- R08-C0F fencing analysis: explicitly says cross-service atomic fencing cannot
  be claimed with current primitives.
- No evidence proves current AWS PITR, backup expiry, restore replay or
  post-restore subject suppression.

## Required decisions/evidence

| Item | Owner | Required evidence | Status |
|---|---|---|---|
| PITR per relevant table | Platform/RIS-DEV | Approved Terraform and authorized read-only live verification | OPEN |
| Backup expiry | Privacy/Legal/Platform | Approved schedule and provider retention artifact | REVIEW REQUIRED |
| Deletion ledger | Privacy/Platform | Minimal schema, authority, retention decision and implementation | BLOCKED |
| Restore reconciliation | Platform/Privacy | Isolated staging restore, ledger replay, revoked-credential check, promotion gate | BLOCKED |
| S3 version purge | RIS-DEV/Security | Version/delete-marker inventory and IAM/Object Lock evidence | BLOCKED |

Gate B remains NO-GO for Apply.
