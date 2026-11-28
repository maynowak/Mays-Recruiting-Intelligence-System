# Privacy acceptance gate

**Current verdict: NO-GO for real personal data / no live release approval.** Synthetic-only technical work may proceed under existing authorization. This gate is a checklist, not an automatic approval mechanism.

| Gate | Acceptance evidence | Current status |
|---|---|---|
| G1 — inventory/roles | Signed, complete processing register across enabled deployments and service owners | PARTIAL |
| G2 — legal basis/notices | Legal approval per purpose, Article 9 assessment, notice/version mapping and withdrawal behavior | OPEN |
| G3 — retention | Approved schedule for active stores, logs, queues, backups, receipts and exceptions | OPEN |
| G4 — access/security | Reviewed auth/tenant boundaries, least privilege, secret lifecycle and live config evidence | PARTIAL |
| G5 — rights | Synthetic end-to-end inspect/export/erase including Jobs/Orders, S3 all versions, queue/results and partial outcomes | OPEN |
| G6 — recovery | Approved backup policy and synthetic restore proving deleted subjects do not reappear | OPEN |
| G7 — processors/transfers | Current contracts, active provider map, transfer safeguards and deletion/retention terms | OPEN |
| G8 — DPIA | Documented screening and completed DPIA where required | OPEN |
| G9 — observability | PII/log payload review, retention verification, no secrets/raw CV in logs, DLQ safety | OPEN |
| G10 — release decision | Named human privacy/legal, security and service-owner sign-off tied to exact immutable deployment SHA | NOT GRANTED |

No gate is inferred satisfied from local tests alone. Stop on any unresolved subject-index gap, undeclared recipient, unexplained personal data in logs, unverified backup resurrection risk, secret exposure, or unauthorized scope. A release requires explicit human approval and cannot be automated by CI.
