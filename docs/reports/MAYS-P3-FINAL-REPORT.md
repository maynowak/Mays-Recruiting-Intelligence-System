# MAYS-P3-FINAL — Orchestrated E2E & Release Closure

**Result:** `PARTNER ERASURE ROUTE LIVE PREVIEW E2E PASS — PRODUCTION DEPLOYMENT PENDING`  
**Safe work:** complete  
**Date:** 2026-11-08

No real user or operator data was deleted. No additional AWS/Terraform change, no
Jobsearch deployment, no push and no merge was performed in this step.

## 1. RIS status

`RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-03` is deployed and post-deploy verified:

| Field | Value |
| --- | --- |
| State serial | **50** |
| Lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Resources | 250 |
| Lambda | `ris-dev-dev-agent`, `Active` |
| Code hash | `/oB1onGisdIHu9/J1RMp80Ti7t8ooGl28yiLRD6BLIE=` |
| Applied plan | `277c3206809309acbdc5fdcd4b2c91d4d8344851c2cc320f298fed475d3dbcba` |
| Documentation commit | `81ae432` |

The partner search-profile deletion step is in the deployed Lambda; environment
and erasure feature flags are unchanged from the deployment report. Health/consent
routes returned 401 without a token (no 5xx) and no destructive operation was run.

## 2. Jobsearch status

Implemented and locally verified, **not deployed**:

- New BFF route `/api/ris/erasure` forwards the verified user token to the
  existing kernel endpoint `POST /me/erasure`.
- No second deletion architecture; no identity accepted from the browser.
- Disabled by default: `RIS_ACCOUNT_ERASURE_ENABLED=false` and
  `VITE_RIS_ACCOUNT_ERASURE_ENABLED=false`.
- Requires server-only `RIS_ERASURE_API_BASE_URL` (kernel API) and the existing
  verified test-user allowlist.
- Existing settings area now has an opt-in confirmation UI with typed
  `LÖSCHEN`; it is not rendered unless the browser flag is enabled.
- Partial/incomplete RIS lifecycle results are shown as incomplete; no
  physical S3/backup/PITR purge is claimed.

Jobsearch commit: `e060606`; browser test/evidence in
`tests/e2e/account-erasure.mjs` and
`docs/reports/assets/MAYS-P3-FINAL/account-erasure-ui.png`.

## 3. Tests actually executed

| Suite | Result |
| --- | --- |
| Jobsearch BFF/router/client/consent suites | **32 passed** |
| Jobsearch local browser E2E for account-erasure UI | **PASS** (mocked BFF; no real deletion) |
| Jobsearch production build | **PASS** |
| RIS P3 erasure suite | **14 passed** |
| RIS privacy/erasure focused set | **104 passed** |
| RIS partner-profile regression set | **146 passed** |
| RIS full suite (`tests --ignore=tests/integration`) | **2551 passed, 17 skipped, 16 pre-existing unrelated failures** |
| RIS Terraform validate/fmt | **PASS** |
| RIS post-deploy health/consent smoke | **401 auth boundary, no 5xx** |

## 4. Why this is BLOCKED

The destructive production E2E requires an explicitly approved **isolated
synthetic identity** (Cognito `issuer|sub`) and a suitable synthetic dataset.
No such identity/credential/session is available in this workspace, and creating
or changing Cognito users is outside the allowed scope. Using the existing
operator identity would delete real operator data and is prohibited.

The Jobsearch BFF/UI also requires a separately approved deployment and runtime
configuration (`RIS_ERASURE_API_BASE_URL`, flags, allowlist).

## 5. Remaining blockers / next approval

1. Provide/approve an isolated synthetic Cognito identity `issuer|sub` and a
   synthetic dataset.
2. Approve the Jobsearch preview/production deployment and set:
   - `RIS_ACCOUNT_ERASURE_ENABLED=true` only for the isolated pilot
   - `RIS_ERASURE_API_BASE_URL=<kernel API>`
   - `VITE_RIS_ACCOUNT_ERASURE_ENABLED=true` only for the pilot
   - existing `RIS_TEST_USER_ALLOWLIST=<synthetic iss|sub>`
3. Then execute the destructive synthetic E2E:
   - create manual, CV-search, ATS profiles and parent links
   - invoke account erasure once
   - verify all three categories are gone, unrelated identities unchanged,
     repeat call is idempotent, partial failure is incomplete
   - verify S3/document/backup limits are still reported as open
4. Only after that consider general account-erasure rollout.

## 6. Safety

- No real account/CV/application/document deletion.
- No AWS apply/change; RIS state remains serial 50.
- No Terraform change in this step.
- No Jobsearch deployment, push or merge.
- No general account-erasure enablement.
- S3/version/backup/PITR erasure remains explicitly unclaimed.

## 7. Cross-repository handoff

The integration uses the existing RIS `POST /me/erasure` contract and a single
Jobsearch BFF. XREPO dispatch/push was not used because this workspace's remote
state is intentionally not pushed. The documented handoff is this report plus
the two repository commits.

## 8. Next gate

`MAYS-P3-FINAL` can become `VERIFIED` only after the isolated synthetic identity
approval, Jobsearch deployment, and destructive synthetic erasure E2E have all
been completed and evidenced.

## 9. 2026-11-09 status reconciliation

### Production Jobsearch

- Production `https://www.mays-job-matcher.app` is live via
  `dpl_6DiPJxotbPSC8K5u8C8ZYkizTYdA` (deployment URL
  `https://mays-job-matcher-g997tkrur-maymilly.vercel.app`), source branch
  `feature/jm-ris-vercel-test-env-05-integration @ e5716f1`.
- Public smoke `/`, `/datenschutz`, `/impressum`: 200, no console errors
  (reported by the production deployment operator; this workspace independently
  confirmed the public alias returns 200).
- Authenticated login/consent/application E2E remains manual and was not run by
  this agent. This production build is **not** the local P3 branch
  `feature/jm-ris-cv-storage-integration-01`.

### RIS-DEV current state

- State serial is now **54**, not the serial 50 recorded in RAESP-03, after
  allowlist test setup/rollback and the local partner-context handler fix.
- Lambda `ris-dev-dev-agent` is Active at
  `FlXserJvs+Cxi0uGTyKkIReLFs2kOTyJXtGTivNe8+0=`.
- `CONSENT_PILOT_ALLOWLIST` is back to the original operator identity only.
- The synthetic test user was deleted; its synthetic CV/search profiles were
  removed. No real operator data was touched.

### Actual erasure blocker discovered

`POST /me/erasure` is on the RIS **kernel** API
(`g6901and25`), whose JWT authorizer uses a different Cognito pool
(`eu-central-1_ojbmoiYGM`, client `7ldhihlpdgsgcl3puvu4oi7ksv`). The Jobsearch
partner edge (`c7e9pdwe78`) uses the Jobsearch pool
(`eu-central-1_ZURSMpD2O`, client `5hb3f6dj5ialg77jf4blur9g6g`) and does not
expose an erasure route. A Jobsearch access/ID token therefore receives 401
from the kernel route; an account-erasure request cannot be completed via the
current BFF/base URL.

**Minimal correction:** add `POST /v1/partner/me/erasure` to the existing
partner edge with the existing Jobsearch JWT authorizer and dispatch it to the
existing `_handle_me_erasure` (no second engine), then point the Jobsearch BFF
at that partner route and use the browser access token. This requires a
reviewed Terraform/API change and a Jobsearch deployment approval.

### Current status

`MAYS-P3-FINAL — BLOCKED`

RIS search-profile erasure is deployed; the cross-repository *account* erasure
path is not reachable for Jobsearch users until the partner-edge route exists.
No destructive production E2E was executed.

## 11. Partner-edge erasure route — local verification (2026-11-09)

The kernel/partner topology blocker is resolved **locally**; no AWS apply or
deployment was performed.

### RIS

- Added `POST /v1/partner/me/erasure` to the existing partner edge route set
  (`terraform/modules/partner_edge/main.tf`).
- Added a dispatcher branch in `lambda/handler.py` that first verifies the
  existing partner credential/profile context via
  `_partner_profile_context`, then calls the existing `_handle_me_erasure`.
  No second deletion engine.
- The partner-application/tenant resolution fix remains in place for standard
  Cognito users without custom partner claims.
- Commit: `451c12e` — `feat(privacy): expose partner-edge erasure route`.

### Jobsearch

- BFF now targets `POST /v1/partner/me/erasure` on the existing partner base;
  no separate kernel base URL.
- Existing `RIS_ACCOUNT_ERASURE_ENABLED`, `VITE_RIS_ACCOUNT_ERASURE_ENABLED`,
  allowlist and `LÖSCHEN` confirmation remain. Disabled by default.
- Commit: `424da71` — `feat(privacy): point erasure BFF at partner route`.

### Plan (not applied)

| Field | Value |
| --- | --- |
| Plan | `/tmp/opencode/ris-dev-partner-erasure.tfplan` |
| SHA-256 | `837068b155f953272600ec46a03efe9f82ef5472f00b9b6b283e67f936729148` |
| Changes | **1 add** (partner route) + **1 update** (agent Lambda code) |
| Deletes/replacements | 0 |
| State serial at plan | 55 |
| Apply | **none** |

### Tests

- Jobsearch BFF/router/client/consent: **23 passed**
- Jobsearch account-erasure browser E2E (mocked BFF): **PASS**
- Jobsearch build: **PASS**
- RIS partner/erasure focused: **77 passed**
- RIS full suite: **2555 passed**, 17 skipped, 16 pre-existing unrelated failures
- `terraform fmt -check` / `validate`: PASS

### Current blocker

Deployment is now the only remaining step for this local route: apply the
reviewed plan, deploy the Jobsearch BFF/UI, and then run the destructive
synthetic E2E with an approved isolated identity. No real data was deleted.
S3/document/backup/PITR limits remain open.

## 12. Live preview E2E with isolated synthetic identity (2026-11-09)

The exact partner-erasure plan was applied, the Jobsearch BFF was deployed to a
preview, and a real browser E2E was executed with a new isolated Cognito test
user. Only that synthetic identity was deleted.

### Deployment

- Applied `/tmp/opencode/ris-dev-partner-erasure.tfplan`, SHA-256
  `837068b155f953272600ec46a03efe9f82ef5472f00b9b6b283e67f936729148`:
  **1 add** (`POST /v1/partner/me/erasure`) + **1 update** (agent Lambda),
  0 delete/replace.
- Live partner route: `POST /v1/partner/me/erasure`.
- RIS state after deploy/allowlist rollback: serial **58**; Lambda
  `nmpYXt+WGUx6rPlkcGbYb78XuBLDmJYIUfUqVgfbh8g=`.
- Jobsearch preview `mays-job-matcher-d4rbxb3hv-maymilly.vercel.app` (removed
  after test); BFF env/flags were preview-only.
- Production Jobsearch remains `dpl_6DiPJxotbPSC8K5u8C8ZYkizTYdA` from
  `e5716f1`; this E2E did not deploy to production.

### Browser E2E

- Isolated Cognito user created for the test; `CONSENT_PILOT_ALLOWLIST` and
  preview `RIS_TEST_USER_ALLOWLIST` temporarily scoped to its exact `iss|sub`.
- Synthetic CV + manual + CV-search + ATS profile created.
- Real Settings UI, typed `LÖSCHEN`, clicked delete.
- Response: **complete=true**, `searchProfiles=3`, `documents=1`,
  `applications=0`, `credentials=0`.
- Search-profile lists after erasure: manual **0**, CV-search **0**, ATS route
  **404** (parent gone).
- Second erasure call: **complete=true**, `searchProfiles=0`, `documents=0`
  (idempotent for the exercised path).
- Screenshot: `docs/reports/assets/MAYS-P3-FINAL/p3-final-real-erasure.png`.

### Finding: CVDocument metadata remains

After the lifecycle returned `complete=true`, the synthetic `CVDocument`
metadata still appeared in `GET /api/ris/cvs`. The S3 document count was 1 and
the S3 object was deleted, but the metadata row was not part of this erasure
phase. The synthetic CV metadata was then deleted manually for cleanup.

This is an **open S3/document boundary**, not a failed search-profile deletion.
It must be resolved before claiming complete account erasure of CV documents.

### Cleanup

- Test user deleted from Cognito.
- Temporary allowlist entry removed; allowlist restored to the original
  operator identity (state serial 58).
- Synthetic CV/search profiles removed; preview deployment and preview env
  removed; local session/test artifacts deleted.
- No real user data deleted.

### Current status

`MAYS-P3-FINAL — PARTNER ERASURE ROUTE LIVE PREVIEW E2E PASS`

Production Jobsearch deployment and CVDocument-metadata erasure remain
separate approvals/open boundaries.

