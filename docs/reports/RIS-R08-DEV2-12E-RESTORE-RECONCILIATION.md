# RIS-R08-DEV2-12E — Restore Reconciliation

The local contract requires restore into separate STAGING, current-ledger
reconciliation, replay/fencing of erased subjects, credential revocation and
complete checkpoints before promotion. A restored record matching a later
`ABSENT_AFTER_ERASURE` entry produces `RECONCILIATION_REQUIRED`; missing,
corrupt, stale or unavailable ledger evidence is fail-closed. Cross-tenant or
issuer mismatch is not accepted as valid evidence. Interrupted work must be
resumed from a valid CAS checkpoint, not marked complete by inference.

Covered locally: restored deleted subject/resource, ledger conflict,
unavailable or incomplete evidence, invalid restore/checkpoint and promotion
with open evidence. No AWS restore, backup creation, SQS operation or data
mutation was run.

The separate ledger reduces the risk of restoring deletion knowledge with the
application domain, but a same-account table is not an absolute disaster or
administrator isolation boundary. Promotion therefore remains a human and
evidence gate.

Status: **VERIFIED LOCAL / BLOCKED FOR LIVE RESTORE**.
