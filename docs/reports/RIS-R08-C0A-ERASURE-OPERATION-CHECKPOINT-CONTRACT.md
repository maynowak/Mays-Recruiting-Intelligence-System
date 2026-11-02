# RIS-R08-C0A — ERASURE OPERATION & CHECKPOINT CONTRACT

**Status:** CONTRACT DEFINED / EXECUTION NOT ACTIVATED

## Baseline

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `4f379171d98db66fd59a07565a571f5a7d2d412c`
- Scope: RIS only; no AWS calls, deployment, data deletion, Jobsearch or
  Orders changes
- Receipt journal: remains disabled
- Original untracked files: 39, preserved

## Contract

`agents/ecosystem/privacy_erasure_contract.py` defines `ErasureOperationV1`,
`ErasureProgressV1` and `ErasureCheckpointV1`. The operation is version 1 and
contains:

- operation ID and caller-supplied idempotency key;
- verified user, tenant, partner-application and issuer scope;
- `USER` or single-`CV` scope (with `cvId` required only for `CV`);
- `PENDING`, `RUNNING`, `PARTIAL`, `FAILED`, `COMPLETED` status;
- per-category affected counts, status, retryability, error code and checkpoint;
- created/updated/started/completed timestamps, optimistic version and retry
  count.

`COMPLETED` is terminal and cannot be reached while any present progress item
is not `COMPLETED` or `SKIPPED`. Partial/failed progress requires an error
code. Invalid transitions, missing identity, invalid timestamps, wrong scope
and cross-scope fields fail closed.

Checkpoints contain a phase, state, attempt, timestamp and opaque server-side
references only. Raw DynamoDB keys, S3 keys, continuation tokens, URLs,
credentials, JWTs and CV content are not contract evidence. Checkpoint state is
technical execution state and is deliberately separate from `PrivacyReceiptV1`
and its legal/retention policy.

## DynamoDB persistence contract

`to_dynamodb_item()` is a logical projection only; it does not access AWS.
C1 persistence must implement:

1. conditional create keyed by `operationId` with
   `attribute_not_exists(operationId)`;
2. idempotency lookup bound to tenant and idempotency key;
3. scope key derived from tenant/user/partner/issuer, never from client data;
4. conditional update requiring the stored operation version, with an atomic
   increment of that version;
5. rejection of foreign scope, stale updates, duplicate divergent idempotency
   payloads and invalid status transitions;
6. checkpoint update and operation status update in one transaction where
   possible, otherwise an explicit recoverable ordering and resume rule.

No retention duration is invented. Operation and checkpoint retention remains
`REVIEW_REQUIRED` and is separate from receipt retention. The contract creates
no table and does not activate a writer.

## Race and resume rules

The future C1/C2 executor must acquire a subject deleting guard before profile
enumeration, reject or quarantine new writes, use conditional resource
versions, checkpoint DynamoDB/S3 page progress, and classify unknown outcomes as
indeterminate. A retry may continue only from a valid operation version and
checkpoint. Missing data is idempotently absent only after the relevant scoped
read has succeeded; an unavailable store is not an empty result.

S3 versions/delete markers are a separate phase and must not be represented by
current-object deletion alone. User erasure remains child-first
(ATS → CVSearch → Manual → CV/PDF → system records → UserProfile), while
single-CV CRUD keeps its existing guarded parent-delete semantics.

## Verification

| Check | Result |
|---|---|
| Contract tests | **6 passed** |
| Existing B1/B2A/privacy/API focused regression | **115 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| AWS/DynamoDB access | **None** |

Known environment limits from prior gates remain: DynamoDB Local and `boto3`
are unavailable, and the receipt journal remains disabled. No test was changed
to manufacture a pass.

## Gate decision

- **R08-C0A:** PASS — contract and local validation are defined.
- **R08-C1:** **BLOCKED** — durable persistence, subject write-freeze,
  operation-status authorization, approved retention and receipt policy are
  still required. No erasure implementation is activated by this gate.
