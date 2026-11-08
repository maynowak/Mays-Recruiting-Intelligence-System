# SEARCH-PROFILE-STORAGE-03 — Approved-Pilot E2E Runbook

**Status:** `PREPARED — NOT EXECUTED`  
**Notice:** `search-profile-storage/1.0` `APPROVED`  
**Text:** `search-profile-storage-consent-2026-11-08-v2`  
**SHA-256:** `75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6`

## 1. Preconditions

- Applied RIS plan `d6cfcda99a73dacf6ed44f111c42f719f8c401dcea6d7edb82caf9bfd1e2576a`
  (only after explicit GO APPLY).
- Jobsearch preview deployment with:
  - `RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`
  - `RIS_CONSENT_SERVICE_ENABLED=true`
  - `RIS_SEARCH_PROFILE_CONSENT_NOTICE_VERSION=1.0`
  - `RIS_SEARCH_PROFILE_CONSENT_TEXT_VERSION=search-profile-storage-consent-2026-11-08-v2`
  - `RIS_SEARCH_PROFILE_CONSENT_TEXT_SHA256=75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6`
  - `RIS_SEARCH_PROFILE_CONSENT_TEXT_STATE=APPROVED`
  - `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`
  - `RIS_TEST_USER_ALLOWLIST=<confirmed operator issuer|sub>`
- RIS `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=false` for the first run.
- Synthetic ready CV `$CV_ID`; no real applicant data.
- Existing Cognito login only; no new login flow.

## 2. Web E2E

1. Log in with the existing Cognito account.
2. Open the search-profile area.
3. Verify the displayed consent text is v2 and the notice is `APPROVED`.
4. Grant consent; verify `GRANTED`.
5. Create a manual profile `synthetic-manual-01`; save.
6. Edit it, save, reload the page, and verify it is still present.
7. Create a CV-search profile under the durable `$CV_ID`; save and edit.
8. Create an ATS profile under that CV-search profile; save.
9. Reload and verify manual, CV-search and ATS profiles are still present.
10. Withdraw consent; verify `WITHDRAWN`.
11. Verify existing profiles remain readable and deletable.
12. Delete ATS, then CV-search, then the manual profile.
13. Regrant; create one new synthetic manual profile; verify it persists after reload.
14. Delete it; withdraw; verify cleanup.

## 3. Server gate check

After the first run, use a **separate reviewed plan** with
`SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true`:

1. Withdraw consent.
2. POST/PUT a profile via the UI/BFF → expect `403`
   `SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED`.
3. Verify list/read and delete still work.
4. Regrant → new write succeeds.
5. Delete all synthetic data and withdraw.

The 403 result may only be reported after the enforcement plan has been
explicitly approved and applied.

## 4. Evidence

Record:

- actual preview URL and deployment ID;
- Lambda code hash `pStIe5JG66TGF6PyltAmLJQ/0yKSgoWI6H7AmrAKwHU=`;
- consent state transitions `NOT_GRANTED → GRANTED → WITHDRAWN → GRANTED`;
- text version/hash and `APPROVED` notice;
- synthetic profile IDs (no PII);
- 403 code and read/delete statuses;
- cleanup: all lists empty;
- non-allowlisted identity check.

## 5. Cleanup

Delete all synthetic profiles child-first, withdraw consent, remove preview
test flags, and do not delete consent history. No real data.
