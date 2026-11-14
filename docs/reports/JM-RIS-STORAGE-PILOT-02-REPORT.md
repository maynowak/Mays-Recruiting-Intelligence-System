> **RIS documentation copy.** The pilot implementation was performed on
> `feature/jm-ris-storage-activation-01`. This copy records the RIS Terraform,
> gate, approval-packet and environment evidence. No apply, deployment, env,
> secret or notice-state change was performed.

# JM-RIS-STORAGE-PILOT-02-REPORT

## Result

**Technical status:** `STORAGE PILOT TECHNICALLY READY (LOCAL)`

**Live pilot status:** `BLOCKED`

The existing ApplicationV1, consent, BFF, Terraform and test infrastructure is
prepared for a controlled pilot. A real pilot cannot start yet for two concrete
reasons:

1. **No complete, legally approved ApplicationV1 consent declaration/notice.**
   RIS `application-storage/1.0` remains `DRAFT` with
   `legalApprovalRef = null`. The existing RIS notice draft is written for
   profile/CV/search-profile storage, not for ApplicationV1. No agent may
   approve it or set it to `APPROVED`/`ACTIVE`.
2. **No isolated RIS pilot runtime.** The available `ris-dev` Lambda
   (`ris-dev-dev-agent`) backs `ris-dev-jobsearch-api` (`c7e9pdwe78`), the
   shared Jobsearch partner edge. It must not be switched for this pilot.
   `ris-dev2-dev-agent` is not present in the accessible RIS account.

No push, merge, deployment, Terraform apply, AWS/Cognito mutation, production
Vercel env change, consent activation, or notice-state change was performed. No
live persistence is claimed.

## 1. Baseline

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Main at start | `509d12b` | `612429a` |
| Existing pilot branch | `feature/jm-ris-storage-activation-01` | `feature/jm-ris-storage-activation-01` |
| Baseline before this task | `95680e3` | `e217e5b` |
| New implementation commit | `04f00f4` (docs/plan only) | `81634d8` (Terraform + tests + packet) |
| Push / merge / deploy | none | none |

The previously verified privacy policy v1.1 and the BFF notice gate from
`JM-RIS-STORAGE-ACTIVATION-01` were not rebuilt or changed.

## 2. Phase A — baseline and audit result

- Both feature branches existed locally and were clean at the documented heads.
- Main repositories remained on `main`; no main branch change.
- No remote branch for the pilot branches exists.
- Previous evidence was reused; broad tests were not repeated without a
  concrete change.
- The BFF code (`324ad18`/`b8074a0`) is unchanged by this task. The Jobsearch
  commit `04f00f4` is documentation/plan only.

## 3. Phase B — approval packet

Created:

`docs/reports/APPLICATION-STORAGE-1.0-APPROVAL-PACKET.md`

### Critical finding

No complete, legally approved ApplicationV1 consent declaration exists in the
repository.

| Source | Content | Assessment |
| --- | --- | --- |
| RIS `RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md` | profile/CV/search-profile storage; marked "Arbeitsentwurf — nicht juristisch freigegeben, nicht veröffentlichen" | not ApplicationV1-specific; not a consent declaration |
| Jobsearch public policy v1.1 §9/§10 | application storage privacy notice, withdrawal, versioning | privacy notice, not a first-person consent declaration |
| Jobsearch UI strings (`StorageConsentLive`, i18n) | heading, status, link, "Speicherung zustimmen", versions | no declaration text is displayed |
| RIS processing/retention matrices | profile/CV/search-profile rows | **no ApplicationV1 application/cover-letter row** |

Exact identifiers:

| Side | Identifier | State | Mapping |
| --- | --- | --- | --- |
| RIS purpose | `application-storage` | — | — |
| RIS notice | `application-storage/1.0` | `DRAFT`, `legalApprovalRef=null` | — |
| Jobsearch text | `2026-11-04-draft-1` | DRAFT | **none** |
| Jobsearch privacy notice | `2026-11-04-draft-1` | DRAFT | **none** |

### Purpose and data categories

Purpose: optional durable ApplicationV1 storage so the authenticated user can
retrieve, change, export and delete their applications later.

Data categories in ApplicationV1:

- job reference (`jobId`, title, company, location, source, URL);
- profile/CV reference IDs (no PDF bytes or hashes);
- cover-letter draft and version content;
- document status and metadata;
- application date/channel, contact, notes, salary expectation/offer,
  follow-up;
- feedback/interview/note history.

PDF bytes, browser-extracted CV text, AI prompts and provider payloads are not
stored by this flow. `documents.cvReference` is a reference only.

### Withdrawal

- Withdrawal is possible in every notice state.
- With `APPLICATION_CONSENT_ENFORCED=true`, withdrawal blocks the five
  ApplicationV1 write paths (create, patch, status, history, cover-letter) with
  `403 CONSENT_REQUIRED`.
- Read, list, detail, metrics, export and delete remain available.
- Withdrawal does not delete existing applications and does not rewrite stored
  consent versions.

### Actual retention facts (not approvals)

| Resource | Current technical behavior | Approved period |
| --- | --- | --- |
| Applications table | TTL enabled on `expiresAt`, but repository never writes it → no automatic expiry; persists until explicit delete | none |
| Application delete | owner-scoped API delete; no automatic backup purge | none |
| Consents table | no TTL; current state + append-only history | none |
| Consent history | append-only, never updated/deleted by module | none |
| Applications PITR | `r08_pitr_enabled=false` | n/a |
| Lambda logs | default 14 days | not a data-subject retention approval |
| S3 documents | not used by this ApplicationV1 flow | n/a |
| Account-level application erasure | `ERASURE_APPLICATIONS_ENABLED=false` | not enabled |

### Missing operator/legal decisions

1. Approve an exact, complete application-storage consent declaration.
2. Confirm that ApplicationV1 is within the notice scope.
3. Determine controller/processor roles and Art. 6(1) basis.
4. Complete the Art. 9 assessment for cover-letter/notes/contact free text.
5. Approve the Jobsearch `2026-11-04-draft-1` ↔ RIS `1.0` mapping or a successor.
6. Define the real `legalApprovalRef` (record ID, owner, date, approving body).
7. Approve the ApplicationV1 retention clock/duration and backup/PITR rule.
8. Decide whether `ERASURE_APPLICATIONS_ENABLED` is part of approval.
9. Confirm recipients/transfers, including AWS `eu-central-1` and Vercel.
10. Confirm withdrawal semantics (block writes, keep existing data readable).
11. Approve the isolated pilot environment and the synthetic test identity.
12. Approve the separate GO for `CONSENT_NOTICE_STATE_ENFORCED=true` and
    `APPLICATION_CONSENT_ENFORCED=true`.

No text was invented and no notice state was changed.

## 4. Phase C — RIS gates and Terraform

### Implemented

`terraform/variables.tf`:

```hcl
variable "consent_notice_state_enforced" {
  description = "Reject new consent grants for non-grantable notice states (DRAFT/SUPERSEDED) in the Lambda runtime (Default AUS; separate activation gate)."
  type        = bool
  default     = false
}
```

`terraform/modules/lambda/variables.tf`: matching bool variable, default `false`.

`terraform/modules/lambda/main.tf`:

```hcl
CONSENT_NOTICE_STATE_ENFORCED = var.consent_notice_state_enforced ? "true" : "false"
```

`terraform/main.tf` passes the root variable into `module "lambda"`.

The existing module structure was reused. Only one Lambda module (`module
"lambda"`, the RIS agent runtime) receives the env var; the health/reader
modules are unaffected. The default remains fail-closed/disabled. No plan or
apply was run against AWS, and no protected Cognito/CloudFront/DNS/ACM resource
was touched.

### Gate combination

| `CONSENT_NOTICE_STATE_ENFORCED` | Notice state | Grant | Application writes |
| --- | --- | --- | --- |
| false | DRAFT | technically grantable for synthetic runs only | only if `APPLICATION_CONSENT_ENFORCED=false` or consent exists |
| true | DRAFT/SUPERSEDED | rejected (`NOTICE_NOT_ACTIVE`, 422) | no new grant, no dependent write |
| true | APPROVED/ACTIVE | grantable if `noticeApproved=true` and `acceptedForNewGrant=true` | allowed after grant |
| either | — | — | without GRANTED and with `APPLICATION_CONSENT_ENFORCED=true`: `403 CONSENT_REQUIRED` |
| either | — | withdrawal always allowed | read/export/delete remain available |

`APPLICATION_CONSENT_ENFORCED` must be `true` for the end-to-end safety test;
the activation plan enables it only in the isolated pilot environment.

### Tests

New/affected RIS tests:

```text
PYTHONPATH=/tmp/opencode/pydeps python3 -m pytest \
  tests/test_consent_active_notice_pilot.py \
  tests/test_consent_notice_state_enforcement_terraform.py \
  tests/test_consent_e2e_joint.py \
  tests/test_consent_gate.py \
  tests/test_consent_notice_catalog_contract.py \
  tests/test_consent_notice_lifecycle.py \
  tests/test_consent_repository.py -q
→ 55 passed in 7.04s
```

Wider focused check including project-config/plan-input/identity-mode
contracts:

```text
→ 91 passed in 7.88s
```

Terraform checks:

```text
terraform fmt -check -recursive
→ exit 0

terraform init -backend=false (temporary copy)
→ exit 0 (aws 6.67.0 installed)

terraform validate
→ Success! The configuration is valid.
→ 27 pre-existing hash_key deprecation warnings only
```

The temporary copy was `/tmp/opencode/tf-validate-pilot2`; no plan, apply,
backend access, or AWS mutation occurred.

Synthetic active-notice test proves:

- no consent → create denied 403 `CONSENT_REQUIRED`;
- grant under ACTIVE + legal ref → create/update allowed;
- withdrawal → new writes denied;
- read/export/delete remain available;
- regrant works;
- DRAFT/SUPERSEDED cannot be granted under enforcement;
- APPROVED/ACTIVE can be granted only with both flags true.

## 5. Phase D — Jobsearch integration review

Verdict: `PASS`; no code change was justified.

Confirmed:

- RIS catalogue is loaded live; `grantAllowed` requires `APPROVED` or `ACTIVE`,
  `noticeApproved=true` and `acceptedForNewGrant=true`.
- POST grant re-reads the catalogue immediately before writing.
- Missing/malformed catalogue, unknown version, DRAFT/SUPERSEDED, RIS 5xx,
  timeout and network failure fail closed.
- The browser cannot choose the notice version; legal approval refs are not
  forwarded.
- Consent UI shows status, RIS state, block reason and both text versions.
- Remote mode requires `VITE_RIS_APPLICATION_STORAGE_ENABLED=true`, verified
  login and access token; session mode remains the default.
- Server-side test allowlist is enforced; empty list denies.
- UI state is updated only after the backend response; failed requests show an
  error and do not claim durable success.
- Withdrawal and read/export/delete semantics match the RIS contract.

Residual non-blocking items:

- A RIS uppercase 422 code after the BFF pre-check can surface a generic UI
  message; no write is performed.
- `VITE_RIS_CONSENT_UI_ENABLED=true` exists in production but grants remain
  blocked by the DRAFT notice.

## 6. Phase E — isolated pilot environment

### Read-only live facts

Using the `mayaws` profile, account `240571105849`:

| Fact | Observed |
| --- | --- |
| `ris-dev-dev-agent` | Active |
| `CONSENTS_TABLE` | `ris-dev-dev-consents` |
| `APPLICATION_CONSENT_ENFORCED` | `false` |
| `PARTNER_SURFACE_ENABLED` | `true` |
| `CONSENT_NOTICE_STATE_ENFORCED` | absent |
| API `c7e9pdwe78` | `ris-dev-jobsearch-api` |
| API `g6901and25` | `ris-dev-dev-api` |
| `ris-dev2-dev-agent` | not found in this account |

No secret values were read or printed.

### Why `ris-dev` is not the pilot

`ris-dev` is the permanent dev install shared with the Jobsearch partner edge:

- `installer/project-configs/ris-dev.json` enables the partner surface and uses
  the production Jobsearch Cognito issuer/client;
- CORS includes the production Jobsearch domains;
- `c7e9pdwe78` (`ris-dev-jobsearch-api`) is documented as the Jobsearch partner
  edge;
- its consents table contains historical synthetic rows.

Changing `APPLICATION_CONSENT_ENFORCED` or `CONSENT_NOTICE_STATE_ENFORCED` there
would change partner-edge behavior for all clients, not just a pilot user.
Therefore `ris-dev` must not be switched.

`ris-dev2` is not present in this account; its project config points at a
separate Cognito pool/account. It cannot be assumed to be available. It would
need a separate read-only inventory and approval.

### Smallest safe alternative

Recommended: a dedicated workspace

```text
project_name = ris-storage-pilot
environment  = test
prefix       = ris-storage-pilot-test
```

with its own:

- Terraform state bucket/key/lock table (explicitly supplied);
- DynamoDB applications/consents tables and Lambda;
- API Gateway/partner surface and CORS (preview origin only);
- managed or dedicated Cognito test pool and one synthetic test identity;
- partner registry row and server-only credential, created through the approved
  secret process.

Alternative: verify and bring up `ris-dev2` in its real account, after
confirming it has no partner-edge traffic and its consent/ApplicationV1
resources are current.

Neither alternative is applied in this task; each requires a separate plan,
review and GO.

## 7. Phase F — A→B→A review

| Step | Agent | Session | Result |
| --- | --- | --- | --- |
| RIS Terraform/tests/approval packet | RIS | `ses_e49a08eb7ffe8RltsM98S9VTQq` | `81634d8` |
| Jobsearch BFF/preview review | Jobsearch | `ses_e49a66ef3ffeCeeSQhQhNwNnqs` | `04f00f4` |
| Jobsearch reviews RIS | Jobsearch | same session | `PASS` |
| RIS reviews Jobsearch | RIS | same session | `PASS` |

Jobsearch focused tests:

```text
npx vitest run tests/api/ris-consents.test.mjs \
  tests/api/ris-routing.test.mjs \
  tests/api/ris-config-separation.test.mjs
→ 3 files passed, 50/50 tests

npx vitest run src/components/StorageConsentLive.test.tsx \
  src/lib/applications/risRemoteRepository.test.ts \
  src/lib/applications/remoteSessionRepository.test.ts
→ 3 files passed, 36/36 tests

git diff --check
→ PASS
```

The previous full Jobsearch suite (`1562 passed / 5 skipped`) remains the
baseline; it was not repeated without a code change. No live persistence is
claimed by any test.

## 8. Exact preview / RIS configuration plan (no secret values)

### RIS pilot workspace (`ris-storage-pilot` / `test`)

| Setting | Value |
| --- | --- |
| `consent_notice_state_enforced` | `true` after GO |
| `application_consent_enforced` | `false` first, `true` before write-block tests |
| `partner_surface_enabled` | `true` |
| Notice registry | `application-storage/1.0` `APPROVED`/`ACTIVE` + real `legalApprovalRef` |
| `jobsearch_cognito_issuer` / `_client_id` | pilot pool, not production |
| `jobsearch_edge_cors_origins` | preview origin only |
| `api_cors_origins` | preview origin only, no wildcard |
| `applications_cursor_secret_arn` | pilot secret ARN, value never in Terraform |
| `r08_pitr_enabled` | `false` unless separately approved |
| `orders_lifecycle` | `disabled` |

### Jobsearch pilot preview (names only)

| Variable | Pilot value |
| --- | --- |
| `RIS_API_BASE_URL` | pilot API invoke URL |
| `RIS_PARTNER_CREDENTIAL` | pilot credential; server-only secret |
| `RIS_COGNITO_ISSUER` / `RIS_COGNITO_CLIENT_ID` | pilot pool |
| `RIS_CONSENT_SERVICE_ENABLED` | `true` |
| `RIS_APPLICATION_STORAGE_ENABLED` | `true` |
| `RIS_CONSENT_NOTICE_VERSION` | `1.0` |
| `RIS_TEST_USER_ALLOWLIST` | `<pilot issuer>|<synthetic sub>` only |
| `VITE_RIS_CONSENT_UI_ENABLED` | `true` (preview only) |
| `VITE_RIS_APPLICATION_STORAGE_ENABLED` | `true` (preview only) |
| `VITE_RIS_APPLICATION_MIGRATION_MOCK` | absent |

`VITE_RIS_APPLICATION_STORAGE_ENABLED` is absent from both production Vercel
projects today. It must remain preview-only for the pilot; production
`mays-job-matcher` flags stay unchanged.

Recommended topology: a dedicated Vercel pilot project/preview with Deployment
Protection and no production alias, plus the dedicated RIS workspace. Do not
point it at `ris-dev`/`c7e9pdwe78`.

## 9. Activation order

1. Operator/legal approval of the exact ApplicationV1 consent declaration and
   retention rule (Section 3).
2. Set RIS notice `application-storage/1.0` to `APPROVED` or `ACTIVE` with a
   real `legalApprovalRef`; rebuild the Lambda bundle; create a new plan.
3. Review/approve the dedicated `ris-storage-pilot` plan (or verified
   `ris-dev2`); apply only under separate GO.
4. Set pilot RIS `consent_notice_state_enforced=true`; keep
   `application_consent_enforced=false` initially.
5. Configure the Jobsearch pilot preview server variables, then the two
   `VITE_` flags; keep production untouched.
6. Verify non-allowlisted identity → 403 and allowlisted identity → consent
   status.
7. Grant `application-storage/1.0`; verify `GRANTED`.
8. Enable pilot RIS `application_consent_enforced=true`.
9. Run the synthetic storage flow (Section 10).
10. Withdraw; verify write block and read/export/delete.
11. Clean up synthetic data; record deployment IDs and evidence.
12. Do not open to general users until the separate RG-09/privacy approval.

## 10. Pilot E2E test plan

```text
1. Login as synthetic allowlisted user
2. Load consent status (NOT_GRANTED)
3. Show the approved notice text/version
4. Grant application-storage/1.0
5. Create synthetic application
6. RIS returns applicationId + ownerId; UI shows "Gespeichert"
7. Reload; application is still present
8. Logout/login; application is still present
9. Update application; version increments
10. Export; exported application contains the synthetic record
11. Withdraw consent
12. New write → 403 CONSENT_REQUIRED
13. Existing application remains readable/exportable/deletable
14. Delete application; verify not retrievable
15. Delete synthetic consent/test-user data
```

Expected evidence: actual HTTP statuses, RIS application IDs, versions,
timestamps, export/delete responses, and cleanup counts. A mock test is not
accepted as live persistence evidence.

## 11. Rollback plan

1. Set preview `VITE_RIS_APPLICATION_STORAGE_ENABLED=false`; UI returns to
   session mode.
2. Set pilot `application_consent_enforced=false` (or disable the partner
   surface → 503) if writes must stop immediately.
3. If the notice approval is withdrawn, revert notice state to `DRAFT` or
   `SUPERSEDED`; existing grants remain valid, new grants blocked.
4. Keep pilot data for export/delete; delete only synthetic rows.
5. Revert the preview deployment to the previous known-good image.
6. Tear down the pilot workspace only after the data decision and a separate
   GO; do not delete production or shared `ris-dev` resources.
7. Re-run the focused consent/gate tests after rollback and record deployment
   IDs.

## 12. Commits

| Repository | Commit | Purpose |
| --- | --- | --- |
| RIS | `81634d8` | Terraform wiring, active-notice tests, approval packet, env analysis |
| Jobsearch | `04f00f4` | preview config plan and BFF review |
| Jobsearch | `[final docs]` | final report + auditlog + precision fixes |
| RIS | `[final docs]` | final report + auditlog + baseline fix |

The final docs commits are local only. No branch was pushed or merged.

## 13. Blockers

1. **Legal/operator decision:** no complete, approved ApplicationV1 consent
   declaration; notice `1.0` must stay DRAFT.
2. **No isolated RIS runtime:** `ris-dev` is the shared Jobsearch partner edge;
   `ris-dev2` is not present in the accessible account. A dedicated
   `ris-storage-pilot` workspace (or verified `ris-dev2`) requires a separate
   plan/apply GO.
3. **Pilot identity/partner binding:** the pilot Cognito app client
   callback/logout URLs and the partner registry/credential row must be defined
   before apply.
4. **Preview config not applied:** `VITE_RIS_APPLICATION_STORAGE_ENABLED` is
   absent from both Vercel projects; no production env was read/changed.
5. **Live persistence not executed:** only local tests and read-only AWS
   inspection were performed.

## 14. Safety confirmation

- No push, merge, deployment, Terraform apply, AWS/Cognito mutation, or
  production Vercel env change.
- No notice state or `legalApprovalRef` change.
- No `APPLICATION_CONSENT_ENFORCED` or `CONSENT_NOTICE_STATE_ENFORCED`
  live activation.
- No secret, token, private key, real applicant data, or CV content was read or
  committed.
- No production `main` branch was changed.
- The privacy policy v1.1 was not modified.

## 15. Final status

`STORAGE PILOT TECHNICALLY READY (LOCAL)`

`BLOCKED FOR LIVE PILOT — LEGAL NOTICE APPROVAL AND ISOLATED RIS RUNTIME REQUIRED`

No production activation without a separate GO.
