# RIS-R08-C1A — RESUMABLE PROFILE-ONLY ERASURE

**Status:** LOCAL PROFILE-ONLY GO / FULL ERASURE PENDING

## Scope and boundary

- Baseline: `8550cfa4348c010ff21707f3c98e28dfd0ae2fac`
- RIS only; no AWS/S3 calls, deployment, productive activation or receipt
  journal activation
- Existing C0A operation/checkpoint contracts and C0E G5 profile repository
  delete paths are reused; no second deletion engine was introduced
- 39 pre-existing untracked files preserved

`ProfileOnlyErasureExecutor` is a thin orchestration layer. It receives an
already authorized `ErasureExecutionContextV1`, validates operation identity and
version before each mutation, and uses `PartnerProfileRepository` for all
profile reads and conditional deletes.

## Execution order

USER scope processes paginated:

1. `ATSSearchProfile` leaf records;
2. `CVSearchProfile` parents;
3. `ManualSearchProfile` records; and
4. `UserProfile`, through the existing transactional delete binding supplied by
   the caller.

CV scope walks only the selected CV's `CVSearchProfile` children and their
`ATSSearchProfile` children, then removes those profile records. Other users
and CVs are not selected.

`CVDocument` records are never deleted by C1A. Their metadata, document IDs,
and S3 references remain available to the separate document/S3 phase.

## Resume and safety properties

- Every list uses the existing repository pagination APIs.
- Opaque base64 JSON cursor references are stored only in the existing
  checkpoint contract; raw DynamoDB keys are not exposed publicly.
- A checkpoint is persisted after each confirmed profile delete and at each
  page boundary.
- Replay treats already absent records as idempotent and reuses conditional
  repository deletes for concurrent mutation detection.
- Freeze/context loss or version conflicts fail closed and persist the last
  safe point as partial where the checkpoint CAS remains available.
- Resume uses the existing operation repository's versioned `resume` path;
  stale execution contexts are rejected.
- CV search parents are deleted only after their ATS children. The CVDocument
  parent is intentionally retained.
- USER `UserProfile` deletion runs after profile references have been
  checkpointed; if its existing transactional binding is unavailable, that
  category remains partial rather than being guessed successful.

## Completion semantics

The `cvDocuments` category is always `PARTIAL` with
`DOCUMENT_S3_PHASE_PENDING` and `retryable=true`. Consequently C1A never
transitions the overall operation to `COMPLETED`. A later document/S3 phase
must resolve retained references and update the existing operation contract.

## Local verification

Transaction-fake tests cover USER/CV isolation, leaf-before-parent ordering,
pagination, checkpoint replay/resume, retained documents, skipped user scope
for CV operations, and pending completion semantics.

| Check | Result |
|---|---|
| C1A profile-only tests | **3 passed** |
| C0F, freeze and profile regression subset | **312 passed, 252 subtests** |
| AWS/S3 calls | **None** |
| DynamoDB Local | unavailable; transaction fakes used |

## Gate decision

- **R08-C1A local profile-only:** **GO** — implementation is locally
  resumable and fail-closed within the existing G5/operation contracts.
- **R08-C1B local:** **BLOCKED** until the separate document/S3 phase resolves
  retained CVDocument references and the full operation can be assessed.
- **Production:** **BLOCKED** by the unresolved distributed S3 fencing,
  legacy upload-ticket evidence, IAM/Object-Lock verification and disabled
  productive erasure persistence.
