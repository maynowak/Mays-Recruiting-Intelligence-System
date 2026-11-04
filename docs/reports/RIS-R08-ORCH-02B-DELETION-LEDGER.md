# RIS-R08-ORCH-02B — Deletion Ledger

## Status

**LOCAL SYNTHETIC CONTRACT READY / DURABLE PRODUCTION LEDGER BLOCKED**

`agents/ecosystem/privacy_deletion_ledger.py` provides an in-memory,
version-1-compatible local ledger. Each entry binds user, tenant, partner
application, issuer and scope. Resource references are SHA-256 digests only;
CV content, S3 keys/version IDs, URLs, credentials and tokens are not stored.

## Safety behavior

- Capture is idempotent; divergent replay is a conflict.
- Unknown resource types, invalid scope and unknown inventory fail closed.
- `mark_erasure_result(..., complete=False)` cannot mark absence.
- Restore of a previously erased scoped resource returns
  `RECONCILIATION_REQUIRED` and never mutates the restored fixture.
- Missing or foreign ledger evidence cannot satisfy reconciliation.
- Cross-tenant, cross-partner and cross-issuer inventory is not attributed to
  another operation.

The ledger is intentionally not wired to DynamoDB or a public handler. The
existing R08-C operation, freeze, checkpoint and S3 fencing components remain
the leading erasure architecture; this module supplies local evidence
semantics only and is not a second erasure engine.

## Completion integration

`ErasureOperationV1.transition(COMPLETED)` now requires every standard
`ERASURE_CATEGORIES` entry to be present and complete/skipped. An explicit
reduced category set is accepted only by the existing synthetic C1B local
executor. It is not a general production bypass.

RG-10 remains **BLOCKED** pending durable ledger design/approval, restore replay
and live backup evidence.
