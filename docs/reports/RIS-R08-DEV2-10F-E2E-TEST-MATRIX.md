# RIS-R08-DEV2-10F — AWS E2E Test Matrix

No test data, Lambda invocation, queue message, DynamoDB write, erasure call,
restore or redrive was performed.

| Test | Preconditions | Synthetic action | Expected evidence | Cleanup/approval |
|---|---|---|---|---|
| E2E-01 Auth | Isolated Cognito test user/client and JWT | Call protected route with valid/invalid JWT | 2xx vs 401/403, issuer/audience/tenant claims | Auth owner approval; delete test identity separately |
| E2E-02 ApplicationV1 | Isolated tenant/partner registry and test subject | Create/read/update/list synthetic application pages | Owner/tenant isolation and complete pagination | Explicit data cleanup approval |
| E2E-03 Erasure | Synthetic subject with applications; flags and scope approved | POST `/me/erasure`; inject controlled partial failure/resume | Application phase required; 207 until complete; no false completion | Erasure owner approval; verify all stores |
| E2E-04 Fence | Synthetic WorkItem and subject | Submit, fence, redeliver old message | No resurrection; final admission blocked | Queue/DynamoDB mutation approval |
| E2E-05 SQS worker | Isolated queue/subject and agent stub | Duplicate, retry-CAS, terminal failure, DLQ | One execution, correct retry/dead-letter state | SQS send/receive/delete/redrive approval |
| E2E-06 Recovery | Separate restore sandbox and backup evidence | Restore simulation and ledger reconciliation | Reappeared data detected; no automatic reactivation | PITR/restore approval; currently blocked |
| E2E-07 Privacy API | Synthetic authenticated subject | Inspect/export and cache-header checks | Self-only data, no-store/private, cross-tenant denial | Read-only HTTP first; no erasure activation |
| E2E-08 Operations | Deployed artifact and alarms | Observe logs/metrics/IAM denials/queue metrics | CloudWatch and alarm evidence | No secrets/PII in logs; operations approval |

The matrix is **READY as a test plan**, not as permission to execute. All
mutating rows require isolated identities, explicit test-data ownership,
cleanup evidence and separate authorization.
