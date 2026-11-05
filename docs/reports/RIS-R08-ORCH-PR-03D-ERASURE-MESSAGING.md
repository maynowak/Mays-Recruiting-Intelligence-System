# RIS-R08-ORCH-PR-03D — Erasure and Messaging Review

## Result: BLOCKED

| Finding | Severity | Datei/Zeile | Szenario | Empfehlung | Merge-Blocker |
|---|---|---|---|---|---|
| ApplicationV1 resume hides `IN_PROGRESS` records | HIGH | `privacy_profile_erasure.py:379-406`; `application_repository.py:250-253` | Failed delete leaves an application in progress; resumed list excludes it | Reconcile deleting records/final absence before completion | Yes |
| Retry race | HIGH | `agents/runtime/pipeline.py:279-300,385-398` | Two deliveries can promote one FAILED row without conditional update | Conditional status/version/attempt admission | Yes |
| Missing-row stale-message fence | CRITICAL | `agents/runtime/pipeline.py:226-236` | Erasure removes row; queued message creates new RUNNING row | Durable subject-level erasure fence before registration | Yes |
| Running-worker cancellation race | HIGH | `agents/runtime/pipeline.py:400-468` | Already admitted worker executes without final check | Execution-time freeze/subject check | Yes |
| Non-retryable failures remain FAILED | HIGH | `agents/runtime/pipeline.py:444-466,487-503` | Redelivery may rerun permanent denial/error | Persist retryability/terminal rejection | Yes |
| Whole-batch redelivery | MEDIUM | `lambda/handler.py:160-191`; `terraform/modules/lambda/main.tf:619-623` | One failure retries successful records | Partial batch failure or explicit fencing | No |
| Shared DLQ governance | LOW/MEDIUM | `terraform/modules/sqs*` | Shared DLQ/redrive bounds lack review evidence | Document and validate redrive isolation | No |

The existing `CANCELLED` suppression is useful but insufficient for the
missing-row, running-worker and conditional-retry races. No queue or Orders
resource was modified.
