# RIS-R08-SECURITY-06C — Messaging Review

Conditional retry claims require `FAILED` plus the expected attempt. COMPLETED,
CANCELLED, and DEAD_LETTER suppress duplicate delivery. `POST_UNKNOWN` is now a
terminal error and cannot trigger a blind external POST retry. Conditional
result/failure writes prevent stale workers from overwriting newer or cancelled
attempts.

SQS maxReceiveCount/DLQ state is not synchronously written back to WorkItems;
live DLQ/redrive reconciliation remains an operational Gate-B blocker. Exactly
once external side effects are not claimed.
