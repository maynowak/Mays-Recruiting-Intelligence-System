# RIS-R08-DEV2-11E — Cutover Readiness

## Required sequence

1. Obtain separate approval for the clean `1 create / 2 update` plan and
   verify its hash immediately before Apply.
2. Keep the Health Lambdas on the existing byte-identical baseline; do not
   include Health repackaging in R08.
3. Confirm the WorkItems IAM policy update before any worker code can execute.
4. Keep all erasure, receipt, freeze, S3-execution and upload-cutover flags
   disabled.
5. Apply only the approved route, agent artifact and WorkItems IAM change.
6. Run protected API/authorizer smoke checks without creating test data first.
7. Under separate authorization, use isolated synthetic identities and data for
   ApplicationV1, fence, retry/DLQ, privacy and public-erasure tests.
8. Capture Lambda, API Gateway, IAM, DynamoDB, SQS/DLQ and CloudWatch evidence.
9. Stop on any protected-resource action, state drift, authorization failure,
   cross-tenant result, stale-message resurrection or unexpected Health change.

## Preconditions still open

- PITR/backup policy and durable deletion-ledger approval;
- live restore/reconciliation evidence;
- live SQS/DLQ/redrive evidence;
- positive synthetic partner/tenant identity and data-isolation approval;
- explicit Apply and test-data cleanup authorization.

No migration or fence bootstrap is required for the currently empty R08 data
tables. Existing WorkItems must not be bulk-mutated. The worker remains
fail-closed for missing/invalid fence context.

**E2E STATUS: PLANNED / NOT EXECUTED.** No test data, queue message, Lambda
invocation, restore or erasure call was performed.
