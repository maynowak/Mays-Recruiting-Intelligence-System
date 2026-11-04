# RIS-R08-DEV2-12D — Ledger Migration

No historical ledger migration was executed. Existing erasure-operation,
WorkItems, ApplicationV1 and profile rows do not provide sufficient
authoritative, complete deletion evidence to invent past ledger entries.

Proposed treatment:

* Existing erasure operations may be imported only after identity scope,
  operation fingerprint and terminal evidence are independently verified.
* Historical WorkItems and ApplicationV1 data without a verified erasure
  event remain `UNKNOWN`, never synthetic `ABSENT`.
* Missing tenant/partner/issuer references require quarantine and manual
  resolution; they cannot be reconstructed from guesses.
* Promotion remains blocked while any restore scope has unresolved deletion
  evidence.
* New operations must record capture/fence evidence before erasure proceeds,
  category outcomes before completion, and reconciliation evidence before
  promotion. Cross-system atomicity across S3, SQS and DynamoDB is not
  claimed.

Status: **BLOCKED pending migration inventory, policy approval and controlled
STAGING validation**.
