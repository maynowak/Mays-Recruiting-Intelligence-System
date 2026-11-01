# PrivacyReceiptV1 — Retention Decision Record

**Status:** BLOCKED / REVIEW_REQUIRED · **Gate:** R08-POLICY-01
**Date:** 2026-11-01

R08-A1 provides the dedicated table, validated `PrivacyReceiptV1`, conditional
insert/idempotent replay, identity isolation and bounded pagination. The
journal remains disabled by default. This record does not approve a legal
basis or final duration.

| Question | Decision state |
|---|---|
| Why retain? | Candidate: prove a technical operation/user decision and support scoped export, erasure review and reconciliation. REVIEW_REQUIRED. |
| Which events? | Candidate: profile create/update/delete, confirmed CV storage, notice acknowledgement, applicable consent events, erasure request/partial/completed. A2 must bind them to successful operations. |
| Retention clock? | Not approved; candidate clocks are server-confirmed event, request completion or account closure for minimal closure evidence. |
| How long? | No final period. Use the shortest approved evidence period; never indefinite by convenience. |
| May it survive profile deletion? | Only if approved as minimized proof; no CV content, name, filename, email, secret, prompt, S3 key or full profile payload. |
| Does it prove physical deletion? | No. `ERASURE_COMPLETED` requires the approved scope, including S3 versions/markers where applicable, to be verified. |
| Partial deletion? | Use `ERASURE_PARTIALLY_COMPLETED`/operation state; never claim completed while required scope is open. |
| How delete? | Future policy-controlled delete/minimize path. A1 IAM has no `DeleteItem`; no TTL is configured. |
| Production writes? | No: `PRIVACY_RECEIPT_JOURNAL_ENABLED=false`; A2 and policy approval are prerequisites. |

## Minimal contract rules

- `recordedAt` is server-generated; `contentHash` supports idempotency only.
- Notice version/digest is recorded only for an actual notice event.
- `legalBasisRef` and `retentionPolicyRef` are references, not legal findings;
  `REVIEW_REQUIRED` remains explicit.
- `CV_STORAGE_CONFIRMED` follows verified object storage and status transition.
- `PROFILE_DELETED` proves only the recorded profile operation.
- `ERASURE_COMPLETED` is forbidden while S3, backup, Cognito or other required
  scope remains unresolved.
- No raw CV data or secrets enter a receipt.

Before enabling writes, approve purpose/basis, event allow-list, evidence
threshold, clock/duration, erasure treatment, deletion authority, user notice,
export behavior and backup/restore reconciliation. Until then R08-A2 is
**BLOCKED**.
