# APPLICATION-STORAGE-1.0 — NOTICE MAPPING

**Status:** `PROPOSED — NOT APPROVED`
**Date:** 2026-11-07
**RIS branch:** `feature/jm-ris-storage-activation-01`
**Jobsearch text commit:** `5ac025f` (v4, read-only reference); `9eecf83`
(v3), `47f73c4` (v2) and `2b4b520` (v1), all superseded
**Purpose:** document the exact identity of the ApplicationV1 consent-text
candidate and state, explicitly, that it is **not** mapped to RIS notice
`1.0` until an operator/legal decision records it.

> This document does not approve text, does not set `legalApprovalRef`, and
> does not change the notice lifecycle. RIS notice `application-storage/1.0`
> remains `DRAFT`.

---

## 1. Exact identifiers

| Field | RIS side | Jobsearch side (current) |
| --- | --- | --- |
| Purpose | `application-storage` | `application-storage` |
| Notice / text version | `1.0` | `application-storage-consent-2026-11-07-v4` |
| Text SHA-256 | — (RIS stores no text bytes) | `8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7` |
| Lifecycle state | `DRAFT` | `DRAFT` |
| `legalApprovalRef` | `null` | n/a |
| Mapping | **none** | **none** |

v4 adds an explicit Art. 9(2)(a) special-category consent paragraph
(including **Sexualleben und sexuelle Orientierung**, voluntary, no
self-categorisation, no automatic gender/orientation inference) and the stable
category set (9 codes):

`health`, `religious_or_philosophical_beliefs`, `trade_union_membership`,
`political_opinions`, `sexual_orientation`, `sex_life`, `biometric_data`,
`genetic_data`, `racial_or_ethnic_origin`.

Historical candidates (kept for audit traceability, never mapped):

| Version | SHA-256 | Jobsearch state | RIS external ref |
| --- | --- | --- | --- |
| `application-storage-consent-2026-11-07-v3` | `696f9e66d8098b2dce56a93418ba598145b669934662e2b52d9a332731517668` | `DRAFT` (superseded by v4) | `DRAFT`, `noticeVersion: None`, `supersededBy: ...v4` |
| `application-storage-consent-2026-11-07-v2` | `232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca` | `DRAFT` (superseded by v3) | `DRAFT`, `noticeVersion: None`, `supersededBy: ...v3` |
| `application-storage-consent-2026-11-07-v1` | `2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953` | `DRAFT` (superseded by v2) | `DRAFT`, `noticeVersion: None`, `supersededBy: ...v2` |
| `2026-11-04-draft-1` | — | `DRAFT` | `DRAFT`, `noticeVersion: None` |

Historical versions are deliberately kept at `noticeState: DRAFT`, **not**
`SUPERSEDED`: `SUPERSEDED` implies the version was approved at some point,
which none of them was. `supersededBy` records the replacement without
implying approval.

## 2. External reference registered in RIS

`jobsearch/consent_contract.py` `EXTERNAL_NOTICE_REFS["application-storage"]`:

```python
"application-storage-consent-2026-11-07-v4": {   # current candidate
    "source": "mays-jobsearch",
    "noticeState": NOTICE_DRAFT,
    "noticeVersion": None,  # no equivalence until separately approved
    "textSha256": (
        "8722aed9fa78e5ee49c2b5e5a031bfd53a7109bf625dfb0e0c99743fd82443c7"
    ),
},
"application-storage-consent-2026-11-07-v3": {   # historical, superseded
    "source": "mays-jobsearch",
    "noticeState": NOTICE_DRAFT,
    "noticeVersion": None,
    "textSha256": (
        "696f9e66d8098b2dce56a93418ba598145b669934662e2b52d9a332731517668"
    ),
    "supersededBy": "application-storage-consent-2026-11-07-v4",
},
"application-storage-consent-2026-11-07-v2": {   # historical, superseded
    "source": "mays-jobsearch",
    "noticeState": NOTICE_DRAFT,
    "noticeVersion": None,
    "textSha256": (
        "232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca"
    ),
    "supersededBy": "application-storage-consent-2026-11-07-v3",
},
"application-storage-consent-2026-11-07-v1": {   # historical, superseded
    "source": "mays-jobsearch",
    "noticeState": NOTICE_DRAFT,
    "noticeVersion": None,
    "textSha256": (
        "2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953"
    ),
    "supersededBy": "application-storage-consent-2026-11-07-v2",
},
```

Meaning:

- the texts are **known** to RIS (source, state and exact hashes are visible in
  the partner catalogue response under `externalRefs`);
- none is accepted as a `noticeVersion` (`422 INVALID_NOTICE_VERSION`);
- none is equivalent to RIS `1.0`; `noticeVersion` stays `None`.

Each hash pins the exact text. It is computed over
`APPLICATION_STORAGE_CONSENT_PARAGRAPHS.join("\n\n")` (UTF-8) and is asserted
by the Jobsearch test `src/lib/storageConsent.test.ts`; the BFF pins the same
value in `api/_lib/ris/consentText.mjs`. Historical hashes must never be
reused for new text.

### 2.1 Stored grant proof

A v4 grant stores, on the current row and every append-only history event:

| Field | Meaning |
| --- | --- |
| `specialCategoriesConsent` | explicit Art. 9 consent boolean |
| `specialCategories` | non-empty allowed subset, canonical order, only when consent is true |
| `externalTextVersion` | known partner text version (`...v4`) |
| `externalTextSha256` | exact SHA-256 pin |

The backend rejects true consent without categories, categories without
consent, unknown/duplicate categories, unknown external text versions, partial
pairs and hash mismatches. An explicit Art. 9 consent additionally requires the
**current Art. 9-capable text** (`...-v4` and its exact hash):

- missing text pair → `422 EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES`;
- historical text (for example `...-v2`) → `422 EXTERNAL_TEXT_NOT_ART9`.

A non-Art. 9 grant may still carry a historical text for traceability (or no
text at all). A repeat with the same proof is idempotent; a different valid
text or category scope for an existing grant returns `409 RECONSENT_REQUIRED`
and never rewrites the stored proof. Withdrawal preserves the proof.

## 3. Lifecycle states

| State | Meaning | New grants (RIS, enforced) |
| --- | --- | --- |
| `DRAFT` | text exists, not legally approved | **no** (`422 NOTICE_NOT_ACTIVE`) |
| `APPROVED` | legally approved, not yet rolled out | yes, if `noticeApproved` and `acceptedForNewGrant` are true |
| `ACTIVE` | approved and offered to new users | yes, if both flags are true |
| `SUPERSEDED` | replaced; existing grants stay valid | no |

Both the RIS notice and the Jobsearch text are currently `DRAFT`. A hash match
or a rename does **not** change the state.

## 4. Proposed mapping (requires approval)

The mapping below is a **proposal**, not a fact:

| Step | Proposed action | Required decision |
| --- | --- | --- |
| 1 | Treat `application-storage-consent-2026-11-07-v4` (hash `8722…43c7`) as the text for RIS `application-storage/1.0` | Operator/legal approval of the exact text |
| 2 | Record the approval as a real `legalApprovalRef` (record ID, owner, date, approving body) | Operator/legal |
| 3 | Set `NOTICE_REGISTRY["application-storage"]["1.0"]` to `APPROVED` or `ACTIVE` with that ref | Operator change + new Lambda bundle |
| 4 | Keep the Jobsearch text state `DRAFT` until its own mapping is approved; then set the server mapping (`RIS_CONSENT_TEXT_STATE=APPROVED`) | Operator change in the preview environment |
| 5 | Change `EXTERNAL_NOTICE_REFS[...]["noticeVersion"]` from `None` to `"1.0"` only after steps 1–3 | Separate documented decision |

Until steps 1–5 are recorded:

- RIS notice `1.0` stays `DRAFT`, `legalApprovalRef = null`;
- the external ref stays `noticeVersion: None`;
- new grants for pilot identities are rejected by the scoped notice gate;
- no production activation may rely on this document.

## 5. Verification

- `tests/test_consent_pilot_allowlist.py` — pilot scope, effective gates,
  repository `enforce_notice_state`, ACTIVE full flow.
- `tests/test_consent_notice_catalog_contract.py` — v4 external ref is DRAFT,
  `noticeVersion is None`, hash exact, never accepted as a `noticeVersion`;
  v3/v2/v1 stay DRAFT/historical with `supersededBy`.
- `tests/test_consent_special_categories.py` — proof validation, persistence,
  idempotency/reconsent and withdrawal-preserves-proof.
- `tests/test_consent_notice_state_enforcement_terraform.py` — pilot allowlist
  variable default empty and env wiring.

## 6. Jobsearch consent-text review (read-only, commit `5ac025f`)

Verdict: **PASS** (v4; v3/v2/v1 superseded).

| Requirement | Finding |
| --- | --- |
| Complete first-person declaration | nine paragraphs, canonical join `\n\n`; version `...-v4` and hash `8722…43c7` pinned |
| Data categories | job reference, cover letters and versions, document status, **application status, status changes and status history**, CV/search-profile references (no document copy), application date/channel, contact, notes, salary, follow-ups, history — matches ApplicationV1 `validate_create`/`status` |
| Art. 9 special categories | explicit Art. 9(2)(a) paragraph covering **Sexualleben und sexuelle Orientierung** plus the other categories, voluntary, no self-categorisation, **no automatic gender/orientation inference**; stable nine-code set including `sex_life` |
| Purpose | retrieval, change, export and deletion of the stored application data |
| RIS role | RIS is the storage service in the existing RIS/AWS infrastructure |
| Withdrawal | any time with future effect; blocks new dependent writes; existing data remains readable/exportable/deletable; not an immediate physical deletion |
| Retention/erasure | no blanket period approved; data remains until the user deletes it; backups/logs/legal obligations may delay or limit deletion |
| No invented legal basis | the Art. 9 citation is the consent mechanism itself; no invented retention period, transfer guarantee or recipient list |
| Scope separation | storage consent is explicitly not AI consent and not a provider-transmission consent |

v4 adds „Sexualleben und sexuelle Orientierung“, the `sex_life` category and an
explicit no-inference statement; only v4 can back an Art. 9 consent. v3/v2/v1
remain historical and superseded; none is approved and none is mapped.

Residual legal items (already open in the approval packet, not text defects):
the controller/processor wording and the final legal review of the Art. 9
paragraph still require the legal reviewer.

No Jobsearch file was edited.
