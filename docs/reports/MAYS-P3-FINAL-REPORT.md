# MAYS-P3-FINAL — Orchestrated E2E & Release Closure

**Result:** `BLOCKED — PARTNER-EDGE ERASURE ROUTE MISSING + JOBSEARCH DEPLOYMENT PENDING`  
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

