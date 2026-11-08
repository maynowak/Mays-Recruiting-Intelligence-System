# SEARCH-PROFILE-STORAGE-03 — Connect & Release Status

**Status:** `RIS DEPLOYED — JOBSEARCH PREVIEW BLOCKED — LIVE E2E NOT EXECUTED`  
**Live E2E:** `BLOCKED — CREDENTIALS/SESSION + PREVIEW CALLBACK UNAVAILABLE`  
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
| RIS notice | `search-profile-storage/1.0` — **`APPROVED`** |
| `legalApprovalRef` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` |
| Approval date / body | `2026-11-08` / Betreiberin May’s Job Matcher |
| Privacy policy | v1.2, 2026-11-08 |

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

The old plans `d94550010417d964fc9c3e5c94259a3eb8b692995f9bac41edd023c12bfcdc14`
(v1) and `9c6924e990f1029afdb1aa08b38e12bd9e744054eb3fe01b50f356f6028d6271`
(pre-approval v2/DRAFT) are **superseded**. The notice is now APPROVED, so a
fresh plan was made.

| Field | Value |
| --- | --- |
| Plan file | `/tmp/opencode/ris-dev-search-profile-04.tfplan` |
| Plan SHA-256 | `d6cfcda99a73dacf6ed44f111c42f719f8c401dcea6d7edb82caf9bfd1e2576a` |
| Plan JSON | `/tmp/opencode/ris-dev-search-profile-04-plan.json` |
| Terraform | `1.16.1` |
| State | `mays-ris-tf-state-dev` / `env:/ris-dev/dev/terraform.tfstate` |
| State serial / lineage | `46` / `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Changes | **0 add, 1 change, 0 destroy, 0 replace** |
| Active change | `module.lambda.aws_lambda_function.agent` UPDATE |
| Code hash | `EUSPzucGkHqwcazIch3ny4oCshvwjbFxJP8Hhe48QRc=` → `pStIe5JG66TGF6PyltAmLJQ/0yKSgoWI6H7AmrAKwHU=` |
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

- **Apply GO** for plan `d6cfcda99a73dacf6ed44f111c42f719f8c401dcea6d7edb82caf9bfd1e2576a` — not yet given.
- **Vercel preview/deployment GO** — not yet given.
- **Enforcement=true GO** for the 403 test — not yet given.

No push, merge, AWS mutation, Vercel deployment, notice activation or live
persistence claim was made.

## 6. Definition of Done

The final DoD (`LIVE E2E VERIFIED`) is **not claimed** because the apply,
deployment and enforcement gates above have not been explicitly granted. The
notice text itself is now approved. Once the apply/preview GO is granted, the
prepared sequence can be executed without further architecture work.

## 7. RIS deployment (executed)

The saved plan was applied after hash/state/artifact re-check:

| Field | Value |
| --- | --- |
| Plan | `/tmp/opencode/ris-dev-search-profile-04.tfplan` |
| SHA-256 | `d6cfcda99a73dacf6ed44f111c42f719f8c401dcea6d7edb82caf9bfd1e2576a` |
| Apply result | **0 added, 1 changed, 0 destroyed** |
| State after apply | serial **47**, lineage `9cec61e5-c036-1ad5-6ae4-8b48a50122a4`, 250 resources |
| Lambda | `ris-dev-dev-agent`, `Active`, code `pStIe5JG66TGF6PyltAmLJQ/0yKSgoWI6H7AmrAKwHU=` |
| Env | `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=false`; CV gate true; application gate false; pilot allowlist unchanged |

The notice code is now live with `search-profile-storage/1.0` `APPROVED` and
`legalApprovalRef=JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08`.

## 8. Jobsearch preview blocker

No preview deployment was made. The Vercel preflight found:

- this worktree is not linked; project is `maymilly/mays-job-matcher`
  (`prj_wdzpRfrGENG82Txi9Sa9QTzKruk9`);
- the Preview environment has **no** RIS server variables (they exist only in
  Production), so the BFF would fail closed;
- the Cognito client callback URLs are only
  `http://localhost:5173/auth/callback`,
  `https://mays-job-matcher.vercel.app/auth/callback`,
  `https://www.mays-job-matcher.app/auth/callback` — no preview URL;
- no Cognito test-user credentials or reusable session exists in the
  workspace; the OIDC session uses `sessionStorage`, so cookie storageState is
  not reusable.

A public preview with copied production secrets would expose the RIS
credential; that was not done. A Cognito callback/pool change is outside the
allowed scope and was not made.

## 9. Enforcement plan (prepared, not applied)

`/tmp/opencode/ris-dev-search-profile-05.tfplan`  
SHA-256 `53bcc0a09c9a878d4ca90e65c75fba1a9219084d181b9eac2544f5c33908e5a9`  
Base state serial **47**; **0 add / 1 change / 0 destroy**; only
`SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED: false → true`.

This plan must not be applied until the first web E2E succeeds and a separate
**GO ENFORCEMENT** is given.

## 10. Exact unblock

Provide one of:

1. a Cognito test-user credential or an interactive operator login plus
   approval to register the exact preview callback URL; or
2. an already-authenticated operator session/token for the target origin; or
3. a controlled production deployment by the operator, with the same
   allowlisted pilot and no general rollout.

Until then the live web E2E cannot be honestly claimed.

