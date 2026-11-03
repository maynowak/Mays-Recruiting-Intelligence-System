# RIS-JOBSEARCH-APPLICATION-ORCH-02B — Repository Runtime

## Result: PASS for covered local runtime paths; residual limits documented

Moto-backed verification exercised create, idempotent retry, status/stage,
PATCH, owner isolation, signed cursors, history, cover-letter versions,
export, delete and erasure harness behavior.

Runtime hardening committed in `5a67804`:

- low-level transaction requests use explicit `TypeSerializer` values and a
  dedicated DynamoDB client;
- export and delete consume all child query pages;
- delete batches transactions at DynamoDB's 100-action limit and conditions
  the META delete on owner plus expected version;
- metrics use the UTC date boundary;
- privacy inspect/export now traverse all ApplicationV1 list pages.

Additional runtime tests committed in `76848a1` and `e065a9f` cover follow-up
create/complete/reopen/remove, stale delete rejection, and Moto metrics across
owner-scoped records.

## Atomicity statement

Create, status, history append, and cover-letter append use DynamoDB
transactions with parent version conditions. Detail PATCH uses one conditional
`PutItem`. Delete is version-conditional per transaction batch, but multi-batch
erasure is not one transactionally consistent snapshot. Idempotency records are
still stored in a separate partition and are not removed by application delete.
These are explicit residual integration/privacy items, not claimed as solved.

## Evidence

- `tests/test_application_repository.py` + `tests/test_application_e2e_harness.py`:
  **11 passed**.
- Complete ApplicationV1 selection: **43 passed**.
- No Moto skip remains in the ApplicationV1 selection.
