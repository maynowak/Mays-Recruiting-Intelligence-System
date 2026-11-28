# Privacy / DSGVO review package

**Package status:** DOCUMENTATION READY FOR REVIEW — not a legal opinion, deployment attestation, or permission to process real personal data.
**Evidence date:** 2026-11-28. Status values apply to repository evidence at the pins below.

## Evidence index

| Material | Status | Canonical document / evidence |
|---|---|---|
| Discovery and cross-repository evidence | VERIFIED (source inventory) | [`../reports/RIS-DSGVO-COMPLIANCE-01-PHASE-1-DISCOVERY.md`](../reports/RIS-DSGVO-COMPLIANCE-01-PHASE-1-DISCOVERY.md) |
| RIS data inventory | PARTIAL (historical entries reconciled in discovery) | [`RIS_PRIVACY_DATA_INVENTORY_V1.md`](RIS_PRIVACY_DATA_INVENTORY_V1.md) |
| Capability and erasure contract | PARTIAL | [`RIS_PRIVACY_CAPABILITY_CONTRACT.md`](RIS_PRIVACY_CAPABILITY_CONTRACT.md) |
| Receipt and retention decision | OPEN | [`RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md`](RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md), [`PRIVACY_RECEIPT_V1.md`](PRIVACY_RECEIPT_V1.md) |
| Backup/restore | OPEN | [`BACKUP_RESTORE_PRIVACY_CONTRACT.md`](BACKUP_RESTORE_PRIVACY_CONTRACT.md), [`R08_ROADMAP.md`](R08_ROADMAP.md) |
| Processing activities (ROPA working register) | PARTIAL | [`DSGVO-REVIEW-REGISTER.md`](DSGVO-REVIEW-REGISTER.md) |
| Legal basis, purpose and consent | OPEN / PARTIAL | [`DSGVO-REVIEW-REGISTER.md`](DSGVO-REVIEW-REGISTER.md); `RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md`; `RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md`; `ANALYSIS-PROCESSING-APPROVAL-PACK.md` |
| Data-subject requests (inspect/export/erasure) | PARTIAL | `RIS_PRIVACY_CAPABILITY_CONTRACT.md`; `USER_PRIVACY_VIEW_SPEC.md`; discovery report |
| Retention/erasure | OPEN | `RIS_PRIVACY_DATA_INVENTORY_V1.md`; `RIS-JOBSEARCH-RETENTION-POLICY-V1.md`; `RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md` |
| TOM | PARTIAL | [`DSGVO-REVIEW-REGISTER.md`](DSGVO-REVIEW-REGISTER.md); code/config evidence linked in discovery |
| Processors/transfers | OPEN | [`DSGVO-REVIEW-REGISTER.md`](DSGVO-REVIEW-REGISTER.md) |
| DPIA pre-screen | OPEN | [`DSGVO-REVIEW-REGISTER.md`](DSGVO-REVIEW-REGISTER.md) |
| Cross-repository contract | PARTIAL | [`XREPO-PRIVACY-CONTRACT.md`](XREPO-PRIVACY-CONTRACT.md) |
| Release acceptance | NO-GO for real data | [`PRIVACY-ACCEPTANCE-GATE.md`](PRIVACY-ACCEPTANCE-GATE.md), [`../reports/RIS-DEV2-PRIVACY-RELEASE-GATE-02.md`](../reports/RIS-DEV2-PRIVACY-RELEASE-GATE-02.md), [`../reports/RIS-PRIVACY-R08-GATE-B-ORCH-01-ABSCHLUSS.md`](../reports/RIS-PRIVACY-R08-GATE-B-ORCH-01-ABSCHLUSS.md) |
| Remediation sequence and tests | PLANNED | [`PRIVACY-REMEDIATION-PLAN.md`](PRIVACY-REMEDIATION-PLAN.md) |
| Final execution report | COMPLETE (documentation scope only) | [`../reports/RIS-DSGVO-COMPLIANCE-01-EXECUTION-REPORT.md`](../reports/RIS-DSGVO-COMPLIANCE-01-EXECUTION-REPORT.md) |
| DSGVO master orchestration status | RIS PRIVACY PROVIDER INTEGRATION READY FOR REVIEW — STOP before implementation | [`DSGVO-MASTER-ORCHESTRATION-STATUS.md`](DSGVO-MASTER-ORCHESTRATION-STATUS.md) |
| DSGVO-02 decisions and XRepo subject identity draft | COMPLETE AS PROPOSAL; approval OPEN | [`DSGVO-02-DECISIONS-AND-CONTRACT.md`](DSGVO-02-DECISIONS-AND-CONTRACT.md) |
| DSGVO-02A technical contract resolution | COMPLETE AS PROPOSAL; no approval or implementation | [`DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md`](DSGVO-02A-TECHNICAL-CONTRACT-REVIEW.md) |
| DSGVO-02B Mays-Orders provider integration alignment | READY FOR REVIEW; RIS documentation only; provider CR drafts unsubmitted | [`DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md`](DSGVO-02B-PROVIDER-INTEGRATION-REVIEW.md) |

## System boundaries and pins

- RIS baseline: `073fb5f5384736b6b6d8f0d1a0b987e4e9ceb070`.
- Integrated Mays-Orders source: `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (unchanged).
- Mays-Jobsearch source reviewed: `origin/main` `c298d223e38407781b4f63426be9f9228ccb4467`.
- No deployed-state proof is implied by source/config/test evidence. Each repository owner must independently confirm current releases and operational controls.

## Status vocabulary

- **VERIFIED** — direct evidence supports the narrow statement, not broader legal or live claims.
- **PARTIAL** — some implementation or test evidence exists; material scope/evidence gaps remain.
- **OPEN** — unresolved, unverified, or requires owner/legal decision.
- **NOT APPLICABLE** — justified as outside the defined processing; record the boundary and rationale. Do not use merely because evidence is missing.

## Review decisions required

Controller/processor roles per purpose; lawful bases and any Article 9 condition; notice and consent validity; retention periods and exceptions; whether DPIA is required; processor/subprocessor terms and international transfers; log/backup erasure and restore policy; DSAR deadlines/identity process; and whether real-data processing is permitted at all. These questions remain for the responsible privacy/legal and service owners.
