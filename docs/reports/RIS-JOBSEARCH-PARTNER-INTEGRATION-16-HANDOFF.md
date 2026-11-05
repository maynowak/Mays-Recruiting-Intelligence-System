# RIS-JOBSEARCH-PARTNER-INTEGRATION-16 — DEV2 Handoff

**Status:** DIAGNOSED / PARTNER BINDING BLOCKED / NO MUTATION

## Executive result

The existing DEV2 API and dual-auth implementation are present, but the
Mays-Jobsearch partner cannot currently call ApplicationV1. The three required
RIS metadata stores are empty:

| Store | Live table | Result |
|---|---|---|
| Partner Application Registry | `ris-dev2-dev-partner-applications` | ACTIVE, 0 items |
| API Profiles | `ris-dev2-dev-api-profiles` | ACTIVE, 0 items |
| Credentials | `ris-dev2-dev-credentials` | ACTIVE, 0 items |

No credential value was read or emitted. No profile, partner record or
credential was created. No Terraform, Cognito, Jobsearch or Vercel mutation was
performed.

## 1. Metrics 401 root cause

The 401 is a **RIS Lambda partner-boundary denial**, not an issuer/audience
failure at API Gateway, when a valid Cognito access token reaches the route
without a usable `X-Api-Credential`.

Evidence:

1. Live API Gateway route `GET /v1/partner/me/applications/metrics` exists,
   targets the deployed Lambda integration, uses JWT authorizer `9i4w8r`, and
   has no API-key requirement.
2. The live authorizer uses issuer
   `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ` and
   audience `21j28p71vogg0m41tcue0ib3l4`.
3. The prior synthetic access JWT passed the same authorizer: authenticated
   `/health` returned `200`.
4. The prior metrics response was `401` with body
   `{"error":"Unauthorized","code":"unauthorized"}` and
   `Cache-Control: no-store, private`, matching Lambda's
   `_partner_profile_context` contract rather than API Gateway's generic
   `{"message":"Unauthorized"}` response.
5. Deployed code requires `token_use=access`, extracts the opaque value from
   `X-Api-Credential`, resolves credential/profile, then cross-checks Partner
   Registry `apiProfileId` and `tenantId`.

The missing `custom:tenant_id` in the synthetic **access** token is not, by
itself, the root cause for this partner route: L03 allows a missing claim when
the tenant is resolved and cross-checked from credential and Registry. An ID
token must still not be substituted for an access token.

### Required request shape

```http
GET /v1/partner/me/applications/metrics
Authorization: Bearer <Cognito access token>
X-Api-Credential: <existing server-side RIS credential>
```

The credential must be held by a server-side Jobsearch BFF/Vercel function,
never by the browser.

## 2. Live identity contract

| Contract item | Verified value/status |
|---|---|
| API base | `https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com` |
| JWT issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ` |
| JWT audience | `21j28p71vogg0m41tcue0ib3l4` |
| Token required | Cognito access JWT, `token_use=access` |
| User identity | verified `iss + sub`; email is not an owner key |
| Partner header | `X-Api-Credential` |
| Server-side tenant | credential `tenantId` cross-checked with Registry; present JWT tenant must not contradict it |
| API Gateway CORS | `CorsConfiguration=null`; OPTIONS preflight returned `404 Not Found` |

Old Jobsearch-side documents contain historical pool/account values that do not
match this live DEV2 authorizer. Use the live values above.

## 3. Existing Jobsearch key and adapter assessment

**Existing RIS key contract: DOCUMENTED, LIVE PRESENCE/VALIDITY BLOCKED.**

Available Jobsearch evidence specifies a server-side `RIS_API_KEY`/RIS
credential and the correct forwarding header, but no authorized Vercel secret
metadata was available to inspect. The RIS credential table is empty, so no
live credential metadata exists to which a Jobsearch key could be mapped. The
key itself was not read, logged, tested, or exposed.

The pinned Jobsearch read-only source confirms that `ApplicationPersistencePort`
is a type-only contract: it has no HTTP client, route assumption or credential
storage implementation. Local application management remains in-memory and
account persistence is explicitly deferred until RIS auth/privacy gates pass.

## 4. Existing routes and contracts

The following routes were confirmed in the live API Gateway inventory; all
partner routes require JWT plus `X-Api-Credential`:

| Function | Route | Contract |
|---|---|---|
| Create | `POST /v1/partner/me/applications` | 201 |
| List | `GET /v1/partner/me/applications` | 200 `{items,nextCursor}`; identity-bound cursor |
| Metrics | `GET /v1/partner/me/applications/metrics` | 200 `{metrics}`; current call blocked at auth |
| Read | `GET /v1/partner/me/applications/{applicationId}` | 200/403/404 |
| Update | `PATCH /v1/partner/me/applications/{applicationId}` | 200; stale version 409 |
| Status | `POST /v1/partner/me/applications/{applicationId}/status` | exactly one `status` or `stage` |
| History | `POST /v1/partner/me/applications/{applicationId}/history` | 201 |
| Cover letters | `POST /v1/partner/me/applications/{applicationId}/cover-letter-versions` | 201 |
| Export | `GET /v1/partner/me/applications/{applicationId}/export` | 200; owner/partner scoped |
| Privacy inspect | `GET /v1/partner/me/privacy/inspect` | 200 COMPLETE/PARTIAL |
| Privacy export | `GET /v1/partner/me/privacy/export` | 200; owner/partner scoped |

ApplicationV1 uses server-generated `applicationId` and server-derived identity
context. The live table uses `applicationId`/`entityKey`; `gsi-owner` is active
on `ownerKey`/`updatedAt`. No live application item was created or read.

## 5. Isolation assessment

| Check | Result | Evidence |
|---|---|---|
| Partner A/user A | LOCAL VERIFIED only | local dual-auth and HTTP integration harness |
| Partner A/user B | LOCAL VERIFIED only | cross-identity denial tests |
| Partner B/user A | LOCAL VERIFIED only | Registry/tenant mismatch tests |
| Same email, different pools | CONTRACT PASS / LIVE NOT TESTED | ownership uses `iss + sub`, not email |
| Missing/invalid credential | LOCAL VERIFIED; live no valid credential exists | local 401 tests; empty live table |
| Valid key without user entitlement | LOCAL VERIFIED | entitlement denial tests |
| Missing tenant claim | LOCAL VERIFIED by L03 | trusted credential/Registry resolution |
| Live multi-partner isolation | BLOCKED | no two authorized partner bindings exist |

Focused local result: **59 passed, 7 subtests passed** across auth-boundary,
partner dual-auth and HTTP integration tests. This is not a live DEV2 E2E claim.

## 6. Required Jobsearch follow-up

1. Keep `RIS_API_KEY` (or the agreed existing credential name) in a server-side
   Vercel environment secret only; never `VITE_*`, `NEXT_PUBLIC_*`, browser
   storage, request payloads or logs.
2. Add a server-side BFF adapter that forwards the user access JWT and adds
   `X-Api-Credential`; the browser must not call the partner route directly.
3. Implement `ApplicationPersistencePort` against the verified `/v1/partner/me`
   routes, not the older proposed unprefixed `/applications` paths.
4. Preserve `iss + sub`, server-generated IDs, cursors, `expectedVersion`, 409
   conflicts and explicit status transitions.
5. Transfer local drafts only after explicit selection, preview and
   confirmation; keep the local draft on failed transfer.
6. Keep local application management usable when RIS is unavailable; never
   fabricate remote success.
7. Add BFF CSRF/session protections and redact authorization material.
8. Do not create Cognito resources or alter RIS/Orders infrastructure.

## 7. Minimal RIS provisioning prerequisite (separate approval required)

An authorized operator must use the existing guarded RIS admin path to create or
select one Jobsearch API profile, issue/select the existing server-side
credential, register the Jobsearch Cognito client/issuer as an ACTIVE Partner
Application bound to the same profile and tenant, and grant only required user
entitlements. This is a proposed sequence only. No mutation was run because no
tenant-scoped RIS admin authorization was available. Do not self-authorize,
write DynamoDB directly, or replace the existing key with a new one.

## 8. Phase 16 completion table

| Prüfung | Ergebnis | Evidence |
|---|---|---|
| Metrics 401 Root Cause | FOUND | valid JWT reaches API; Lambda dual-auth returns 401 without usable credential |
| Existing RIS Key Contract | BLOCKED | documented server-side contract; no authorized Vercel metadata; empty live credential table |
| Partner Registry Binding | BLOCKED | live Registry ACTIVE, 0 items |
| Issuer/Audience Binding | VERIFIED for RIS DEV2 / Jobsearch binding BLOCKED | live authorizer `9i4w8r`; no Partner Application |
| Multi-Pool Isolation | PASS LOCAL / BLOCKED LIVE | 59 focused tests; no live bindings |
| Metrics DEV2 E2E | BLOCKED | 401; no valid credential/profile/Registry chain |
| ApplicationV1 DEV2 E2E | BLOCKED | prerequisite binding absent |
| Jobsearch Handoff | COMPLETE for diagnosis / PARTIAL for usable integration | this report |
| Frontend Changes | NOT EXECUTED | Jobsearch read-only boundary |
| Cognito Changes | NONE | no pool/client/domain mutation |
| Gate B | NO-GO | binding and live isolation remain open |
| Production | BLOCKED | no production authorization |
