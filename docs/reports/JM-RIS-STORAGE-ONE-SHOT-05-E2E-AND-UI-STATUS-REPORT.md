# JM-RIS-STORAGE-ONE-SHOT-05 — ApplicationV1 Production E2E & UI Status Fix

## Result

`APPLICATIONV1 PRODUCTION E2E VERIFIED — SYNTHETIC DATA CLEANED`

`UI STATUS FIX IMPLEMENTED LOCALLY — NOT DEPLOYED, RELEASE APPROVAL PENDING`

No new infrastructure, no Terraform apply, no new consent version, no general
rollout and no real applicant data were used.

## 1. Production targets

| Item | Value |
| --- | --- |
| Site | `https://www.mays-job-matcher.app` |
| Production build | `e9a4116` (footer Build SHA) |
| `mays-job-matcher` deployment | `dpl_FtVGZeNwHpNCesWY5fWJKLH6Dyji` (READY, `www` alias) |
| `mays-jobsearch` deployment | `dpl_6QX58A7At7AhuavCCd4pALNtBj3G` (READY) |
| RIS-DEV plan | `d9689931cab89181ec9262407b85dd37ec107f8ae5db32d1241163a6a0a6d532` |
| RIS-DEV apply | 0 added / 1 changed / 0 destroyed; state serial 43; agent Lambda code `xcbJ2JEI3ouo7VRXMT1nOtei7wlvQEhdTPhKNzJDA1U=` |
| Operator identity | issuer `https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ZURSMpD2O`, subject `2344d8d2-f0e1-70a4-a1ff-1b7a6c843558` |
| Consent text | `application-storage-consent-2026-11-07-v4` |
| Consent SHA-256 | `8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7` |
| RIS notice | `application-storage/1.0`, state **APPROVED** (not `ACTIVE`) |
| `legalApprovalRef` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |

Only the confirmed operator identity was enabled. No tokens, cookies or
credentials are reproduced in this report.

## 2. Live BFF/contract verification

`GET /api/ris/consents` with the operator session returned **200**:

- `consent.status = GRANTED`
- `consent.noticeVersion = 1.0`
- `consent.externalTextVersion = application-storage-consent-2026-11-07-v4`
- `consent.externalTextSha256 = 8722aed9…43c7`
- `consent.specialCategoriesConsent = true`
- nine Art. 9 categories including `sex_life` and `sexual_orientation`
- `noticeState = APPROVED`, `textState = APPROVED`, `textMapped = true`,
  `textApproved = true`, `grantAllowed = true`

The settings UI initially rendered a stale preparation state while the BFF was
already returning the granted state. After the live request completed, the same
UI showed `Status: erteilt (Textversion 1.0)` and
`Textstatus: rechtlich freigegeben (APPROVED)`. This timing/state display is
covered by the UI fix below.

Transient observation: one immediate post-E2E `GET /api/ris/consents` returned
**503**; three immediate retries returned **200** with the same GRANTED/APPROVED
state. No persistent consent-service failure was observed.

## 3. Synthetic production E2E

All data was synthetic and visibly labelled as such. No real applicant data was
entered.

| Step | Evidence |
| --- | --- |
| Create | Synthetic application created in production, `applicationId = d66c3482-70c5-4bca-a742-78b179d4c719`; `jobId = manual:ebfc8266-69dc-4397-881e-b3aaace99385`; title `Synthetic Pilot Role`; company `Synthetic Pilot Company`; location `Berlin`; created `2026-11-08T08:15:14.397167+00:00` |
| Reload / persisted | Page reload and applications tab reload returned the same server-backed application; list count `1` |
| Update | Notes updated through the applications UI; server version advanced to `2`, `updatedAt = 2026-11-08T08:16:13.375225+00:00` |
| Export | `Lokalen Entwurf exportieren` produced `bewerbung-d66c3482-70c5-4bca-a742-78b179d4c719.json` (938 bytes), `schemaVersion 1`, `localDraft false`, `note "Server-backed application"`, application version `2` |
| Withdraw | UI withdrawal returned `200` with `consent.status = WITHDRAWN`, `withdrawnAt = 2026-11-08T08:21:16.234112+00:00` |
| Write block | `PATCH /api/ris/applications?id=…` after withdrawal returned **403** `forbidden`; no write occurred |
| Read after withdrawal | `GET` returned **200**, version `2`; export returned **200**, version `2` |
| Delete | UI deletion returned **200** `{ "deleted": true, "idempotent": false }`; subsequent list returned `0` items |
| Cleanup | Synthetic application deleted; no synthetic application remains |
| Regrant | UI regrant returned **200** `GRANTED` at `2026-11-08T08:22:27.433881+00:00`, Art. 9 consent `true`, v4 text version recorded |

The operator account was left with the application-storage consent granted so
the limited pilot remains usable.

## 4. UI defects confirmed by the E2E

1. Overview/profile and settings showed hard-coded `Vorbereitung` and
   `Nicht freigegeben` even though the server had `GRANTED` / `APPROVED`.
2. The overview card claimed durable application storage was not available.
3. The applications remote notice said `RIS bleibt Eigentümer des gespeicherten
   Datensatzes`; that ownership statement is misleading.
4. A legacy data-controls block remained disabled with
   `backend_unavailable` and an obsolete consent-text version.
5. When the Art. 9 checkbox was unchecked, the UI claimed the consent text was
   not approved, although the server text state was `APPROVED`. The only
   missing action was the explicit Art. 9 check.

## 5. UI status fix (local implementation)

### Behaviour

- Overview, settings and application-status displays now use the server-side
  consent status for the active `application_storage` purpose.
- `Vorbereitung` remains only where it is true: CV and search-profile storage
  are still session-only and have no separate persistence integration.
- The active purpose shows `Aktiv` / `Freigegeben`, or
  `Zustimmung erforderlich` / `Widerrufen` when applicable.
- The obsolete disabled `Datenkontrolle` block and `backend_unavailable`
  metadata are removed while the live consent UI is enabled.
- The remote application notice now says that the data remains assigned to the
  user's account and that RIS is the storage service. It no longer claims RIS
  owns the record.
- The Art. 9 hint now asks for the missing explicit check instead of falsely
  reporting an unapproved text version.

### Files

- `src/lib/storageConsentDisplay.ts` (new display-state helper)
- `src/components/StorageConsentOverview.tsx` (new server-backed overview card)
- `src/components/StorageConsentSection.tsx` (dynamic status and preparation
  hints)
- `src/components/StorageConsentLive.tsx` (publishes server state; corrected
  Art. 9 hint)
- `src/components/DashboardV2.tsx` (uses the server-backed overview card)
- `src/i18n.tsx` (active/checking/unavailable/withdrawn labels; ownership text)
- tests: `storageConsentDisplay.test.ts`,
  `StorageConsentSection.active.test.tsx`, `StorageConsentOverview.test.tsx`,
  `StorageConsentLive.test.tsx`, `ApplicationsSection.remote.test.tsx`

### Verification

- Targeted tests: `npx vitest run src/lib/storageConsentDisplay.test.ts
  src/components/StorageConsentSection.test.tsx
  src/components/StorageConsentSection.active.test.tsx
  src/components/StorageConsentLive.test.tsx
  src/components/StorageConsentOverview.test.tsx
  src/components/DashboardV2.test.tsx
  src/components/ApplicationsSection.remote.test.tsx`
  = **7 files / 38 tests PASS**.
- `npm run build` = PASS (TypeScript + Vite).
- Full suite was also run: **1560 passed, 5 skipped, 9 failed in 7 files**. The
  failures are environmental in this worktree: Vite denies the `pdfjs-dist`
  worker URL because `node_modules` is a symlink to the main checkout
  (`Denied ID .../repos/mays-jobsearch/node_modules/pdfjs-dist/...`). The
  changed-file suites above pass. No product-code failure was observed in the
  changed area.

### Release status

The UI fix is committed locally only. It is **not deployed**; deployment
requires a separate explicit release approval. No new consent text, no v5, no
architecture change and no general rollout.

## 6. Cross-repository review

- The Jobsearch UI consumes only the existing RIS consent contract
  (`GET/POST /consents`, status, notice state, external text version/hash,
  special-category proof). No new RIS field or endpoint is required.
- The live production response confirms RIS returns the approved v4 text,
  `noticeState=APPROVED`, `textState=APPROVED`, and the nine Art. 9 categories.
- The write-block behaviour after withdrawal was verified in production:
  `PATCH` returned 403 while `GET` and export remained available.
- No RIS code, Terraform, state, notice, environment or deployment was changed
  by this UI fix.

## 7. Remaining open points

- Full account deletion / ApplicationV1 account erasure.
- Final consent-history retention period.
- DPA/transfer review for AWS/Vercel.
- Explicit release approval for the UI fix deployment.
- General rollout approval beyond the confirmed operator limited pilot.
