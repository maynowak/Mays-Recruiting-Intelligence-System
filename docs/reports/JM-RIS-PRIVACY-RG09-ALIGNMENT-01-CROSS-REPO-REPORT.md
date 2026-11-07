# JM-RIS-PRIVACY-RG09-ALIGNMENT-01 — Cross-Repository Report

## Result

`CROSS-REPO PRIVACY ALIGNMENT VERIFIED`
`JOBSEARCH PRIVACY DISPLAY READY`
`READY FOR CONTROLLED RELEASE` (local integration; legal approvals remain a separate gate)

No push, merge, deployment, AWS/Terraform/Cognito change, new secret, or
permission expansion was performed.

## 1. Sources used

### Jobsearch

- `public/legal/datenschutz.md` / `public/legal/datenschutz.html`
- `public/legal/prinzipien.md`
- `docs/mays_job_matcher_datenschutzerklaerung_1.0.md`
- `docs/mays_job_matcher_datenschutzprinzipien.md`
- `src/components/Privacy.tsx`
- `src/components/StorageConsentLive.tsx`
- `src/components/StorageConsentSection.tsx`
- `src/lib/storageConsent.ts`
- `docs/contracts/JM-RIS-STORAGE-CONSENT-HANDOFF-V1.md`
- `docs/contracts/JM-RIS-STORAGE-CONSENT-CONTRACT-01.md`
- `docs/reports/JOBMATCHER-DATENSCHUTZ-*`, `CONSENT-PRIVACY-01`
- `docs/DEPLOYMENT.md`

### RIS

- `docs/privacy/RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md`
- `docs/contracts/CONSENT-V1.md`
- `docs/privacy/RIS_PRIVACY_DATA_INVENTORY_V1.md`
- `docs/privacy/RIS_PRIVACY_CAPABILITY_CONTRACT.md`
- `docs/privacy/USER_PRIVACY_VIEW_SPEC.md`
- `docs/reports/RIS-R08-RG09-METRICS-PRIVACY-ASSESSMENT.md`
- `docs/reports/RIS-PARTNER-USER-CONSENT-*`, `JM-RIS-CONSENT-RECONCILIATION-01`

## 2. Existing evidence reused

- RIS Consent V1 is implemented/verified locally, with versioned purposes,
  grant/withdraw/history and a DRAFT notice `1.0` (no legal approval).
- ApplicationV1 durable storage is prepared but gated/inactive by default.
- RG-09 metrics are aggregate counts only; technical privacy assessment PASS
  LOCAL, legal/retention review pending.
- RIS privacy inventory: no blanket TTL; S3 versions, backups/PITR, logs and
  receipt retention remain open; full physical deletion is not proven.
- Jobsearch storage-consent UI is preparation-gated; text version
  `2026-11-04-draft-1` is displayed-text metadata, not equivalent to RIS `1.0`.
- The old public Jobsearch HTML/Markdown contained an internal editorial review
  note and the HTML was stale versus the Markdown.

No completed audit was re-run as a new legal assessment.

## 3. Resolved differences

| Topic | Jobsearch old | RIS evidence | Consolidation |
|---|---|---|---|
| Durable CV/application storage | “im Aufbau”; separate hints | ApplicationV1 prepared, gated, consent required | One section: prepared, inactive by default, only after release + consent |
| Consent version | `2026-11-04-draft-1` in client | RIS `1.0`, DRAFT; mapping not equivalent | Public text avoids internal IDs; UI shows displayed version and RIS version; report records mapping |
| RG-09 metrics | absent | aggregate counts; legal review pending | Added “Bewerbungskennzahlen” with six aggregate counts, no CV/IDs |
| Retention/deletion | generic; older HTML claimed a server cache | no blanket TTL; S3 versions/backups/logs survive | One accurate section: no blanket period; partial deletion/backups explicit |
| Identity | account via RIS/Cognito | iss+sub+partner credential; email not identity | Account section aligned; no email-as-identity claim |
| Public HTML vs MD | HTML stale, internal note in both | — | Both regenerated from one Markdown source; internal note removed |
| Route/display | `/datenschutz` link only; no direct rewrite | — | `Privacy.tsx` fetches/displays MD; rewrites added for both privacy routes |

## 4. Final document

- Public path: `public/legal/datenschutz.md`
- Mirror: `public/legal/datenschutz.html`
- Version: **1.1 · 7. November 2026**
- Sections now cover: responsible party, scope, legal bases, hosting, job
  search, AI providers, CV/browser processing, account/RIS, optional
  ApplicationV1 storage, consent/versioning/withdrawal, RG-09 metrics, alerts,
  external sources, cookies/local storage, recipients/transfers, retention and
  deletion, security, rights, changes.
- Internal editorial/audit notes were removed from the public text.
- Pending legal/retention/provider items are explicitly marked as pending, not
  invented.

## 5. Jobsearch integration

- `Privacy.tsx` now fetches and renders the current Markdown in-page; it remains
  available without login.
- Direct links to the raw Markdown and privacy principles remain.
- `StorageConsentLive` now links directly to the privacy notice and shows the
  displayed text version plus the RIS notice version.
- `vercel.json` now rewrites `/datenschutz` and `/datenschutzprinzipien` to the
  SPA, so direct navigation works.
- Responsive CSS for the document uses `pre-wrap`, `overflow-wrap:anywhere`, and
  a mobile width constraint.

## 6. RIS review

- RIS agent session `ses_e49e9b94bffeeqW6GiCOn1Pseq`
- Verdict: **PASS**
- Confirmed: ApplicationV1 gating, consent states/versioning/withdrawal/history,
  RG-09 aggregate metrics, no legal approval claimed, retention/backups/versions
  correctly described as partial/pending.
- Only info/low notes; no blocking contradiction. One low note: privacy-receipt
  retention is covered generically rather than named explicitly.
- Review artifact: `docs/reports/JM-RIS-PRIVACY-RG09-RIS-REVIEW.json` (RIS
  feature branch).

## 7. Jobsearch review

- Jobsearch agent session `ses_e49ea284bffexefbb3iDz6bO2K`
- Verdict: **PASS**
- Confirmed public route, no login requirement, display behavior, version/date,
  explicit pending markers, and no factual contradiction.
- Review artifact: `docs/reports/JM-RIS-PRIVACY-RG09-JOBSEARCH-REVIEW.json`
  (Jobsearch agent worktree).

Long-running analysis sessions timed out and were **not** used as evidence.
The final reviews above are real, completed OpenCode sessions.

## 8. Tests actually executed

Jobsearch:

- Focused Privacy/Consent/Footer tests: **18/18 PASS**
- `npm run build`: **PASS**
- Full Vitest suite: **1535 passed, 5 skipped, 1 failed** in
  `CvBuilderEditorPdf.test.tsx` (unrelated to privacy); rerun in isolation:
  **4/4 PASS** — flake, not a privacy regression.
- `git diff --check`: PASS.

RIS:

- Selected privacy/erasure tests: **53 passed**
  (`test_privacy_receipt_contract.py`, `test_application_privacy_contract.py`,
  `test_privacy_erasure_security.py`).
- Two older consent test modules (`test_consent_notice_lifecycle.py`,
  `test_consent_repository.py`) fail collection on `main` with
  `NameError: ConsentContext is not defined`; this is pre-existing and unrelated
  to this documentation task. No RIS code was changed.

## 9. Git evidence

| Repo/branch | Commit | Purpose |
| --- | --- | --- |
| Jobsearch `feature/jm-ris-privacy-rg09-alignment-01` | `5fcb66d` | consolidated policy, HTML, display, consent link, rewrites, tests, audit |
| RIS `feature/jm-ris-privacy-rg09-alignment-01` | `efca176` | RIS review artifact and audit |
| Jobsearch `agent/jobsearch-privacy-rg09` | `ef63337` | agent definition |
| Jobsearch `agent/jobsearch-privacy-rg09` | `c426276` | Jobsearch review |
| RIS `agent/ris-privacy-rg09` | `93f5a4b` | agent definition |
| RIS `agent/ris-privacy-rg09` | `d308093` | RIS review |

No branch was pushed. `origin/main` remained:
- Jobsearch `4e2b640`
- RIS `1068d83`

## 10. Remaining concrete items

1. Legal approval of the consent notice `1.0` / displayed text version and the
   final retention policy is still pending. The public text marks this as
   pending and does not claim approval.
2. Final recipient list, processor contracts and third-country safeguards must
   be confirmed against the productive configuration.
3. ApplicationV1/durable storage and the live consent UI remain gated/inactive
   until the separate release approval.
4. RIS privacy-receipt retention is not explicitly named in the public policy;
   it is covered by the general pending-retention wording. This is a low
   completeness note, not a contradiction.
5. Two pre-existing consent test modules have a collection error on `main`;
   separate cleanup is recommended.
6. A real browser/mobile visual check and the productive route check remain
   part of the controlled release step; local tests/build and CSS are verified
   here.

## 11. Status

`CROSS-REPO PRIVACY ALIGNMENT VERIFIED`

`JOBSEARCH PRIVACY DISPLAY READY`

`READY FOR CONTROLLED RELEASE` — local only; no publication, push or deployment.
