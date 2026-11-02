# RIS-R08-C1B-0 — DOCUMENT ERASURE INTEGRATION

**Status:** LOCAL SYNTHETIC SIMULATION GO / REAL INTEGRATION BLOCKED

## Baseline and boundaries

- Baseline: `063133a3ec423a6088a8970a34ed04751aa8a642`
- C1A, C0F-2A/B/C/D and C0F-2E-G0 contracts reviewed
- RIS only; no AWS calls, real S3 mutation, deployment or Terraform change
- Erasure persistence and receipt journal remain governed by their existing
  disabled-by-default switches
- 39 pre-existing untracked files preserved

## Integration design

`DocumentErasureIntegration` connects the existing C1A profile executor to the
existing `FencedS3ErasureOrchestrator`; it does not create a second erasure
engine.

1. C1A completes the USER/CV profile hierarchy first.
2. CVDocument records are paginated and their document IDs are retained as
   internal references. Missing document IDs are a hard `PARTIAL` blocker.
3. A scoped wrapper around the injected C0F fencing adapter rejects any S3
   version/delete-marker that has no retained document reference. It never
   silently ignores an object.
4. C0F performs inventory, explicit-version/delete-marker deletion and full
   re-inventory through the injected fake adapter.
5. Only after C0F reports `COMPLETED` and final quiescence is proven are
   CVDocument metadata records deleted using the existing conditional profile
   repository path.
6. Other required G5 categories remain open; therefore successful local
   document simulation still returns overall `PARTIAL`, never a false
   `COMPLETED` operation.

The existing S3 phase read/resume path now accepts operation-version advances
between retry boundaries and refreshes the phase ledger's current operation and
freeze versions on retry claim. An `ACTION_STARTED` crash boundary can resume
through the existing retry claim instead of being treated as success.

## Failure and resume behavior

- Unknown S3 results leave metadata intact and produce `PARTIAL`/
  `DOCUMENT_S3_RETRY`.
- Stale fencing, missing quiescence, unmapped objects and missing document
  references fail closed and do not delete metadata.
- Retry resumes the existing operation and C0F phase identity; it does not
  create a parallel operation.
- Version IDs and delete markers are deleted only through the injected adapter's
  explicit-version method.
- Synthetic fake-S3 results are not production evidence and do not resolve the
  C0F-2E distributed-fencing or C0F-2D legacy-ticket blockers.

## Verification

| Check | Result |
|---|---|
| C1B integration tests | **6 passed** |
| C1A + C0F focused tests | **38 passed** |
| C0B–C1B regression subset | **318 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| AWS/S3 calls | **None** |

## Gate decisions

- **C1B Simulation:** **GO** — synthetic USER/CV document flow, pagination,
  versions, delete markers, re-inventory, retry and metadata-release gates are
  locally verified.
- **C1B Real Integration:** **BLOCKED** — no approved/verified distributed S3
  fencing, production quiescence, IAM/Object-Lock evidence or legacy-ticket
  cutover proof.
- **Production:** **BLOCKED** — existing C0F-2D/C0F-2E blockers remain and
  productive erasure persistence is disabled.
