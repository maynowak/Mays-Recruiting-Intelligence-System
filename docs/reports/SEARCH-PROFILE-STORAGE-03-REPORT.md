# SEARCH-PROFILE-STORAGE-03 — Connect & Release Status

**Status:** `READY FOR FINAL TEXT CONFIRMATION + APPLY/DEPLOY GO`  
**Live E2E:** `NOT EXECUTED`  
**Date:** 2026-11-08

The integration was not redeveloped. The existing RIS contracts, Jobsearch BFF,
profile adapters and UI were reused. This task completed the P1/P2 text
corrections and produced a new plan; the notice remains DRAFT until the
operator confirms the final text.

## 1. Final text and policy

| Field | Value |
| --- | --- |
| Consent text | `search-profile-storage-consent-2026-11-08-v2` |
| SHA-256 | `75919c8bc219c938bdd2452a8bf02955997d1336ba2ca716bc691dd54eaa7ef6` |
| RIS notice | `search-profile-storage/1.0` — `DRAFT` |
| `legalApprovalRef` | `null` |
| Privacy policy | v1.2, 2026-11-08 |
| Proposed approval ref | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` — not yet approved |

P1: Datenschutzerklärung §9 now describes search-profile storage as a separate
`search-profile-storage` purpose, not covered by ApplicationV1, stored in
RIS/AWS, with no AI call for storage/CRUD and separate terms for later AI use.
Both `datenschutz.md` and `.html` carry version 1.2.

P2: consent paragraph 3 now names RIS including AWS, confirms that creating,
saving, loading, editing or deleting a profile makes no AI request, and states
that later AI use (especially ATS analyses) is governed by separate processing
terms. No other content changed; paragraph 6 now references policy v1.2.

Compact diff and full text:
`SEARCH-PROFILE-STORAGE-03-FINAL-CONSENT-PACKET.md`.

P3 remains an open boundary for general rollout: account erasure does not
currently include partner search profiles; per-profile deletion is implemented.
No erasure redesign was performed.

## 2. New Terraform plan

The old plan `d94550010417d964fc9c3e5c94259a3eb8b692995f9bac41edd023c12bfcdc14`
is **invalid** because the RIS consent text changed and therefore the Lambda
code hash changed.

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-search-profile-03.tfplan` |
| Plan SHA-256 | `9c6924e990f1029afdb1aa08b38e12bd9e744054eb3fe01b50f356f6028d6271` |
| Plan JSON | `/tmp/opencode/ris-dev-search-profile-03-plan.json` |
| Terraform | `1.16.1` |
| State | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage | `46` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Changes | **0 add, 1 change, 0 destroy, 0 replace** |
| Active change | `module.lambda.aws_lambda_function.agent` UPDATE |
| Code hash | `EUSPzucGkHqwcazIch3ny4oCshvwjbFxJP8Hhe48QRc=` → `gl6tIdxgZonvpfq0y+W+c5oSO5fIbHX8DyPwPMRevtY=` |
| Env delta | add `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=false` |

No Cognito, CloudFront, DNS, ACM, Mays-Orders, DynamoDB, API Gateway, S3,
health-plane or partner-edge change. No state write; serial remained 46.

## 3. Verification

- Jobsearch targeted: **68 tests PASS** across search-profile BFF, routing,
  CV regression, consent text, API client, manual profiles and privacy pages.
- `npm run build`: **PASS**.
- RIS targeted: **172 tests PASS** across search-profile consent/gate,
  manual/CV/ATS APIs, consent catalogue/lifecycle, application consent and
  partner integration.
- No live E2E was run.

## 4. Deployment order (not executed)

1. Operator confirms final text + P1 policy + approval fields.
2. Set RIS notice `search-profile-storage/1.0` to `APPROVED` with the real
   reference, date and approving body; create and review a new plan if this
   changes code.
3. Apply the reviewed RIS plan; keep
   `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=false` for the first technical test.
4. Deploy Jobsearch preview with the existing RIS config, the v2 text/hash,
   `RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`,
   `VITE_RIS_SEARCH_PROFILE_STORAGE_ENABLED=true`, and the scoped allowlist.
5. Run the synthetic E2E (grant, manual, CV-search, ATS, reload, edit, delete,
   withdraw, read/delete, regrant, cleanup).
6. For the 403 write-block, obtain a separate GO for a reviewed plan with
   `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true`.
7. Only after E2E and approval consider the limited production deployment.

## 5. Blocking gates

- **Final text confirmation** of v2 hash and policy v1.2 — not yet given.
- **Notice approval** with a real `legalApprovalRef` — not yet given.
- **Apply GO** for the saved plan — not yet given.
- **Vercel preview/deployment GO** — not yet given.
- **Enforcement=true GO** for the 403 test — not yet given.

No push, merge, AWS mutation, Vercel deployment, notice activation or live
persistence claim was made.

## 6. Definition of Done

The final DoD (`LIVE E2E VERIFIED`) is **not claimed** because the required
approval gates above have not been explicitly granted. Once they are, the
prepared sequence in this report and the existing synthetic E2E runbook can be
executed without further architecture work.
