# MAYS-P3-FINAL — Consolidated Report

**Status:** `PARTNER ERASURE ROUTE LIVE PREVIEW E2E PASS — PRODUCTION DEPLOYMENT PENDING`  
**Date:** 2026-11-09  
**Scope:** P3 account erasure, partner route, Jobsearch BFF, synthetic E2E, health schedule

No real user or operator data was deleted. No push or merge was performed.
The historical P3 detail reports remain in Git history; this is the current
consolidated status.

## 1. Executive summary

The previously reported blocker — `POST /me/erasure` being reachable only on the
RIS kernel API with a different Cognito pool — is resolved:

- `POST /v1/partner/me/erasure` is live on the existing Jobsearch partner edge.
- The existing JWT authorizer and partner credential boundary apply.
- The existing `_handle_me_erasure` lifecycle is reused; no second deletion
  engine.
- Jobsearch BFF points to the partner route.
- A real browser E2E with an isolated synthetic Cognito identity passed against
  a temporary preview.
- The synthetic identity, its CV/search profiles, temporary allowlist entry and
  preview environment were removed afterwards.

CVDocument metadata erasure is now also implemented and live-verified: after
the S3 phase, the existing CVDocument rows are deleted through the same partner
repository. The remaining open points are **production deployment** and
S3-version/backup/PITR erasure.

## 2. RIS current state

| Field | Value |
| --- | --- |
| AWS account / region | `240571105849` / `eu-central-1` |
| Terraform workspace | `ris-dev` |
| State serial | **61** |
| Lambda | `ris-dev-dev-agent`, `Active` |
| Code hash | `uQqKk33NnwxWnaGm2PDUhpCnyhIFVUZ5Zxe9oUotirs=` |
| Partner erasure route | `POST /v1/partner/me/erasure` — live |
| `CONSENT_PILOT_ALLOWLIST` | original operator identity only |
| Synthetic test user/profile data | deleted |
| Health publisher | `rate(15 minutes)`, `ENABLED` |

### Applied plans

| Plan | Result |
| --- | --- |
| `d6cfcda…` — search-profile notice/code | 0 add / 1 change / 0 destroy |
| `53bcc0a…` — search-profile enforcement | 0 add / 1 change / 0 destroy |
| `09ce68b…` — API Gateway v2 gate fix | 0 add / 1 change / 0 destroy |
| `837068b155f953272600ec46a03efe9f82ef5472f00b9b6b283e67f936729148` — partner route + code | **1 add / 1 change / 0 destroy** |
| `f8b02fb0…` — health publisher 15 min | 0 add / 1 change / 0 destroy |
| `5ef5567121deb72a7da82a08257bb6c20d06174a3228754b123bc18f84aa980b` — CVDocument metadata cleanup | 0 add / 1 change / 0 destroy |

No Cognito, CloudFront, Route53/DNS, ACM, Mays-Orders, API Gateway (other than
the new partner route), S3, DynamoDB or Partner Edge resource was otherwise
changed by the P3 work.

## 3. Jobsearch current state

| Field | Value |
| --- | --- |
| Production | `https://www.mays-job-matcher.app` |
| Production deployment | `dpl_6DiPJxotbPSC8K5u8C8ZYkizTYdA` |
| Production source | `feature/jm-ris-vercel-test-env-05-integration @ e5716f1` |
| Production public smoke | `/`, `/datenschutz`, `/impressum` = 200 |
| Authenticated production E2E | manual; not run by this agent |
| BFF partner route | implemented locally (`424da71`), preview-tested |
| Production BFF/UI | **not deployed** by this work |
| Erasure flags | default off / preview-only during test |

The production build is **not** the local P3 branch. No production deployment
of the partner-erasure BFF/UI was made.

## 4. Live preview E2E

Setup:

- Isolated synthetic Cognito user with exact `iss|sub`.
- Temporary RIS `CONSENT_PILOT_ALLOWLIST` and preview Jobsearch
  `RIS_TEST_USER_ALLOWLIST` scoped to that identity.
- Synthetic durable CV plus manual, CV-search and ATS profiles.
- Jobsearch preview `mays-job-matcher-d4rbxb3hv-maymilly.vercel.app`
  (removed after test).

Browser result:

- Real Settings UI, typed `LÖSCHEN`, delete clicked.
- Response: **`complete=true`**
  - `searchProfilesDeleted=3`
  - `documentsDeleted=1`
  - `credentialsRevoked=0`
  - `applicationsDeleted=0`
- Search-profile lists after erasure:
  - manual: **0**
  - CV search: **0**
  - ATS: **404** (parent gone)
- Second erasure call: **complete=true**, search profiles 0, documents 0;
  idempotent for the exercised path.
- Screenshot: `docs/reports/assets/MAYS-P3-FINAL/p3-final-real-erasure.png`.

## 5. CVDocument metadata — resolved and live-verified

The first live run exposed that CVDocument metadata remained after
`complete=true`. The fix deletes `CVDocument` metadata through the existing
partner repository only after the S3 phase succeeds; if S3 is pending, the
metadata step fails closed and does not delete the row.

A second isolated synthetic run after deploying the fix returned
`complete=true`, `searchProfilesDeleted=3`, `documentMetadataDeleted=1`,
`documentsDeleted=1`; `GET /api/ris/cvs` then returned **0** synthetic CVs.
The synthetic test user and allowlist entry were cleaned up afterwards.

S3 versions/backups/PITR remain separate open boundaries.

## 6. Tests

| Suite | Result |
| --- | --- |
| Jobsearch BFF/router/client/consent | **23 passed** |
| Jobsearch account-erasure browser E2E (mocked BFF) | **PASS** |
| Jobsearch production build | **PASS** |
| RIS partner/erasure focused (after metadata fix) | **46 passed** + **77 passed** earlier |
| RIS full suite (`tests --ignore=tests/integration`) | **2555 passed**, 17 skipped, 16 pre-existing unrelated failures |
| RIS `terraform validate` / `fmt -check` | **PASS** |
| Live preview browser E2E | **PASS** (synthetic identity only) |

Health publisher schedule verification: `rate(15 minutes)`, `ENABLED`;
expected 4 invocations/hour / 96/day (pre-change 12/hour / 288/day).

## 7. Cleanup

- Synthetic Cognito user deleted.
- Temporary allowlist entry removed; allowlist restored to original operator.
- Synthetic CV/search profiles removed; CV metadata manually removed.
- Preview deployment and preview environment removed.
- Local session/test artifacts removed.
- No real user data deleted.

## 8. Commits

- RIS partner route: `451c12e`
- RIS CVDocument metadata erasure: `2c7c200`
- Jobsearch BFF partner route: `424da71`
- RIS live E2E docs: `a52fabd`
- Jobsearch live E2E docs: `938f82b`
- Health schedule: `74e766c` / docs `70c9bf0`

## 9. Remaining approvals

1. **Production Jobsearch deployment**: review/deploy the BFF/UI on the
   selected production branch; keep erasure flags limited to the approved pilot
   identity.
3. **Production copy cleanup**: ensure no test identity/allowlist remains.
4. **S3 versions/backups/PITR**: separate evidence and approval; no physical
   purge is claimed.

## 10. Result

`MAYS-P3-FINAL — PARTNER ERASURE ROUTE LIVE PREVIEW E2E PASS`

The partner route and search-profile erasure are verified live in an isolated
preview. Production deployment and CVDocument metadata erasure remain pending.
