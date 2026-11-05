# RIS-R08-ORCH-02A — Recovery Contract

## Status

**LOCAL CONTRACT READY / LIVE RECOVERY BLOCKED**

No AWS, Terraform state, PITR mutation, restore or deployment was performed.

## Implemented local contract

`agents/ecosystem/privacy_recovery_contract.py` defines version-1
`RecoveryPlanV1` and `RecoveryCheckpointV1`. It permits only an isolated
`STAGING` target and models these phases:

`RESTORE_STAGING` → `REPLAY_DELETIONS` → `VERIFY_CREDENTIAL_REVOCATION` →
`VERIFY_SUBJECT_INACCESSIBILITY` → `RECONCILED` → `PROMOTION_GATE`.

The in-memory `LocalRecoveryRepository` provides idempotent create, opaque
reference validation and expected-version checkpoint CAS. Promotion eligibility
is false until every phase is complete. Sensitive backup URLs/ARNs, keys,
tokens and content are rejected. It has no boto3 import, AWS client or runtime
activation.

## Boundaries

- A local plan is not evidence that DynamoDB PITR is enabled.
- Reconciliation does not automatically delete or reactivate any data.
- Retention, backup expiry and deletion-ledger retention remain
  `REVIEW_REQUIRED`; no seven-year period was implemented.
- Receipts remain separate evidence and are never used as deletion authority.

## Remaining RG-10 blockers

Executable PITR declarations, an approved durable ledger, authorized staging
restore, provider backup-expiry evidence and live promotion verification remain
open. RG-10 therefore remains **RED/BLOCKED**.
