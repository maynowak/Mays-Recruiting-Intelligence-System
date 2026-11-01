# RIS-R08-C0E — AUTHORIZED G5 ERASURE OVERRIDE

**Status:** PARTIALLY IMPLEMENTED / R08-C0F BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `a6a64ca62d907bd26f12967df6bebee317a3b91c`
- RIS only; no AWS, deployment, Terraform, productive deletion, S3,
  Jobsearch or Orders changes
- Erasure persistence and receipt journal remain disabled by default
- 39 original untracked files preserved

## Implemented authorization boundary

`ErasureExecutionContextV1` is an internal-only context containing the
operation ID, USER/CV scope, user, tenant, partner, issuer and the expected
operation/freeze versions. It is not accepted from HTTP input and is not
serialized as a public override.

`WriteFreezeRepository.authorize_execution()` atomically checks, in one
`TransactWriteItems` call:

1. the matching `ErasureWriteFreeze` is `ACTIVE`, has the operation ID,
   verified identity scope and expected freeze version; and
2. the matching `ErasureOperation` is `RUNNING`, has the verified identity
   scope and expected operation version.

Foreign scope, stale versions, missing/released freezes, completed operations
and conditional races fail closed. No `bypassGuard` parameter, HTTP flag or
header was introduced.

## G5 integration boundary

The existing `PrivacyErasure` engine performs independent mutations across
credentials, API profiles, work items, S3 and UserProfile. Those collaborators
do not yet accept the internal execution context and do not couple every
mutation to the operation/freeze conditions in its own atomic transaction.
Therefore the legacy G5 engine now refuses to execute before its first
mutation whenever `ERASURE_WRITE_FREEZE_ENABLED=true`. The public
`POST /me/erasure` path returns an unavailable response in that state rather
than becoming a general guard bypass.

This is deliberate: an authorization check performed once before a sequence
of independent writes would still leave a race window. No partial G5 run is
started under an active freeze. The existing G5 behavior remains unchanged
when the freeze mechanism is disabled, and no productive erasure was enabled.

## Verification

| Check | Result |
|---|---|
| Atomic scoped authorization tests | **4 passed** |
| C0B/C0C repository and freeze tests | **44 passed** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| DynamoDB Local | Not available; transaction fake used |

The repository's existing privacy-security test subset has six known local
failures when `boto3` is unavailable because its fake work-table path imports
`boto3` for the DynamoDB `Key` condition. This is pre-existing and unrelated
to C0E; the new C0E tests pass without that dependency.

## Remaining G5 limits and gate

- No authorized G5 mutation path is enabled yet; the all-collaborator atomic
  adapter is the remaining implementation requirement.
- Per-mutation authorization for credentials, API profiles, work items,
  documents and UserProfile must be added before an override can be allowed.
- No S3-ticket behavior, retention policy, receipt journal or productive
  deletion was changed.

**R08-C0E:** scoped authorization primitive and fail-closed boundary PASS.

**R08-C0F:** **BLOCKED** until the existing G5 collaborators are connected to
the internal context with atomic per-mutation guard/operation checks.
