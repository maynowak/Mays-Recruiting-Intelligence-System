> **RIS-side copy of the cross-repository analysis.** The canonical report is
> also committed in the Jobsearch repository on branch
> `docs/xrepo-parallel-analysis-01`. This copy is read-only analysis evidence;
> it makes no RIS code, API, Terraform or deployment change.

# XREPO-PARALLEL-ORCHESTRATION-01 — Consolidated Analysis Report

**Status: XREPO PARALLEL ANALYSIS COMPLETE**

- Mode: read-only, four independent analysis agents (A–D)
- Jobsearch: `maynowak/mays-jobsearch` — `origin/main` `aa57500d85e8c30fb2db9455f3c3e5998470759f`
- RIS: `maynowak/Mays-Recruiting-Intelligence-System` — `origin/main` `97a60df83a5db56ea750e4342d7a01b00c8ad56b`
- No implementation, merge, deployment, AWS/Terraform call, repository mutation or write/delete request was performed.
- Live `ris-dev` route/flag state was **not** queried; repository and prior-report evidence only. A read-only AWS confirmation requires a separate approval.
- Prior alignment report: `XREPO-JOBSEARCH-RIS-DOCUMENTATION-ALIGNMENT-01-REPORT.md`.

---

## 1. Confirmed causes

| ID | Cause | Evidence | Severity |
|---|---|---|---|
| **A-P0** | Jobsearch BFF erasure path `/v1/partner/me/erasure` is absent from RIS main/OpenAPI/API-STANDARD; RIS main only implements `POST /me/erasure`. The partner route exists on branches `70a9fb9` (`feature/ris-erasure-recovery-02`) and `451c12e` (`feature/jm-ris-cv-storage-integration-01` / RC2). | Jobsearch `api/_lib/ris/config.mjs:240-254`, `api/_lib/ris/accountErasureHandler.mjs:71-76`; RIS `lambda/handler.py:508`, `terraform/modules/api/main.tf:133`, `terraform/modules/partner_edge/main.tf:7-49`, `docs/api/openapi-platform.yaml:297`; branch commits above | **P0 / High** |
| **B-P0** | RIS IaC on main does not wire `CV_STORAGE_CONSENT_ENFORCED`, `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`, `CONSENT_NOTICE_STATE_ENFORCED` or `CONSENT_PILOT_ALLOWLIST`. Handler reads them; a plan/apply from main would drop live env keys and silently weaken consent enforcement. | RIS `terraform/modules/lambda/main.tf:708-713` only has `CONSENTS_TABLE`/`APPLICATION_CONSENT_ENFORCED`; `terraform/variables.tf:345-349`; `installer/project-configs/ris-dev.json`; `lambda/handler.py:630-696` | **P0 / Critical (deployment safety)** |
| **B-DOC** | RIS `docs/contracts/CONSENT-V1.md` says “nicht deployt” and documents only `application-storage`; registry has 3 APPROVED purposes (`application-storage`, `cv-storage`, `search-profile-storage`) plus DRAFT `analysis-processing`. | RIS `jobsearch/consent_contract.py`, `docs/contracts/CONSENT-V1.md:3,92,116,125-129`, `docs/api/openapi-platform.yaml:2321-2382` | High (operator/legal misjudgement) |
| **C-P1a** | Remote cover-letter versioning is blocked in both Jobsearch repository layers (`risRemoteRepository` and `remoteSessionRepository`), although BFF and RIS support `/cover-letter-versions`. BFF/RIS return only the version, while the Jobsearch port expects a full application. | Jobsearch `src/lib/applications/risRemoteRepository.ts:320-326`, `remoteSessionRepository.ts:192-204`; BFF `applicationsHandler.mjs:154,201-206`; RIS `docs/api/openapi-platform.yaml:2289`, `lambda/handler.py` route | P1 |
| **C-P1b** | Search-profile updates send no optimistic `version`; RIS accepts optional version; ATS BFF rejects version as unexpected. Stale clients can overwrite silently. | `src/lib/profiles/contractTypes.ts:124-156`; `searchProfilesApi.ts:146-230`; `searchProfilesHandler.mjs:87`; RIS PUT handlers optional version | P1 |
| **C-P1c** | Builder-CV references are offered in remote application UI but rejected by BFF (`422 builder_cv_unsupported`); RIS ApplicationV1 cannot store them. Error is mapped to generic `validation_error`. | `ApplicationsSection.tsx:1628-1643`; `api/_lib/ris/map.mjs:112-119`; `risRemoteRepository.ts:121-123`; RIS `jobsearch/application_contract.py:194-203` | P1 |
| **D-P2a** | RIS privacy inspect/export exists and is documented, but no Jobsearch BFF/UI exposes it. | RIS `lambda/handler.py:4283,4488`, OpenAPI `:915-1013`, Terraform `api/main.tf:690-704`; Jobsearch `api/ris/router.mjs:23-41` | P2 |
| **D-P2b** | BFF clamps CV list limit to 100; RIS max is 50. UI sends 50 and capacity is 10, so latent. | `api/_lib/ris/cvsHandler.mjs:130`; RIS `lambda/handler.py:5370-5376`, OpenAPI `:1258-1261` | P3 |
| **D-P2c** | Multi-source / multi-location jobs are rejected by BFF single-value mapping; direct adoption/draft creation lacks a pre-check and shows a generic error. | `api/_lib/ris/map.mjs:25-73`; `src/types.ts:11-20`; `api/_lib/sources/index.mjs:44-60`; `ApplicationsSection.tsx`/`App.tsx` adoption paths | P2 (P1 if public ATS/Adzuna/Greenhouse active) |

---

## 2. Security and availability risks

| Risk | Assessment | Evidence |
|---|---|---|
| Erasure 404 / privacy right unavailable | Fail-closed, no false success, but user cannot delete account data if enabled. Applying main removes the live partner route. | Agent A; `accountErasureHandler.mjs:28-36` |
| Consent env flags dropped by IaC | Critical: a routine plan/apply from main converges to weaker enforcement. Must be proven by a plan, not assumed. | `terraform/modules/lambda/main.tf:708-713` |
| Art. 9 proof only in BFF | RIS `grant(cv-storage)` without special-category proof authorizes writes at RIS layer; only Jobsearch BFF requires the explicit flag. Other partner/direct credential callers are weaker. | `jobsearch/consent_contract.py`, `lambda/handler.py:724-726,5304` |
| `CONSENT_NOTICE_STATE_ENFORCED=false` default | RIS API can grant DRAFT notices (currently `analysis-processing`). | registry / handler |
| Pilot allowlist overloaded | Same variable controls pilot write access and notice-state enforcement scope; undocumented 403s. | `handler.py:5231-5236,5287-5295` |
| Two allowlists | BFF `RIS_TEST_USER_ALLOWLIST` + RIS `CONSENT_PILOT_ALLOWLIST` must agree; mismatch is opaque. | `.env.example`, BFF |
| Privacy export PII | If exposed without care, full contact/notes/cover-letter text crosses BFF; export is PARTIAL by default and files not included. | Agent D |
| Multi-source save dead end | Public-ATS/cross-posted jobs can fail after letter creation with generic error. | Agent D |
| Builder CV misleading | UI offers option that cannot be persisted remotely. | Agent C |
| Remote version UI | Version action fails in remote mode; no data loss but broken parity. | Agent C |

---

## 3. Documentation deviations

| # | Area | Current documentation | Actual code/registry | Correction |
|---|---|---|---|---|
| D1 | RIS consent status | `CONSENT-V1.md`: “nicht deployt”, only application-storage | 3 purposes APPROVED, DRAFT analysis; routes used by production | Update status/catalog/external refs; mark historical if not maintained |
| D2 | Consent OpenAPI | purpose enum only `application-storage`; POST body only purpose/noticeVersion; 422 for unknown purpose | 4 purposes; proof fields; 404 UNKNOWN_PURPOSE | Update OpenAPI/API-STANDARD; add 403 codes |
| D3 | Consent IaC | no cv/search/profile/notice/pilot flags | handler reads all | Wire Terraform/installer; plan check |
| D4 | Jobsearch `.env.example` | missing application consent vars; cv state DRAFT | RIS registry APPROVED | Add vars, correct examples |
| D5 | ApplicationV1 | no consent-gate section | 403 CONSENT_REQUIRED write gate | Add section |
| D6 | Jobsearch storageConsent | “future/draft” wording | durable consent live | Mark UI-only/historical |
| D7 | Erasure route | Jobsearch comment says `POST /me/erasure`; config uses partner path | partner route absent from RIS main | Align comment/doc and route |
| D8 | Privacy export | RIS docs complete; Jobsearch legal text points to email | no Jobsearch BFF/UI | Document RIS-only or add BFF after approval |
| D9 | CV list limit | Jobsearch BFF 100 vs RIS 50 | UI 50 | Document/clamp |
| D10 | Multi-source | architecture documents combined sources; no remote limitation in UI | BFF rejects >1 | Document limitation or change policy/contract |

---

## 4. Concrete correction proposals

### P0 — Erasure
- **Recommended:** forward-fix RIS main (not BFF): add exact partner route branch to `lambda/handler.py`, route to `terraform/modules/partner_edge/main.tf`, tests from `70a9fb9`, surface-gate entry; keep `_handle_me_erasure` and existing lifecycle.
- Do **not** change Jobsearch to `/me/erasure`: different Cognito pool/kernel API; would 401/404 and widen credential scope.
- Keep BFF path and add a 404-mapping/UI error test.
- Release order: RIS branch → focused/full tests → plan with 0 delete/replace (route no-op, Lambda update) → G5 approval/apply → unauth 401 vs 404 probe → optional synthetic erasure E2E → only then enable Jobsearch flags.
- Open question: whether partner route belongs only on partner edge or also kernel API/OpenAPI; do not add spec route without Terraform source (P20 test).

### P0 — Consent
- Update RIS docs/OpenAPI/API-STANDARD as above.
- Wire four consent env flags + sensitive allowlist into Terraform/installer (no secret in Git); prove plan does not remove live keys.
- Decide whether RIS must require Art. 9 proof for `cv-storage`/`application-storage` (Privacy/Legal), and whether notice-state enforcement defaults true in deployed envs.
- Separate pilot access from notice-enforcement scope or document the coupling.
- Tests: per-purpose BFF, cross-repo constant lock, OpenAPI enum/status parity, IaC flag wiring, DRAFT grant behavior.

### P1 — Remote versioning
- Implement `remoteSessionRepository.addCoverLetterVersion` delegation; `risRemoteRepository` POST `action=cover-letter` then GET application (or add `application` to BFF response). No auto-retry; 409 → conflict and reload.
- `adoptCoverLetter` remains separate; do not claim atomic adoption without a dedicated action.
- Tests: body/URL, follow-up GET, 409/422, abort/session invalidation, version count.

### P1 — Search-profile versioning
- Add `version` to update input types and UI payloads (manual/CV/ATS), preserve manual version mapping; BFF allowlist includes version for ATS, validates integer and rejects version-only PUT.
- Optional `If-Match` translation in BFF; conflict UX reload + localized message.
- Keep optional initially; require in a later contract step.

### P1 — Builder CV
- Smallest: hide builder optgroup in remote mode; guard `builder:` selection; keep BFF guard/migration diagnostic; optionally specific error code.
- In `LetterModal`/`App`, omit builder `cvReference` in remote mode with clear copy or block adoption; keep builder for letter generation.
- RIS contract extension only with durable builder-profile storage/consent/erasure/OpenAPI; not a quick fix.

### P2 — Privacy export
- Keep RIS-only short term; document that account export is RIS-owned/email channel.
- If self-service: new read-only BFF flag/handler, GET only, allowlisted cursors/limit, no-store, byte/time guard, PARTIAL/UNAVAILABLE rendering, no persistence; Privacy/Legal approval.

### P2/P3 — CV limit and multi-source
- Clamp BFF CV limit to 50 via shared constant; tests for 51/100/default.
- Add shared `canPersistJobOnRis(job)` pre-check for adoption/draft and specific DE/EN messages; keep migration reasons. Decide data policy (canonical join/first source) or RIS contract extension `sources[]`/`locations[]`; never silently drop.

---

## 5. Dependencies and recommended order

1. **RIS erasure main alignment** (P0) — prerequisite for erasure enablement.
2. **RIS consent IaC/docs alignment** (P0) — prerequisite for any apply/deploy from main; plan must show no env removal.
3. **Jobsearch builder-CV UI restriction** (P1, smallest) — no RIS change.
4. **Jobsearch remote cover-letter versions** (P1) — depends on RIS cover-letter route live.
5. **Search-profile optimistic versioning** (P1) — Jobsearch + BFF; optional RIS OpenAPI clarification.
6. **Multi-source/location pre-check** (P2) — Jobsearch only for immediate UX; contract decision separate.
7. **Privacy inspect/export** (P2) — Privacy/Legal + RIS live-route confirmation.
8. **CV list limit** (P3) — Jobsearch small fix.
9. **Cross-repo contract tests** — after P0/P1 changes.

No implementation may start without separate approval. The recommended release order keeps RIS P0 before enabling Jobsearch erasure/consent-dependent features.

---

## 6. Required approvals

- **RIS release/API owner:** erasure partner route, OpenAPI/API-STANDARD scope, consent env/IaC wiring.
- **AWS/Terraform G4/G5:** read-only plan then apply for `ris-dev`; no operation in this analysis.
- **Privacy/Legal:** Art. 9 proof policy, consent notice status, privacy export scope/retention, erasure completeness.
- **Jobsearch product/release owner:** builder-CV restriction, remote versioning, profile versioning UX, multi-source policy.
- **Security:** privacy export PII handling, allowlist coupling.
- **Live verification:** separate read-only AWS approval for current `ris-dev` route/flag state.

---

## 7. Evidence index

- Agent A: `api/_lib/ris/config.mjs`, `accountErasureHandler.mjs`, `api/ris/router.mjs`, `vercel.json`; RIS `lambda/handler.py:508`, `terraform/modules/api/main.tf:133`, `partner_edge/main.tf`, `openapi-platform.yaml:297`, `API-STANDARD.md:74`; commits `451c12e`, `70a9fb9`; prior `MAYS-P3-FINAL-REPORT.md`, `RIS-SCV-AWS-G4-EXECUTION-07-REPORT.md`, `RIS-SCV-AWS-G4-REPLAN-10-REPORT.md`.
- Agent B: `jobsearch/consent_contract.py`, `consent_repository.py`, `lambda/handler.py:586-773,5219-5332`, `terraform/modules/lambda/main.tf:708-713`, `docs/contracts/CONSENT-V1.md`, `openapi-platform.yaml:2304-2382`; Jobsearch `consentsHandler.mjs`, `consentNotice.mjs`, `*ConsentText.mjs`, `.env.example`, `tests/api/ris-consents.test.mjs`.
- Agent C: `risRemoteRepository.ts`, `remoteSessionRepository.ts`, `ApplicationsSection.tsx`, `LetterModal.tsx`, `App.tsx`, `searchProfilesApi.ts`, `profiles/contractTypes.ts`, `searchProfilesHandler.mjs`, `map.mjs`; RIS `lambda/handler.py`, `application_contract.py`, `partner_profile_repository.py`, OpenAPI/APPLICATION-V1.
- Agent D: Jobsearch `api/ris/router.mjs`, `cvsHandler.mjs`, `map.mjs`, `cvStorageApi.ts`, `usePersistentCvStorage.ts`, `StorageConsentSection.tsx`; RIS `lambda/handler.py:4283,4488,5370-5376`, OpenAPI `:915-1013,1258-1261`, `terraform/modules/api/main.tf:690-704`, `jobsearch/application_contract.py:66-78`.

**Note:** Agents A/B/C/D ran independently and read-only. Agent B/C used pinned blobs/snapshots because their sandbox lacked shell; their function-level findings were cross-checked against `origin/main` where possible. No live AWS call was made.

`XREPO-PARALLEL-ORCHESTRATION-01 — XREPO PARALLEL ANALYSIS COMPLETE`
