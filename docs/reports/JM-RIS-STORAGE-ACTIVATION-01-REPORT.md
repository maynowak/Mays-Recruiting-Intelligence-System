> **RIS documentation copy.** The storage gate implementation was performed in
> `maynowak/mays-jobsearch`; this copy records the RIS contract review and the
> cross-repository activation plan. No RIS product code, deployment, env,
> Terraform, AWS, Cognito, or consent activation was performed by this task.

# JM-RIS-STORAGE-ACTIVATION-01-REPORT

## Result

`APPLICATION STORAGE TECHNICALLY VERIFIED`

`PARTIALLY READY — CONTROLLED TEST-USER ACTIVATION BLOCKED`

The existing ApplicationV1 persistence and consent gates are technically
connected and locally verified. The primary activation blocker is that the RIS
`application-storage` notice `1.0` is still `DRAFT` with
`legalApprovalRef = null`; the new Jobsearch gate correctly rejects all grants
until that notice is legally approved and activated. No production activation,
push, merge, deployment, AWS/Terraform/Cognito mutation, or live persistence
test was performed.

## 1. Baseline

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Main at start | `509d12b` | `612429a` |
| Feature branch | `feature/jm-ris-storage-activation-01` | `feature/jm-ris-storage-activation-01` |
| Worktree | `worktrees/jobsearch-storage-activation-01` | `worktrees/ris-storage-activation-01` |
| Agent commits | `324ad18`, `b8074a0` | `54d6a77` |
| Push / merge / deploy | none | none |

The privacy policy v1.1 release is separate and was not changed. The consent
notice `1.0` is also separate from privacy policy `v1.1`.

## 2. Phase A — actual storage state

### Jobsearch

| Function | Implemented | Locally tested | Live reachable | Activation required |
| --- | --- | --- | --- | --- |
| Cognito login / verified identity | yes | yes | yes | no |
| Session application repository | yes | yes | yes | no |
| RIS remote application repository | yes | yes | BFF reachable; auth required | `VITE_RIS_APPLICATION_STORAGE_ENABLED=true` |
| Jobsearch applications BFF | yes | yes | HTTP 401 without token on `www.mays-job-matcher.app` | test user/token |
| Consent UI | yes | yes | flag key present in production | valid approved notice |
| Consent BFF | yes | yes | HTTP 401 without token on `www.mays-job-matcher.app` | approved notice |
| Test-user allowlist | yes | yes | production key present | explicit test identity |
| Privacy policy v1.1 | yes | yes | live | no |
| CV builder profiles | session memory only | yes | local-only | no RIS persistence exists |
| PDF export | local browser | yes | live | no |

Actual Vercel project env names (values not read):

- `mays-job-matcher` production has `RIS_API_BASE_URL`,
  `RIS_APPLICATION_STORAGE_ENABLED`, `RIS_CONSENT_SERVICE_ENABLED`,
  `RIS_CONSENT_NOTICE_VERSION`, `RIS_PARTNER_CREDENTIAL`,
  `RIS_COGNITO_ISSUER`, `RIS_COGNITO_CLIENT_ID`,
  `RIS_TEST_USER_ALLOWLIST`, `VITE_RIS_CONSENT_UI_ENABLED`.
- `VITE_RIS_APPLICATION_STORAGE_ENABLED` is **absent** from both Vercel
  projects. The browser therefore stays in session mode by code default.
- The separate `mays-jobsearch` Vercel project has no RIS env; its BFF returns
  `503 ris_disabled` / `503 consent_disabled`.
- `www.mays-job-matcher.app/api/ris/applications` and `/api/ris/consents`
  return **401 unauthenticated**, proving the production BFF is enabled and
  configured, but not proving storage or consent.

### RIS

| Function | Implemented | Locally tested | Live reachable | Activation required |
| --- | --- | --- | --- | --- |
| Partner API / ApplicationV1 | yes | yes | historical live evidence; no new call | auth/test user |
| Application create/list/get/patch/status/history/cover-letter | yes | yes | not re-tested live | approved test user |
| Export and delete | yes | yes | not re-tested live | approved test user |
| Consent service / history | yes | yes | historical live evidence; no new call | approved notice |
| Notice catalogue | yes | yes | yes via partner API with auth | notice approval |
| Tenant/partner/owner isolation | yes | yes | code/tests | no |
| `APPLICATION_CONSENT_ENFORCED` | yes | yes | Terraform default false; historical live false | enable for test env |
| `CONSENT_NOTICE_STATE_ENFORCED` | yes in code | yes | **not wired in Terraform**, default false | wire + enable |
| Application metrics | yes | yes | not re-tested live | test user |
| CV document API / S3 presign | yes | yes | not connected to Jobsearch | separate scope |
| Notice `application-storage/1.0` | yes | yes | **DRAFT, legalApprovalRef null** | **primary blocker** |

Live AWS/Lambda configuration was not read or mutated. Historical reports are
used only as context; the current repository/Terraform state is authoritative.

## 3. Phase B — consent and notice gate

### Finding

The Jobsearch BFF previously returned:

```js
grantAllowed: Boolean(cfg.noticeVersion)
```

and forwarded `RIS_CONSENT_NOTICE_VERSION` without checking the RIS notice
state. That treated a configured version as an approval. RIS already exposes
the authoritative catalogue on `GET /v1/partner/me/consents`.

### Implemented correction

New helper `api/_lib/ris/consentNotice.mjs`:

- loads the live RIS catalogue from `GET /v1/partner/me/consents?purpose=application-storage`;
- matches the server-configured notice version;
- requires **all** of:
  - state `APPROVED` or `ACTIVE` (mirrors RIS `GRANTABLE_NOTICE_STATES`),
  - `noticeApproved === true`,
  - `acceptedForNewGrant === true`;
- rejects `DRAFT`, `SUPERSEDED`, unknown, missing, malformed, conflicting or
  unavailable catalogues;
- re-reads the catalogue immediately before a POST grant; a blocked grant never
  reaches the RIS grant endpoint;
- keeps withdrawal available in every notice state;
- keeps the notice version server-owned; a browser-supplied version is ignored;
- does not expose `legalApprovalRef`.

`GET /api/ris/consents` now returns `noticeVersion`, `noticeState`,
`noticeApproved`, `acceptedForNewGrant`, `grantAllowed` and `noticeReason`.
The consent UI shows the RIS state and the fail-closed reason.

### RIS contract verified by the RIS agent

`GET /v1/partner/me/consents` returns top-level `items`, `catalog` and
`externalRefs`; the catalogue is per-purpose and each entry has `purpose`,
`noticeVersion`, `noticeState`, `noticeApproved`, `acceptedForNewGrant`.

Exact state matrix:

| State | `noticeApproved` | `acceptedForNewGrant` (enforcement off) | Grantable |
| --- | --- | --- | --- |
| `DRAFT` | false | true | no |
| `APPROVED` | true | true | yes |
| `ACTIVE` | true | true | yes |
| `SUPERSEDED` | true | true | no |

The state check is load-bearing: DRAFT and SUPERSEDED can both report
`acceptedForNewGrant=true` while enforcement is off. Flags alone are not enough.

Initial Jobsearch implementation accepted only `ACTIVE`; RIS review returned
`REWORK_REQUIRED` because `APPROVED` is also contractually grantable.
Jobsearch commit `b8074a0` fixed this. Final RIS review: **PASS**.

## 4. Phase C — persistent application management

The existing flow is wired as follows:

1. Cognito login provides `iss + sub` + access token.
2. `VITE_RIS_APPLICATION_STORAGE_ENABLED` and verified auth select the remote
   repository; otherwise the session repository remains.
3. The consent UI loads the RIS consent status.
4. Grant is possible only after the approved/active notice gate.
5. Application create goes through the Jobsearch BFF to RIS.
6. The UI updates its state only after the backend response resolves.
7. Reload / logout / new login invalidates the repository; a new instance is
   created from auth state.
8. Update, export and delete use the existing ApplicationV1 routes.
9. A failed backend request throws and the UI shows the error; it does not
   report a successful durable save from local React state.

Local evidence:

- Remote repository tests cover create/list/get/update/status, export, delete,
  metrics, missing token, 401, 409 version conflict, network failure, abort,
  session invalidation and idempotency key reuse.
- Consent BFF tests cover missing/invalid token, non-allowlisted user, missing
  consent service, DRAFT block, APPROVED/ACTIVE allow, missing/malformed
  catalogue, RIS 5xx/network failure, unknown version, duplicate/conflicting
  entries and withdrawal.
- RIS tests cover `APPLICATION_CONSENT_ENFORCED=true`: create/patch/status/
  history/cover-letter return `CONSENT_REQUIRED` without consent; list/detail/
  metrics/export/delete remain available; withdrawal remains possible in every
  notice state; tenant/user isolation is preserved.

**No live persistence test was executed.** A mock/BFF test is not a live
storage proof. Live execution requires the primary notice approval and an
authorized test user.

## 5. Phase D — CV storage boundary

| Item | Current status |
| --- | --- |
| Structured CV profiles | jobsearch session memory only; no RIS persistence |
| CV builder data | jobsearch session memory only; no RIS persistence |
| CV reference in ApplicationV1 | stored as `documents.cvReference` (cvId, optional documentId, label, source); RIS verifies ownership; **no PDF bytes/hash** |
| Uploaded PDF files | processed in the browser for local profile/letter/PDF export; not uploaded to RIS by this flow |
| RIS CV document API | exists separately (CVDocument + S3 presigned upload/download/delete); not connected to Jobsearch ApplicationV1 |
| PDF export | local browser export; unchanged and still tested |

A stored CV reference is not a stored PDF file. No new persistence architecture
was introduced.

## 6. Phase E — real A→B→A agent execution

| Step | Agent | Session | Result |
| --- | --- | --- | --- |
| Jobsearch implementation + A→B requirements | Jobsearch | `ses_e49a66ef3ffeCeeSQhQhNwNnqs` | commit `324ad18` |
| RIS contract verification + tests | RIS | `ses_e49a08eb7ffe8RltsM98S9VTQq` | commit `54d6a77` |
| RIS review of Jobsearch | RIS | same RIS session | `REWORK_REQUIRED` (state mismatch) |
| Jobsearch rework | Jobsearch | same Jobsearch session | commit `b8074a0` |
| Jobsearch review of RIS | Jobsearch | same Jobsearch session | `PASS` |
| RIS final review of Jobsearch rework | RIS | same RIS session | `PASS` |

Both agents worked in isolated worktrees, committed their own changes, and did
not edit the other repository. No push, merge, deployment, env change or
secret operation occurred.

## 7. Git commits

| Repository | Commit | Purpose |
| --- | --- | --- |
| Jobsearch | `324ad18` | fail-closed notice gate, tests, UI/API types, docs, auditlog |
| Jobsearch | `b8074a0` | accept APPROVED or ACTIVE; correct DRAFT/SUPERSEDED evidence |
| RIS | `54d6a77` | catalogue contract tests, A→B evidence, auditlog |

Final branches are local only:
- Jobsearch `feature/jm-ris-storage-activation-01` at `b8074a0`
- RIS `feature/jm-ris-storage-activation-01` at `54d6a77`

## 8. Real test results

### Jobsearch

```
npm test
→ Test Files 149 passed | 3 skipped (152)
→ Tests 1562 passed | 5 skipped (1567)
→ 103.95s

npx vitest run tests/api/ris-consents.test.mjs tests/api/ris-routing.test.mjs tests/api/ris-config-separation.test.mjs
→ 3 files passed | 50 tests passed

npx vitest run src/components/StorageConsentLive.test.tsx \
  src/lib/applications/risRemoteRepository.test.ts \
  src/lib/applications/remoteSessionRepository.test.ts
→ 3 files passed | 36 tests passed

npx vitest run tests/api
→ 40 files passed | 3 skipped (43)
→ 553 passed | 5 skipped (558)

npm run build
→ tsc -b && vite build PASS

node --check api/**/*.mjs
→ all API files OK

git diff --check
→ PASS
```

The full suite required a local hardlink copy of `node_modules` because the
isolated worktree's symlink was rejected by Vite's filesystem guard; this was a
test-environment artifact, not a code failure.

### RIS

```
PYTHONPATH=/tmp/opencode/pydeps python3 -m pytest \
  tests/test_consent_notice_catalog_contract.py \
  tests/test_consent_notice_lifecycle.py \
  tests/test_consent_gate.py \
  tests/test_consent_e2e_joint.py \
  tests/test_consent_repository.py \
  tests/test_application_repository.py \
  tests/test_application_api_security.py \
  tests/test_application_auth_boundary.py \
  tests/test_application_privacy_contract.py \
  tests/test_application_erasure.py \
  tests/test_application_contract.py -q
→ 79 passed in 52.10s
```

`moto` was installed only into `/tmp/opencode/pydeps` for local tests; no
system or production dependency was changed.

## 9. Consent and notice status

- Current notice: `application-storage` / `1.0`.
- State: **DRAFT**.
- `legalApprovalRef`: **null**.
- `noticeApproved`: false.
- With `CONSENT_NOTICE_STATE_ENFORCED=false`, DRAFT still reports
  `acceptedForNewGrant=true`; the Jobsearch state check is therefore essential.
- With `CONSENT_NOTICE_STATE_ENFORCED=true`, DRAFT/SUPERSEDED grants are
  rejected with `NOTICE_NOT_ACTIVE` → HTTP 422; APPROVED/ACTIVE are accepted.
- Withdrawal is possible in every notice state.
- `APPLICATION_CONSENT_ENFORCED` is false by default; it gates the five
  ApplicationV1 write paths and leaves reads/export/delete available.
- `CONSENT_NOTICE_STATE_ENFORCED` is not wired in Terraform; this is an RIS
  defence-in-depth blocker until wired/enabled.

## 10. Security review

- No production secrets, tokens, private keys, CV contents or applicant data
  were read, printed, or committed.
- No production env, AWS, Terraform, Cognito, CloudFront, DNS, or ACM change.
- No `APPLICATION_CONSENT_ENFORCED` or `CONSENT_NOTICE_STATE_ENFORCED`
  activation.
- No push, merge, deployment, force-push, branch deletion, or live dispatch.
- Jobsearch BFF fails closed for missing/invalid token, non-allowlisted user,
  missing/malformed catalogue, unknown version, DRAFT/SUPERSEDED, RIS errors,
  and network failures.
- Browser cannot choose the notice version; legal approval references are not
  returned to the browser.
- Existing grants survive a notice becoming SUPERSEDED; no silent rewrite.
- Owner scope is `tenant + partner + issuer + subject`; tenant/user isolation
  tests pass.
- Deletion is idempotent and owner-scoped; export and delete remain available
  after withdrawal.

## 11. First controlled activation — exact steps

**Primary blocker:** legal/operator approval of `application-storage` notice
`1.0`. Do not substitute privacy policy v1.1 and do not disable the notice check
for real user data.

Recommended target: a dedicated preview/test deployment, not the general
production audience. If production is required, add a UI test-user allowlist
before enabling the global remote-storage flag.

1. **Legal approval / notice state**
   - Record the approval reference for `application-storage/1.0`.
   - Set `NOTICE_REGISTRY["application-storage"]["1.0"]` to `APPROVED` or
     `ACTIVE` with a non-null `legalApprovalRef`.
   - Build/package and deploy the RIS change through the approved RIS process.
2. **RIS server-side notice enforcement**
   - Wire `CONSENT_NOTICE_STATE_ENFORCED` into the RIS Lambda Terraform module
     (currently missing) with default `false`.
   - Set it `true` for the test environment and redeploy.
3. **RIS application consent enforcement**
   - Keep `APPLICATION_CONSENT_ENFORCED=false` until the synthetic consent flow
     passes.
   - After grant/withdraw/regrant succeeds, set it `true` for the test
     environment.
4. **Jobsearch test deployment**
   - Deploy the Jobsearch branch code with the new BFF gate.
   - In the dedicated preview/test environment set:
     - `RIS_APPLICATION_STORAGE_ENABLED=true`
     - `RIS_CONSENT_SERVICE_ENABLED=true`
     - `RIS_CONSENT_NOTICE_VERSION=1.0`
     - `RIS_TEST_USER_ALLOWLIST=<issuer>|<sub>` (only the approved synthetic user)
     - `VITE_RIS_CONSENT_UI_ENABLED=true`
     - `VITE_RIS_APPLICATION_STORAGE_ENABLED=true`
     - existing `RIS_API_BASE_URL`, `RIS_PARTNER_CREDENTIAL`,
       `RIS_COGNITO_ISSUER`, `RIS_COGNITO_CLIENT_ID`
   - `VITE_RIS_APPLICATION_STORAGE_ENABLED` is currently absent from both
     Vercel projects; it must not be enabled for all production users without a
     UI allowlist.
5. **Pre-live checks**
   - Login as the synthetic test user.
   - `GET /api/ris/consents` must show `noticeState=APPROVED|ACTIVE`,
     `grantAllowed=true`, and the consent status `NOT_GRANTED`.
   - A non-allowlisted identity must receive 403 and must not reach RIS.
6. **Synthetic live flow**
   - Grant consent for `application-storage/1.0`.
   - Create a synthetic application; require a RIS `applicationId` and
     `ownerId`; do not use local state as proof.
   - Reload, log out, log in again, and re-read the application.
   - Update it and verify the version increments.
   - Export it and verify the export contains the application.
   - Withdraw consent.
   - Confirm a new write returns `CONSENT_REQUIRED` (403) while list/detail/
     export/delete remain available.
   - Delete the synthetic application and confirm it is no longer retrievable.
   - Delete the synthetic consent/test user data.
7. **Production gate**
   - Only after the synthetic flow passes and legal/ops approve: enable
     `APPLICATION_CONSENT_ENFORCED=true` for the intended environment.
   - Keep the test-user allowlist; do not open the flow to real users until the
     separate RG-09/privacy approval is complete.

## 12. Rollback plan

1. Set `VITE_RIS_APPLICATION_STORAGE_ENABLED=false` to return the UI to session
   mode; do not delete stored applications.
2. If writes must be stopped immediately, set
   `APPLICATION_CONSENT_ENFORCED=false` for the test environment (or disable
   `RIS_APPLICATION_STORAGE_ENABLED` / `RIS_CONSENT_SERVICE_ENABLED` to return
   503s); reads/exports/deletes remain available where possible.
3. Revert the Jobsearch deployment to the previous known-good commit; keep the
   RIS data and consent rows for export/delete.
4. If the notice approval is withdrawn, set the notice state back to DRAFT or
   SUPERSEDED; existing grants remain valid but new grants are blocked. Do not
   silently rewrite stored consent versions.
5. Delete only synthetic test applications and test-user consent rows; never
   delete production applicant data as part of rollback.
6. Re-run the consent/gate tests after rollback and record the deployment IDs.

## 13. Open points

1. **Primary blocker:** legal approval of consent notice `1.0` and a non-null
   `legalApprovalRef`; until then controlled test-user activation cannot start.
2. `CONSENT_NOTICE_STATE_ENFORCED` is not wired in Terraform; server-side
   notice enforcement is currently inactive. The Jobsearch BFF is the only
   notice barrier.
3. `VITE_RIS_APPLICATION_STORAGE_ENABLED` is absent from the production env;
   remote storage is not user-visible yet.
4. `APPLICATION_CONSENT_ENFORCED` is false; writes are not yet blocked after
   withdrawal in the deployed environment.
5. No live persistence, export, delete, reload, or re-login test was executed;
   only local tests and live BFF reachability (401) were verified.
6. `legalApprovalRef` is exposed on the RIS partner catalogue; Jobsearch filters
   it, but future partners must do the same.
7. Non-blocking UI detail: a RIS 422 race after the BFF pre-check may surface a
   generic consent error because RIS error codes are uppercase; no grant is
   written.

## 14. Final status

`APPLICATION STORAGE TECHNICALLY VERIFIED`

`PARTIALLY READY — CONTROLLED TEST-USER ACTIVATION BLOCKED BY NOTICE 1.0 DRAFT / MISSING LEGAL APPROVAL`

No production activation, deployment, push, merge, AWS/Terraform/Cognito
mutation, or live persistence claim was made.
