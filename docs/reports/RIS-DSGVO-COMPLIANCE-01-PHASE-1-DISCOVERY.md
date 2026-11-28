# RIS-DSGVO-COMPLIANCE-01 — Phase 1 Discovery

**Status:** COMPLETE (repository/source discovery only; review required)
**Date:** 2026-11-28
**RIS branch/base:** `feature/ris-dsgvo-compliance-01` / `073fb5f5384736b6b6d8f0d1a0b987e4e9ceb070`
**Mays-Orders evidence pin:** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Mays-Jobsearch source reviewed:** `origin/main` `c298d223e38407781b4f63426be9f9228ccb4467`

## Scope and method

Read-only inspection of repository code, Terraform declarations, tests and existing reports. No tests were rerun for this discovery; no AWS/API calls, deployment, Terraform operation, queue mutation, or changes in sister repositories were made. These findings describe checked-in source and historical/local test evidence, not current deployed configuration or legal compliance. Synthetic data only for any later testing.

## Repository and evidence boundary

| Boundary | Verified source | What this establishes | Does not establish |
|---|---|---|---|
| RIS | requested baseline above; runtime/config/tests and docs | checked-in route, repository, Terraform and test contracts | live AWS state, deployed behavior, approved legal basis/retention |
| Mays-Orders | exact integrated source pin above | internal inspect/export/erase implementation and tests at that pin | currently deployed stack, end-to-end RIS invocation, complete subject coverage |
| Mays-Jobsearch | fetched `origin/main` above (not local feature branch) | current frontend/serverless code and consent flow as source | production deployment/configuration or provider-side deletion |

RIS `docs/reports/RIS-DEV2-PRIVACY-RELEASE-GATE-02.md` and the privacy sections of `docs/integration/RIS-MAYS-ORDERS-INTEGRATION-DOSSIER.md` were treated as required historical evidence, reconciled against current source. Older inventory statuses are not accepted as proof where source/config differs.

## Integrated data paths and findings

| Data/process | Source-level path and ownership | Status | Evidence / limitation |
|---|---|---|---|
| Identity and profile | Cognito verified identity → RIS Lambda; UserProfile in RIS DynamoDB | PARTIAL | `lambda/handler.py`, G5 erasure in `agents/ecosystem/privacy_erasure.py`; account/Cognito deletion is not completed by G5. |
| CV upload/storage | Jobsearch browser PDF parsing; optional RIS durable document upload uses tenant/user-scoped S3 object and RIS profile metadata | PARTIAL | `lambda/documents.py`, `terraform/modules/documents/main.tf`, profile repositories/tests. S3 versioning is declared, lifecycle purge is absent; G5 current-object delete is not all-version purge. |
| Search/ATS profiles | Jobsearch browser processing and optional RIS Manual/CVSearch/ATS profile persistence in `partner-profiles` | PARTIAL | `jobsearch/partner_profile_repository.py`, contract and focused tests; resource rows have no general TTL and G5 does not cover the full hierarchy. |
| Applications/ATS tracker | Jobsearch application API/storage consent path; RIS ApplicationV1 and job/application metadata have separate RIS ownership/interfaces | PARTIAL | RIS ApplicationV1 privacy matrix/release reports and `jobsearch/application_*` plus consent modules. Purpose-specific storage consent exists in source; broader purpose, retention, deployment and legal scope need owner/legal confirmation. |
| Jobsearch transient AI/search | Jobsearch `POST /api/profile` sends CV text to server for each request; docs state no server-side CV-profile cache and browser-session hash only. AI/provider and job-source integrations are separate transfers. | PARTIAL | Jobsearch `AGENTS.md`, `src/api.ts`, current Main source. No provider retention/deletion evidence here; operational logs/cache/processor terms require verification. |
| Consent | RIS partner consent endpoints and server-derived identity; purpose registry includes application-storage, cv-storage, search-profile-storage, analysis-processing. Jobsearch Main includes consent UI/serverless routes and storage semantics. | PARTIAL | RIS `lambda/handler.py`, `jobsearch/consent_contract.py`, repository tests, Jobsearch `api/` and `src/`. Checked-in notice/approval labels do not constitute general legal approval; analysis-processing remains draft; verify matching current Jobsearch route/purpose and rollout configuration before real use. |
| RIS WorkItems/results | API → WorkItem/SQS → worker/agent → DynamoDB; order/result correlation and result transport may include subject-linked metadata/payload | PARTIAL | runtime pipeline, Terraform queue config and R08 reports. G5 cancels nonterminal work; terminal payloads may remain under policy/TTL. No subject-complete export/erasure proof. |
| Mays-Orders AgentOrders | RIS dispatch → pinned Orders service; internal privacy direct-Lambda actions inspect/export/erase protected by `PRIVACY_INTERNAL_SECRET` | PARTIAL | pinned `lambda/src/index.py`, `order_service.py` and `lambda/tests`. Existing privacy methods query the privacy GSI, but RIS-created AgentOrders lack `gsi2pk`/subject linkage; embedded `agentOrder` anonymization is incomplete. Secret protection exists in source, but rotation/revocation and deployed secret controls are not proven by RIS discovery. |
| Logs, DLQ, audit | RIS Lambda/CloudWatch/CloudTrail and SQS/DLQ retain operational/error payloads by declared settings | PARTIAL | Terraform defaults include 14-day Lambda log retention and 14-day SQS retention; CloudTrail and CloudWatch settings vary by module. Retention config is not live-state proof; no subject-oriented log erasure or PII-free guarantee proven. DLQ/redrive is explicitly outside this work. |
| Backups/PITR/restore | DynamoDB recovery/PITR option and S3 object versioning; restore reconciliation contracts/reports | OPEN | `r08_pitr_enabled=false` default; no live AWS read. S3 old versions persist without lifecycle. Deletion ledger durability, restore replay and no-resurrection are not production-verified. |
| Privacy receipts / DSAR | internal receipt repository and read-only inspect/export contracts; existing G5 erasure route; resumable profile-only executor | PARTIAL | receipt writes default fail-closed; legal retention unresolved. `privacy_profile_erasure.py` is DynamoDB-only and cannot delete S3 or mark complete. User-facing full export/erasure and cross-domain completion are not established. |

## Required gap register

| Requirement | Status | Evidence-backed conclusion |
|---|---|---|
| Subject index across RIS → Orders | OPEN | Orders privacy lookup depends on `gsi2pk`; RIS dispatch test explicitly asserts no `gsi2pk` on stored AgentOrder. Existing Orders privacy functions therefore do not prove reachability of all RIS-originated orders. |
| Complete export | PARTIAL | RIS and Orders have internal/local export paths, but index coverage, all stores, browser-side data, log/backup and provider coverage are incomplete. |
| Complete erasure/anonymization | OPEN | G5 is ordered but bounded; partner profile executor is profile-only; S3 historical versions, Cognito, Jobsearch, Orders linkage, logs/backups and terminal results need explicit handling/evidence. |
| Embedded AgentOrder minimization | OPEN | At the Orders pin the operational consumer retains an internal AgentOrder copy; privacy export projection omits internal fields, but erase does not establish complete erasure of all embedded personal fields. |
| Secret lifecycle | PARTIAL | Orders internal calls fail closed on secret auth and infrastructure includes secret resources; rotation/revocation evidence exists in separate Orders branch history, not verified as deployed behavior for this pin. |
| Legal basis, Article 9, role allocation, retention, notices/transfers | OPEN | Technical notice registries and historical limited-pilot approvals are not a legal assessment for the complete processing landscape or general rollout. |
| Live configuration/deployment/restore | OPEN | This phase used no AWS reads; source configuration and historical test evidence cannot prove live state. |

## Older privacy work and reconciliation

Relevant branch/history families were inventoried: RIS R08 orchestration, structured-CV privacy approval, consent deployment/recovery, XRepo consent contract, Jobsearch/RIS privacy alignment, and Orders RC4/KMS privacy-retention. They are historical evidence, not current deployment proof. The R08 Gate-B completion report says privacy readiness is NO, legal/retention/erasure gates remain open and APPLY is unauthorized. Gate-02's synthetic `ris-dev2` verdict is narrowly bounded and does not grant approval for real personal data. The current Jobsearch Main is newer than several handoffs: its purpose-specific consent implementation supersedes claims that no consent API exists, but does not close legal, retention, full DSAR, or deployment gaps.

## Stop conditions

No runtime code or module pin changed. No Terraform Apply, AWS deployment/read, queue redrive, Main merge, or automatic real-data approval. Phase 1 completion means discovery artifacts only; remediation and live release remain explicitly out of scope.
