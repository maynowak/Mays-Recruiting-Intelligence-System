# RIS-CONSENT-IAC-ALIGNMENT-01 — Report

**Status:** IMPLEMENTED / VERIFIED LOCAL — **NO AWS, NO PLAN, NO APPLY, NO DEPLOY**
**Date:** 2026-11-25
**Branch:** `feature/ris-consent-iac-alignment-01`
**Base:** `origin/main` `97a60df83a5db56ea750e4342d7a01b00c8ad56b`
**Scope:** RIS only. No Jobsearch, AWS, Terraform state, consent activation or
legal-policy change.

---

## 1. Problem

`lambda/handler.py` and `jobsearch/consent_contract.py` read four enforcement
variables that `terraform/modules/lambda` did not declare or wire:

```text
CV_STORAGE_CONSENT_ENFORCED
SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED
CONSENT_NOTICE_STATE_ENFORCED
CONSENT_PILOT_ALLOWLIST
```

`APPLICATION_CONSENT_ENFORCED` was wired. The wiring exists on the unmerged
pilot branch (`a0f16a8`, `feature/jm-ris-cv-storage-integration-01`) but not on
`main`. A routine apply from a `main` checkout therefore planned the removal of
the live environment keys (or their reset to `false`), which weakens
enforcement without any code change. Additionally, the runtime parser treated
*any* value other than `"true"` as `"false"`, so a typo or an empty injected
value silently disabled a legal gate.

## 2. Changes

### 2.1 Terraform wiring

Root (`terraform/variables.tf`) and Lambda module
(`terraform/modules/lambda/variables.tf`) now declare:

| Variable | Type | Default | Notes |
|---|---|---|---|
| `cv_storage_consent_enforced` | bool | `false` | CV create/upload/complete/update |
| `search_profile_storage_consent_enforced` | bool | `false` | manual/CV/ATS search-profile writes |
| `consent_notice_state_enforced` | bool | `false` | only `APPROVED`/`ACTIVE` grantable |
| `consent_pilot_allowlist` | string | `""` | `<issuer>\|<sub>`, `sensitive = true`, format-validated |

`terraform/main.tf` passes all four to `module.lambda`. The Lambda environment
now contains exactly this mapping:

| Terraform variable | Lambda env | Value expression |
|---|---|---|
| `application_consent_enforced` | `APPLICATION_CONSENT_ENFORCED` | `var… ? "true" : "false"` |
| `cv_storage_consent_enforced` | `CV_STORAGE_CONSENT_ENFORCED` | `var… ? "true" : "false"` |
| `search_profile_storage_consent_enforced` | `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | `var… ? "true" : "false"` |
| `consent_notice_state_enforced` | `CONSENT_NOTICE_STATE_ENFORCED` | `var… ? "true" : "false"` |
| `consent_pilot_allowlist` | `CONSENT_PILOT_ALLOWLIST` | `var.consent_pilot_allowlist` |

No literal `"true"` is assigned to any of these keys; every value derives from
a declared variable. This is asserted by the new static tests.

### 2.2 Fail-closed plan guards

`terraform/modules/lambda/main.tf` (`aws_lambda_function.agent`) gained two
`lifecycle.precondition` blocks:

1. Any active storage gate requires `consent_notice_state_enforced = true`.
   Otherwise a DRAFT notice could be granted while storage writes are gated —
   a contradictory policy that the plan now refuses.
2. `cv_storage_consent_enforced` / `search_profile_storage_consent_enforced`
   require a non-empty `consent_pilot_allowlist`. These gates are pilot-scoped;
   an empty allowlist would silently widen them to every partner user (a
   general-rollout decision, not a typo side effect).

The allowlist variable additionally rejects malformed entries at plan time.
The runtime intentionally *ignores* malformed entries (it can never widen
scope), so a typo would otherwise silently shrink the pilot scope.

### 2.3 Installer

`PROJECT_CONFIG_ALLOWED_KEYS` now permits the three site booleans
(`cv_storage_consent_enforced`, `search_profile_storage_consent_enforced`,
`consent_notice_state_enforced`). `consent_pilot_allowlist` is deliberately
**not** an overlay key: its identity values must come from a protected
plan-time var file (0600) and must never be committed. `ris-dev.json` was not
changed and contains no consent values.

### 2.4 Runtime parser

`jobsearch/consent_contract.py`:

- `ENFORCEMENT_FLAG_NAMES` lists the four switches.
- `enforcement_flag(name, default=False)`:
  - unset → documented default (`false`; backwards-compatible install);
  - `"true"`/`"false"` (trimmed, case-insensitive) → that value;
  - any other value (including empty, `1`, `yes`, `ture`) → **`True`** plus an
    ERROR log. A broken deployment value cannot disable a gate.
- `notice_state_enforced()` uses it.
- `handler._consent_enforced`, `_cv_storage_consent_enforced`,
  `_search_profile_storage_consent_enforced` use it.

## 3. Art. 9 / special-category analysis (OPEN)

RIS validates Art. 9 proof technically (`validate_consent_proof`), but for
`cv-storage` a grant with only `purpose` + `noticeVersion` is accepted and
stored as `specialCategoriesConsent=false`, `specialCategories=[]`. The
Jobsearch BFF requires an explicit Art. 9 consent for CV data.

Consequence: **RIS does not independently prove Art. 9 consent for CV
contents.** The partner is currently the only Art. 9 gate. This is documented
in `docs/contracts/CONSENT-V1.md` §9c and marked **OPEN — Privacy/Legal
decision required**:

- **Option A:** RIS enforces Art. 9 for `cv-storage` (and later
  `search-profile-storage`) with the purpose-specific text and a new error
  contract.
- **Option B:** the partner remains the sole Art. 9 boundary; this must be an
  explicit, audited trust boundary.

No policy, registry, notice text or handler behaviour was changed for this
question.

## 4. Documentation and registry parity

`docs/contracts/CONSENT-V1.md` was reconciled with the actual registry:

| Purpose | Version | State | Legal reference |
|---|---|---|---|
| `application-storage` | `1.0` | `APPROVED` | `JM-APPLICATION-STORAGE-V4-PILOT-2026-11-08` |
| `cv-storage` | `1.0` | `APPROVED` | `JM-CV-STORAGE-V1-BETA-2026-11-08` |
| `search-profile-storage` | `1.0` | `APPROVED` | `JM-SEARCH-PROFILE-STORAGE-V1-2026-11-08` |
| `analysis-processing` | `1.0` | `DRAFT` | none |

Also documented: proof fields, `404 UNKNOWN_PURPOSE` vs `422
INVALID_NOTICE_VERSION`/`NOTICE_NOT_ACTIVE`, the five 403 gate codes,
pilot-allowlist semantics, enforcement variables/defaults, plan guards and the
Art. 9 gap. `APPROVED` continues to mean “approved for the limited
pilot/beta”, never a general rollout.

`docs/api/openapi-platform.yaml`:

- `ConsentPurpose` enum matches the registry (four purposes).
- `ConsentSpecialCategory` enum matches the nine canonical codes.
- Consent list/history query params use the schema ref.
- Unknown purpose is `404 UNKNOWN_PURPOSE` for list/grant/withdraw/history.
- Grant documents `specialCategoriesConsent`, `specialCategories`,
  `externalTextVersion`, `externalTextSha256`; responses distinguish 404/409/422.
- Withdraw documents `409 NOT_GRANTED`.

`docs/api/API-STANDARD.md`: consent route codes corrected and a new
§2.1.2 “Consent-Zwecke und Gates” added.

## 5. Tests

New:

- `tests/test_consent_flag_fail_closed.py` — unset/valid/invalid values for all
  four switches; invalid values deny ApplicationV1, CV and search-profile
  writes; invalid notice-state enforcement rejects a DRAFT grant.
- `tests/test_consent_iac_alignment.py` — static parity between runtime reads,
  Lambda env, root/module variables and root module call; safe defaults; no
  hard-coded enforcement; preconditions; sensitive/validated allowlist;
  installer overlay rules and absence of committed values.
- `tests/test_consent_purpose_registry_parity.py` — purpose/version/state/legal
  reference parity; OpenAPI enum, 404 semantics and proof schema; contract-doc
  coverage.

Results:

```text
python3 -m pytest tests/test_consent_flag_fail_closed.py \
  tests/test_consent_iac_alignment.py \
  tests/test_consent_purpose_registry_parity.py -q
# 36 passed, 103 subtests passed

Focused consent/OpenAPI/installer batch:
# 275 passed, 421 subtests passed
```

Full suite: see §7 (result appended after the run).

## 6. Terraform checks (local, no backend, no AWS)

```text
terraform fmt -check -recursive terraform/                PASS
terraform init -backend=false + validate, modules/*       15/15 PASS
  (agent_transport, analysis_runtime, api, cloudtrail, cognito, documents,
   dynamodb, health_plane, health_public, iam, lambda, monitoring,
   orders_reader, partner_edge, sqs)
root validate                                              PASS against a
  temporary copy with a stub for the gitignored generated
  `modules/mays_orders` (the checkout's stale generated module lacks
  `iam_handler_role_name`; this is pre-existing and unrelated)
```

No `terraform plan`, no backend, no state, no AWS identity, no apply.

## 7. Full suite

```text
python3 -m pytest tests/ -q
# 4 failed, 3230 passed, 129 skipped, 544 subtests passed (53.99 s)
```

Failures are environment-only and unrelated to this change:

- `tests/test_composite_lifecycle.py` (3) — installer/orchestrator fixture
  expectations in this checkout;
- `tests/test_lambda_packaging.py::test_c_exclusions` (1) — the deployment
  bundle `terraform/lambda.zip` is not built in this worktree.

No failure touches the consent registry, parser, Terraform wiring or docs.

## 8. Boundaries

- No AWS CLI/SDK, no plan/apply, no state/backend, no deployment.
- No consent activation; all defaults remain `false`/empty.
- No real personal data and no allowlist values in Git.
- No legal-approval language inferred; Art. 9 remains an open Privacy/Legal
  decision.
- No main merge, no force-push, no branch deletion.

## 9. Expected integration conflicts with the erasure branch

`feature/ris-erasure-partner-route-alignment-01` (`db5ba54`) touches:

- `lambda/handler.py` — adds a partner erasure dispatch and route-only code.
  Low textual conflict risk with the consent functions; any conflict is
  additive.
- `terraform/modules/api/main.tf` + `terraform/modules/partner_edge/main.tf` —
  route additions only; this branch does not touch those modules.
- `docs/api/openapi-platform.yaml` — adds `/v1/partner/me/erasure` (and the P20
  route inventory). This branch changes consent operations and component
  schemas. Likely auto-merge; if Git aligns both near partner paths, keep both
  changes.
- `docs/api/API-STANDARD.md` — erasure adds a partner-table row and docs near
  the partner section; this branch edits the consent rows and inserts §2.1.2.
  **Expected textual conflict**; keep both, and do not lower the route count.
- `docs/AI_AUDITLOG.md` — both append at EOF. **Expected conflict**; keep both
  entries.
- No overlap in `terraform/variables.tf`, `terraform/modules/lambda/*` or the
  consent registry.

The unreleased pilot wiring branch (`feature/jm-ris-cv-storage-integration-01`,
`a0f16a8`/`d04afbb`) is the source of the ported variables. If both branches
are merged, prefer this branch's variable blocks (validation, sensitive flag,
plan guards) and keep the pilot tests from the older branch.

## 10. Required follow-up approvals

1. Privacy/Legal decision on the Art. 9 `cv-storage` gap (§3).
2. A separately approved plan that supplies the intended live values from a
   protected var file; the plan must show **no** unexpected consent-key
   removal and **0 destroy / 0 replace**.
3. Any actual enforcement activation (global or per-pilot identity) as its own
   explicit operator decision.
