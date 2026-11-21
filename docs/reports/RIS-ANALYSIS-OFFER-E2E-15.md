# RIS-ANALYSIS-OFFER-E2E-15 — CV Analysis · Job Analysis · Matching · Product Readiness

**Date:** 2026-11-21
**Base:** RIS `0c18e47` (`feature/ris-analysis-integration-07`), Jobsearch
`e77ee94` (parser code `c40bf78`)
**Status:** **READY FOR CONTROLLED AWS CANARY APPROVAL**
**No apply. No offer activation. No real data.**

---

## 1. Product / capability matrix

| Offer | Agent / capability | Input | Requested results | Result body | Required entitlements | Consent |
|---|---|---|---|---|---|---|
| **CV Analysis** `analysis.cv` | `analysis-agent` / `analysis.run` | `cv.cvId` (owner PDF) or `cv.structured{skills,…}` | `["cv.tags"]` | `CVParserResultBody` 1.0 | `parse.cv` | `analysis-processing` 1.0 |
| **Job Analysis** `analysis.job` | same | `job.text` or `job.jobRef` | `["job.tags"]` | `JobParserResultBody` 1.0 | `parse.job` | same |
| **CV-Job Matching** `analysis.match` | same | CV + job as above | `["comparison"]`, optional `["ats.tags"]` | `ComparisonResultBody` 1.0; optional `ATSAnalysisResultBody` 2.0 | `parse.cv`, `parse.job`, `compare.tags`; optional `analyze.job` | same |

Call paths (Correction-14):

- RIS API Execute `agentId=analysis-agent` → work queue → shared worker;
- paid Mays-Order `agentOrder.target=analysis-agent` → `ORDER_DISPATCH` →
  dispatch queue → ingress (persist + enqueue) → work queue → worker.

Both use the same WorkItem, registry, entitlement re-check, AgentBody and
result transport. No separate offer-specific queue or dispatcher.

Prepared (not activated): `agent-installations/analysis-agent/offers.yaml`
(3 offers, `DRAFT`, `activation: false`, catalog `ABSENT`, pricing owner
**Mays-Orders**, no price defined).

## 2. Contract and error surface

- Request `schemaVersion` 1.0; result bodies versioned as above; new fields are
  additive only (no version bump in this task).
- Stable error codes: `missing_cv`, `missing_job`, `missing_ats_inputs`,
  `missing_comparison_inputs`, `invalid_cv`, `cv_not_found`,
  `cv_not_accessible`, `cv_not_ready`, `cv_unsupported`, `cv_access_denied`,
  `cv_not_available`, `job_ref_expired`, `job_access_denied`,
  `job_text_too_large`, `invalid_input`, `entitlement_denied`,
  `consent_required`, `consent_purpose_mismatch`, `consent_notice_not_approved`,
  `partner_mismatch`.
- CV is owner/tenant-only; `cvId` is resolved server-side. Structured CVs skip
  the parser.
- Job text ≤ 32 000 chars; `jobRef` is temporary (2 h default / 4 h hard max,
  1 MiB).
- Consent purpose `analysis-processing` 1.0 remains **DRAFT**; the approval flag
  must be explicitly true only after legal approval.

## 3. ATS overlap

The existing **ATS agent** (`ats-agent`, `analyze.job`, external ATS API) remains
the full ATS product. Analysis does **not** reimplement it: `ats.tags` uses the
shared Jobsearch parser projection (`ats.mjs`) through the existing parser
Lambda. `compare_tags` never mixes the ATS score into deterministic coverage;
the ATS score is exposed separately under `provenance.atsScore` and
`ATSAnalysisResultBody`.

`offers.yaml` records `ats-agent` as `notOffer`; no second ATS or scoring
implementation was introduced.

## 4. CV / job / matching tests

New `tests/test_analysis_offers.py` (14 tests) plus existing pipeline/canary
tests cover:

- CV PDF path and structured path; skills, experience, education, languages;
  missing fields remain empty (not invented); invalid structured CV, unknown and
  foreign CV references.
- Job text and `jobRef`; required/preferred skills; experience requirements;
  location/work mode; missing data stays empty/unknown. The parser contract has
  **no dedicated education requirement field**; none is fabricated.
- Matching: full match, partial coverage, missing must-have, preferred-only
  gap, aliases (`k8s`, `Amazon Web Services`, `postgres`), unknown criteria,
  explainable `matched`/`missingInCv`/`missingInJob`/`extraInCv`, and ATS kept
  separate from deterministic coverage.
- Result versions unchanged (`CVParserResultBody 1.0`,
  `JobParserResultBody 1.0`, `ATSAnalysisResultBody 2.0`,
  `ComparisonResultBody 1.0`).

## 5. Ecosystem E2E (local, Correction-14 chain)

Tested end-to-end without AWS:

- Addition-Agent regression through dispatch → work queue → worker.
- Analysis-Agent through the same path (remote execution-only Lambda adapter).
- Registry selects the correct agent; Analysis only `analysis.run`.
- `ORDER_DISPATCH` → ingress persists (fence) + enqueues; worker claims
  `QUEUED → RUNNING`; duplicate/replay does not re-execute.
- Entitlement revoke after enqueue → DEAD_LETTER, no execution; consent denial
  and cross-tenant CV deny; subject fence remains in the worker path.
- Success → `ORDER_RESULT` with stable message/idempotency key; terminal
  failure → `ORDER_FAILED` with stable id; retryable failure does not emit
  ORDER_FAILED.
- Result deduplication is deterministic (Mays consumer deduplicates); no
  exactly-once claim. Analysis never mutates order data.
- No CV/job payloads in WorkItems, logs or result bodies (synthetic fixtures).
- **Open:** SQS-DLQ exhaustion still cannot emit ORDER_FAILED (no DLQ consumer);
  this is not claimed as fixed.

## 6. AWS preflight (read-only)

| Item | Value |
|---|---|
| Caller / account / region | `arn:aws:iam::262370457690:user/devnemo` / `262370457690` / `eu-central-1` |
| Backend / workspace | `ris-dev2-tf-state-dev` / `dev/terraform.tfstate` / lock `ris-dev2-tf-lock` / `ris-dev2` |
| State | serial **67**, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Plan | **4 add / 3 change / 0 destroy / 0 replace** |
| Plan SHA-256 | `11fb32d81b68780f1cdaa3a9856287a3282552af2c6a648d41cb3fe8f802cee2` |
| Plan JSON SHA-256 | `caeaea14bde50c8333a9db2a646a5e6c2c4af9e659cae279b3233b2b42a98cb4` |
| Guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `0d49527e3a74c7e84d0a7ac9c6e0fcfa3673ae510a17ad075848f2e30fc61b37` |
| Analysis bundle | `83eef8e691e15ada27bd9afa109b551c00dae766fe0b8a57c4ce1fc637df1184` |
| Parser artifact | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |

Runtime wiring verified read-only:

- event source mapping work queue → `ris-dev2-dev-agent` (Enabled, batch 5);
- dispatch queue → `ris-dev2-dev-agent-dispatch-ingress` (Enabled, batch 5);
- work queue visibility 300 s, DLQ maxReceiveCount 3;
- worker/ingress timeout 60 s; parser 15 s; analysis remote timeout pinned 45 s
  (new plan) so the worker keeps headroom; analysis Lambda timeout 60 s;
- Mays result consumer accepts `ORDER_RESULT` and `ORDER_FAILED` and verifies
  the HMAC signature (`result_envelope.py`, `result_consumer.py`);
- analysis Lambda is not deployed yet; no apply performed.

## 7. Offer activation checklist (prepared, not executed)

1. Legal approval and `legal_approval_ref` for `analysis-processing` 1.0.
2. Consent notice version ACTIVE; no global test shortcut.
3. Explicit entitlement grant (`parse.cv`/`parse.job`/`compare.tags`/optional
   `analyze.job`).
4. Catalog/offer seed with status ACTIVE (currently ABSENT/DRAFT).
5. Mays-Orders price/billing contract for paid offers (not defined in RIS).
6. Result retrieval contract for Jobsearch/partner.
7. Activation, monitoring, and rollback (disable entitlement/catalog; restore
   deny env).
8. Separate synthetic env configuration approval for canary; no real users.

## 8. Tests and commits

| Check | Result |
|---|---|
| New offer/CV/job/matching tests | 14 passed |
| Broad focused set (25 files) | **363 passed, 9 skipped** |
| Terraform fmt / validate | PASS |
| AWS preflight | read-only, no mutation |

Commits: ecosystem/correction base `6440e53`; this package adds the offer
contract + tests + report. **No apply.**

## 9. Verdict

**READY FOR CONTROLLED AWS CANARY APPROVAL.**

The three offers are contract-complete, versioned and locally tested through the
Correction-14 ecosystem path. AWS canary and any activation remain blocked on
the explicit apply approval, a separate synthetic env approval, legal notice,
entitlement/catalog approval and the DLQ-exhaustion decision. No agent is
publicly offered and no real user data is processed.
