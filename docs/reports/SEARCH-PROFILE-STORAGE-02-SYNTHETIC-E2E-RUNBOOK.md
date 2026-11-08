# SEARCH-PROFILE-STORAGE-02 — Synthetic E2E Runbook

**Status:** `PREPARED — NOT EXECUTED`
**Purpose:** synthetic verification of grant, withdraw, regrant and write-block
for the separate `search-profile-storage` purpose.

No real applicant data may be used. No production/general-user activation is
implied by executing this runbook.

## 1. Preconditions

- RIS-DEV or an isolated preview deployment only.
- A confirmed, allowlisted synthetic identity:
  - `RIS_TEST_USER_ALLOWLIST` (Jobsearch)
  - `CONSENT_PILOT_ALLOWLIST` (RIS)
  - same exact `<issuer>|<sub>` in both.
- A synthetic ready RIS CV `$CV_ID` created under the existing CV pilot, or a
  synthetic PDF created solely for this test. Do not upload a real CV.
- Jobsearch preview flags:

```text
RIS_SEARCH_PROFILE_STORAGE_ENABLED=true
RIS_CONSENT_SERVICE_ENABLED=true
RIS_SEARCH_PROFILE_CONSENT_NOTICE_VERSION=1.0
RIS_SEARCH_PROFILE_CONSENT_TEXT_VERSION=search-profile-storage-consent-2026-11-08-v1
RIS_SEARCH_PROFILE_CONSENT_TEXT_SHA256=926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8
RIS_SEARCH_PROFILE_CONSENT_TEXT_STATE=DRAFT
RIS_SEARCH_PROFILE_CONSENT_SYNTHETIC=true
VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED=true
RIS_TEST_USER_ALLOWLIST=<confirmed operator issuer|sub>
```

- RIS flags for the write-block phase, via a separate reviewed mutation:
  - `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true`
  - `CONSENT_NOTICE_STATE_ENFORCED=false` (allows the synthetic DRAFT grant)
  - notice still `DRAFT`; `legalApprovalRef=null`.

The synthetic flag and the enforcement flag are test-only and must be removed
after the run.

## 2. Variables

```bash
export JOBSEARCH_BASE="https://<preview-host>"
export TOKEN="<short-lived access token; never commit>"
export CV_ID="<synthetic durable cvId>"
export MANUAL_ID=""
export SEARCH_PROFILE_ID=""
export ATS_ID=""
```

Never print or commit `TOKEN`, RIS partner credentials, or real user IDs.

## 3. Steps and expected results

### 3.1 Consent baseline

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profile-consents"
```

Expected:

- HTTP `200`
- `noticeState = "DRAFT"`
- `textVersion = "search-profile-storage-consent-2026-11-08-v1"`
- `textHash = "926d1b9b…f0f8"`
- `textApproved = false`
- `grantAllowed = false` without the synthetic test switch; with the explicit
  synthetic switch the local test path may still be exercised.

### 3.2 Grant

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"search-profile-storage"}' \
  "$JOBSEARCH_BASE/api/ris/search-profile-consents"
```

Expected:

- HTTP `200`
- `consent.purpose = "search-profile-storage"`
- `consent.status = "GRANTED"`
- no `specialCategoriesConsent=true` is required or claimed for this purpose.

Record `version`, `grantedAt`, `externalTextVersion`, `externalTextSha256`.

### 3.3 Manual profile (no CV parent)

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "synthetic-manual-01",
    "description": "synthetic only",
    "searchConfig": {
      "skills": "synthetic",
      "targetRoles": ["Synthetic Role"],
      "city": "Synthetic City",
      "radiusKm": 10,
      "workModes": ["remote"],
      "employmentTypes": ["full_time"]
    },
    "matchingPreferences": {
      "requiredSkills": ["synthetic"],
      "preferredSkills": [],
      "excludedTerms": []
    }
  }' \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=manual"
```

Expected: HTTP `201`, `manualSearchProfileId` present. Set `MANUAL_ID`.

### 3.4 CV search profile (durable RIS cvId only)

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "synthetic-cv-search-01",
    "description": "synthetic only",
    "searchConfig": {
      "skills": "synthetic",
      "targetRoles": ["Synthetic Role"],
      "city": "Synthetic City",
      "radiusKm": null,
      "workModes": ["remote"],
      "employmentTypes": ["full_time"]
    }
  }' \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=cv&cvId=$CV_ID"
```

Expected: HTTP `201`, `searchProfileId` present. Set `SEARCH_PROFILE_ID`.

Negative check: repeat with `cvId` empty or a session hash → HTTP `422`
`invalid_request`; no profile is created.

### 3.5 ATS profile (persistent parent only)

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "synthetic-ats-01",
    "targetRoles": ["Synthetic Role"],
    "skills": ["synthetic"]
  }' \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=ats&searchProfileId=$SEARCH_PROFILE_ID"
```

Expected: HTTP `201`, `atsSearchProfileId` present. Set `ATS_ID`.

Negative check: use a random/non-existent parent → `404`; no profile is
created.

### 3.6 Read/list

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=manual"
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=cv&cvId=$CV_ID"
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=ats&searchProfileId=$SEARCH_PROFILE_ID"
```

Expected: HTTP `200`, each list contains the synthetic item; no CV/PDF content
is returned.

### 3.7 Withdraw

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"search-profile-storage"}' \
  "$JOBSEARCH_BASE/api/ris/search-profile-consents?action=withdraw"
```

Expected: HTTP `200`, `consent.status = "WITHDRAWN"`.

### 3.8 Write-block after withdrawal

```bash
curl -sS -o /tmp/sp-block.json -w '%{http_code}' \
  -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"synthetic-blocked","searchConfig":{"skills":"","targetRoles":[],"city":"","radiusKm":null,"workModes":[],"employmentTypes":["full_time"]},"matchingPreferences":{"requiredSkills":[],"preferredSkills":[],"excludedTerms":[]}}' \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=manual"
```

Expected:

- HTTP `403`
- code `SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED`
- no new profile created.

Repeat with `PUT` on `MANUAL_ID`; expected `403` and unchanged version.

### 3.9 Read/delete after withdrawal

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=manual"
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=ats&searchProfileId=$SEARCH_PROFILE_ID&id=$ATS_ID"
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=cv&cvId=$CV_ID&id=$SEARCH_PROFILE_ID"
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "$JOBSEARCH_BASE/api/ris/search-profiles?type=manual&id=$MANUAL_ID"
```

Expected:

- list/read: HTTP `200`
- deletes: HTTP `204`
- delete order: ATS child first, then CV search profile, then manual.

### 3.10 Regrant and new write

```bash
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"search-profile-storage"}' \
  "$JOBSEARCH_BASE/api/ris/search-profile-consents"
```

Then create one new synthetic manual profile. Expected: HTTP `200` grant,
HTTP `201` create. Delete it and withdraw again.

### 3.11 Non-allowlisted identity

Use a valid token for a different synthetic identity that is not in either
allowlist:

- Jobsearch BFF: HTTP `403` `test_user_not_allowed`, no RIS call.
- Direct RIS partner route: HTTP `403` `SEARCH_PROFILE_STORAGE_PILOT_NOT_ALLOWED`
  when the allowlist is configured.

### 3.12 Cleanup

- Delete all synthetic profiles in child-first order.
- Withdraw consent.
- Verify each list is empty.
- Remove preview flags and the synthetic test switch.
- Restore `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=false` unless the separate
  activation decision says otherwise.
- Do not delete consent history; it is evidence.

## 4. Evidence to capture

| Field | Example |
| --- | --- |
| Timestamp | ISO-8601 UTC |
| Deployment/build | Vercel deployment ID / RIS Lambda code hash |
| Consent state | `NOT_GRANTED → GRANTED → WITHDRAWN → GRANTED` |
| Notice/text | `1.0` / `search-profile-storage-consent-2026-11-08-v1` |
| Text hash | `926d1b9b…f0f8` |
| Profile IDs | synthetic only; no PII |
| Block response | HTTP `403`, `SEARCH_PROFILE_STORAGE_CONSENT_REQUIRED` |
| Read/delete after withdrawal | HTTP `200` / `204` |
| Cleanup | all synthetic lists empty |
| Negative identity | `test_user_not_allowed` / `..._PILOT_NOT_ALLOWED` |

No real applicant data, no automatic CV upload, no AI/model call is part of
this runbook.
