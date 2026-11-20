# Analysis Processing Notice — DRAFT v1.0

**Status:** **DRAFT — legal/operator approval required.** Not grantable until
`analysis-processing` v1.0 is moved to `APPROVED`/`ACTIVE` in
`jobsearch/consent_contract.py` and a `legal_approval_ref` is recorded.

**Purpose:** `analysis-processing` (separate from `application-storage`,
`cv-storage` and `search-profile-storage`; existing consents are **not**
extended).

## Processing

| Item | Detail |
|---|---|
| Inputs | CV reference (owner-scoped) or structured CV data; job text or temporary `jobRef` |
| Operations | CV parsing, job parsing, ATS analysis, deterministic CV↔job comparison |
| Providers | none (no external AI provider, no network call in the comparison) |
| Outputs | `cv.tags`, `job.tags`, `ats.tags`, `comparison` |
| Storage by the agent | none; parsed results are returned to the caller |
| Temporary job objects | private S3, 2 h default, 4 h hard maximum, deleted/expired |
| CV documents | unchanged; read from the existing owner-scoped RIS storage |

## Legal basis / retention / withdrawal — REVIEW REQUIRED

- **Legal basis:** to be confirmed by legal (Art. 6 and, where applicable,
  Art. 9 GDPR for CV content). This draft claims none.
- **Retention:** agent stores no results; result retention is owned by the
  caller/Orders. Temporary job objects expire after 4 h at the latest.
- **Withdrawal:** withdrawing `analysis-processing` stops further analysis.
  Existing results/orders follow the caller's retention; CV deletion follows
  the existing CV/erasure flow.
- **Erasure:** no new erasure pipeline; the agent stores nothing. CV documents
  remain governed by the existing RIS CV deletion and consent withdrawal.
- **No silent extension:** `application-storage`, `cv-storage` and
  `search-profile-storage` do not authorize analysis.

## Runtime gate

The orchestrator requires:

1. `consent == true`,
2. `consent_purpose == "analysis-processing"`,
3. `consent_notice_version == "1.0"` and `consent_notice_approved == true`.

The last flag stays `false` until the notice above is approved. Missing or
mismatched consent fails closed with `consent_required`,
`consent_purpose_mismatch` or `consent_notice_not_approved`.

## Internal partner

The analysis agent is the internal partner `ris-internal` /
`ris-internal-analysis`. The caller partner comes from the verified runtime
context; the CV owner must equal the authenticated user and tenant. Cross-tenant
and cross-partner access fail closed (`cv_owner_mismatch`, `cv_tenant_mismatch`,
`partner_mismatch`).
