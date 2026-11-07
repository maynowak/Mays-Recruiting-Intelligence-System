# APPLICATION-STORAGE-1.0 — NOTICE MAPPING

**Status:** `PROPOSED — NOT APPROVED`
**Date:** 2026-11-07
**RIS branch:** `feature/jm-ris-storage-activation-01`
**Jobsearch text commit:** `47f73c4` (v2, read-only reference); `2b4b520` (v1,
superseded)
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
| Notice / text version | `1.0` | `application-storage-consent-2026-11-07-v2` |
| Text SHA-256 | — (RIS stores no text bytes) | `232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca` |
| Lifecycle state | `DRAFT` | `DRAFT` |
| `legalApprovalRef` | `null` | n/a |
| Mapping | **none** | **none** |

Historical candidates (kept for audit traceability, never mapped):

| Version | SHA-256 | Jobsearch state | RIS external ref |
| --- | --- | --- | --- |
| `application-storage-consent-2026-11-07-v1` | `2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953` | `DRAFT` (superseded by v2) | `DRAFT`, `noticeVersion: None`, `supersededBy: ...v2` |
| `2026-11-04-draft-1` | — | `DRAFT` | `DRAFT`, `noticeVersion: None` |

v1 is deliberately kept at `noticeState: DRAFT`, **not** `SUPERSEDED`:
`SUPERSEDED` implies the version was approved at some point, which v1 never
was. `supersededBy` records the replacement without implying approval.

## 2. External reference registered in RIS

`jobsearch/consent_contract.py` `EXTERNAL_NOTICE_REFS["application-storage"]`:

```python
"application-storage-consent-2026-11-07-v1": {   # historical, superseded
    "source": "mays-jobsearch",
    "noticeState": NOTICE_DRAFT,
    "noticeVersion": None,  # no equivalence until separately approved
    "textSha256": (
        "2615314738ca991f232314529d0bd473585758b4d1dd4b780f29bcc4c5289953"
    ),
    "supersededBy": "application-storage-consent-2026-11-07-v2",
},
"application-storage-consent-2026-11-07-v2": {   # current candidate
    "source": "mays-jobsearch",
    "noticeState": NOTICE_DRAFT,
    "noticeVersion": None,  # no equivalence until separately approved
    "textSha256": (
        "232cc8206261b5d14f7a269f63a58320f76eea435a65f7e039b25c62d26da0ca"
    ),
},
```

Meaning:

- the texts are **known** to RIS (source, state and exact hashes are visible in
  the partner catalogue response under `externalRefs`);
- neither is accepted as a `noticeVersion` (`422 INVALID_NOTICE_VERSION`);
- neither is equivalent to RIS `1.0`; `noticeVersion` stays `None`.

Each hash pins the exact text. It is computed over
`APPLICATION_STORAGE_CONSENT_PARAGRAPHS.join("\n\n")` (UTF-8) and is asserted
by the Jobsearch test `src/lib/storageConsent.test.ts`; the BFF pins the same
value in `api/_lib/ris/consentText.mjs`. Historical hashes must never be
reused for new text.

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
| 1 | Treat `application-storage-consent-2026-11-07-v2` (hash `232c…a0ca`) as the text for RIS `application-storage/1.0` | Operator/legal approval of the exact text |
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
- `tests/test_consent_notice_catalog_contract.py` — v2 external ref is DRAFT,
  `noticeVersion is None`, hash exact, never accepted as a `noticeVersion`;
  v1 stays DRAFT/historical with `supersededBy: ...v2`.
- `tests/test_consent_notice_state_enforcement_terraform.py` — pilot allowlist
  variable default empty and env wiring.

## 6. Jobsearch consent-text review (read-only, commit `47f73c4`)

Verdict: **PASS** (v2; v1 superseded).

| Requirement | Finding |
| --- | --- |
| Complete first-person declaration | eight paragraphs, canonical join `\n\n`; version `...-v2` and hash `232c…a0ca` pinned |
| Data categories | job reference, cover letters and versions, document status, **application status, status changes and status history**, CV/search-profile references (no document copy), application date/channel, contact, notes, salary, follow-ups, history — matches ApplicationV1 `validate_create`/`status` |
| Purpose | retrieval, change, export and deletion of the stored application data |
| RIS role | RIS is the storage service in the existing RIS/AWS infrastructure |
| Withdrawal | any time with future effect; blocks new dependent writes; existing data remains readable/exportable/deletable; not an immediate physical deletion |
| Retention/erasure | no blanket period approved; data remains until the user deletes it; backups/logs/legal obligations may delay or limit deletion |
| No invented legal basis | no Art. 6/9 citation, no invented retention period, no invented transfer guarantee or recipient list |
| Scope separation | storage consent is explicitly not AI consent and not a provider-transmission consent |

v2 adds the explicit „Bewerbungsstatus, Statusänderungen und der
Statusverlauf“, closing the earlier wording gap around ApplicationV1
`status`/`statusHistory`. The previous v1 text remains historical and
superseded; it is not approved and never mapped.

Residual legal items (already open in the approval packet, not text defects):
the Art. 9 assessment for free-text cover letters/notes/contact and the exact
controller/processor wording still require the legal reviewer.

No Jobsearch file was edited.
