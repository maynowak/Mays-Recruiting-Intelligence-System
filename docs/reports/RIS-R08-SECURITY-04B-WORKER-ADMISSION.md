# RIS-R08-SECURITY-04B — Worker Admission

## Result: BLOCKED for production / hardened locally

The worker now performs a final current-row check immediately before agent
execution and supports an injected `erasure_admission(work, phase)` callback at
`before_registration` and `before_execution`. Retry promotion is conditional on
current `FAILED` status and expected attempt number.

However, the production Lambda path currently invokes `process_record` without
a durable erasure-fence resolver. Therefore a stale message whose work row is
already absent can still enter the existing registration fallback. A local
callback or in-memory ledger is not sufficient proof of production resurrection
safety. FIX-01 remains a merge blocker until a durable RIS-owned fence is
selected and wired with fail-closed lookup/error behavior.

Already-started external side effects cannot be atomically rolled back across
SQS, DynamoDB and external agents. The final admission boundary prevents a
known cancellation before execution; it does not claim atomic cancellation of
an agent already executing.
