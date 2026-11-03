# RIS-JOBSEARCH-APPLICATION-ORCH-03B — Concurrency and Erasure

## Result: LOCAL PASS WITH EXPLICIT CONSISTENCY LIMITS

Implemented hardening:

- idempotency records are removed together with the application and are
  reusable after delete;
- stale delete requires the expected parent version;
- delete places an internal `IN_PROGRESS` marker before child deletion;
- normal reads/writes reject records marked for erasure;
- child deletion consumes all query pages and batches at 100 actions;
- a failure between batches can be retried with the original expected version;
- typed `feedback`, `interview` and `note` history events are validated while
  legacy `type` events remain readable/accepted for compatibility.

## Evidence

- Follow-up/version/stale-delete runtime suite: **13 passed**.
- Application repository plus E2E runtime subset: **15 passed**.
- The 105-child test injects a failure on the second deletion batch and then
  successfully resumes and removes the application.
- Idempotency cleanup/reuse test passed.

## Non-claims

Multi-batch deletion is resumable, not globally atomic. A partial failure can
leave a marked parent and remaining children until retry. The marker blocks
normal application mutations, but a durable external erasure checkpoint and
retention/backup semantics remain the responsibility of the privacy
orchestrator and RIS-DEV.
