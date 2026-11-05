# RIS-R08-ORCH-02C — SQS Erasure Safety

## Status

**RIS LOCAL ADMISSION HARDENING READY / DLQ AND LIVE REDRIVE OPEN**

No queue, DLQ, IAM, Lambda or Mays-Orders resource was changed.

## Implemented local safety seam

In `agents/runtime/pipeline.py`, a redelivered work item with status
`CANCELLED` is now suppressed before retry or agent execution. A duplicate in
any other non-terminal state is no longer blindly promoted to `RUNNING`;
retry admission requires current `FAILED` status. This closes the local
cancellation-vs-redelivery race for RIS work rows and prevents
`CANCELLED → RUNNING` through the worker retry path.

## Remaining messaging limits

The current RIS Terraform contract has a 300-second visibility timeout,
14-day message/DLQ retention, max receive count 3, batch size 5 and no partial
batch response configuration. Existing evidence does not prove current AWS
state. There is no implemented age/generation fence for all legacy messages,
DLQ replay governance, targeted stale-message reconciliation or live redrive
evidence. An uncertain external Orders POST remains governed by its existing
`POST_UNKNOWN` behavior and is outside this RIS-only change.

Therefore RG-11 is **LOCAL HARDENED / LIVE AND OPERATIONAL SAFETY BLOCKED**.
No blanket queue purge is proposed.
