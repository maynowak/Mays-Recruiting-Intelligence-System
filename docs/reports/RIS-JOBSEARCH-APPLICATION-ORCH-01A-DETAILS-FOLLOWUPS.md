# RIS-JOBSEARCH-APPLICATION-ORCH-01A — Details and Follow-ups

## Result

```text
PACKAGE A — IMPLEMENTED LOCALLY / MOTO RUNTIME EVIDENCE OPEN
```

The existing ApplicationV1 create/PATCH path now validates and persists:

- `applicationDate`
- `applicationChannel`
- `contact.name`, `contact.email`, `contact.phone`
- `notes`
- `salary.expectation` and `salary.offer`
- `followUp.dueOn`, `note`, `status`, `completedAt`

PATCH semantics are explicit: omitted fields remain unchanged; `null` removes
optional values. Follow-up validation uses real calendar dates, requires
`completedAt` for `completed`, rejects `completedAt` for `open`, and never
changes application status/stage.

Existing GAP-01 behavior is preserved. Detail and follow-up mutations use the
existing `expectedVersion` and owner-scoped conditional write path. History and
cover-letter mutations also advance the parent version transactionally.

## Evidence

- Contract/detail validation: **11 passed** in the initial package gate.
- Combined local status/contract/API subset: **15 passed**.
- Full Application selection after integration: **30 passed, 11 skipped**.
- Python compilation and `git diff --check`: PASS.
- Moto-dependent repository/E2E tests remain skipped because `boto3` is not
  installed. No DynamoDB runtime round-trip is claimed.

## Commits

- `e3f352d` — contract and validation
- `8db5bbf` — repository details/follow-up persistence

Package A is locally implemented but not release-ready without Moto/runtime
evidence and the later live gates.
