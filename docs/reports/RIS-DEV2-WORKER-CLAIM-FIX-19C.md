# RIS-DEV2-WORKER-CLAIM-FIX-19C

**Datum:** 2026-11-26

**Baseline:** Feature branch `feature/ris-analysis-integration-07`; initial HEAD/Remote `d7dfe455a5715e47d8acf34458c362c79af05d76`.

**Scope:** Local source fix and regression only. No AWS operation, deployment, Terraform plan, recovery, Mays-Orders source change or upgrade.

## Ergebnis

- Root cause: `VERIFIED / CLAIM_WITHOUT_EXECUTION` (Forensics 19B).
- Local fix: **VERIFIED**; first conditional `QUEUED → RUNNING` claim now proceeds directly to execution. FAILED retry claim runs only in the FAILED retry branch.
- RED→GREEN: focused regression failed before the source fix because updates were `QUEUED` followed by an invalid `FAILED` retry claim and the agent was not called; it passes after the fix.
- Recovery: `RECOVERY_PATH=NOT_AVAILABLE`. The code has no supported stale-RUNNING resume/lease-expiry interface. The existing RUNNING duplicate guard remains; this fix does not recover or reset old RUNNING items.

## 1. Control-flow / transition matrix

| Observed row state at worker admission | Conditional operation | Successful result | Lost/invalid condition | Execution behavior |
|---|---|---|---|---|
| No pre-existing row | `_register_processing`: conditional Put (`attribute_not_exists(workId)`) creating attempt 1, RUNNING | Newly registered RUNNING row | Existing-row condition returns the existing row and enters duplicate-state handling | New row continues toward execution; existing row follows its state branch |
| Existing `QUEUED` | `_claim_queued_work`: conditional update requiring `status=QUEUED`; set RUNNING, `attempt_no=1` | The claimed item continues to entitlement/fence checks and execution; **no retry claim** | Conditional loss returns duplicate/suppressed RUNNING; no second execution | Initial attempt only |
| Existing `FAILED` | `_start_retry_attempt`: conditional update requiring `status=FAILED AND attempt_no=:expectedAttempt`; increment attempt, assign execution/attempt IDs, remove error | Retry attempt continues to execution | `_RetryClaimLost` returns duplicate/suppressed RUNNING; no agent execution | Retry attempt only |
| Existing `RUNNING` | No write/claim | Not applicable | Existing item is treated as another delivery's active run | Duplicate suppressed; no re-execution or stale recovery |
| `COMPLETED` | No new attempt | Existing result may be re-forwarded through existing deterministic delivery/idempotency path | No new execution | Terminal duplicate |
| `DEAD_LETTER` | No new attempt | Existing failure may be re-forwarded through existing deterministic delivery/idempotency path | No new execution | Terminal duplicate |
| `CANCELLED` | Erasure/terminal suppression; no claim | Not applicable | Suppressed | No execution |
| Any other state | No valid claim | Not applicable | `WORK_ADMISSION_STATE_UNSAFE` | No execution |

Terminal writes retain their existing `status=RUNNING AND attempt_no=:attempt` conditional guard. Result persistence sets `COMPLETED`; failure persistence sets `FAILED` or terminal `DEAD_LETTER` according to the existing error contract. Transient failures continue to raise for SQS redelivery; stable result publication/idempotency logic is unchanged. No new state transition or schema was introduced.

### Shared worker scope

`lambda/handler.py` routes SQS work records to the shared `agents.runtime.pipeline.process_record`. Agent selection remains registry/eligibility/router-driven. The pipeline is shared by the registered reference, Orders function, development dummies, JobSearch, ATS, addition, CV/job parser and analysis agents. The fix therefore applies to all worker agent types using this common admission path; it does not change their domain handlers. Dispatch ingress only creates/enqueues work and does not call this worker pipeline.

## 2. RED regression and minimal fix

The new test `TestWorkerPipeline.test_existing_queued_item_claim_executes_without_retry_claim` starts with an ingress-created persisted QUEUED item, lets real registry resolution/selection and the conditional table seam run, and asserts one execution, attempt 1, completion, and absence of a FAILED retry condition.

**RED before source change:**

```text
expected conditions: ['#status = :queued']
observed conditions: ['#status = :queued',
                      '#status = :failed AND attempt_no = :expectedAttempt']
agent calls: []
1 failed
```

This fails against the original implementation for the intended bug, not a bypassed mock path.

The fix in `agents/runtime/pipeline.py` is deliberately small: make FAILED retry claiming an `elif status == FAILED` branch, and raise the existing unsafe-state error for all other states. The successful QUEUED claim now falls through directly to shared execution. Atomics, duplicate guards, attempt/version conditions and terminal-state behavior are unchanged.

Additional tests cover lost initial claim, existing RUNNING suppression without mutation/re-execution, lost retry claim, and two concurrent FAILED retry claims (exactly one CAS winner). Existing pipeline tests cover completed/terminal duplicates, missing agent, successful execution, failure, result forwarding and sender failure.

## 3. Commits

| Step | Commit | Content |
|---|---|---|
| 19B evidence commit | `3bddf6dafaae4551fbfffcffad0ac622775c8d35` | Verified forensic trace/artifact report and audit log |
| Source + regression | `c6e996a8f22afe9b248094cf278a0c2f31846782` | Minimal worker claim control-flow fix and lifecycle tests |
| Bundle pin | `46e98c30a07eca53d91646429e5fc78e36fdc02f` | Pin reviewed local worker artifact hash; explicitly not a deployed bundle |

Each commit was pushed to `feature/ris-analysis-integration-07`; remote HEAD matched after each push. Mays-Orders repository was read-only and unchanged.

## 4. Local recovery readiness

Source search found no worker recovery API, stale-`RUNNING` lease expiry, owner-claim record, resume operation, or controlled RUNNING-to-new-attempt transition. Retry is available only from FAILED; the SQS redrive policy bounds delivery attempts but does not safely reclaim an already RUNNING DynamoDB item. The fix must not be interpreted as recovery of the Canary WorkItem.

**Recommendation:** separate `19E — RIS-CANARY-WORKITEM-RECOVERY-DESIGN`, starting with a non-mutating design/review. It must define an auditable ownership/lease/fencing and idempotent-result protocol before any write/replay is proposed. Keep the old WorkItem and Order untouched until a separately approved recovery execution explicitly names them.

## 5. Safety record

Source files changed: `agents/runtime/pipeline.py`, `tests/test_worker_pipeline.py`, and artifact hash assertion in `tests/test_analysis_ecosystem_wiring.py`. No infrastructure/runtime configuration changes. `MODE=true` was not changed. No AWS mutations, live invocations, redrives, WorkItem writes, tests against AWS, Terraform plan/apply, Mays-Orders changes, or main merge.
