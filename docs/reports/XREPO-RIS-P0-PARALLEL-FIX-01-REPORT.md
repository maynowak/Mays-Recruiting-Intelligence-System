# XREPO-RIS-P0-PARALLEL-FIX-01 — Consolidated Report

**Status: BLOCKED — SECURITY/PRIVACY REVIEW REQUIRED**

- Repository: `maynowak/Mays-Recruiting-Intelligence-System`
- Base: `origin/main` `97a60df83a5db56ea750e4342d7a01b00c8ad56b`
- Integration branch: `integration/xrepo-ris-p0-parallel-fix-01`
- Feature branches: `feature/ris-erasure-partner-route-alignment-01` (`db5ba54`), `feature/ris-consent-iac-alignment-01` (`68f9074`)
- Integration merges: `de15bac` (erasure), `a1ef3ca` (consent)
- No main merge, no AWS mutation, no Terraform apply/plan against live state, no deployment, no Jobsearch change.
- Technical fixes are implemented and locally verified. Release is blocked by two unresolved privacy decisions documented below.

---

## 1. Agent results

### Agent A — RIS-ERASURE-PARTNER-ROUTE-ALIGNMENT-01

Branch `feature/ris-erasure-partner-route-alignment-01`, commit `db5ba54`.

- Added `POST /v1/partner/me/erasure` to `lambda/handler.py`, routed through the existing `_partner_profile_context(event)` gate and then to the existing `_handle_me_erasure`.
- Added the route to `terraform/modules/partner_edge/main.tf` and `terraform/modules/api/main.tf` (Terraform provenance matching other `/v1/partner/me/*` routes).
- `/me/erasure` unchanged. Exactly one `PrivacyErasure` construction; no second executor.
- OpenAPI/API-STANDARD/Privacy capability contract updated; tests `tests/test_partner_erasure_route.py` (15 tests), P20 route inventory, partner surface gate.
- Jobsearch BFF is now HTTP-compatible on main: partner route exists, JWT + `X-Api-Credential` + partner/tenant binding, no client-supplied identity, 200/207 result.
- **Open P0:** main’s erasure lifecycle lacks the `erase-partner-search-profiles` and CVDocument-metadata steps that exist on the deployed `ris-dev` lineage. On main the route can return `complete: true` while durable search profiles/CV metadata remain. This is not silently fixed and blocks real-user rollout.

### Agent B — RIS-CONSENT-IAC-ALIGNMENT-01

Branch `feature/ris-consent-iac-alignment-01`, commit `68f9074` (implementation `2dd89be`).

- Wired the missing Lambda environment variables from Terraform variables:
  - `CV_STORAGE_CONSENT_ENFORCED`
  - `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`
  - `CONSENT_NOTICE_STATE_ENFORCED`
  - `CONSENT_PILOT_ALLOWLIST` (sensitive, format-validated)
- All values derive from variables; no literal `"true"`. `APPLICATION_CONSENT_ENFORCED` unchanged.
- Plan guards fail closed: active storage gates require notice-state enforcement; CV/search gates require a non-empty pilot allowlist; malformed allowlist fails the plan.
- Runtime `enforcement_flag()`: unset → false; `true`/`false` parse; any other value (empty, `1`, `yes`, `ture`) is treated as **enforced** and logged.
- Installer allows only the three site booleans; `ris-dev.json` unchanged; no real allowlist or consent values committed.
- Consent docs/OpenAPI/API-STANDARD aligned with the registry: 3 APPROVED purposes, DRAFT `analysis-processing`, proof fields, 404 `UNKNOWN_PURPOSE`, 403 pilot/consent codes.
- **Open P0:** RIS accepts a `cv-storage` grant without Art.-9 proof and stores `specialCategoriesConsent=false`; only the Jobsearch BFF requires explicit Art.-9 consent. This requires a Privacy/Legal decision.

---

## 2. Integration

Integration branch from `origin/main` `97a60df`:

1. `de15bac` — merge erasure branch.
2. `a1ef3ca` — merge consent branch.

Conflicts:

- `docs/AI_AUDITLOG.md` — both append entries; resolved by keeping both.
- `docs/api/API-STANDARD.md` — erasure row vs consent status-code rows; resolved by keeping the erasure row and the consent branch’s corrected 404/409/422 rows.
- `docs/api/openapi-platform.yaml`, `lambda/handler.py`, Terraform and tests merged automatically without source conflict.
- No function removed; no duplicate route.

Whole diff vs main: 22 files, +2037/−106.

---

## 3. Tests and checks

| Check | Result |
|---|---|
| Focused erasure/consent/OpenAPI/P20/surface suite | **102 passed, 425 subtests passed** |
| Full RIS suite `pytest tests/ -q` | **3245 passed, 129 skipped, 4 failed, 549 subtests** |
| `terraform fmt -check -recursive terraform/` | PASS |
| `terraform init -backend=false` + `validate` modules `api`, `partner_edge`, `lambda` | 3/3 PASS |
| Root Terraform validate | Pre-existing failure on generated `modules/mays_orders` missing `iam_handler_role_name`; reproduced by both agents on a main export |
| Terraform plan | **Not generated** — requires protected live context/approval; no backend/state access |
| AWS/Terraform apply | Not performed |

The 4 full-suite failures are pre-existing/environmental: three `test_composite_lifecycle` installer arg-ordering tests and `test_lambda_packaging::test_c_exclusions` (missing non-checked-in `terraform/lambda.zip`). Both agents reproduced the same failures on a pristine main export.

---

## 4. Contract comparison

| Contract | Status |
|---|---|
| Jobsearch BFF `POST /api/ris/erasure` → `/v1/partner/me/erasure` | HTTP-compatible after Agent A; auth/credential/tenant boundary preserved |
| Erasure lifecycle completeness | **Blocked** — main lacks search-profile/CVDocument-metadata deletion; `complete: true` can be semantically too optimistic |
| Consent purposes/notice versions/hashes | Registry and Jobsearch BFF constants aligned for application-storage v4, cv-storage v1, search-profile-storage v2 |
| Consent env wiring | Fixed on integration branch; plan not generated |
| Art. 9 enforcement | RIS still accepts a cv-storage grant without Art.-9 proof; only Jobsearch BFF enforces — open Privacy/Legal decision |
| OpenAPI/API-STANDARD | Updated for partner erasure and full consent purposes/proof/status codes |
| Installer | Site booleans added; pilot allowlist remains server-only; no live values |

---

## 5. Terraform plan assessment

No plan was generated; no backend/state/AWS access was used. Therefore this report cannot claim `0 Delete / 0 Replace`.

What can be stated from configuration:

- The erasure route is additive in both the partner-edge and kernel API modules; no data/IAM/S3/DynamoDB resource is added.
- Consent wiring adds variables and Lambda environment entries only; no resource topology change.
- Any future plan must be reviewed for:
  - no loss of the four consent env variables;
  - no deletion/replacement of the live partner erasure route;
  - Lambda environment diff matching the variable map;
  - no IAM or resource deletion/replacement.
- A plan is only acceptable with a fresh protected `ris-dev` context, G4/G5 approval and explicit review of Lambda environment/IAM changes.

---

## 6. Open privacy/legal questions

1. **Erasure lifecycle parity:** must main include `erase-partner-search-profiles` and CVDocument-metadata deletion before the partner route is enabled? Without it, `complete: true` does not mean all Jobsearch-visible partner data is gone.
2. **Art. 9 for `cv-storage`:** should RIS reject a cv-storage grant without explicit special-category proof, or is the Jobsearch BFF the audited sole boundary?
3. **Notice-state enforcement:** should `CONSENT_NOTICE_STATE_ENFORCED` default true in deployed environments, and how are synthetic flows protected?
4. **Pilot allowlist semantics:** keep it as an access boundary and notice-enforcement scope, or split into two variables?
5. **Retention/PITR/S3 versions:** remain outside G5 scope; deletion receipts/completeness need separate legal confirmation.
6. **Production deployment source:** main `97a60df` vs the deployed `ris-dev` lineage; the plan must not silently roll back live erasure/consent behavior.

---

## 7. Required approvals

- RIS release owner / API contract owner.
- AWS/Terraform G4/G5 for a fresh read-only plan and later apply; no apply in this task.
- Privacy/Legal for lifecycle parity and Art. 9.
- Security for erasure authorization/idempotency and allowlist coupling.
- Separate live synthetic E2E approval after deployment.
- No Jobsearch merge/deploy; Jobsearch BFF remains compatible but flags stay default-off.

---

## 8. Integration risks

| Risk | Assessment |
|---|---|
| Route present but lifecycle incomplete | **High / blocking** for real-user rollout |
| Art. 9 boundary only in BFF | **High / blocking** without Privacy/Legal decision |
| IaC plan could still alter live env | Must be reviewed; not proven |
| Root Terraform validate pre-existing failure | Environmental; modules validate; root needs generated module copy |
| Full suite 4 failures | Pre-existing/environmental, reproduced on main |
| Route duplication kernel + partner edge | Intentional provenance; validate/tests pass; plan must show additive only |

---

## 9. Branch state

- Integration branch: `integration/xrepo-ris-p0-parallel-fix-01`
- HEAD before this report commit: `a1ef3ca`
- Feature commits: `db5ba54`, `68f9074` (`2dd89be` implementation)
- No main merge, no push to main, no AWS/Terraform/deployment operation.

`XREPO-RIS-P0-PARALLEL-FIX-01 — BLOCKED — SECURITY/PRIVACY REVIEW REQUIRED`
