# Structured CV Profile Storage — Privacy Draft

**Status:** DRAFT / REVIEW REQUIRED — not a legal approval  
**Purpose proposal:** `cv-builder-profile-storage`  
**Contract:** `docs/contracts/STRUCTURED-CV-PROFILE-V1.md`  
**Date:** 2026-11-12

## 1. Processing description

RIS stores an editable structured CV-builder profile and its 03B import-review
backlog after an explicit user action. It is not a PDF document copy and not a
search profile.

| Data | Purpose | Storage |
|---|---|---|
| Profile name, structured draft, template, version/timestamps | Durable CV editing | DynamoDB `partner-profiles`, new `StructuredCvProfile` item type |
| Review original/corrected text, page/section/reason/status/applied | Restore review after login | Embedded in the profile item for V1 |
| Owner identity | Isolation/authentication | Server-derived keys/fields; never client-provided |
| Technical idempotency/capacity/cursor records | Safe writes and limits | Existing technical stores; no user content |

## 2. Purpose and legal basis

Proposed purpose: **`cv-builder-profile-storage`**.

- Candidate basis for the requested product feature: Art. 6(1)(b) or separate
  Art. 6(1)(a) consent — **legal decision required**.
- CV free text may contain Art. 9 special-category data. An Art. 9 assessment
  and, if applicable, explicit consent under Art. 9(2)(a) must be approved
  before real-user activation.
- The storage purpose does **not** authorize AI-provider transfer, matching,
  profiling or reuse for another product.
- A grant for PDF storage or search-profile storage is **not** reused.
- No automatic legal approval is claimed from a notice version identifier.

## 3. Notice lifecycle

Proposed notice:

```text
version: structured-cv-profile-storage-2026-11-12-draft-1
state: DRAFT
legalApprovalRef: null
```

States follow `CONSENT-V1.md`: `DRAFT → APPROVED → ACTIVE → SUPERSEDED`.
`DRAFT` is not grantable for real-user processing when notice-state enforcement
is active. A newer notice does not silently rewrite an existing grant.

The Jobsearch UI must display the exact notice text and version and record the
displayed external reference separately from the RIS notice version. No
mismatch may be treated as approval.

## 4. Consent operations

| Operation | Behavior |
|---|---|
| Grant | Creates/updates a purpose-specific GRANTED consent; idempotent for same notice |
| Withdraw | Changes to WITHDRAWN; append-only history; no new structured-profile writes |
| Regrant | New grant under an approved notice; does not restore already purged data |
| Create/PATCH | Require active GRANTED consent and accepted notice |
| Read/list | Normal product reads require active consent, subject to legal review |
| Export/Delete | Must remain available for data-subject rights; exact withdrawal grace policy is `REVIEW_REQUIRED` |
| Account erasure | Deletes profile and review sidecar independent of consent state |

Proposed withdrawal behavior: block new writes immediately; mark profile
unavailable for normal product reads; allow export/delete during a
**30-day** grace period, then purge (`REVIEW_REQUIRED`, no invented legal
period).

## 5. Art. 9 assessment

CV content can reveal health, disability, union membership, religion,
nationality/ethnic origin or other sensitive data. Required before real-user
activation:

- identify likely special-category fields/free text;
- define explicit consent/notice wording;
- define minimization and review of free text;
- confirm legal basis and controller/processor roles;
- confirm retention and withdrawal consequences;
- confirm no provider transfer by storage.

## 6. Recipients and transfers

- No AI provider or external model receives data because of this storage
  purpose.
- RIS backend and AWS storage/backup processors only as documented.
- No RIS credential or owner identity is exposed to the browser.
- Jobsearch BFF is a transport boundary; it must not cache CV content beyond
  the active request/session.

## 7. Retention, backups and export

- Active profile: until explicit delete or verified account erasure; no
  indefinite silent retention.
- No TTL for active profiles unless a legally approved retention period exists.
- Backups/PITR/CloudTrail/CloudWatch may retain copies per their own retention;
  application erasure does not synchronously purge them.
- Restore must replay the deletion ledger/erasure intent before promotion.
- Export is a full structured JSON export including review provenance; no PDF
  assumption and no provider data.
- Review items are embedded, so profile deletion cannot leave orphan review
  data in V1.

## 8. Erasure

Add a structured-profile step to the existing `PrivacyErasure`/R08 lifecycle:

1. Resolve only the verified owner.
2. Delete the profile item and embedded review idempotently.
3. Report partial failure and resume; never claim complete while items remain.
4. Include structured profiles in privacy inspect/export categories.
5. Record minimized receipt metadata (IDs/hashes/phase/counts), no CV/review
   text.
6. Account erasure covers this resource; single-profile delete remains
   available.
7. Do not claim physical deletion of provider backups/PITR unless verified.

## 9. Security and logging

- Server-derived owner: tenant, partner, issuer, subject; no email ownership.
- No PII/CV/review text in technical logs, errors, metrics or traces.
- Payload/body limits prevent unbounded storage and accidental exposure.
- Version conflicts fail closed; no last-write-wins.
- Foreign/missing IDs share a 404 shape.
- No browser credential, owner ID or partner ID in responses.

## 10. Open privacy decisions

1. Controller/processor roles and Art. 6 basis.
2. Art. 9 condition and notice wording.
3. Approved retention and withdrawal grace periods.
4. Exact read/export/delete behavior after withdrawal.
5. Backup/PITR and restore-ledger ownership.
6. Capacity limit and whether it affects retention.
7. Privacy inventory and receipt category names.
8. Legal approval reference for the notice.

**This draft does not authorize production storage, consent activation,
Terraform/AWS changes, main merge or deployment.**
