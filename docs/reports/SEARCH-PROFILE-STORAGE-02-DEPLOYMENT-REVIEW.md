# SEARCH-PROFILE-STORAGE-02 — Deployment Review

**Status:** `READY FOR NOTICE APPROVAL + DEPLOYMENT REVIEW`
**Date:** 2026-11-08
**Scope:** deployment preparation only; no mutation performed

## 1. Decision state

| Field | Value |
| --- | --- |
| Purpose | `search-profile-storage` |
| RIS notice | `search-profile-storage/1.0` |
| Notice state | `DRAFT` |
| `legalApprovalRef` | `null` |
| Proposed operator reference | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` — **not a legal approval yet** |
| Consent text | `search-profile-storage-consent-2026-11-08-v1` |
| SHA-256 | `926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8` |
| RIS gate | `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=false` |
| Jobsearch browser flag | `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED` absent |

The text remains a candidate. No agent set the notice to `APPROVED`/`ACTIVE`
and no agent wrote a legal approval reference.

## 2. Privacy alignment

Targeted findings are in
`SEARCH-PROFILE-STORAGE-02-PRIVACY-ALIGNMENT.md`:

- **P1:** policy §9 still frames CV/search profiles under ApplicationV1; a
  clarifying sentence or explicit legal decision is required before notice
  approval.
- **P2:** “keine … sonstige Anbieter” must be clarified for the AWS/DynamoDB
  processor; if the proposed replacement is adopted, the text version/hash and
  all mappings change.
- **P3:** account erasure does not currently include partner search profiles;
  per-profile deletion exists. Decide before real-user rollout whether to wire
  account erasure or state the limitation.
- **P4:** live profile table has no PITR/no listed backups; per-profile delete
  is a hard delete. The candidate’s “können” wording is not false but is broad.
- **P5:** free-text descriptions could contain Art. 9 data; add a UI hint or
  accept professional-data-only scope.

No general privacy analysis and no privacy-policy edit was made.

## 3. Terraform plan against current RIS-DEV state

### Command shape

```bash
AWS_PROFILE=mayaws terraform -chdir=terraform plan \
  -input=false -lock=false \
  -var-file=/tmp/opencode/ris-dev-search-profile-02.tfvars.json \
  -out=/tmp/opencode/ris-dev-search-profile-02.tfplan
```

Variable values were carried over from the last reviewed clean plan; the only
new value is:

```text
search_profile_storage_consent_enforced = false
```

### Evidence

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-search-profile-02.tfplan` |
| Plan SHA-256 | `d94550010417d964fc9c3e5c94259a3eb8b692995f9bac41edd023c12bfcdc14` |
| Plan JSON | `/tmp/opencode/ris-dev-search-profile-02-plan.json` |
| Plan log | `/tmp/opencode/ris-dev-search-profile-02-plan.log` |
| Terraform | `1.16.1` |
| State bucket/key | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage | `46` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| State resources | 250 |
| Changes | **0 add, 1 change, 0 destroy, 0 replace** |
| Plan timestamp | `2026-11-08T14:35:07Z` |

### Only active change

`module.lambda.aws_lambda_function.agent` — **UPDATE**

- `source_code_hash`:
  - before: `EUSPzucGkHqwcazIch3ny4oCshvwjbFxJP8Hhe48QRc=`
  - after: `55vbOpZMYHaj/eXJ+ukcpkPcXWiiCuN+9aqMquOplNs=`
- Environment:
  - **new** `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED = "false"`
  - 37 other variables unchanged.

The plan contains no API Gateway, DynamoDB, Cognito, CloudFront, Route53, ACM,
S3, Orders, health-plane, or partner-edge change. No replacement is planned.
No other consent purpose is changed.

### Current live state (read-only)

- Lambda `ris-dev-dev-agent`: `Active`, code
  `EUSPzucGkHqwcazIch3ny4oCshvwjbFxJP8Hhe48QRc=`;
  `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` absent;
  `CV_STORAGE_CONSENT_ENFORCED=true`;
  `APPLICATION_CONSENT_ENFORCED=false`;
  `CONSENT_NOTICE_STATE_ENFORCED=false`;
  `PARTNER_SURFACE_ENABLED=true`.
- `ris-dev-dev-partner-profiles`: 3 items, TTL on `expiresAt`, PITR disabled,
  no listed backups, deletion protection false.
- `ris-dev-dev-consents`: TTL disabled, PITR disabled.
- Existing partner routes for manual/CV-search/ATS/consents are present on
  `ris-dev-jobsearch-api` (`c7e9pdwe78`).

No apply, state write, lock acquisition, or resource mutation was performed.
The plan used `-lock=false`; the state serial remained 46.

## 4. Deployment order

### Gate A — DRAFT / synthetic only (no real users)

1. **RIS code first.** Apply the reviewed plan after a separate GO. This adds
   the search-profile gate/code with `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`
   still `false`.
2. Verify Lambda `Active`, the new code hash, and the new env var = `false`.
3. **Jobsearch preview** with:
   - `RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`
   - `RIS_CONSENT_SERVICE_ENABLED=true`
   - `RIS_SEARCH_PROFILE_CONSENT_NOTICE_VERSION=1.0`
   - `RIS_SEARCH_PROFILE_CONSENT_TEXT_VERSION=search-profile-storage-consent-2026-11-08-v1`
   - `RIS_SEARCH_PROFILE_CONSENT_TEXT_SHA256=926d1b9bbeefac4b97a5c51e3b6e6c1ed33a3affc3698e07456132be39b0f0f8`
   - `RIS_SEARCH_PROFILE_CONSENT_TEXT_STATE=DRAFT`
   - `RIS_SEARCH_PROFILE_CONSENT_SYNTHETIC=true` (preview/synthetic only)
   - `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`
   - `RIS_TEST_USER_ALLOWLIST=<confirmed operator issuer|sub>`
4. For the write-block phase, use a **separate one-variable plan** with
   `search_profile_storage_consent_enforced=true`; this is a separate mutation
   decision, not part of the current plan. Keep the notice DRAFT and
   `CONSENT_NOTICE_STATE_ENFORCED=false` for the synthetic grant.
5. Run the synthetic E2E in
   `SEARCH-PROFILE-STORAGE-02-SYNTHETIC-E2E-RUNBOOK.md`.
6. Remove the synthetic flag and preview flags after the test.

### Gate B — approved limited pilot

Only after the operator approves the exact text/notice:

1. Update RIS notice `search-profile-storage/1.0` from `DRAFT` to
   `APPROVED`/`ACTIVE` with the real `legalApprovalRef`, date and approving
   body. This is a code change and needs a new reviewed plan.
2. Set Jobsearch `RIS_SEARCH_PROFILE_CONSENT_TEXT_STATE=APPROVED`; keep the
   canonical text/hash.
3. Set `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true` on RIS via a reviewed
   plan.
4. Deploy Jobsearch; production `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`
   only for the approved test audience.
5. Run the same E2E against the limited pilot; verify non-allowlisted users
   cannot enter persistent mode.
6. No general rollout.

### Rollback

- RIS: apply the previous reviewed Lambda plan or disable
  `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` with a reviewed change; keep
  reads/deletes available.
- Jobsearch: remove `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED` and redeploy the
  previous build; session profiles remain available.
- Notice: do not change a `DRAFT` to `APPROVED` as a rollback shortcut, and do
  not delete consent history.

## 5. Synthetic E2E preparation

The exact steps, expected statuses and evidence fields are in
`SEARCH-PROFILE-STORAGE-02-SYNTHETIC-E2E-RUNBOOK.md`. It covers:

- GET consent before grant;
- grant → manual profile → durable-CV search profile → ATS profile;
- withdraw → write `403` → read/export/delete allowed;
- regrant → new write allowed;
- non-allowlisted identity → `403`;
- cleanup of all synthetic profiles.

No live E2E was executed in this task.

## 6. Remaining operator decisions

1. Approve or amend the text (P1/P2), then supply the real
   `legalApprovalRef`, approval date and approving body.
2. Decide P3: wire account erasure for search profiles, or state the
   limitation.
3. Decide P4/P5 wording/UX.
4. Approve the saved RIS plan and the separate deployment/E2E GO.
5. Approve any preview/production Vercel mutation separately.

## 7. Result

`READY FOR NOTICE APPROVAL + DEPLOYMENT REVIEW`

No AWS apply, Terraform state mutation, Vercel deployment, notice activation,
real-user data processing, push or merge was performed.
