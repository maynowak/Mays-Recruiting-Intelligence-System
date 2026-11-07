> **RIS documentation copy.** The production release was performed in
> `maynowak/mays-jobsearch`. This copy is stored in the RIS repository for
> cross-repository audit. No RIS source code, infrastructure, deployment,
> Terraform, AWS, Cognito, consent enforcement, or ApplicationV1 gate was
> changed by this release.

# JM-RIS-PRIVACY-RG09-PRODUCTION-RELEASE-04-REPORT

## Result

`PRIVACY V1.1 PRODUCTION VERIFIED`

The verified Jobsearch privacy policy **Version 1.1 · 7. November 2026** is
live on both production projects. No merge, infrastructure, consent, or
ApplicationV1 change was made outside the approved release scope.

## 1. Release input and approval

| Item | Value |
| --- | --- |
| Repository | `maynowak/mays-jobsearch` |
| Source branch | `feature/jm-ris-privacy-rg09-alignment-01` |
| Approved candidate | `adfe23f7644c6a331090f6ebd80034993dee1d67` |
| Base `main` before merge | `4e2b64013c096fecf830147f17659068ef876aa7` |
| Approval | `GO JM-RIS-PRIVACY-RG09-PRODUCTION-RELEASE-04` |
| PR | [#4](https://github.com/maynowak/mays-jobsearch/pull/4) |
| Merge commit | `2aed1c3a31cd6b91ebf2e4174e0c3353cffc2181` |
| Merge method | regular merge commit, no force, no branch deletion |
| Feature branch after merge | retained at `adfe23f7644c6a331090f6ebd80034993dee1d67` |

### Pre-merge verification

- PR was `MERGEABLE` and `CLEAN`; no branch protection on `main`.
- All checks passed: CodeQL JavaScript/TypeScript, Vercel Preview Comments,
  Vercel Deployments, `mays-jobsearch`, `mays-job-matcher`.
- Diff against `main` was limited to privacy content/display, routing,
  privacy tests, `vercel.json`, reports, screenshots, and the audit log.
- No RIS product code, AWS, Terraform, Cognito, consent activation, or
  ApplicationV1 files were changed.
- `git diff --check`: PASS.

## 2. Production deployments

Both deployments were triggered by merge commit `2aed1c3` and reached
`READY` with `target=production`.

| Project | Deployment ID | Immutable URL | Production aliases |
| --- | --- | --- | --- |
| `mays-jobsearch` | `dpl_HEzi1SxsVN7jgajq3EehyEEX21q6` | https://mays-jobsearch-9cv51frue-maymilly.vercel.app | `mays-jobsearch.vercel.app`, `mays-jobsearch-maymilly.vercel.app`, `mays-jobsearch-git-main-maymilly.vercel.app` |
| `mays-job-matcher` | `dpl_yAmFr8JxrY2G4qis6g82hbGVB85x` | https://mays-job-matcher-dau0ne2fb-maymilly.vercel.app | `www.mays-job-matcher.app`, `mays-job-matcher.app`, `mays-job-matcher.vercel.app`, `mays-job-matcher-maymilly.vercel.app`, `mays-job-matcher-git-main-maymilly.vercel.app` |

- Both deployment records carry Git commit
  `2aed1c3a31cd6b91ebf2e4174e0c3353cffc2181`.
- Both deployment records report `readyState=READY`.
- No deployment error or build warning was recorded for either project.

## 3. HTTP verification

Checked against both production aliases. `/datenschutz` is a client-rendered
SPA route, so the raw HTTP shell does not contain the policy body; the
browser-rendered DOM was verified separately below.

| Path | `www.mays-job-matcher.app` | `mays-jobsearch.vercel.app` | Content result |
| --- | --- | --- | --- |
| `/datenschutz` | 200 | 200 | SPA shell; browser renders v1.1 |
| `/legal/datenschutz.md` | 200 | 200 | Version 1.1 · 7. November 2026; no internal note |
| `/legal/datenschutz.html` | 200 | 200 | Version 1.1; semantic `<h1>/<h2>`; no `<pre>`; no internal note |
| `/datenschutzprinzipien` | 200 | 200 | Existing principles page; footer target works |

The Markdown and HTML mirrors both contain the public version marker
`Version 1.1 · Stand: 7. November 2026`. The HTML mirror renders the policy
as semantic headings and paragraphs rather than a single `<pre>` block.

## 4. Browser verification

Playwright/Chromium, production aliases, desktop 1440×900 and mobile 390×844.

| Check | `www.mays-job-matcher.app` desktop | mobile | `mays-jobsearch.vercel.app` desktop | mobile |
| --- | --- | --- | --- | --- |
| HTTP status | 200 | 200 | 200 | 200 |
| Final URL | `/datenschutz` | `/datenschutz` | `/datenschutz` | `/datenschutz` |
| Version 1.1 · 7 Nov 2026 | PASS | PASS | PASS | PASS |
| Internal editorial note | ABSENT | ABSENT | ABSENT | ABSENT |
| H1 / H2 / H3 | 1 / 1 / 19 | 1 / 1 / 19 | 1 / 1 / 19 | 1 / 1 / 19 |
| Paragraphs | 38 | 38 | 38 | 38 |
| Footer links | 5 | 5 | 5 | 5 |
| Horizontal overflow | NONE | NONE | NONE | NONE |
| Footer navigation to `/datenschutzprinzipien` | PASS | — | PASS | — |
| Public without login | PASS | PASS | PASS | PASS |
| Old static version 1.0 page | GONE | GONE | GONE | GONE |

Footer links observed on both production sites:
`Impressum`, `Datenschutz`, `Datenschutzprinzipien`, `Arbeitnow`,
`Arbeitsagentur`.

The footer navigation opened the correct production URL:
- `https://www.mays-job-matcher.app/datenschutzprinzipien`
- `https://mays-jobsearch.vercel.app/datenschutzprinzipien`

## 5. Active privacy version

- Public policy: **Version 1.1 · Stand: 7. November 2026**.
- No old Version 1.0 static page is served on `/datenschutz`.
- No internal editorial/review note is present in the public response.
- `/datenschutzprinzipien` remains its existing static page and uses a
  `<pre>` presentation; it is not the privacy policy and was not part of the
  Version 1.1 policy replacement.

## 6. Consent and ApplicationV1 configuration

**Unchanged.** The release diff contains no change to:

- `src/lib/storageConsent.ts` (consent text/version source),
- `.env`, `.env.*`, or Vercel environment variables,
- `api/` BFF routes or RIS backend configuration,
- Terraform, AWS, Cognito, CloudFront, DNS, or ACM,
- `APPLICATION_CONSENT_ENFORCED`,
- `VITE_RIS_CONSENT_UI_ENABLED`,
- ApplicationV1 feature gates.

The only consent-related UI change is in `StorageConsentLive.tsx`: it adds a
link to `/datenschutz` and displays the shown draft text version and the RIS
notice version. It does not enable, enforce, or widen a consent feature.
No production environment value was read, printed, or changed.

## 7. Tests and evidence

- Focused Privacy/Consent/Footer tests: **20/20 PASS**.
- `npm run build`: **PASS**.
- `git diff --check`: **PASS**.
- Known unrelated PDF flake:
  `CvBuilderEditorPdf.test.tsx` failed once in the full run
  (1535 passed, 5 skipped, 1 failed); isolated run **4/4 PASS**.
  No relation to privacy routing or content.
- RIS selected privacy tests: **53 PASS**; two older consent test modules
  still fail collection with `NameError: ConsentContext is not defined` on
  `main` (pre-existing, not changed by this release).
- Production HTTP/browser evidence:
  `docs/reports/assets/JM-RIS-PRIVACY-RG09-PRODUCTION-RELEASE-04/results.json`
  plus desktop/mobile screenshots for both projects.

## 8. Safety boundaries

- No force-push, no branch deletion, no direct push to `main` before the PR.
- No RIS deployment, RIS product change, AWS/Terraform/Cognito mutation.
- No consent activation or ApplicationV1 activation.
- No new secret, permission, token, or credential.
- Only the approved Jobsearch privacy release was merged to `main`.
- The feature branch remains available for audit and rollback.

## 9. Open points

1. Legal approval of the consent notice version and the retention/recipient/
   transfer items remains a separate gate.
2. `/datenschutzprinzipien` still uses the existing static `<pre>` page; a
   future content/design update is outside this release.
3. RIS `ci-cd.yml` retains its pre-existing zero-job failure behavior for
   pushes; this release did not modify or trigger any Terraform/AWS work.
4. A rollback, if ever required, should revert the merge commit or deploy a
   prior known-good production deployment; no rollback was performed.

## 10. Final status

`PRIVACY V1.1 PRODUCTION VERIFIED`

`READY FOR OPERATIONAL USE` for the published privacy policy. Legal and
consent-enforcement approvals remain separate from this release.
