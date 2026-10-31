# PrivacyReceiptV1 — Canonical Processing-Evidence Contract

Status: **SPECIFIED / CONTRACT-ONLY**. No storage, no API, no erasure in
R08-G0. Implementation module:
`agents/ecosystem/privacy_receipt.py`; tests:
`tests/test_privacy_receipt_contract.py`.

## Purpose

A receipt is a minimal, server-side record of a privacy-relevant event. It is
**not** a legal opinion and **not** a claim that an external provider or a
backup was erased. It records what RIS can evidence at the stated
`evidenceLevel`.

## Fields

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | integer | exactly `1` |
| `receiptId` | string | server-generated opaque ID |
| `subjectRef` | string | verified Cognito `sub` (pseudonymous, no email) |
| `tenantRef` | string | verified tenant claim |
| `partnerApplicationRef` | string | verified partner application |
| `issuerRef` | string | verified JWT issuer |
| `eventType` | enum | see below |
| `purpose` | enum | `authentication`, `cv_processing`, `profile_management`, `job_matching`, `ai_processing`, `privacy_request`, `audit`, `service_operation` |
| `legalBasisRef` | string | reference, never free legal prose; `REVIEW_REQUIRED` is explicit |
| `privacyNoticeVersion` | string / null | required for notice/consent events |
| `privacyNoticeDigest` | sha256 / null | digest of the exact notice text |
| `dataCategories` | enum array | minimal categories, no raw data |
| `processingDomain` | enum | `ris`, `jobsearch`, `mays_orders`, `ai_provider`, `browser`, `aws_platform` |
| `operationRef` | string | links related events/operations |
| `recordedAt` | ISO-8601 with timezone | server clock; future > 5 min rejected |
| `status` | enum | `requested`, `completed`, `partially_completed`, `blocked`, `failed` |
| `retentionPolicyRef` | string | reference; `REVIEW_REQUIRED` allowed |
| `evidenceLevel` | enum | `server_verified`, `third_party_confirmed`, `client_reported`, `requested`, `not_provable` |

## Events and status

| Event | Required status | Evidence restriction |
|---|---|---|
| `PRIVACY_NOTICE_PRESENTED` | completed | server-verified presentation |
| `CONSENT_GRANTED` / `CONSENT_WITHDRAWN` | completed | server-verified event; legal validity still REVIEW REQUIRED |
| `CV_STORAGE_CONFIRMED` | completed | server-verified storage |
| `PROFILE_CREATED` / `PROFILE_UPDATED` | completed | server-verified write |
| `AI_TRANSFER_REQUESTED` | requested | client_reported/requested/server_verified |
| `AI_TRANSFER_CONFIRMED` | completed | **only** third_party_confirmed or server_verified |
| `DATA_EXPORT_COMPLETED` | completed | server-verified export |
| `ERASURE_REQUESTED` | requested | request evidence only |
| `ERASURE_PARTIALLY_COMPLETED` | partially_completed | server_verified/third_party_confirmed |
| `ERASURE_COMPLETED` | completed | server_verified/third_party_confirmed |

`AI_TRANSFER_CONFIRMED` and `ERASURE_COMPLETED` cannot be based on a browser
event, a button click or a client assertion alone. A client-side event may be
recorded as `client_reported`; it is never promoted to a verified fact.

## Forbidden content

Receipts must never contain:

- CV text/content, file bodies, raw CVs
- model prompts, prompts, model responses/explanations
- Authorization headers, bearer tokens, access/ID/refresh tokens
- Presigned URLs or `X-Amz-Signature`
- secrets, passwords, private keys, AWS access keys
- raw evidence blobs

The validator rejects forbidden field names and values recursively and caps a
receipt at 8 KiB. No receipt journal may store these values either.

## Identity binding

A receipt is valid only for the exact verified context:

`receipt.subjectRef == context.user_id`, plus tenant, partner application and
issuer. A receipt from user A must not be readable by user B; a receipt from
tenant/partner/issuer A must not be accepted for B. Cursor-style opaque IDs
are not authorization; every read re-checks the normal RIS auth boundary.

## Legal/consent separation

- `CONSENT_GRANTED` records that the server received and verified a consent
  action. It does **not** establish that the consent is legally valid.
- `legalBasisRef` is a reference; `REVIEW_REQUIRED` is the accepted placeholder
  until legal review decides the basis.
- A technical button click or general terms acceptance is not automatically a
  GDPR consent. The notice version/digest identifies what was shown; the
  legal assessment remains REVIEW REQUIRED.

## Storage and API (later gates)

R08-A will define append-only storage, write points, pagination, access and
retention. R08-G0 defines no table and no endpoint. A receipt is never
rewritten in place; corrections are new events with a reference to the prior
`operationRef`.

## Minimum read model

A user-facing read later returns only:

- receipt metadata as above
- human-readable event labels
- notice version/digest references (not the full notice text)
- operation status and limitations

No CV text, prompts, tokens or raw provider payloads.
