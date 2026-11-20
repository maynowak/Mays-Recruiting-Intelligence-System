# RIS-ANALYSIS-INTERNAL-PARTNER-08 — Dedicated Runtime · Partner Isolation · Privacy

**Date:** 2026-11-20
**Verdict:** **READY FOR CONTROLLED DEPLOYMENT REVIEW** (with explicit PENDING
approvals; not LIVE, no apply).

---

## 1. Internal partner architecture

The analysis agent is modeled as a dedicated internal partner:

| Role | Identity | Source |
|---|---|---|
| Caller | verified runtime context (`caller_partner_id`) | never from the request body |
| Executor | `ris-internal` / `ris-internal-analysis` / `analysis-agent` | fixed constants in `agents/analysis/partner.py` |
| CV owner | authenticated user + tenant | RIS CV storage / structured input |

Enforcement:

- `partnerId` in a request must be absent or `ris-internal`; any other value is
  `partner_mismatch`.
- A caller partner other than `ris-internal` is rejected.
- CV use is owner-only: `cv_owner_mismatch` / `cv_tenant_mismatch`.
- Tenant and user are required (`missing_identity`).
- Existing WorkItem, Order and Entitlement contracts are reused; no new
  orchestration platform.

Tests: claimed external partner, caller mismatch, wrong tenant, wrong owner,
missing identity.

## 2. Dedicated infrastructure (Terraform, plan only)

New module `terraform/modules/analysis_runtime`:

- dedicated IAM role `${project}-${env}-analysis` (assume role: Lambda only),
- least-privilege policy: logs, `s3:GetObject` on the existing documents
  `tenant/*`, `Put/Get/Delete` only on `jobs/*` of the new bucket,
- private S3 bucket `${project}-${env}-analysis-jobs` with Public Access Block,
  SSE AES256 and a 1-day lifecycle backup,
- log group.

Root wiring added; **no shared transport policy is replaced or deleted**.
The legacy result-policy addresses are retained additively so the live IAM
resources are not migrated.

**Node execution path:** the Python agent uses
`agents/parsers/node_adapter.py` → jobsearch `scripts/ris-parser-cli.mjs`
(parse.cv/parse.job/parse.ats). The dedicated Lambda binding is PENDING (see
approvals); the role and bucket are prepared for it.

**Temporary job storage:** `agents/analysis/job_store.py` enforces 2 h default,
4 h hard maximum, 1 MiB, opaque `job_` refs, owner binding, SSE, delete and
cleanup; S3 lifecycle is only a backup.

**CV storage:** `agents/analysis/cv_bridge.py` resolves `cvId` through
`PartnerProfileRepository` (owner/tenant/ready) and reads the PDF from the
existing documents bucket; structured data skips parsing. No CV bytes in
WorkItems, SQS, logs or errors.

## 3. Terraform plan and shared guard

- `terraform fmt -recursive` **PASS**, `init -backend=false` + `validate`
  **PASS** (deprecation warnings only).
- Read-only plan via the standard installer workflow (no PowerShell list
  quoting workaround): **11 add / 2 change / 0 destroy**.
- Shared-infrastructure guard: **`plan deletes/replaces no shared infrastructure`** (`NO_SHARED_DESTROY`).
- No IAM policy migration, no queue/Lambda/table/secret deletion.
- Adds: analysis role/policy/bucket/log group, `orders_agent_dispatch`,
  documents CORS; changes: two Lambda in-place updates.
- The ris-dev2 overlay now carries the non-secret live transport references
  (enable flag, producer role ARNs, dispatch/result queue URLs and ARNs); only
  the result secret **ARN** is passed as a single `--var` (no list quoting).

## 4. Privacy and consent contract

- New purpose **`analysis-processing` v1.0** in
  `jobsearch/consent_contract.py`, separate from `application-storage`,
  `cv-storage` and `search-profile-storage`; existing consents are **not**
  extended.
- The notice is registered as **DRAFT** with an empty `legal_approval_ref`.
- The orchestrator requires:
  `consent == true`, `consent_purpose == analysis-processing`,
  `consent_notice_version == 1.0`, `consent_notice_approved == true`.
  Missing/mismatched → `consent_required`, `consent_purpose_mismatch`,
  `consent_notice_not_approved`.
- `docs/privacy/ANALYSIS-PROCESSING-NOTICE-DRAFT.md` marks legal basis,
  retention and withdrawal as **REVIEW REQUIRED**.
- Erasure/retention: the agent stores no results or CV bytes; temporary job
  objects expire/delete; CV deletion and result retention stay with the
  existing RIS/Orders flows. PURGE remains blocked.

## 5. Tests and synthetic E2E

| Check | Result |
|---|---|
| `tests/test_analysis_pipeline.py` | **31 passed** (CV/job/ATS/comparison, input/choice errors, consent purpose/draft, partner/owner isolation, cross-tenant, idempotency, TTL, size, cleanup, ATS 2.0, determinism, agent/registration) |
| `tests/test_parser_agents.py` | 17 passed (incl. real CLI PDF/job) |
| Focused RIS regression | **161 passed, 13 subtests** |
| Jobsearch parser CLI | 3 passed |
| `terraform fmt` / `validate` | PASS |

Synthetic full-pipeline run with the real Node CLI:

```
results   [ats.tags, comparison, cv.tags, job.tags]
comparison required 100 %, preferred 100 %, overall 100 %, weighted 100.0
atsTags   4
idempotent replay true
```

## 6. Shared resources and isolation

- No shared IAM policy replaced or deleted (0 destroys).
- Shared queues, Lambdas, tables and the HMAC secret untouched.
- Dedicated analysis role and private job bucket are additive.
- No Cognito/CloudFront/DNS change.

## 7. Open approvals (before any deployment)

1. **Legal/operator approval** of the `analysis-processing` notice v1.0
   (legal basis, retention, withdrawal).
2. **Node execution path** for the dedicated runtime (Node Lambda/container or
   approved runtime switch); until then no LIVE enablement.
3. **Apply approval** for the additive plan (role/bucket/CORS/updates); no
   apply in this package.
4. **CV service wiring**: inject `RequestCvResolver(repository=…,
   document_loader=…)` in the service layer.
5. Entitlement/catalog decision for `analysis-agent` (dispatch-only today).

## 8. Verdict

**READY FOR CONTROLLED DEPLOYMENT REVIEW.** The internal-partner contract,
privacy gate, dedicated IAM/bucket design and the full pipeline are locally
verified; the plan is additive and the shared guard passes. LIVE remains
blocked until approvals 1–3 and the Node path are resolved.
