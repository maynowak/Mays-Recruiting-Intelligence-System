# DSGVO review register (working ROPA / legal / TOM / DPIA register)

**Status:** Working technical inventory; not a signed Article 30 ROPA or legal assessment. Controller must validate completeness, roles, purposes, recipients, deadlines and retention. Source baseline and limitations: [Phase 1 discovery](../reports/RIS-DSGVO-COMPLIANCE-01-PHASE-1-DISCOVERY.md).

## Processing activities

| Activity / categories | Purpose and systems | Candidate basis (NOT DECIDED) | Recipients / boundary | Retention & rights status |
|---|---|---|---|---|
| Account/profile: identifiers, contact, tenant, auth claims | RIS Cognito, UserProfile/DynamoDB | Art. 6(1)(b)/(f) candidate; factual analysis required | RIS; AWS as infrastructure provider | Account/config TTL is not legal approval; Cognito not included in G5 completion. PARTIAL |
| CV intake, parsing, matching and optional durable CV storage; potentially special-category data | Jobsearch browser; RIS document API/S3 and profile metadata; AI/provider paths vary | Contract necessity and/or explicit consent candidate; Article 9 condition and safeguards unresolved | RIS, Jobsearch, configured AI/job providers; map per deployed path | Transient browser and durable RIS storage are distinct purposes; storage consent does not imply AI transfer. Export/erasure incomplete. OPEN |
| Search profiles, ATS profile and job matching | Jobsearch UI/provider; optional RIS Manual/CVSearch/ATS persistence | Art. 6(1)(a)/(b)/(f) candidate, purpose-by-purpose assessment | RIS, Jobsearch, job data providers | Durable profiles have no general TTL; RIS hierarchy deletion incomplete. OPEN |
| Applications, status, notes and follow-up | Jobsearch application tracker and RIS ApplicationV1 interfaces where enabled | Art. 6(1)(b)/(f) candidate; avoid assuming consent is necessary/sufficient | Jobsearch and RIS service boundary; downstream recipients require confirmation | Purpose-specific consent exists in code, but deletion/export and deployed retention evidence are partial. PARTIAL |
| AgentOrders, WorkItems and Results | RIS dispatch/worker; separate Mays-Orders service at pinned version | Depends on requested service and role split; assess per transaction | Mays-Orders/AWS; internal service-to-service interface | Orders subject-index coverage gap; RIS terminal work/results retention unresolved. OPEN |
| Receipts, security/audit and operational logs | RIS privacy journal, CloudWatch, CloudTrail, SQS/DLQ | Art. 6(1)(c)/(f) candidate depending on necessity; minimize content | AWS and authorized operators | Journal disabled by default pending retention; log/DLQ retention not live verified and not subject-erasure based. OPEN |
| Backups, PITR and recovery copies | RIS/AWS storage services | Ancillary security/recovery purpose; legal basis/period to approve | AWS; restore operators | PITR default off in checked-in config; restore reconciliation and expiry not evidenced live. OPEN |

## Consent and notice boundary

Current source separates `application-storage`, `cv-storage`, `search-profile-storage`, and `analysis-processing`. The first three have technical approval references for limited pilots in the RIS consent registry; `analysis-processing` is draft. These records do not establish legal approval for general rollout. Consent must be freely given, specific, informed, purpose-separated and withdrawable where relied upon; check the actual notice version, UI, grant/revocation persistence, and enforcement at the exact deployed Jobsearch and RIS versions. A storage grant is not an AI-processing or provider-transfer grant.

## DSAR operating model (proposed, not an implemented service guarantee)

1. Receive and timestamp request; verify identity using an approved channel without collecting excess identity data.
2. Resolve purposes, controller/service boundary and relevant subject keys; open a tracked case and deadline.
3. Inspect/export from RIS and any authorized processor; separately request Jobsearch/Orders/provider data where applicable. Redact third-party data and secrets.
4. Erasure: determine exceptions and lawful retention; stop new processing, execute idempotent domain actions, record partial blockers, and verify each store. Do not label request complete based only on a receipt.
5. Respond within the legally applicable period, including scope, exclusions, retention/backup caveats and appeal/contact route. Legal owner must confirm deadlines and exceptions.

Current implementation is **PARTIAL**: internal inspect/export and bounded erasure pieces exist; there is no evidence of a complete user-facing, cross-domain DSAR workflow or full export/erasure of all stores.

## TOM evidence matrix

| Control | Status | Evidence boundary / remaining proof |
|---|---|---|
| Authentication, tenant/owner scoping | PARTIAL | RIS JWT/partner context and Orders internal secret gates exist in source/tests; live IAM/API configuration and complete path review needed. |
| Encryption/private document access | PARTIAL | Terraform declares private S3 controls/encryption/versioning and presigned access; live settings and key lifecycle not inspected. |
| Least privilege and secret handling | PARTIAL | Source declares scoped service permissions and internal secret usage; secret rotation/revocation/deployed access must be evidenced per owner. |
| Availability/recovery | OPEN | PITR default false, S3 version recovery and restore reconciliation need approved design and live synthetic restore evidence. |
| Confidentiality/log minimization | OPEN | CloudWatch/CloudTrail/SQS/DLQ contain potential operational metadata; payload minimization and retention need review/test. |
| Erasure and data portability | OPEN | Subject indexing, cross-domain completeness and all-version purge gaps remain. |
| Change management and test | PARTIAL | CI and focused contract/security tests exist; no dedicated complete privacy release gate. See remediation plan. |

## Processor / transfer register

| Provider/boundary | Evidence required before approval | Status |
|---|---|---|
| AWS services used by RIS/Orders | Executed DPA/terms, region, subprocessor list, transfer mechanism, service-specific retention and access roles | OPEN; source region/config is not a contract or live proof |
| Jobsearch hosting, Redis/cache and email services | Current agreements, data locations, access, TTL/deletion and transfer mechanism | OPEN; identify actual enabled providers/environment |
| AI providers (e.g. configured OpenRouter/EdenAI or others) | Per-provider routing, training/retention policy, DPA, region, transfer mechanism, request minimization and user notice | OPEN; no inference from a provider name or code path |
| Job-source/APIs and analytics/diagnostics | Field-level disclosures, retention, onward transfer and processor/controller role | OPEN; confirm enabled integrations and payloads |
| Mays-Orders | Role allocation, contract, region, internal secret lifecycle, subject link and deletion acknowledgment contract | PARTIAL; source pin only, no deployed proof |

## DPIA pre-screen

**Outcome: OPEN — no determination that a DPIA is or is not required.** Screening triggers to assess include CVs and employment decisions, potentially special-category information, systematic profiling/matching, AI processing and multiple recipients. Privacy/legal must document nature, scope, context, purposes, necessity/proportionality, risks, mitigations and consultation decision before any real-data approval. This technical discovery is not a DPIA.

## Explicit legal questions

1. Who is controller/joint controller/processor for each activity and user journey?
2. What Article 6 basis applies to each purpose, and what Article 9(2) condition/safeguards apply to CV-derived special-category data?
3. Is consent necessary, valid, withdrawable and technically enforced for each storage/analysis/transfer purpose?
4. What retention periods, legal holds, limitation periods and backup expiry apply to each record category?
5. Is a DPIA mandatory; are automated-decision/profiling disclosures or human-review rights implicated?
6. Which processors/subprocessors and international transfers are active in each deployment, and which safeguards apply?
7. What DSAR deadlines, identity checks, exemptions and communication templates are approved?
8. What minimal audit/receipt evidence may be retained after erasure and for how long?
