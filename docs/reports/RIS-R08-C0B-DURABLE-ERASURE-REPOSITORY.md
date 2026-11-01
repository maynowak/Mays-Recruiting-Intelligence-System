# RIS-R08-C0B — DURABLE ERASURE OPERATION REPOSITORY

**Status:** IMPLEMENTED / FAIL-CLOSED BY DEFAULT

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `a1640d56267223a7d3a013a1ec178ae997289206`
- RIS only; no deletion, AWS access, deployment, Terraform, Jobsearch or
  Orders changes
- Receipt journal remains disabled
- 39 original untracked files preserved

## Repository guarantees

`agents/ecosystem/privacy_erasure_repository.py` implements the C0A contract
using an injected DynamoDB-shaped table. It creates no boto3 client and is
disabled unless `ERASURE_OPERATION_REPOSITORY_ENABLED=true` is explicitly
passed/configured. Disabled or unavailable storage fails closed with an
operator-safe error.

Implemented operations:

- create with an atomic operation item plus idempotency marker transaction;
- exact idempotent replay for the same scoped request;
- conflict for reuse of an idempotency key with a different request;
- point-read get with exact user/tenant/partner/issuer scope checks;
- compare-and-swap operation updates using resource type, identity and
  expected version;
- checkpoint/progress save and point-read;
- resume of `PENDING`, `PARTIAL` and `FAILED` operations to `RUNNING`;
- no resume of `COMPLETED` operations;
- no table scan or receipt-journal interaction.

A concurrent create uses a conditional transaction and re-reads the marker
only after a conditional race. A concurrent update fails with a version
conflict rather than overwriting progress. Checkpoints remain inside the
operation item and use the C0A opaque-reference model; raw DynamoDB/S3 keys,
tokens, URLs, credentials and CV content are not emitted by the contract.

`ErasureWriteFreezeV1` is also available as a contract for the next gate. C0B
does not enforce write blocking and does not modify upload/profile handlers.

## Retention and activation

No operation/checkpoint retention period is invented. Retention remains
`REVIEW_REQUIRED`. The repository is fail-closed until that policy and the
operation table/IAM configuration are approved. This is technical persistence,
not a Privacy Receipt and not erasure evidence.

## Verification

| Check | Result |
|---|---|
| C0A contract tests | **6 passed** |
| C0B repository tests | **6 passed** |
| Combined focused Privacy/API regression | **126 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| DynamoDB Local | Not available; conditional fake used |

The fake verifies conditional create/replay, version conflicts, checkpoint
resume, scope isolation and scan absence. Real DynamoDB Local semantics,
throughput and IAM behavior remain unverified because DynamoDB Local and
`boto3` are unavailable in this environment.

## Gate decision

- **R08-C0B:** PASS — durable repository contract and fail-closed adapter are
  locally verified.
- **R08-C0C Write-Freeze Readiness:** **BLOCKED** — the freeze is only a
  prepared contract; no active subject guard or upload/profile write
  enforcement exists yet. C0C must add and test that enforcement before any
  erasure execution can be considered.
