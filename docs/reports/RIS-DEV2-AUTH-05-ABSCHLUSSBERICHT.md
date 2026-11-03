# RIS-DEV2-AUTH-05 — Abschlussbericht

**Date:** 2026-11-03  
**Branch:** `feature/ris-application-persistence-v1`

## Final decision

```text
PARTIAL VERIFIED — FAIL-CLOSED FIX COMPLETE; BOOTSTRAP BLOCKED
```

## Gate matrix

| Gate | Ergebnis | Evidence |
|---|---|---|
| 500 Root Cause | VERIFIED | Undefined `_handle_application_routes` dispatcher symbol identified and fixed |
| Fail-Closed Fix | PASS | Existing dual-auth boundary retained; malformed input 401; backend outage 503 |
| Auth Regression | PASS | 78 tests, 304 subtests |
| DEV2 Admin Bootstrap | BLOCKED | No independently issued principal-bound DEV2 authorization |
| Credential Lifecycle | BLOCKED for live run / READY by existing contract | No live credential provisioned; existing issue/revoke lifecycle inspected |
| ApplicationV1 HTTP CRUD | PENDING | Requires authorized PartnerApplication/APIProfile/Credential binding |
| Protected Infrastructure | UNCHANGED | Guarded account/state and read-only scope; no infra mutation |
| AWS Deployment | NOT AUTHORIZED | No Lambda update, Terraform apply or deployment |

## Implemented changes

- ApplicationV1 dispatcher now calls the implemented `_application_routes`.
- Malformed `X-Api-Credential` values are rejected before store construction
  with stable 401 `unauthorized` response.
- Added regression coverage for missing/invalid credentials, unknown
  well-formed credentials, inactive partner, tenant conflict and service
  unavailability.
- Updated `docs/api/API-STANDARD.md` with the controlled dual-auth error form.

## Validation

- Auth/Application/Tenant/API contract suite: **78 passed, 304 subtests
  passed**.
- Existing credential/machine/application E2E subset: **90 passed**.
- Broader admin credential selection: **175 passed, 6 failed, 15 deselected,
  7 subtests passed**. The six failures are runner-specific: Windows lacks the
  privilege required by symlink tests, and the Windows temporary-directory ACL
  rejects the owner-only output-directory assumption. No production security
  check was weakened and these failures are not claimed as passes.
- Focused authorization trust-anchor subset: **10 passed, 39 deselected**.

## Bootstrap outcome

The existing `tools/ris_admin` trust anchor requires an out-of-band issued,
owner-only mapping for the exact STS principal, role and tenant. No mapping
exists for `arn:aws:iam::262370457690:user/devnemo`. The local file format has
no issuer/signature/expiry/replay fields, so creating one locally would be
self-authorization and is prohibited. The current Partner CLI mutation path
also requires review to enforce the same trust anchor before use.

## Remaining gates

Provide an authorized, tenant-scoped DEV2 approval; guard the Partner CLI with
the existing trust anchor; then run a separate approved provisioning manifest.
Only after that may positive ApplicationV1 CRUD, isolation, privacy and
credential revocation E2E tests run. No AWS deployment or provisioning was
performed in this phase.
