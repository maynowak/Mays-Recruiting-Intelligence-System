# Analysis Processing — Approval Pack (DRAFT v1.0)

**Purpose:** `analysis-processing` v1.0
**Status:** **DRAFT — not grantable.** Every item below is a release gate, not a
completed approval. Nothing in this pack grants a consent, an entitlement, a
catalog entry or an activation.

Related documents:

- `jobsearch/consent_contract.py` — purpose/version registry (`NOTICE_DRAFT`),
- `docs/privacy/ANALYSIS-PROCESSING-NOTICE-DRAFT.md` — customer-facing notice,
- `agent-installations/analysis-agent/entitlements.yaml` — approval-gated
  entitlement configuration,
- `docs/reports/RIS-ANALYSIS-READINESS-09.md` — release-candidate evidence.

## 1. Roles

| Role | Identity | Responsibility |
|---|---|---|
| Controller | the RIS tenant/operator | purpose, notice, retention |
| Caller | verified runtime partner `ris-internal` | requests analysis for its own user |
| Processor (internal) | `ris-internal-analysis` / `analysis-agent` | parses and compares, stores no results |
| CV owner | authenticated user + tenant | sole owner of the CV |

No external subprocessor or AI provider is involved.

## 2. Data and processing

| Item | Detail |
|---|---|
| Inputs | CV reference (owner-scoped) or structured CV; job text or temporary `jobRef` |
| Operations | CV parsing, job parsing, ATS analysis, deterministic comparison |
| Outputs | `cv.tags`, `job.tags`, `ats.tags`, `comparison` |
| Agent storage | none (results returned to the caller) |
| Temporary job objects | private S3, 2 h default / 4 h hard maximum, SSE, deleted or expired |
| CV documents | unchanged; read through the existing owner-scoped storage |
| Logging | no CV/job content, no PII, no document bytes |

## 3. Legal basis — REVIEW REQUIRED

- Art. 6 GDPR basis: **not claimed by this draft.**
- Art. 9 GDPR (CV content may reveal special categories): **not claimed.**
- Legal must confirm the basis, the necessity/proportionality assessment and
  the wording of the notice before `state` may move from `DRAFT`.
- Until then `consent_notice_approved` stays `false` and the orchestrator fails
  closed with `consent_notice_not_approved`.

## 4. Retention and erasure

| Data | Retention | Erasure |
|---|---|---|
| Parsed results | caller/Orders retention; agent stores none | caller's existing flow |
| Temporary job objects | 2 h default, 4 h hard max | delete + lifecycle backup |
| CV documents | existing RIS CV retention | existing CV deletion/erasure flow |
| Audit/logs | 14 days (log group) | no content logged |

Withdrawal of `analysis-processing` stops further analysis. Existing results
follow the caller's retention; CV deletion follows the existing RIS erasure
flow. No new erasure pipeline and no PURGE are introduced.

## 5. Approval record — all PENDING

| Gate | Owner | Status | Evidence |
|---|---|---|---|
| Legal notice approval (basis, retention, withdrawal) | legal | **PENDING** | this pack, section 3 |
| Operator entitlement approval (`ris-internal-analysis`, `analysis-agent`) | operator | **PENDING** | `entitlements.yaml` |
| Terraform apply approval (additive plan, default-off runtime) | operator | **PENDING** | READINESS-09 report |
| Catalog seed approval (visibility ABSENT today) | operator | **PENDING** | `lifecycle.yaml` |

An approval is recorded only by naming the approver, the date, the exact notice
version and the `legal_approval_ref`; a verbal or implied approval is not
sufficient.

## 6. Activation gate (must all be true)

1. Notice v1.0 moved to `APPROVED`/`ACTIVE` with a non-empty
   `legal_approval_ref`.
2. `consent_notice_approved=true` set explicitly by the operator.
3. Entitlements granted explicitly; `autoGrant` remains `false`.
4. Additive Terraform plan reviewed and applied; `enable_analysis_runtime`
   enabled only with the pinned artifact and SHA-256.
5. Canary with a synthetic tenant passed; no live CV used before approval.
6. Rollback: disable `enable_analysis_runtime`, set `RIS_PARSER_MODE=cli`,
   withdraw entitlements, restore `visibility: ABSENT`.

## 7. Explicit non-actions

- No consent is granted automatically.
- Existing `application-storage`, `cv-storage` and `search-profile-storage`
  consents are not extended.
- No agent activation and no catalog seed in this package.
- No Terraform apply, no production deployment, no PURGE.
