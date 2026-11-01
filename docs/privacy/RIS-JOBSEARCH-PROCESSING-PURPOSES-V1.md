# RIS Jobsearch Profile Storage — Processing Purposes v1

**Status:** PROPOSED / REVIEW_REQUIRED — not a legal approval
**Gate:** R08-POLICY-01 · **Date:** 2026-11-01

This matrix separates durable RIS account storage from browser/session CV
processing and optional AI analysis. “In meinem Konto speichern” is an
explicit product action, not by itself proof of Art. 7 consent.

| ID | Purpose / data | Candidate basis | Systems / location | Retention candidate | Deletion / evidence | Status |
|---|---|---|---|---|---|---|
| P-01 | Account and profile administration | Art. 6(1)(b) candidate; Art. 6(1)(f) security | Cognito; DynamoDB `user-profile` | Account lifetime, then approved closure period | Account closure; server-verified delete evidence | REVIEW_REQUIRED |
| P-02 | First name, last name, nickname, email | Art. 6(1)(b) for requested account service; Art. 6(1)(a) only for an additional optional use | Cognito/RIS; notification provider only if enabled | While account/purpose exists | Field correction/delete; verified result | REVIEW_REQUIRED |
| P-03 | Voluntary selected CV PDF storage | Art. 6(1)(b) candidate or separate Art. 6(1)(a); Art. 9 assessment required | RIS/S3, AWS | Purpose-based period after confirmed upload | Version-aware deletion and verification | BLOCKED |
| P-04 | CV metadata and document reference | Same basis as P-03; metadata remains personal data | DynamoDB `partner-profiles`; S3 reference | With linked CV; orphan period undecided | Parent-aware delete/reconciliation | BLOCKED |
| P-05 | Manual search profiles | Art. 6(1)(b) candidate; separate consent only if designed | DynamoDB `partner-profiles` | Until user deletion/purpose end | Conditional delete; receipt only after A2 | REVIEW_REQUIRED |
| P-06 | CV-based search profiles | Art. 6(1)(b) candidate, dependent on selected CV | DynamoDB `partner-profiles` | With linked CV and purpose | Parent-aware delete; no orphan | REVIEW_REQUIRED |
| P-07 | ATS variants and restricted criteria | Art. 6(1)(b) candidate; Art. 6(1)(f) only for narrow integrity needs | DynamoDB `partner-profiles` | With parent purpose | Child-first guarded delete | REVIEW_REQUIRED |
| P-08 | Idempotency, cursors, capacity and integrity guards | Art. 6(1)(b) / 6(1)(f) only as technically necessary | DynamoDB technical items | Cursor 15 min; idempotency 24 h; counters/guards until end | TTL/explicit cleanup; query evidence | TECHNICALLY PARTIAL |
| P-09 | Privacy receipts for technical events/decisions | Art. 6(1)(c) only if a real duty applies; otherwise 6(1)(f) or 6(1)(b) candidate | Dedicated `privacy-receipts` table | Separate approved evidence period; never indefinite by convenience | Policy delete/minimize; minimal proof | BLOCKED |
| P-10 | Access, export and erasure handling | Art. 6(1)(c) where applicable; otherwise service/security basis | RIS APIs, DynamoDB, S3, Cognito | Only as long as needed to prove handling | Scoped operation evidence | OPEN |

## Required legal decisions

- Determine controller/processor roles and the Art. 6 basis per purpose.
- Assess Art. 9 conditions for sensitive CV content; no general storage
  approval is possible without this assessment.
- Decide whether storage is a requested contractual feature or consent-based
  option. Storage is not automatically consent to AI/provider processing.
- Approve recipients, transfers, notice wording, retention clocks and
  deletion exceptions.

Browser PDF extraction and `/api/profile` AI processing remain separate from
durable RIS storage. Session state is not a durable RIS resource and is not
automatically migrated. All unresolved items are **REVIEW_REQUIRED**.
