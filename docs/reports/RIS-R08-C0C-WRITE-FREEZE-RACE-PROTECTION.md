# RIS-R08-C0C — ERASURE WRITE-FREEZE & RACE PROTECTION

**Status:** PARTIALLY IMPLEMENTED / R08-C1 BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `82c5fe1035f558b32ea541529e20a4f8c74f8cb4`
- RIS only; no AWS, deployment, Terraform, Jobsearch, Orders or deletion
- Receipt journal and durable erasure persistence remain disabled by default
- 39 original untracked files preserved

## Implemented protection

When `ERASURE_WRITE_FREEZE_ENABLED=true`, partner-profile DynamoDB mutations
include atomic `ConditionCheck` guards in the same transaction as the protected
write. Guards are derived from the verified user/tenant/partner/issuer scope:

- USER freeze blocks all partner-profile resources;
- CV freeze blocks the CV and its CVSearchProfile/ATSSearchProfile children;
- ManualSearchProfile is protected by the USER guard;
- create, update and delete paths are covered;
- guarded CV parent reservation/finalization is covered;
- CV upload-ticket metadata reservation and upload-complete metadata updates
  therefore fail while the corresponding freeze is active.

An absent or `RELEASED` guard permits normal writes. An `ACTIVE` guard causes a
transaction conflict. Missing partner/issuer scope or an unreadable CV parent
fails closed; no read-before-write authorization substitute is used. The
existing capacity, parent, lifecycle and optimistic-version conditions remain
in the same transaction.

`WriteFreezeRepository` provides atomic acquire/release with operation ID,
scope and version checks. Only the matching authorized operation and verified
scope can release its guard. A competing active operation cannot acquire the
same guard. No automatic release occurs on partial failure.

## Deliberate boundaries and blockers

The legacy UserProfile routes use a separate table and JWT-only context, while
the freeze key requires verified partner application scope. A read-before-write
check would be unsafe, so UserProfile create/update/delete fail closed whenever
the freeze mechanism is enabled. C1 must add a cross-table transaction and
verified partner context, or retain this conservative block.

The existing G5 erasure path does not yet carry a C0B operation ID to the
UserProfile mutation, so it is not an authorized C0C freeze override. No
override was added. This prevents claiming complete C1 readiness.

S3 presigned upload URLs are bearer capabilities already issued to a client and
may remain valid until their expiry. C0C does not claim an absolute S3 network
write lock. It protects the metadata reservation and upload-complete mutation,
requires later S3 verification/cleanup, and leaves outstanding-ticket cleanup
as an explicit C1/C2 phase.

## Verification

| Check | Result |
|---|---|
| C0B repository + C0C freeze tests | **44 passed** |
| Focused privacy/API regression | **137 passed, 252 subtests** |
| Existing UserProfile/CV/profile regression | **91 passed** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| DynamoDB Local | Not available; conditional fakes used |

No production freeze was enabled and no AWS access was performed. Real
multi-item DynamoDB cancellation reasons, cross-table transaction behavior and
deployed S3 ticket expiry remain unverified.

## Gate decision

- **R08-C0C:** PASS for the transaction-coupled partner-profile guard and
  fail-closed contract.
- **R08-C1:** **BLOCKED** — UserProfile atomic cross-table enforcement, an
  operation-authorized G5 override, and outstanding S3-ticket cleanup/
  re-verification remain unresolved. No erasure execution is enabled.
