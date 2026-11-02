# ApplicationV1 — Datenschutzmatrix und Datenfluss

| Data element | Purpose | Required | Source | Storage | Retention decision |
|---|---|---:|---|---|---|
| application/job identifiers | application tracking | yes | Jobsearch/client | DynamoDB metadata | **APPROVAL REQUIRED** |
| status/timestamps/history metadata | lifecycle/audit | yes | server/client action | DynamoDB | **APPROVAL REQUIRED** |
| profile reference/version | link to existing RIS profile | optional | existing profile | reference only | existing profile policy |
| CV reference/version | link to existing CV metadata | optional | existing CV repository | reference only | existing CV policy |
| cover-letter text/version | user-managed application draft | optional | explicit user action | DynamoDB | **APPROVAL REQUIRED** |
| CV raw bytes | document processing | no in application table | existing document flow | existing S3 lifecycle | existing document policy |
| tokens/credentials | authentication/integration | never | JWT/partner boundary | never persisted | not applicable |

## Processing purposes

1. Maintain an authenticated user's application drafts and explicit lifecycle
   status.
2. Provide user-scoped access, correction, export and deletion.
3. Preserve minimal operational history needed to make concurrent updates and
   erasure resumable.

Recruitment decisions, automated scoring, model invocation and employer-side
processing are out of scope for this persistence feature.

## Legal and risk gates

The implementation deliberately does **not** choose a legal basis or retention
period. Product/privacy approval is required for:

- legal basis per purpose and jurisdiction;
- draft, submitted, withdrawn and archived retention periods;
- backup expiry and deletion semantics;
- whether cover letters or job metadata can contain special-category data;
- DPIA necessity and controller/processor allocation with Jobsearch and
  external partners.

Until approved, the feature must use explicit user action, data minimisation,
tenant/partner isolation, no model calls, and no activation of global erasure
flags.

## Erasure and backup boundary

Application records participate in the existing resumable privacy operation.
The application erasure phase is checkpointed and idempotent; S3 document
versions are delegated to the existing document erasure executor. A successful
delete response is never issued while a required phase remains pending.

DynamoDB point-in-time recovery/backups are an operational recovery mechanism,
not a retention decision. Backup expiry and legal hold behavior require an
explicit approved runbook before deployment.
