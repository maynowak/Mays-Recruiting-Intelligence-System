# JM-RIS-CV-STORAGE-INTEGRATION-01 — Durable CV Storage

## Result

`PRODUCTION E2E VERIFIED — CV STORAGE PILOT ACTIVE FOR THE CONFIRMED OPERATOR`

No general user enablement. The existing encrypted RIS document store and
partner CV routes were reused; no new storage architecture and no
ApplicationV1 change.

Production deployment: `dpl_5C27DWhDpLT74tbyubbr4mNibCPo` at Build `c3da077`,
aliased to `https://www.mays-job-matcher.app`.

## 0. Production release, incident fixes and E2E

The first production smoke exposed a client pagination bug: the persistent CV
list requested `limit=100`, while RIS caps CV list pagination at `50`; the UI
therefore showed the list error. That release was stopped and the previous
known-good frontend was promoted. A second smoke then exposed a missing IAM
action for the repository's delete reservation: `dynamodb:ConditionCheckItem`.
The action was added for the partner-profile table only; no new resource,
policy widening or Mays-Orders change.

After both fixes:

- Jobsearch PR #8 merged as `c3da077908f72c2fd483279613c10e8a59119d37`.
- Production deployment `dpl_5C27DWhDpLT74tbyubbr4mNibCPo`, Build `c3da077`,
  `www` alias, READY.
- CV consent granted with notice `cv-storage/1.0` `APPROVED`.
- Synthetic PDF uploaded: `pending → ready`; direct S3 PUT 200; complete 200.
- Browser closed and operator re-authenticated; CV and ApplicationV1
  reference were still present.
- Download after restart: 13,569 bytes, SHA-256
  `365ac570ea6da87f1631b05d043824982147410a645b6fae7e661d845cbf4f6c`,
  identical to the source.
- ApplicationV1 selection stored `cvId` + `documentId`.
- CV consent withdrawal: 200 `WITHDRAWN`.
- Post-withdrawal create: 403 `CV_STORAGE_CONSENT_REQUIRED`.
- List and download remained 200; deletion returned 200 with a delete marker
  (`physicalPurge: false`).
- Synthetic application deleted (200, list count 0).
- CV consent regranted; CV list count 0. Session mode remains functional.
- The final CV was deleted with a delete marker; older S3 versions are not
  claimed to be physically purged.

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
| Separate consent | New `cv-storage` purpose and `cv-storage/1.0` notice APPROVED for the limited beta pilot; not coupled to ApplicationV1 consent. |
| CV / builder separation | Builder profiles remain separate; persistent PDFs are labelled as stored documents, not editable builder profiles. |

## 3. RIS changes

- `jobsearch/consent_contract.py`
  - Added `cv-storage` purpose and `cv-storage/1.0` notice `APPROVED` with
    `legalApprovalRef=JM-CV-STORAGE-V1-BETA-2026-11-08` (limited beta pilot).
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
- OpenAPI/contract docs updated with the second purpose and approved limited-pilot notice.

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

### Terraform application (evidence)

- Initial approved activation plan
  `cd099de482abe851b1bad1a3defa5c3d4ac93811e06a73df1174e4431beac3a3`
  applied: 1 add (S3 CORS), 1 change (agent Lambda +
  `CV_STORAGE_CONSENT_ENFORCED=true`), 0 destroy; state serial 44.
- Diagnostic Lambda-only plan
  `d4cd9ea68c1fe138c0fe60aaa78838273e49360883e5a4222392f849911784a9`
  applied: 1 change, 0 destroy.
- IAM-only fix plan
  `c60c01de9fffb2e61208a3e6722792ba6306c59f6d1e454e10349396fe7abe69`
  applied: 1 change (`dynamodb:ConditionCheckItem` on the partner-profile
  policy), 0 add, 0 destroy.
- Final state serial `46`, lineage
  `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`; explicit Mays-Orders boundary
  remained unchanged. No new AWS resources.

## 6. Approval packet

`docs/reports/JM-RIS-CV-STORAGE-CONSENT-V1-APPROVAL-PACKET.md` contains the
full German text, version, SHA-256, purpose mapping, gate behavior, baseline
comparison and the request for the operator's explicit approval. Final plan
and notice approval remain pending.

## 7. Remaining open points

- Full account deletion / ApplicationV1 account erasure.
- Final retention period and physical deletion of older S3 versions.
- DPA/transfer review for AWS/Vercel.
- General rollout approval beyond the confirmed operator pilot.
- No new consent version or general enablement is included.

## 8. Deployment / rollback

Active production: `dpl_5C27DWhDpLT74tbyubbr4mNibCPo` (`c3da077`) on
`https://www.mays-job-matcher.app`; Vercel CV flags are enabled only for the
operator pilot.

Rollback if needed:

1. Disable `VITE_RIS_CV_STORAGE_ENABLED` and promote the previous known-good
   Jobsearch deployment `dpl_8rGdfH7yXiExiEWsgTRGSc7XBr3T` (Build `0951198`).
2. Disable `RIS_CV_STORAGE_ENABLED` to stop new CV BFF calls.
3. Do not delete CV documents or consent history as part of rollback; use the
   existing delete path.
4. No ApplicationV1/Mays-Orders rollback is required.

## 9. Commits

Jobsearch branch `feature/jm-ris-cv-storage-integration-01`:

- `59964a3` — base CV storage implementation
- `ec6f01f` — PDF-only CV uploads
- `1449751` — list limit 50
- `19372b7` — CV capacity aligned to 10
- merged through PR #8 as `c3da077`

RIS branch `feature/jm-ris-cv-storage-integration-01`:

- `216e061` — CV consent/CORS
- `ce55f32` — pilot identity scoping
- `edbf698` — notice approval/PDF-only
- IAM `ConditionCheckItem` fix and diagnostic logging in the final local
  incident commit; applied via the plans above.

No general rollout or new consent version.
