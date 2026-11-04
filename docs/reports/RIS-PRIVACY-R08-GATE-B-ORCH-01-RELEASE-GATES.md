# RIS-PRIVACY-R08-GATE-B-ORCH-01 — Release Gates

| Gate | Anforderung | Code-Evidence | Test-Evidence | Legal/Policy | Live-Evidence | Status | Blocker | Owner |
|---|---|---|---|---|---|---|---|---|
| RG-09 | Privacy-safe ApplicationV1 metrics | Route, JWT context, owner scope, aggregate-only response, no-store | Application/API/privacy suite PASS | Basis, notice and retention REVIEW REQUIRED | None current | PARTIAL / NO-GO | Legal/purpose and live HTTP open | Privacy + RIS-DEV |
| RG-10 | PITR/backup/restore/erasure reconciliation | Contracts and synthetic R08-C only; no PITR/deletion ledger implementation | Synthetic erasure PASS; restore tests absent | Receipt/backup retention unresolved | None current | BLOCKED / RED | PITR, ledger, restore replay, version purge | Platform + Privacy |
| RG-11 | SQS release and erasure safety | External Mays-Orders plan evidence only; no RIS mutation | Local historical evidence only | PII/retention review open | No current live evidence | BLOCKED / NO-GO | DLQ/redrive and stale-message erasure safety | Mays-Orders + RIS-DEV |
| R08-A | Receipt journal | Repository/infrastructure, writes fail-closed | A1 local tests PASS | Retention/legal approval absent | Not deployed/currently verified | PARTIAL / BLOCKED | A2 integration and retention | Privacy + RIS-DEV |
| R08-B | Inspect/export | Read-only routes and partial-state contracts | B1/B2A local tests PASS | Export/notice policy open | Persistence/live HTTP absent | VERIFIED LOCAL / LIVE OPEN | Live stores and receipt availability | Privacy API + RIS-DEV |
| R08-C | Erasure | Operation/checkpoint/profile/document contracts | C1 synthetic local tests PASS | Retention, legal holds and receipt treatment open | Real AWS blocked | VERIFIED LOCAL / PRODUCTION BLOCKED | Fencing, tickets, IAM/Object Lock, restore | Privacy + Platform |
| OI-07 | Session transfer | No route | No test | Jobsearch ownership unresolved | None | OPEN | Preview/confirm/no-loss migration | Jobsearch + RIS-DEV |
| OI-08 | Identity/delegation | Existing boundary only | Local security tests | BFF/DPA role open | Auth HTTP absent | OPEN | Server-side delegation proof | RIS-DEV + Security |
| OI-09 | Retention/delete governance | Local delete semantics only | Local erasure tests | No approved periods | Backup/PITR absent | OPEN | Legal/backup decision | Privacy/Legal |
| OI-10 | Live readiness | Not deployed by this branch | Local only | Approval required | No current `ris-dev` evidence | OPEN | Authorized package/plan/live matrix | RIS-DEV |
| Plan readiness | Safe offline planning | Terraform source reviewed; no Apply | Validate was previously PASS; current invocation environment-blocked | Apply not authorized | No live plan | BLOCKED | State/ownership/PITR/live gates | Platform |
| Deployment | Production or `ris-dev` apply | No activation | N/A | Gate B NO-GO | None | NO-GO | Multiple mandatory gates | Release owner |

**Gate B remains NO-GO for Apply.**
