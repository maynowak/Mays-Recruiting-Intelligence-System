# JM-RIS-STORAGE-PILOT-02 — Isolated environment analysis

**Status:** `ANALYSIS ONLY — NO APPLY, NO FLAG CHANGE, NO ACTIVATION`
**Date:** 2026-11-07
**Scope:** where a consent + ApplicationV1 pilot can run without touching the
shared `ris-dev` integration surface.

---

## 1. Current live facts (read-only, re-verified 2026-11-07)

Commands used (read-only; no mutation):

```
aws sts get-caller-identity --profile mayaws
aws lambda get-function-configuration --function-name ris-dev-dev-agent \
  --profile mayaws --region eu-central-1 --query 'Environment.Variables.{...}'
aws lambda get-function-configuration --function-name ris-dev2-dev-agent \
  --profile mayaws --region eu-central-1
aws apigatewayv2 get-apis --profile mayaws --region eu-central-1 \
  --query 'Items[?contains(Name, `ris-dev`)].{Name:Name,ApiId:ApiId}'
```

| Fact | Observed value |
| --- | --- |
| STS account | `240571105849` (`arn:aws:iam::240571105849:user/Mayaws`, profile `mayaws`) |
| Lambda `ris-dev-dev-agent` | exists, Active (env read successfully) |
| `CONSENTS_TABLE` | `ris-dev-dev-consents` |
| `APPLICATION_CONSENT_ENFORCED` | `false` |
| `PARTNER_SURFACE_ENABLED` | `true` |
| `CONSENT_NOTICE_STATE_ENFORCED` | **absent** (query returned `null`) |
| `ris-dev2-dev-agent` | **not found** in this account (`ResourceNotFoundException`) |
| API `c7e9pdwe78` | `ris-dev-jobsearch-api` |
| API `g6901and25` | `ris-dev-dev-api` |
| API `zf8tc0k2r2` | `ris-dev-mays-orders-api` |

The Lambda env was queried with a projection of only these four keys; no secret
values were read or printed.

---

## 2. Why `ris-dev` is not an isolated pilot runtime

`ris-dev` is the **permanent dev install shared with the Jobsearch partner
edge**:

- `installer/project-configs/ris-dev.json` sets `partner_surface_enabled=true`
  and the Jobsearch production Cognito issuer/client
  (`eu-central-1_ZURSMpD2O` / `5hb3…`).
- `c7e9pdwe78` (`ris-dev-jobsearch-api`) is the partner edge used by
  `www.mays-job-matcher.app` (see `docs/contracts/CONSENT-V1.md` §1).
- Its CORS origins include the production Jobsearch domains.
- `ris-dev-dev-consents` already holds historical synthetic consent rows from
  earlier live tests.

Consequences of flipping either gate in `ris-dev`:

1. `APPLICATION_CONSENT_ENFORCED=true` would immediately change write behavior
   for the shared partner edge, not just for a pilot user.
2. `CONSENT_NOTICE_STATE_ENFORCED=true` would change grant behavior for every
   partner using that workspace.
3. A pilot failure would be indistinguishable from a partner-edge regression.

**Rule for this task:** do not change `ris-dev` variables, Lambda env, table
contents or API configuration.

`ris-dev2` is not available for a pilot in this account. Its project config
points at a different Cognito pool (`eu-central-1_ojbmoiYGM`) and its Lambda
does not exist here, so it belongs to a separate account/workspace that has to
be verified and brought up under its own approval — not assumed.

---

## 3. Smallest safe alternative

**Option A (recommended): dedicated workspace `ris-storage-pilot`.**

- `project_name = ris-storage-pilot`, `environment = test`
  → prefix `ris-storage-pilot-test`, own DynamoDB tables, own Lambda, own API,
  own log group.
- Own Terraform state key/bucket/lock table (explicitly supplied, never
  defaulted or invented).
- Own partner surface (`partner_surface_enabled=true`) and its own API Gateway;
  no production CORS origins.
- Own synthetic test identity. Preferred: the workspace's managed Cognito pool
  (`identity_mode=managed`) with one synthetic user, so no production pool is
  touched. Alternative: a dedicated test pool under a separate explicit scope.
- Own partner registry row + partner credential for the preview BFF (secret
  created through the approved secret process, never in Terraform/git).
- Both consent gates start `false`, are enabled only in a later, separately
  approved step.

**Option B: verify and use `ris-dev2` in its real account.** Only after a
separate read-only inventory confirms: account, workspace, backend state key,
current resources, API ID, and that it has no partner-edge traffic. No apply in
this task.

---

## 4. Prerequisites before any pilot apply (separate GO required)

1. Legal/operator approval of `application-storage/1.0` and a real
   `legalApprovalRef` (see `APPLICATION-STORAGE-1.0-APPROVAL-PACKET.md`);
   otherwise the pilot cannot grant.
2. Approved retention rule for ApplicationV1 and consent history.
3. A reviewed Terraform plan for the new workspace:
   backend bucket/key/lock table supplied explicitly, expected
   CREATE/UPDATE/DELETE counts reviewed, 0 protected-resource changes.
4. Deterministic Lambda bundle rebuild (`python lambda/build_zip.py --bundle all`)
   after any registry change.
5. A dedicated partner credential + partner application registry row for the
   preview BFF; store the credential only in the approved secret store.
6. The synthetic test identity (issuer + sub) and its allowlist entry.
7. Explicit GO naming the workspace, account, region, flags and target
   audience.

**No plan, apply, secret creation or flag change is performed by this task.**

---

## 5. Exact non-secret configuration plan (target state, not applied)

### 5.1 RIS pilot workspace (`ris-storage-pilot` / `test`)

| Setting | Pilot value | Note |
| --- | --- | --- |
| `consent_notice_state_enforced` (root → module) | `true` | Newly wired; default stays `false` until GO |
| `application_consent_enforced` | `false` first, `true` after synthetic consent flow | Default `false` |
| `partner_surface_enabled` | `true` | Required for `/v1/partner/me/*` |
| `NOTICE_REGISTRY["application-storage"]["1.0"]` | `APPROVED` or `ACTIVE` + real `legalApprovalRef` | Code change + new bundle; separate approval |
| `jobsearch_cognito_issuer` / `_client_id` | pilot pool issuer/client | Not the production pool |
| `jobsearch_edge_cors_origins` | preview origin only | No production domain |
| `api_cors_origins` | preview origin only | No wildcard |
| `applications_cursor_secret_arn` | pilot secret ARN | Secret value never in Terraform |
| `r08_pitr_enabled` | `false` unless approved | PITR is not a retention decision |
| `orders_lifecycle` | `disabled` | Unrelated subsystem |

### 5.2 Jobsearch preview environment (server-side unless `VITE_`)

| Variable | Pilot value |
| --- | --- |
| `RIS_API_BASE_URL` | pilot API invoke URL |
| `RIS_PARTNER_CREDENTIAL` | pilot credential (server-only) |
| `RIS_COGNITO_ISSUER` / `RIS_COGNITO_CLIENT_ID` | pilot pool |
| `RIS_CONSENT_SERVICE_ENABLED` | `true` |
| `RIS_APPLICATION_STORAGE_ENABLED` | `true` |
| `RIS_CONSENT_NOTICE_VERSION` | `1.0` |
| `RIS_TEST_USER_ALLOWLIST` | `<pilot issuer>|<synthetic sub>` only |
| `VITE_RIS_CONSENT_UI_ENABLED` | `true` (preview only) |
| `VITE_RIS_APPLICATION_STORAGE_ENABLED` | `true` (preview only) |

`VITE_RIS_APPLICATION_STORAGE_ENABLED` is absent from both production Vercel
projects today; it must not be enabled for the general production audience
without a UI allowlist and RG-09 approval.

---

## 6. Acceptance checks for the later pilot execution (not run here)

1. Non-allowlisted identity → `403`, no RIS call.
2. `GET /api/ris/consents` → `noticeState=APPROVED|ACTIVE`,
   `grantAllowed=true`, status `NOT_GRANTED`.
3. Grant → `GRANTED` with `noticeVersion=1.0`.
4. Create → RIS `applicationId` + `ownerId` (not local React state).
5. Reload/re-login → application readable from RIS.
6. Update → version increment.
7. Export contains the application; delete removes it.
8. Withdraw → new write `403 CONSENT_REQUIRED`; read/export/delete still work.
9. `DRAFT`/`SUPERSEDED` cannot be granted (`422 NOTICE_NOT_ACTIVE`).
10. Cleanup: synthetic applications and consent rows deleted; table returns to
    the agreed baseline.

---

## 7. Rollback (for the later pilot)

1. `APPLICATION_CONSENT_ENFORCED=false` for the pilot workspace (or disable the
   partner surface → 503).
2. `VITE_RIS_APPLICATION_STORAGE_ENABLED=false` in the preview to return the UI
   to session mode.
3. Revert the notice to `DRAFT`/`SUPERSEDED`; existing grants remain valid, new
   grants are blocked.
4. Keep the pilot data for export/delete; delete only synthetic rows.
5. Tear down the workspace only after the data decision and a separate GO.

---

## 8. Conclusion

- The technical implementation is ready to be **tried** in an isolated pilot
  workspace; it is **not** ready to be activated on `ris-dev`.
- `ris-dev` remains a shared partner-edge integration environment and must not
  carry the pilot gates.
- The primary blocker is still the missing legal approval of notice
  `application-storage/1.0`; the environment choice is the second blocker.
