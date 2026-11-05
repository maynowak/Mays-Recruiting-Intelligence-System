# RIS-R08-DEV2 — Mays-Jobsearch Integration Handoff

## Current DEV2 contract

| Item | Value / status |
|---|---|
| API base URL | `https://8apxb6fgne.execute-api.eu-central-1.amazonaws.com` |
| API type | API Gateway HTTP API, `$default` stage, auto-deploy enabled |
| JWT issuer | `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_K3dkdSipZ` |
| JWT audience/client | `21j28p71vogg0m41tcue0ib3l4` |
| Tenant binding | JWT `custom:tenant_id` is required by the RIS application contract |
| Partner binding | `X-Api-Credential` and RIS partner/API-profile binding required for partner routes |
| CORS | API Gateway reported no CORS configuration; browser integration needs an approved frontend/BFF path |

No token, password, secret or real identity is included.

## Route handoff

| Jobsearch function | RIS endpoint | Auth | DEV2 test | Status | Frontend next task |
|---|---|---|---|---|---|
| Application create | `POST /v1/partner/me/applications` | JWT + `X-Api-Credential` | not executed; binding unavailable | LIVE ROUTE / BLOCKED | obtain approved partner credential |
| Application list | `GET /v1/partner/me/applications` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | implement cursor client |
| Application detail | `GET /v1/partner/me/applications/{applicationId}` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | handle 200/403/404 |
| Application update | `PATCH /v1/partner/me/applications/{applicationId}` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | preserve version/concurrency fields |
| Application metrics | `GET /v1/partner/me/applications/metrics` | JWT + `X-Api-Credential` | synthetic request returned 401 | LIVE ROUTE / BLOCKED | resolve tenant/credential auth contract |
| History | `POST /v1/partner/me/applications/{applicationId}/history` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | use after binding |
| Cover-letter versions | `POST /v1/partner/me/applications/{applicationId}/cover-letter-versions` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | preserve version semantics |
| Application export | `GET /v1/partner/me/applications/{applicationId}/export` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | subject-scoped export only |
| Privacy inspect | `GET /v1/partner/me/privacy/inspect` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | do not assume GDPR completion |
| Privacy export | `GET /v1/partner/me/privacy/export` | JWT + `X-Api-Credential` | not executed | LIVE ROUTE / BLOCKED | handle partial state/no-store |
| Public erasure | `POST /me/erasure` | JWT | not executed; mutating | LIVE ROUTE / NOT TESTED | separate approved erasure run |

The inventory comes from live API Gateway routes and `docs/api/API-STANDARD.md`.
No endpoint is invented. Application CRUD, pagination, metrics, inspect/export
and erasure are not claimed live-verified.

## Live observations

* Authenticated synthetic `/health` returned `200`.
* Unauthenticated API `/health` returned `401` with Bearer challenge.
* Synthetic authenticated metrics returned `401` with `Cache-Control:
  no-store, private`.
* The access token did not contain `custom:tenant_id`; the ID token did. The
  frontend must not work around this by using the wrong token type.
* API Gateway reported no CORS configuration.

## Data and integration risks

The live Applications table is `ris-dev2-dev-applications` with
`applicationId`/`entityKey` keys and active `gsi-owner` on
`ownerKey`/`updatedAt`. WorkItems is active with `gsi-user` and `gsi-status`.
No records were created or read.

Full integration requires an independently authorized tenant-scoped RIS
partner/API-profile credential. Privacy runtime and durable ledger writes are
disabled. The Jobsearch team should first resolve the tenant claim,
credential and CORS contracts, then run a new synthetic CRUD/cleanup window.
