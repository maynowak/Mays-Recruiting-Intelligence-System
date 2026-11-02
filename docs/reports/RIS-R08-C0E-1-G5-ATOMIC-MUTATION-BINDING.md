# RIS-R08-C0E-1 — ATOMIC G5 MUTATION BINDING

**Status:** IMPLEMENTED FOR DYNAMODB / S3 PATH BLOCKED / R08-C0F BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `f6421368bfec8f4c64120814a116fd0a9beab25f`
- RIS only; no AWS, deployment, Terraform or productive deletion
- No S3-ticket changes; receipt journal and erasure persistence remain disabled
- 39 original untracked files preserved

## Atomic G5 bindings

`PrivacyErasure` now accepts the internal `ErasureExecutionContextV1` together
with an `AtomicG5MutationExecutor`. For every DynamoDB mutation, the executor
submits one transaction containing:

1. a `ConditionCheck` for the matching active USER/CV freeze, including
   operation ID, user/tenant/partner/issuer and expected freeze version;
2. a `ConditionCheck` for the matching `RUNNING` operation, including the
   same identity scope and expected operation version; and
3. the actual mutation.

The following existing G5 collaborators are bound:

- credential revocation (`DynamoDBCredentialStore`)
- API-profile revocation (`DynamoDBApiProfileStore`)
- non-terminal WorkItem cancellation
- UserProfile deletion

Target-row ownership and tenant conditions remain in each mutation. Credential
and API-profile writes additionally compare the previously observed
`updatedAt` value. A failed guard, operation version, target condition or
transaction fails that step; no plain-write fallback exists.

Direct store calls without an execution context continue to use their normal
non-erasure behavior. Context-bearing calls without the atomic executor fail
closed. The context is internal-only and cannot be supplied through HTTP.

## Safety boundaries

G5 preflight rejects CV contexts for the USER erasure engine and rejects scope
or tenant mismatches. Repeated mutations re-check the same operation and
freeze versions, so a concurrent operation update or freeze release causes a
transaction conflict. A partial result is not marked complete; no checkpoint
or operation status is advanced by this gate.

S3 deletion remains deliberately unbound because S3 cannot participate in the
same DynamoDB transaction. An authorized-context G5 run with a document
deleter is rejected before the first mutation. The public `/me/erasure` route
therefore remains unavailable while freeze enforcement is enabled rather than
providing an unsafe partial override.

No second erasure engine, HTTP bypass, retention rule, G5 override flag or
productive deletion was introduced.

## Verification

| Check | Result |
|---|---|
| Atomic G5 authorization/mutation tests | **5 passed** |
| C0B–C0E regression and G5 security tests | **288 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| DynamoDB Local | Not available; transaction fakes used |

The fakes verify three conditions plus the mutation in each DynamoDB
transaction, scope isolation, stale-version conflicts, replay behavior and
fail-closed S3 handling. Real DynamoDB cancellation reasons, IAM and deployed
cross-table behavior remain unverified.

## Gate decision

- **R08-C0E-1:** PASS for the four DynamoDB G5 mutation collaborators.
- **R08-C0F:** **BLOCKED** until S3/document erasure has an explicitly approved
  race-safe binding or remains a separately orchestrated, non-atomic phase.
