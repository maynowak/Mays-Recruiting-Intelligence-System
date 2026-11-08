# SEARCH-PROFILE-STORAGE-01 — Implementation Report

**Status:** `IMPLEMENTED / VERIFIED LOCAL / READY FOR DEPLOYMENT REVIEW`

**Date:** 2026-11-08
**Architecture decision:** Option A confirmed
**Activation:** not performed; no AWS apply, no Vercel deployment, no real-user data

## 1. Scope

Implement durable storage for:

- **manual search profiles** — no CV parent;
- **CV search profiles** — only under a durable RIS `cvId`;
- **ATS profiles** — only under a durable CV-search profile id.

Session CVs and their associated search/ATS profiles remain session-only. There
is no automatic CV upload and no silent migration from a session CV hash to a
RIS CV id.

The existing ApplicationV1 and CV-storage contracts were not changed. The new
purpose is separate: `search-profile-storage`.

## 2. Consent candidate

| Field | Value |
| --- | --- |
| Text version | `search-profile-storage-consent-2026-11-08-v1` |
| SHA-256 | `926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8` |
| RIS notice | `search-profile-storage/1.0` |
| Notice state | `DRAFT` |
| `legalApprovalRef` | `null` |
| `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | `false` |
| `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED` | absent |

The text and the RIS notice are deliberately not marked `APPROVED` or
`ACTIVE`. No legal approval is invented. A real consent grant is blocked while
the notice/text are DRAFT. The explicit local-only
`RIS_SEARCH_PROFILE_CONSENT_SYNTHETIC=true` switch is used solely to exercise a
synthetic DRAFT grant in tests; it is not a production activation.

## 3. RIS changes

- `jobsearch/consent_contract.py`
  - purpose `search-profile-storage` / notice `1.0` as `DRAFT`,
    `legalApprovalRef=None`;
  - partner text ref `search-profile-storage-consent-2026-11-08-v1` as
    `DRAFT`/unmapped with pinned SHA-256.
- `lambda/handler.py`
  - `_search_profile_storage_consent_enforced()` default `false`;
  - `_search_profile_storage_consent_error(ctx)` fails closed when enforced,
    reuses the existing pilot allowlist, and returns
    `SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED` / `..._PILOT_NOT_ALLOWED`;
  - writes covered: manual POST/PUT, CV-search POST/PUT/PATCH, ATS POST/PUT;
  - list/get/delete remain available after withdrawal.
- Terraform
  - root + lambda module variable
    `search_profile_storage_consent_enforced = false`;
  - Lambda env `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`.
- Tests
  - notice/text candidate contract;
  - gate default-off and fail-closed behavior;
  - manual/CV-search/ATS route-level write blocks;
  - synthetic grant → withdraw → regrant against the real consent repository;
  - Terraform default-off wiring.

## 4. Jobsearch changes

- `api/_lib/ris/searchProfilesHandler.mjs` — one BFF route:
  - `/api/ris/search-profiles?type=manual`
  - `/api/ris/search-profiles?type=cv&cvId={cvId}`
  - `/api/ris/search-profiles?type=ats&searchProfileId={id}`
  - existing RIS contracts, `limit` and `cursor` reused; IDs validated;
    browser cannot select tenant/user or notice version.
- `api/_lib/ris/searchProfileConsentText.mjs` — server-owned text mapping.
- `api/_lib/ris/consentsHandler.mjs` — separate purpose
  `search-profile-storage`; no Art. 9 declaration for this ordinary
  professional-profile purpose; DRAFT text remains blocked.
- `api/ris/router.mjs` + `vercel.json` — two new rewrites, still one router and
  one consent system.
- `src/lib/searchProfilesApi.ts` — typed client for all three contracts.
- `src/lib/usePersistentSearchProfiles.ts` — consent + manual persistence +
  CV/ATS operations.
- `src/components/ManualSearchProfilesSection.tsx` — existing manual UI now
  shows session/persistent state, the separate consent status and the full
  DRAFT text; grant stays disabled while not approved.
- `src/components/PersistentCvList.tsx` + `PersistentCvProfilesOverlay.tsx` —
  persistent CV list opens CV-search/ATS profile management for that durable
  `cvId` only.
- Session repositories and session CV profile code are unchanged.

## 5. Verification evidence

### RIS

Command:

```bash
python3 -m pytest -q \
  tests/test_consent_notice_catalog_contract.py \
  tests/test_consent_notice_lifecycle.py \
  tests/test_consent_gate.py \
  tests/test_cv_storage_consent_gate.py \
  tests/test_cv_storage_consent_route.py \
  tests/test_search_profile_storage_consent_gate.py \
  tests/test_partner_manual_profiles_api.py \
  tests/test_partner_cv_search_profiles_api.py \
  tests/test_partner_ats_profiles_api.py \
  tests/test_partner_terraform_wiring.py \
  tests/test_partner_profile_integration_harness.py
```

Result: **208 passed**.

Full RIS suite: **2536 passed, 17 skipped, 16 failed**. The remaining failures
are the pre-existing project-config/composite/health/platform set in this
worktree (e.g. `cv_storage_consent_enforced` not yet in
`PROJECT_CONFIG_ALLOWED_KEYS`); none concern the search-profile path.

### Jobsearch

Commands:

```bash
npx vitest run \
  tests/api/ris-search-profiles.test.mjs \
  tests/api/ris-routing.test.mjs \
  tests/api/ris-cvs.test.mjs \
  src/lib/searchProfileStorageConsent.test.ts \
  src/lib/searchProfilesApi.test.ts \
  src/lib/manualSearchProfiles.test.ts

npm run build
```

Result: **58 tests passed** and **production build passed** (`tsc -b && vite
build`).

Full Jobsearch suite: **1593 passed, 5 skipped, 9 failed**. The failures are in
this worktree's pre-existing pdfjs/worker-path test environment
(`Denied ID .../node_modules/pdfjs-dist/build/pdf.worker.min.mjs?url`) and
unrelated CV-builder PDF timing; the new targeted suites are green.

## 6. Consent write behavior

| Path | Without enforcement | With enforcement + no grant | After withdrawal |
| --- | --- | --- | --- |
| manual POST/PUT | allowed (rollout off) | 403 | 403 |
| CV-search POST/PUT/PATCH | allowed (rollout off) | 403 | 403 |
| ATS POST/PUT | allowed (rollout off) | 403 | 403 |
| list/get/delete | allowed | allowed | allowed |

## 7. Deployment review checklist

- [ ] Operator approves the consent text and fills `legalApprovalRef`,
      approval date and approving body.
- [ ] RIS notice `search-profile-storage/1.0` is changed from `DRAFT` to
      `APPROVED`/`ACTIVE` by an explicit change, not automatically.
- [ ] `RIS_SEARCH_PROFILE_CONSENT_TEXT_STATE=APPROVED` and the canonical
      version/hash are set in the deployment environment.
- [ ] `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true` only after a separate
      activation decision.
- [ ] `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED=true` only with the deployment.
- [ ] `RIS_SEARCH_PROFILE_STORAGE_ENABLED=true` and the existing RIS/consent
      service envs are present.
- [ ] Synthetic allowlist remains scoped; no general rollout.
- [ ] Separate Vercel deploy / AWS plan+apply approval.

## 8. Commit references

- RIS: `fc32aad` — `feat(profiles): add search-profile consent purpose and write gate`
- Jobsearch: `4811a23` — `feat(profiles): add persistent search-profile BFF and UI`
- Jobsearch consent candidate: `b22a851` — `docs(profiles): add search-profile consent candidate`

No push, merge, apply or deploy was performed.
