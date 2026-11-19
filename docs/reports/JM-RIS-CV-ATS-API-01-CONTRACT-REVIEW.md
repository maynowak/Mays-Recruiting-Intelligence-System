# JM-RIS-CV-ATS-API-01 — CV/ATS Capability & Contract Review

**Status:** `CONTRACT READY FOR IMPLEMENTATION — SECURITY/PRIVACY GATES OPEN`  
**Repositories:** `mays-jobsearch`, `Mays-Recruiting-Intelligence-System`  
**Mode:** analysis only; no endpoint implementation, AWS/Terraform, auth, consent,
CV storage or production change.

## 1. Executive Result

The existing ATS analysis is already server-side and reusable. CV parsing is
mostly a pure TypeScript parser, but PDF extraction is browser-bound and there
is no HTTP contract. The existing Jobsearch ATS/match endpoints are not
authenticated and are not safe to expose to an agent pipeline. The RIS ATS
agent already delegates `analyze.job` to `/api/ats-analysis`, but it has no
service credential and no parse/match capabilities.

**Smallest sensible expansion:** expose versioned **analysis service endpoints**
in Jobsearch that wrap the existing parser, ATS and matching modules. Do not
create a second matching engine or duplicate ATS rules.

## 2. Capability Matrix

| Capability / component | Status | Evidence and reason |
|---|---|---|
| CV text structure detection | **EXISTING / REUSABLE** | `src/lib/cvBuilder/documentStructure.ts`; pure parser, no DOM |
| CV text-to-draft mapping | **REQUIRES EXTRACTION** | `src/lib/cvBuilder/pdfImport.ts` is pure logic but TypeScript; not importable by `.mjs` server functions as-is |
| CV draft contract | **EXISTING / REUSABLE** | `CvBuilderDraftV1` and entry types in `contractTypes.ts` |
| PDF → pages/text | **REQUIRES EXTRACTION** | `src/lib/pdf.ts` uses `pdfjs-dist` browser worker and `File`; not serverless-compatible as-is |
| CV parsing HTTP API | **MISSING** | no server endpoint; only browser import dialog |
| ATS requirement extraction | **EXISTING / REUSABLE** | `extractRequirementsFromJob`, `extractJobMetadata` in `api/_lib/ats.mjs` |
| Deterministic ATS scoring | **EXISTING / REUSABLE** | `analyzeJobForAts` in `api/_lib/ats.mjs` |
| Existing ATS HTTP endpoint | **REQUIRES API WRAPPER** | `api/ats-analysis.mjs` has CORS `*`, no auth/tenant/version and no service credential |
| CV-job matching logic | **EXISTING / REUSABLE** | `computeMatch` / `computeMatchForJob` in `api/_lib/matching.mjs` |
| Existing matching HTTP endpoint | **REQUIRES API WRAPPER** | `api/match.mjs` has no auth/tenant/version; uses AI without server-side consent proof |
| RIS ATS client | **REQUIRES API WRAPPER** | `agents/ats_agent/agent.py` calls `/api/ats-analysis`, no auth headers/credential |
| RIS `analyze.job` agent | **EXISTING / REUSABLE** | `ATSAgent`/`ATSHttpClient`; validates work item and delegates; only `analyze.job` |
| RIS CV parse capability | **MISSING** | no capability, client or contract |
| RIS match capability | **MISSING** | only `ChainTemplate.job_matching` template names `match_agent`; no implemented runtime adapter found |
| RIS CV storage endpoints | **EXISTING / REUSABLE (storage only)** | `/v1/partner/me/cvs`, document upload/download; not a parser/analysis API |
| Service-to-service authentication | **BLOCKED** | no reverse RIS→Jobsearch credential/audience/tenant proof in current code; existing RIS partner credential is Jobsearch→RIS |
| Server-side analysis consent | **BLOCKED** | existing `ai.consent` is a request boolean, not a verified server consent record; no separate analysis purpose/notice |
| Tenant isolation | **BLOCKED** | current public endpoints do not resolve/validate a tenant; body/header values are not trusted |
| Request/file limits | **REQUIRES API WRAPPER** | browser import has client limits; no parser service limit contract |
| Data retention/minimization | **REQUIRES API WRAPPER** | parser can return contact data; no no-store/ephemeral contract yet |
| Structured, versioned errors | **MISSING** | existing endpoints use ad-hoc `{error, code}`; no shared analysis envelope |

## 3. Existing Implementations

### CV parser

- `src/lib/cvBuilder/documentStructure.ts`: pure page/block/section detection.
- `src/lib/cvBuilder/pdfImport.ts`: pure text-to-`CvBuilderDraftV1` mapping,
  confidence, unrecognized items and mapping provenance.
- `src/lib/pdf.ts`: browser-only PDF.js extraction; worker URL and `File`.
- `src/components/CvBuilderImportDialog.tsx`: UI orchestration, not reusable
  as a service.
- `src/lib/cvBuilder/toAnonymizedText.ts`: useful for matching data
  minimization, but it is a frontend module today.

### ATS and matching

- `api/_lib/ats.mjs`: deterministic requirement extraction, metadata, matching,
  scoring and recommendations. No need for a second ATS engine.
- `api/ats-analysis.mjs`: HTTP wrapper around `ats.mjs`; currently
  `Access-Control-Allow-Origin: *`, no `Authorization`/tenant check, no
  `schemaVersion`.
- `api/_lib/matching.mjs`: AI-based `computeMatch` using `chat`; up to 10 jobs
  and 5 detailed results.
- `api/match.mjs`: HTTP wrapper around `matching.mjs`; no auth/tenant/consent
  verification, only CORS and optional guest IP enrichment.

### RIS agents

- `agents/ats_agent/agent.py`: `ATSHttpClient` posts to
  `${ATS_API_BASE_URL}/api/ats-analysis`; no credential header; default base
  URL is `https://mays-jobsearch.vercel.app`.
- `agents/ats_agent/registry.py`: only capability `analyze.job`.
- `agents/runtime/pipeline.py`: registers ATS routes only.
- `agents/ecosystem/chain.py`: `job_matching` is a template (`job_agent`,
  `match_agent`), not an implemented matching client.
- RIS partner API has CV storage/profile endpoints, but no CV parse, ATS
  requirement extraction or matching endpoint.

## 4. Proposed Minimal API Expansion

All endpoints are **Jobsearch-owned analysis service endpoints**, not a new
RIS product API. They call the existing modules; no duplicate business logic.

### 4.1 `POST /api/analysis/v1/cv/parse`

**Purpose:** PDF → structured CV. Ephemeral; no CV retention.

Request (multipart or equivalent short-lived upload reference):

```text
Authorization: Bearer <RIS service JWT>
X-Request-Id: <uuid>
Content-Type: multipart/form-data; boundary=...
file: application/pdf, max 4 MiB direct request
schemaVersion: 1
language: de | en (optional)
includePersonal: false (default)
```

For files above the Vercel body limit (or the 10 MiB product limit), use a
short-lived presigned upload reference; do not base64 a PDF into JSON.

Response `CvParseResultV1`:

```json
{
  "schemaVersion": 1,
  "requestId": "uuid",
  "data": {
    "document": {
      "sha256": "hex",
      "sizeBytes": 12345,
      "pageCount": 3,
      "language": "de"
    },
    "draft": { "schemaVersion": 1, "personal": {}, "profile": {},
      "experience": [], "education": [], "skills": [], "projects": [],
      "certificates": [], "languages": [], "links": [] },
    "confidence": {
      "overall": "confirmed|partial|uncertain",
      "sections": { "skills": "confirmed", "experience": "partial" }
    },
    "unrecognized": [],
    "mapping": { "sections": [], "timeline": [] },
    "anonymizedProfile": {
      "headline": "…",
      "skills": [],
      "targetRoles": [],
      "experienceLevel": "…"
    }
  },
  "warnings": []
}
```

Rules:

- `includePersonal=false` must omit name/e-mail/phone/location from
  `anonymizedProfile`; full `draft` personal fields require an explicit
  analysis purpose and legal basis.
- Never return the raw PDF bytes or unbounded raw text.
- No persistence; no cache; `Cache-Control: no-store`.

### 4.2 `POST /api/analysis/v1/ats/requirements`

**Purpose:** deterministic ATS requirement extraction without AI.

```json
{
  "schemaVersion": 1,
  "job": {
    "slug": "string",
    "title": "string",
    "company_name": "string",
    "descriptionPlain": "string",
    "tags": [],
    "location": [],
    "remote": true,
    "jobTypes": [],
    "contractType": "string"
  },
  "profile": {
    "skills": "string",
    "targetRoles": [],
    "criteria": {
      "requiredSkills": [], "preferredSkills": [], "excludedTerms": []
    }
  }
}
```

Response:

```json
{
  "schemaVersion": 1,
  "data": {
    "analysisStatus": "complete|limited|insufficient",
    "metadata": {},
    "basis": {},
    "requirements": [
      { "id": "skill_0", "text": "…", "category": "skill",
        "importance": "high", "source": "description" }
    ]
  },
  "warnings": []
}
```

Reuse `extractJobMetadata` and `extractRequirementsFromJob` exactly.

### 4.3 `POST /api/analysis/v1/ats/analyze`

**Purpose:** existing deterministic analysis plus recommendations; optional AI
formulation must default off.

```json
{
  "schemaVersion": 1,
  "job": {},
  "profile": {},
  "ai": { "enabled": false }
}
```

Response reuses the stable parts of `/api/ats-analysis`:

```json
{
  "schemaVersion": 1,
  "data": {
    "analysis": {},
    "recommendations": [],
    "ai": { "requested": false, "executed": false }
  },
  "warnings": []
}
```

Do not trust `ai.consent` from the caller. If AI formulation is enabled, the
analysis service must verify a server-side consent record/purpose first.

### 4.4 `POST /api/analysis/v1/match`

**Purpose:** CV/job matching using the existing `matching.mjs` engine.

```json
{
  "schemaVersion": 1,
  "profile": {
    "skills": "normalized skills",
    "targetRole": "role",
    "city": "optional",
    "anonymizedText": "optional bounded text"
  },
  "jobs": [
    { "slug": "…", "title": "…", "company_name": "…", "tags": [],
      "location": [], "remote": false }
  ],
  "mode": "ai",
  "limit": 10
}
```

Response:

```json
{
  "schemaVersion": 1,
  "data": {
    "matches": [
      { "slug": "…", "score": 0, "why": "…", "prepare": "…",
        "job": {} }
    ],
    "meta": { "evaluated": 1, "totalFound": 1, "displayedInitially": 5 }
  },
  "warnings": []
}
```

Rules:

- Maximum 10 evaluated jobs (existing `MATCH_EVAL_LIMIT`); reject larger lists
  rather than silently evaluating a different set.
- Pass only skills/target role/anonymized text; never contact fields.
- AI mode requires verified consent and provider availability; deterministic
  mode can use `analyzeJobForAts` but must be clearly a separate mode/contract,
  not a second matching implementation.
- No result cache currently exists in `matching.mjs`; do not add cross-tenant
  caching.

## 5. Shared Contract Envelope and Error Codes

Use the existing RIS style of `schemaVersion`, request ID, data and structured
errors, but keep the Jobsearch envelope explicit:

```json
{
  "schemaVersion": 1,
  "requestId": "uuid",
  "data": {},
  "warnings": [{ "code": "…", "message": "…" }]
}
```

Error:

```json
{
  "schemaVersion": 1,
  "requestId": "uuid",
  "error": { "code": "…", "message": "…" }
}
```

| Code | HTTP | Meaning |
|---|---:|---|
| `unauthenticated` | 401 | missing/invalid service token |
| `forbidden` | 403 | tenant/audience/scope mismatch |
| `consent_required` | 403 | analysis purpose has no verified consent |
| `schema_version_unsupported` | 422 | unknown contract version |
| `validation_error` | 422 | malformed body/fields |
| `unsupported_media_type` | 415 | not PDF |
| `file_too_large` | 413 | exceeds 4 MiB direct / agreed limit |
| `pdf_invalid` | 422 | unreadable PDF |
| `pdf_encrypted` | 422 | encrypted PDF |
| `pdf_too_many_pages` | 422 | page limit exceeded |
| `text_too_long` | 422 | extracted text limit exceeded |
| `requirements_too_large` | 413 | job/profile payload exceeded |
| `jobs_too_many` | 422 | more than 10 match candidates |
| `rate_limited` | 429 | service rate limit |
| `analysis_timeout` | 503 | parse/analysis exceeded time budget |
| `provider_unavailable` | 503 | AI provider unavailable |
| `internal_error` | 500 | safe generic failure |

Never return parser text, CV contact data, raw provider errors, tokens or
tenant IDs in logs or error details.

## 6. Security Requirements

### Authentication / tenancy

- Use a separate **server-to-server analysis identity** (signed RIS service JWT
  with issuer/audience/tenant, or equivalently strong mTLS). Do not reuse the
  existing `RIS_PARTNER_CREDENTIAL`/`X-Api-Credential`: that is Jobsearch→RIS.
- Resolve `tenantId` and `sub` from the verified token; ignore/reject body
  tenant/user overrides.
- Require explicit scope such as `analysis:parse`, `analysis:ats`,
  `analysis:match`; deny by default.
- The RIS `ATSHttpClient` currently sends **no auth header**; this is a blocker
  for any production exposure.

### Consent / privacy

- CV parsing and matching process personal data; storage consent is not
  analysis consent.
- Add a bounded `analysis` purpose/notice or an explicit server-side consent
  reference from the RIS consent store; fail closed when no approved notice
  exists.
- AI formulation/matching must verify consent server-side; a request boolean is
  not a consent record.
- No CV/profile persistence, no cross-tenant cache, no raw text in logs.
- For matching, send the anonymized profile only; exclude contact fields and
  unneeded free text.
- Retention: request-scoped memory only. If a presigned temporary object is
  used for >4 MiB, delete it immediately after parse and record only metadata.

### Limits / availability

- PDF: `application/pdf` only; direct multipart max **4 MiB** (Vercel body
  boundary); product maximum target **10 MiB** via short-lived upload.
- Max 40 pages and 60,000 extracted characters; timeout 30 s within the
  existing 60 s function limit.
- Reject encrypted/corrupt PDFs before parsing; no OCR fallback.
- Rate-limit per tenant/service and per request; no unbounded AI matching.
- Return `Cache-Control: no-store`; no public CORS for service endpoints.

## 7. Minimal Implementation Plan

1. **Extraction only**
   - Move/mirror pure `documentStructure` + `pdfImport` logic into a JS/TS
     module consumable by serverless functions without browser globals.
   - Add Node PDF extraction using `pdfjs-dist/legacy` (tests already use the
     legacy build); keep the browser path unchanged.
   - Add parser fixtures/tests; no API yet.
2. **Service contract and auth**
   - Add `analysis` service JWT validation/tenant/scope gate and common envelope.
   - Add feature flag, request IDs, limits, structured errors, no-store.
3. **CV parse endpoint**
   - Wrap the extracted parser; no persistence; personal fields off by default.
4. **ATS requirement/analyze endpoints**
   - Wrap `extractRequirementsFromJob`, `extractJobMetadata`,
     `analyzeJobForAts`; AI disabled by default.
5. **Matching endpoint**
   - Wrap `computeMatch`; max 10 jobs; AI consent/provider gate; no cache.
6. **RIS clients**
   - Extend `ATSHttpClient` with credential, versioned path and parse/match
     capabilities; keep `analyze.job` behavior compatible.
   - Add contract tests against a mock server; no RIS duplicate parser/matcher.
7. **Privacy/security release gate**
   - Approve analysis purpose/notice, token/tenant configuration, limits and
     no-retention behavior before any live call.

## 8. Blockers / Decisions Required

- **Service authentication** from RIS → Jobsearch is not present. A signed
  service JWT/mTLS decision and tenant/scope allowlist are required.
- **Analysis consent** is not represented by the existing request booleans;
  privacy/legal approval for a bounded purpose is required.
- **Serverless PDF path** must be extracted and tested; browser PDF.js cannot
  be imported directly.
- **Existing public endpoints** `/api/ats-analysis` and `/api/match` must not be
  exposed as-is to agents.
- **No Search Console/AWS/Terraform** action is part of this review.

**JM-RIS-CV-ATS-API-01 — CONTRACT READY FOR IMPLEMENTATION.**
