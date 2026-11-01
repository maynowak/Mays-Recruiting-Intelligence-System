# RIS-R08-C0F-2E-G0 — DISTRIBUTED S3 FENCING FEASIBILITY

**Status:** LOCAL ANALYSIS GO / DISTRIBUTED S3 EXECUTION BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `4d5781979a533013f5d30cdee60b314ccf9198d1`
- C0F-1 through C0F-2D reviewed
- No AWS calls, S3 mutation, deployment or IAM/Terraform change
- Receipt journal and productive erasure remain disabled
- 39 original untracked files preserved

## Existing controls

The current design has four useful but non-equivalent controls:

1. DynamoDB CAS on operation and phase versions prevents two workers from
   advancing the same durable checkpoint.
2. The local quiescence lease is exclusive and rejects a replaced attempt.
3. Per-phase and per-action condition checks require the expected active freeze,
   operation ID, scope and versions.
4. Final version/delete-marker re-inventory prevents a false empty result when
   a late object is observable.

The injected adapter also checks its attempt immediately before an inventory or
version delete. These controls are intentionally not described as an atomic
DynamoDB/S3 fence.

## Race scenarios

### Worker A loses its lease during S3

A can pass the callback and then pause before or during the S3 request. A
lease change or operation CAS cannot cancel that already-issued request. The
request may succeed after A is stale. The phase ledger rejects A's later
checkpoint, and the final inventory can expose the resulting object state, but
it cannot prove that the stale request was never accepted.

### Worker B takes over

B can claim the next phase only after a versioned retry boundary. A's durable
checkpoint cannot be overwritten. This prevents duplicate phase advancement,
not duplicate external S3 side effects. B must re-inventory before deleting
and must use a new attempt token.

### S3 timeout with unknown result

The design records `UNKNOWN`/`RETRY` and never advances to `COMPLETED`.
Resume re-inventories versions and delete markers. A delete may nevertheless
have succeeded remotely; retrying by explicit `VersionId` is idempotent at the
object-version target, subject to S3/Object-Lock behavior.

### Late upload after inventory or apparent completion

An unrevoked presigned URL can create a new version after inventory. Ticket
quiescence and the mandatory final inventory detect observable late objects,
but cannot prevent the upload or make the earlier inventory atomic with it.
Unknown legacy tickets therefore remain a hard cutover blocker.

### Restart between delete and checkpoint

The durable action boundary is either before the delete or after a confirmed
result. A crash between them yields an unknown outcome, not success. Resume
re-inventories and retries with a new fenced attempt; stale checkpoint writes
fail CAS. This is safe for completion accounting, but not proof that no stale
external request ran.

## Feasibility decision

Complete cross-service fencing is not achievable with the current primitives:
S3 does not accept the DynamoDB attempt token as a conditional write fence,
presigned URLs cannot be revoked by the ledger, and the request boundary is
outside the DynamoDB transaction. Additional S3-side controls would be
required, such as a service-mediated upload path without bearer presigned
URLs, an S3-native policy/state mechanism that enforces the attempt, and
verified versioned-delete IAM. Object Lock, legal holds, bucket Deny rules and
unknown legacy tickets remain independent blockers.

No implementation can safely claim production distributed fencing until those
controls are designed and verified. The current adapter must remain disabled.

## Minimal next implementation plan

1. Keep the current CAS/lease/attempt/checkpoint protocol and its fail-closed
   unknown-result handling.
2. Complete durable ticket cutover evidence; any unknown legacy issuer blocks
   quiescence.
3. Add a distributed action registry/lease with explicit recovery semantics,
   while documenting that it still cannot cancel an in-flight S3 request.
4. Verify `ListBucketVersions` and `DeleteObjectVersion` IAM, bucket-policy
   Denies, versioning and Object Lock in a non-production test account.
5. Prefer replacing bearer presigned uploads with a service-mediated, state-
   checked upload path before considering production erasure activation.
6. Continue to require complete final inventory and never infer completion from
   ticket expiry alone.

## Profile-only assessment

The DynamoDB-backed profile hierarchy can be handled independently of S3:
existing USER/CV guards, parent/child conditions, capacity/lifecycle CAS and
the C0E-1 G5 DynamoDB mutation transactions have local fake coverage. A
profile-only operation may therefore be reported complete only for its
explicit DynamoDB scope; it must not be promoted to a complete erasure while
documents/S3 remain unresolved.

## Verification baseline

The preceding C0F-2D run recorded **309 passed tests and 252 subtests**, with
`py_compile` and `git diff --check` passing and no AWS/S3 calls. This gate adds
analysis only and does not change executable behavior.

## Gate decisions

- **R08-C0F-2E local:** **GO** — feasibility analysis and safe local boundary
  are complete; production execution remains disabled.
- **R08-C1 PROFILE-ONLY local:** **GO** — DynamoDB profile-only mutations may
  be locally verified independently, without claiming full erasure success.
- **Production:** **BLOCKED** — no atomic DynamoDB/S3 fencing, no revocation of
  already-issued presigned URLs, unresolved legacy tickets, IAM/Object-Lock
  verification and no approved activation.
