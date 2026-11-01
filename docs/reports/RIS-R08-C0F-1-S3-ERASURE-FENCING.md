# RIS-R08-C0F-1 — S3 ERASURE AUTHORIZATION & FENCING

**Status:** CONTRACT IMPLEMENTED / EXECUTION DISABLED / R08-C0F-2 BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `42b9a86dbe3d2c8ddd668f58b6b8d7e02f971fd3`
- RIS only; no AWS calls, deployment, productive deletion or S3-ticket changes
- Receipt journal and productive erasure persistence remain disabled
- 39 original untracked files preserved

## Phase contract

`privacy_s3_erasure.py` defines a durable S3-erasure phase ledger with:

- USER/CV scope, operation version and freeze version;
- unique attempt/fencing ID;
- `INVENTORY`, `DELETE`, `VERIFY`, `RETRY` and `COMPLETED` phases;
- atomic phase claim/resume conditions;
- durable per-action STARTED/SUCCEEDED/UNKNOWN events;
- opaque pagination cursor handling;
- safe public checkpoint projection without keys, version IDs or URLs.

Every phase-ledger transaction contains the matching active freeze and running
operation conditions before the ledger update. A stale attempt, operation
version, freeze version or scope fails closed. Concurrent claims cannot both
advance the same phase version.

## Orchestration guarantees

`FencedS3ErasureOrchestrator` requires an adapter advertising fencing support.
Before each inventory or delete action it records the action boundary; the
adapter receives the attempt ID and must reject stale attempts. Unknown S3
results become `RETRY`, never `COMPLETED`. Inventory pagination is fully
consumed, including versioned objects and delete markers. A second inventory
must be empty before `COMPLETED` is returned.

Already-issued presigned upload tickets are not assumed revoked. The contract
requires a fresh inventory after deletion, so late uploads remain visible and
prevent false completion. Ticket expiry/revocation itself is not changed in
this gate.

## Deliberate lock boundaries

No production S3 adapter or S3 client was added. The repository and
orchestrator are disabled unless explicit test/operator configuration enables
them, and a non-fencing adapter is rejected. Thus no stale worker can be
silently treated as safe, and no HTTP/API override exists.

The existing G5 `documents.delete_all_for_user` path remains unbound and
continues to be blocked during an authorized-context G5 run. Existing
DynamoDB G5 mutation bindings are unchanged. S3 IAM behavior, real object
version pagination and cross-process fencing remain deployment-level gaps.

## Verification

| Check | Result |
|---|---|
| S3 fencing/phase tests | **6 passed** |
| C0B–C0E-1 regression | **294 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| Real S3/AWS calls | **None** |
| DynamoDB Local | Not available; transaction fakes used |

## Gate decision

- **R08-C0F-1:** PASS for the disabled, fenced phase contract and fake-backed
  orchestration.
- **R08-C0F-2:** **BLOCKED** — no production-capable fenced S3 adapter,
  deployed IAM verification or approved activation exists; S3 mutation remains
  locked by design.
