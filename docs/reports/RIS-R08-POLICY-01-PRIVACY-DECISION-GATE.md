# RIS-R08-POLICY-01 — Privacy & Retention Decision Gate

**Status:** ANALYSIS COMPLETE / POLICY NOT APPROVED / PRODUCTION BLOCKED
**Date:** 2026-11-01

## Baseline and scope

| Check | Result |
|---|---|
| RIS | `feature/ris-partner-profile-persistence-v1` @ `d087cc7` |
| RIS status | tracked clean; 39 untracked preserved |
| Jobsearch | remote `main` `c787feaf99a604312a2c1f2d28c6e655823856ff`, read-only |
| Changes | no Jobsearch/Vercel/Orders changes; no AWS/Apply/Destroy |
| Receipt flag | remains `PRIVACY_RECEIPT_JOURNAL_ENABLED=false` |

Inputs were R08-G0, R08-A1, R08-JM-G0, the existing privacy documents,
`PrivacyReceiptV1`, `privacy_receipt_journal.py`, profile/CV handlers, G5
erasure, Terraform/S3 configuration and the Jobsearch contract/privacy draft.

## Processing and legal decisions

P-01 through P-10 are documented in
`RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md`. Durable account storage is a
separate explicit action. Browser CV extraction and optional AI processing are
not silently included. No blanket Art. 6 basis is assigned: Art. 6(1)(b),
(a), (f) and (c) are candidates only when their factual conditions apply.

CVs can contain special-category data under Art. 9, including health,
political, religious, union or biometric information. The current contract
does not classify/remove all such content. A production feature therefore
requires an explicit Art.-9 assessment, specific information, minimization
and any required explicit condition/consent. No production approval is
claimed.

## Retention decision

`RIS-JOBSEARCH-RETENTION-POLICY-V1.md` covers UserProfile, CV metadata and
PDFs, S3 versions/markers, all profile types, receipts, idempotency, cursors,
counters/guards, logs, CloudTrail and backups.

Observed technical facts:

- cursors: 15 minutes with explicit expiry;
- idempotency records: 24 hours;
- profiles/counters/guards: no general TTL;
- receipt table: no TTL by design;
- S3 versioning enabled, no lifecycle rule observed;
- backup/PITR and log periods are not proven by application erasure.

No final duration is approved. Receipt retention is separate from CV
retention and cannot be indefinite by convenience.

## Receipt policy

`RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md` preserves the A1 contract.
Receipts document technical events or user decisions; they do not prove the
legal basis, provider deletion or complete physical deletion. `CV_STORAGE_CONFIRMED`
requires verified storage. `ERASURE_COMPLETED` is forbidden while an approved
S3-version purge or other required scope is unresolved.

## Open dependencies and P0 finding

- G5 does not cover partner profiles and all descendants.
- Current S3 deletion does not prove removal of versions/delete markers.
- Cursor/idempotency/capacity/lifecycle cleanup is incomplete.
- Cognito deletion/session revocation is separate.
- G5 work cancellation is not complete paginated proof for every store.
- Receipt survival/minimization during erasure is undecided.
- Backup/PITR restore reconciliation is not implemented.
- F-5 legacy counter reconciliation remains partial.
- Agent CANCELLED/FAILED/COMPLETED retention remains outside this gate.
- R08-C0A now defines an execution-neutral operation/checkpoint contract;
  operation/checkpoint retention remains REVIEW_REQUIRED and no erasure
  implementation is activated.

R08-JM-G0 finding F-JM-13 remains open: `POST /me/documents` returns an
internal S3 `key` and uses `docId`/`expiresIn`, while OpenAPI says
`documentId`/`expiresAt` and Jobsearch v1 forbids S3 keys. R08-P1-1 must close
this before cloud/product release. No fix is made here.

## Gate result

| Area | Result |
|---|---|
| Processing purposes | PROPOSED |
| Legal bases | REVIEW_REQUIRED per purpose |
| Art. 9 assessment | REVIEW_REQUIRED; no production approval |
| RetentionPolicyV1 | PROPOSED; no final durations |
| Receipt retention | BLOCKED; no TTL/no writes |
| Privacy notice | DRAFT only, not publishable |
| P0 document API finding | OPEN; assigned to R08-P1-1 |
| G5 erasure dependencies | OPEN/BLOCKED |
| R08-P1-1 | **BLOCKED** |
| R08-A2 policy enablement | **BLOCKED / REVIEW_REQUIRED** |
| Release/deployment | **NOT DEPLOYED** |

## Evidence

- `docs/privacy/RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md`
- `docs/privacy/RIS-JOBSEARCH-RETENTION-POLICY-V1.md`
- `docs/privacy/RIS-JOBSEARCH-PRIVACY-NOTICE-DRAFT-V1.md`
- `docs/privacy/RIS-PRIVACY-RECEIPT-RETENTION-DECISION.md`
- `docs/reports/RIS-JOBSEARCH-V1-CONTRACT-MATRIX.md`
- `docs/privacy/PRIVACY_RECEIPT_JOURNAL.md`
- `docs/privacy/RIS_PRIVACY_DATA_INVENTORY_V1.md`
- `terraform/modules/documents/main.tf`
- `lambda/handler.py`

**Conclusion:** R08-POLICY-01 is complete as a technically evidenced decision
package, not as legal approval. R08-A2/B/C and R07-B remain blocked.
