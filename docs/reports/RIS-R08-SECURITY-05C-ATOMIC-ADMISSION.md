# RIS-R08-SECURITY-05C — Atomic Admission

Producer and worker registration now use DynamoDB `TransactWriteItems` with a
fence `ConditionCheck` and conditional WorkItem `Put`. The transaction covers
RIS-owned DynamoDB state only; it does not and cannot include SQS delivery,
Lambda execution, external agents, or S3. IAM grants the transaction action
only on the WorkItems table and its indexes. Existing WorkItem rows remain
idempotent and cancellation remains conditional.
