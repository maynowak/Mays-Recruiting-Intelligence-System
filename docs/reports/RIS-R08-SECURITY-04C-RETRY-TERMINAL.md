# RIS-R08-SECURITY-04C — Retry and Terminal Failure

## Result: PASS LOCAL

`_start_retry_attempt()` now uses a conditional update requiring both
`status = FAILED` and the observed `attempt_no`. A conditional loser is
suppressed rather than executing a second attempt.

Permanent entitlement denials and permanent agent error types are persisted as
`DEAD_LETTER`; redelivery is terminally suppressed. Transient exceptions remain
`FAILED` and retryable under the existing bounded SQS/DLQ policy.

Tests cover retry after transient failure, terminal dead-letter suppression,
permanent `CONFLICT` redelivery and existing `COMPLETED`/`CANCELLED` behavior.
Actual concurrent DynamoDB behavior remains unverified because AWS is out of
scope; the production conditional expression is present.
