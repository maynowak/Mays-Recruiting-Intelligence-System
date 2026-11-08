# JM-RIS-CV-STORAGE-INTEGRATION-01 — Durable CV Storage

## Result

`LOCAL IMPLEMENTED — TESTS GREEN — NOT DEPLOYED`

`PRODUCTION E2E NOT EXECUTED — CV NOTICE DRAFT / CORS PLAN + APPLY + RELEASE APPROVAL REQUIRED`

`RELEASE PREPARATION — AWAITING OPERATOR APPROVAL OF THE EXACT CV CONSENT TEXT`

The existing encrypted RIS document store and the existing partner CV
document routes were reused. No new storage architecture, no Terraform apply,
no AWS mutation, no Vercel deployment, no ApplicationV1 change and no general
user enablement were performed.

## 1. Discovery — what already existed

### RIS

- Private S3 document bucket `ris-dev-dev-documents` with versioning, SSE
  AES256, public-access block and `tenant/{tenant}/users/{user}/documents/{doc}`
  keys.
- Short-lived presigned PUT/GET tickets and verified `HeadObject` completion.
- Existing partner CV routes:
  `GET/POST /v1/partner/me/cvs`,
  `GET/PATCH/DELETE /v1/partner/me/cvs/{cvId}`,
  `POST .../document/upload`,
  `POST .../document/complete`,
  `GET .../document`.
- Existing CV metadata contract (`CVDocument`, capacity 10, status
  `pending → ready`, versioning, tenant/user isolation).
- Existing ApplicationV1 `cvReference` ownership verification through the
  same profile repository.

### Missing and implemented

- No separate `cv-storage` consent purpose existed; only
  `application-storage`.
- No CV-specific consent text identity / BFF text gate.
- No Jobsearch BFF for CV documents (`/api/ris/cvs`).
- No Jobsearch UI mode switch, durable CV list, upload/download/delete flow,
  or persistent-CV selection in ApplicationV1.
- S3 CORS for browser presigned PUT was not defined in Terraform.

## 2. Implemented functions

| Requirement | Implementation |
| --- | --- |
| Upload CV | Jobsearch creates RIS CV metadata, obtains a presigned ticket, PUTs the PDF directly to private S3, then calls `complete`. |
| Session vs durable | CV area has `Nur für diese Sitzung` and `Dauerhaft in meinem Konto speichern`; session default remains unchanged. |
| Protected RIS storage | Existing private, encrypted, versioned S3 bucket; no AWS/S3 credentials in the browser. |
| Load after login | `usePersistentCvStorage(token, enabled)` re-fetches the authenticated CV list after login/token change. |
| Multiple CVs | RIS list/CRUD and Jobsearch persistent list support multiple records/capacity 10. |
| Download | Short-lived RIS download ticket; browser opens the presigned URL. |
| Application selection | ApplicationV1 document tab offers `Dauerhaft gespeicherte Lebensläufe` and stores `{cvId, documentId, label, cvSource:"uploaded"}`. |
| Delete | RIS DELETE (versioned bucket; delete marker, no physical purge claim) and UI confirmation. |
| Session mode | Existing session CV upload/process flow remains available and is the default. |
| Separate consent | New `cv-storage` purpose and separate `cv-storage/1.0` notice candidate; not coupled to ApplicationV1 consent. |
| CV / builder separation | Builder profiles remain separate; persistent PDFs are labelled as stored documents, not editable builder profiles. |

## 3. RIS changes

- `jobsearch/consent_contract.py`
  - Added `cv-storage` purpose and `cv-storage/1.0` notice `DRAFT` with no
    legal approval reference.
  - Added external text ref `cv-storage-consent-2026-11-08-v1`, SHA-256
    `2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036`.
  - Added purpose-specific Art. 9 text mapping; ApplicationV1 v4 remains the
    only approved application text.
- `lambda/handler.py`
  - Added `CV_STORAGE_CONSENT_ENFORCED` (default false) and
    `_cv_storage_consent_error`.
  - The existing `CONSENT_PILOT_ALLOWLIST` is an additional server-side
    boundary: non-listed identities receive `CV_STORAGE_PILOT_NOT_ALLOWED` for
    durable CV writes when the allowlist is non-empty.
  - New CV create/upload/complete/update writes require `cv-storage` consent
    when enforced; list/get/download/delete remain available after withdrawal.
- Terraform
  - Added `cv_storage_consent_enforced` root/module variable and Lambda env
    wiring, default `false`.
  - Added private-bucket S3 CORS for the exact production origin
    `https://www.mays-job-matcher.app`, methods PUT/GET/HEAD, `ETag` exposure,
    max age 900s. No public bucket access, no policy widening.
- OpenAPI/contract docs updated with the second purpose and DRAFT notice.

## 4. Jobsearch changes

- BFF:
  - `api/_lib/ris/cvsHandler.mjs` — list/get/create/update/delete, upload
    ticket, complete, download; JWT verification, server allowlist, partner
    credential, strict CV-id/path validation, no browser identity.
  - `api/_lib/ris/cvConsentText.mjs` and config — separate CV consent text
    mapping and notice.
  - `/api/ris/cvs` and `/api/ris/cv-consents` added to the existing
    single-entry router; Vercel function count is unchanged.
- Client/UI:
  - `src/lib/cvStorageApi.ts`, `src/lib/usePersistentCvStorage.ts`.
  - `PersistentCvList` with consent gate, status, upload, download, delete.
  - `DashboardV2CvSection` mode switch and separate builder/persistent lists.
  - Application document selector includes persistent RIS CVs.
  - Settings CV purpose shows `Freigegeben`/`Zustimmung ausstehend` based on
    the separate server state; no stale blanket `Vorbereitung`.

## 5. Verification

### Jobsearch

Clean install in `/tmp/opencode/jobsearch-cv-release-check` (`npm ci`, own
`node_modules`):

- Focused CV/BFF/UI/application suites: **10 files / 142 tests PASS**.
- Full suite serial: **157 files passed / 3 skipped, 1620 tests passed /
  5 skipped, 0 failed**.
- `npm run build`: **PASS**.
- BFF routing tests include ApplicationV1 regression `/api/ris/applications`
  and `/api/ris/consents`: **91 tests PASS** in the combined focused run.

### RIS

Focused CV/consent/API tests:

- `test_cv_storage_consent_gate.py`, `test_cv_storage_consent_route.py`,
  `test_partner_cv_document_api.py`, consent catalog/special-category/
  repository, and API contract consistency:
  **134 tests PASS**. The gate now also covers the pilot allowlist:
  pilot identity allowed, non-pilot denied, consent-required write denial,
  read/delete allowed, and no global flag by default.
- `terraform fmt -check -recursive`: PASS.
- `terraform init -backend=false` + `terraform validate`: PASS (warnings only).
- Full suite: **2531 passed / 56 skipped / 6 failed**. The remaining failures
  are outside the CV/consent change surface:
  `test_composite_lifecycle` (3 arg-order assertions),
  `test_g2c7d_plan_input_contract` (formatting expectation),
  `test_health_plane_integration` (known entitlement degradation),
  `test_platform_handlers` (durable subject fence store not configured).
  The one CV/consent-related full-suite expectation was updated for the new
  second purpose and passes.

### Terraform plan (read-only)

- Pre-approval technical plan:
  `/tmp/opencode/ris-cv-storage-01-preapproval.tfplan`
- SHA-256: `5986eadd20e6a4c93a9016a889cec73abd40727da0fd6c0c3a53965c62c145e0`
- State serial `43`, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`
- Changes: **1 to add (documents S3 CORS), 1 to change (agent Lambda code +
  `CV_STORAGE_CONSENT_ENFORCED=false`), 0 to destroy**. This is not the final
  activation plan; the final plan will set the actual CV gate to `true` after
  text approval and will be regenerated with its own SHA-256.
- With explicit `mays_orders_lambda_execution_boundary`, the Mays-Orders worker
  boundary is NO-OP. Without it, the plan shows an out-of-scope boundary
  removal and must not be applied.
- Plan is saved for review; **no apply**.

## 6. Approval packet

`docs/reports/JM-RIS-CV-STORAGE-CONSENT-V1-APPROVAL-PACKET.md` contains the
full German text, version, SHA-256, purpose mapping, gate behavior, baseline
comparison and the request for the operator's explicit approval. Final plan
and notice approval remain pending.

## 7. Blockers before production

1. **CV consent notice is DRAFT** (`cv-storage/1.0`, no
   `legalApprovalRef`). The BFF correctly refuses grants until the notice is
   approved/active and the CV text mapping is configured as `APPROVED`.
2. **CORS plan/apply** is required for browser presigned PUT. Current clean
   plan has 1 add / 1 change / 0 delete; apply is not approved.
3. RIS Lambda deploy of the consent/CV gate and Jobsearch BFF deployment are
   required; neither was performed.
4. Jobsearch production env must include only after approval:
   `RIS_CV_STORAGE_ENABLED=true`,
   `RIS_CV_CONSENT_NOTICE_VERSION=1.0`,
   `RIS_CV_CONSENT_TEXT_VERSION=cv-storage-consent-2026-11-08-v1`,
   `RIS_CV_CONSENT_TEXT_SHA256=2fe65fd1…d036`,
   `RIS_CV_CONSENT_TEXT_STATE=APPROVED`, `VITE_RIS_CV_STORAGE_ENABLED=true`.
5. RIS `CV_STORAGE_CONSENT_ENFORCED=true` requires a separate reviewed plan.
6. Production E2E is not executed; no `PRODUCTION VERIFIED` status is claimed.

## 8. Deployment / rollback plan

After a separate release GO:

1. Review and apply the clean plan with the explicit Mays-Orders boundary
   variable; verify 1 add / 1 change / 0 destroy and no protected-resource
   drift.
2. Set the CV consent text/notice envs only after approval; enable
   `CV_STORAGE_CONSENT_ENFORCED=true` in a separate reviewed plan.
3. Deploy RIS Lambda and Jobsearch production; run the acceptance E2E:
   grant CV consent → upload synthetic PDF → logout/login → list → download →
   select for an application → delete → verify session mode still works.
4. Rollback frontend by disabling `VITE_RIS_CV_STORAGE_ENABLED` and redeploying
   the previous known-good Jobsearch deployment. Disable
   `RIS_CV_STORAGE_ENABLED` to stop new writes. Do not delete RIS documents or
   consent history as part of a rollback; preserve existing data and use the
   existing deletion path.

## 9. Commits

Jobsearch branch `feature/jm-ris-cv-storage-integration-01`:

- `59964a3` — `feat(cv): add durable RIS CV storage`
- report/audit commit in this branch.

RIS branch `feature/jm-ris-cv-storage-integration-01`:

- `216e061` — `feat(cv): add cv-storage consent and browser CORS plan`
- `1316647` — `test(consent): cover the separate cv-storage purpose`
- `ce55f32` — `fix(cv): scope durable CV writes to the pilot identity`
- report/audit commit in this branch.

No push, merge, deployment, Terraform apply or AWS mutation.
