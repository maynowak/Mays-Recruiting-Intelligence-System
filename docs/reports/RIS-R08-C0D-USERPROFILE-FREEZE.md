# RIS-R08-C0D — USERPROFILE ATOMIC FREEZE ENFORCEMENT

**Status:** IMPLEMENTED / C0E READY

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `8c5bcdc9910fd27b69afa9c6156b43a3cd9e01ba`
- RIS only; no deletion, AWS access, deployment, Terraform or G5 override
- Receipt journal and erasure persistence remain disabled by default
- 39 original untracked files preserved

## Implementation

All UserProfile mutations now use the same subject USER guard as partner
profiles when `ERASURE_WRITE_FREEZE_ENABLED=true`:

- `POST /me/profile` uses Guard `ConditionCheck` + conditional `Put`;
- `PATCH /me/profile` and legacy `PUT /me/profile` use Guard
  `ConditionCheck` + version/tenant-conditional `Update`;
- `DELETE /me/profile` uses Guard `ConditionCheck` + conditional `Delete`.

The guard is stored in the existing partner-profile table and the UserProfile
mutation in the UserProfile table, in one DynamoDB `TransactWriteItems` call.
The mutation remains conditional on the existing user/tenant/version rules.
Concurrent freeze acquisition and mutation therefore resolve atomically: one
transaction fails rather than authorizing from a stale read. A guard conflict
does not fall back to the old single-table write.

When the mechanism is enabled, the legacy JWT-only routes must additionally
resolve the verified partner context through `_partner_profile_context`. A
missing/foreign user, tenant, partner or issuer context fails closed with no
mutation. With the mechanism disabled, the existing normal CRUD paths and
version/`If-Match`/409 behavior remain unchanged.

No G5 override was added. G5 remains a separate authorized lifecycle and is
not silently granted a freeze bypass by C0D.

## Verification

| Check | Result |
|---|---|
| Atomic UserProfile/freeze tests | **4 passed** |
| UserProfile/C0C regression | **23 passed** |
| Combined C0A–C0D/privacy/profile regression | **265 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| DynamoDB Local | Not available; transaction fake used |

The fake verifies transaction ordering, guard conflict fail-closed behavior,
version conditions and context isolation. Real DynamoDB transaction-cancellation
reasons, IAM, cross-table capacity and deployed behavior remain unverified.

## Remaining legacy limitations

- Freeze-enabled legacy callers without the verified partner credential/context
  receive a fail-closed response; no unsafe JWT-only fallback exists.
- Existing presigned S3 upload URLs can remain valid until expiry. C0D does not
  claim an absolute S3 write lock; upload completion and metadata writes remain
  guarded and later cleanup/re-verification is still required.
- G5 operation-authorized freeze override is intentionally not part of C0D.
- Freeze and erasure persistence remain disabled by default pending policy and
  deployment approval.

## Gate decision

- **R08-C0D:** PASS — UserProfile write mutations are atomically guard-coupled.
- **R08-C0E Write-Freeze Readiness:** **GO** for the local contract and
  transaction path, subject to real DynamoDB Local/deployed verification.
