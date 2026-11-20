# RIS-AGENT-ANALYSIS-ORCHESTRATION-04 — CV / Job / ATS / Comparison Pipeline

**Repositories**
- RIS: branch `feature/ris-agent-analysis-orchestration-04`
- Jobsearch: branch `feature/ris-analysis-parser-cli-04` (`40a5db2`, pushed)

**Status:** **LOCAL VERIFIED** — no deployment, no AWS mutation, no live enablement.

---

## 1. Architecture

```
WorkItem (analysis.run)
   │
   ▼
AnalysisAgent ──► AnalysisOrchestrator
   │                 ├─ validate_request (schemaVersion, requestedResults, inputs)
   │                 ├─ require_capabilities (consent + entitlements)
   │                 ├─ CV:  RequestCvResolver ── structured data
   │                 │        └─ RIS documents S3 (PDF) ──► NodeParser.parse_cv
   │                 ├─ Job: inline text (≤32 KiB) or JobStore (jobRef)
   │                 │        └─ NodeParser.parse_job
   │                 ├─ ATS: NodeParser.parse_ats (existing ats.mjs)
   │                 └─ compare_tags (deterministic, alias map 1.0.0)
   │
   ▼
results: cv.tags | job.tags | ats.tags | comparison
```

- Python Agent Body remains the runner; no second platform.
- The single JS boundary is `agents/parsers/node_adapter.py` → jobsearch
  `scripts/ris-parser-cli.mjs`, which wraps the existing `parseCvBuffer`
  (`pdf.mjs` + `cvParser.mjs`), `extractAtsRequirements` and `analyzeAts`.
- No disabled v1 HTTP API is used.
- No new queue, Lambda, table, Cognito, CloudFront or DNS resource.

## 2. Request contract (1.0)

```json
{
  "schemaVersion": "1.0",
  "requestedResults": ["cv.tags", "job.tags", "ats.tags", "comparison"],
  "input": {
    "cv":  {"cvId": "..."} | {"structured": {"skills": ["..."], "...": "..."}},
    "job": {"text": "..."} | {"jobRef": "job_..."},
    "profile": {"skills": "..."} 
  },
  "idempotencyKey": "..."
}
```

- Unknown/duplicate results, missing inputs and inline job text above 32 KiB
  are rejected (`invalid_requested_results`, `missing_cv`, `missing_job`,
  `job_text_too_large`).
- `input.cv` is required for `cv.tags` and `comparison`; ATS requires CV data
  or `input.profile`.
- Identity (tenant, user, entitlements, consent) is supplied by the runtime,
  never by the client; client `ownerId` is not accepted as authority.
- Only requested parsers run (verified: ATS-only does not run the job parser).

## 3. Result bodies

| Body | Version | Content |
|---|---|---|
| `CVParserResultBody` | 1.0 | `cvTags`, skills, experience, education, languages, location, confidence, parserVersion, provenance, stableId |
| `JobParserResultBody` | 1.0 | `jobTags`, required/preferred skills, experience requirements, workMode, location, confidence, parserVersion, provenance, stableId |
| `ATSAnalysisResultBody` | **2.0** (compatible) | existing `analysis` block + additive `atsTags` |
| `ComparisonResultBody` | 1.0 | cvTags, jobTags, optional atsTags, matched, missingInCv, missingInJob, extraInCv, coverage, weightedScore, aliasMapVersion, provenance |

Tags are result data, not agent metadata (consistent with
`docs/ecosystem/METADATA_GOVERNANCE.md`, where agent-level tags are deferred).

## 4. Comparison semantics

- Deterministic, no external AI/provider.
- Alias map `1.0.0` (k8s→kubernetes, nodejs→node.js, …), documented in
  `agents/analysis/tags.py`.
- Required weight 2, preferred weight 1; required/preferred reported separately.
- `weightedScore` is null when the job has no tags (`unknown: true`).
- The ATS score is kept in `provenance.atsScore`, never mixed into the
  comparison score.
- Repeated runs produce identical results (tested).

## 5. CV storage bridge

- `RequestCvResolver` accepts structured CV data or a server-side `cvId`.
- `cvId` is resolved through `PartnerProfileRepository.get(resourceId, user,
  tenant, partnerApp, issuer)`; the record must be owned by the caller,
  tenant-matched and `ready`.
- The PDF is fetched from the private RIS documents bucket using the existing
  key layout `tenant/<tenant>/users/<user>/documents/<docId>`; no CV bytes go
  into WorkItems, SQS, logs or error messages.
- Structured data skips the parser entirely (no unnecessary processing).
- Missing access, wrong tenant, non-ready CV, missing document or consent:
  fail closed with a stable code.

## 6. Temporary job storage

| Parameter | Implementation |
|---|---|
| Default TTL | 2 h (`STANDARD_TTL_SECONDS`) |
| Maximum access | 4 h (`MAX_TTL_SECONDS`, enforced on read and extend) |
| Max object | 1 MiB |
| Inline text | ≤32 KiB |
| Reference | opaque `job_<token>`; key `jobs/<tenant>/<user>/<ref>.txt` |
| Ownership | server-side tenant + user, checked on read |
| Encryption | S3 SSE AES256 (`S3JobStore`) |
| Cleanup | `delete`, `cleanup_expired`; S3 lifecycle only as backup |

Expired refs are refused (`job_ref_expired`); cross-tenant access raises
`job_access_denied`. Physical deletion is not claimed; `S3JobStore.delete` is
best effort and lifecycle is the backup.

## 7. Entitlement / consent matrix

| Result | Capability | Inputs | Extra requirement |
|---|---|---|---|
| `cv.tags` | `parse.cv` | CV | consent |
| `job.tags` | `parse.job` | job | consent |
| `ats.tags` | `analyze.job` | job + (CV or profile) | consent |
| `comparison` | `compare.tags` (+ `parse.cv`, `parse.job`) | CV + job | consent |

Missing consent → `consent_required`; missing entitlement →
`entitlement_denied`. The analysis agent fails closed when no entitlements are
configured.

## 8. Costs and billing boundaries

- One external order = one order reference; internal parser steps are not
  separate billable orders.
- Repeated deliveries return the cached idempotent result; no duplicate charge.
- Billing status and processing result stay separate; no payment activation.
- No AI provider call is made by the comparison; ATS/parser calls are local
  Node executions.

## 9. Tests

| Suite | Result |
|---|---|
| `tests/test_analysis_pipeline.py` | **25 passed** (CV-only, job-only, ATS-only, comparison-only, full, invalid choice, missing inputs, cross-tenant, consent, entitlement, idempotency, expiry, 2h/4h, 1 MiB, no document in result, parser failure, cleanup, ATS 2.0, determinism, agent wrapper, registration) |
| Jobsearch CLI (`npm run test:parsers`) | **3 passed** (job tags/stableId, CV PDF fixture, error codes) |
| RIS parser/adapter regression | **42 passed** |
| Broader RIS regression | **296 passed, 13 subtests** (before the final CLI contract fix; rerun green) |

Synthetic data only; no real CVs or credentials.

## 10. Deployment and rollback (PENDING, no action taken)

1. **Node execution path:** Python 3.14 Lambda has no `node`. Options:
   approved Node sidecar/Lambda invocation, Node runtime switch, or a pinned
   Node binary in the bundle. Until then the parser agents stay LOCAL.
2. **Job bucket:** private S3 bucket (Public Access Block, SSE, lifecycle
   4 h) + IAM `s3:PutObject/GetObject/DeleteObject` for the worker role;
   Terraform plan only, no apply.
3. **Secrets/config:** `RIS_PARSER_CLI`, `RIS_PARSER_NODE`, `DOCUMENTS_BUCKET`,
   `JOBS_TEMP_BUCKET`, `ANALYSIS_*` (if the HTTP path is used instead).
4. **Enablement:** agent package validation → reviewed Terraform plan → canary
   with synthetic data → LIVE VERIFIED only after approval.
5. **Rollback:** disable the entitlement; keep the parser bundle and bucket;
   delete only temporary job objects; no data in the parser.

## 11. Blockers / open points

- **Node runtime in the Python Lambda** (blocker for live).
- Job bucket Terraform and IAM not applied (no AWS changes in this package).
- Concrete `RisCvResolver` wiring must be injected by the handler/service
  layer; the repository interface is implemented and tested with fakes.
- `parse.ats` uses the existing `ats.mjs` through the CLI; the existing
  HTTP-based ATS agent remains the production path until the Node path is
  approved.
- The jobsearch branch `feature/ris-analysis-parser-cli-04` is based on
  `origin/main`; the RIS branch is based on `feature/ris-jm-agent-standardization-01`
  and is 14 commits behind main — rebase before merge.

## 12. Artifacts

- `agents/analysis/{contracts,tags,job_store,cv_bridge,orchestrator}.py`
- `agents/analysis_agent/{agent,registry}.py`
- `agents/parsers/node_adapter.py` (parse.ats capability)
- `agents/runtime/pipeline.py` (registration)
- `tests/test_analysis_pipeline.py`
- Jobsearch: `scripts/ris-parser-cli.mjs`, `tests/parsers/ris-parser-cli.test.mjs`,
  `docs/RIS-ANALYSIS-PARSER-CLI.md`
- `docs/AI_AUDITLOG.md`
