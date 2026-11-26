# RIS-P0-CONSENT-DEPLOYMENT-DECISION-04 — CONSENT ACTIVATION, PRIVACY DECISION & TERRAFORM SAFETY

**Status: READY FOR DEPLOYMENT DECISION**

- Repository: `maynowak/Mays-Recruiting-Intelligence-System`
- Base: `feature/ris-p0-security-gate-03` at `3ff903f`
- Work branch: `feature/ris-p0-consent-deployment-decision-04`
- Worktree: `/home/dci-student/projects/mays-xrepo-orchestration/worktrees/ris-p0-consent-decision-04`
- AWS mode: read-only
- No AWS mutation, no Terraform plan/apply, no state mutation, no main merge,
  no deployment and no real erasure.

## 1. Repository state and preflight

| Item | Value |
| --- | --- |
| RIS `origin/main` | `97a60df` |
| P0 integration | `8d15c82` |
| Security Gate 03 | `3ff903f` |
| This branch | `feature/ris-p0-consent-deployment-decision-04` at `3ff903f` |

Read and considered:

- `AGENTS.md`
- `docs/AI_AUDITLOG.md`
- `docs/reports/RIS-P0-SECURITY-GATE-03-REPORT.md`
- `docs/reports/XREPO-RIS-P0-PARALLEL-FIX-01-REPORT.md`
- `docs/reports/RIS-CONSENT-IAC-ALIGNMENT-01.md`
- `docs/contracts/CONSENT-V1.md`
- Terraform variables/preconditions and installer code.

No already-implemented security correction was repeated.

## 2. Read-only live verification

Authorization was present through the documented `mayaws` read-only profile.
Only read operations were used. No tokens, secrets, allowlist entries, user IDs
or personal data are recorded here.

### 2.1 Identity and state

| Item | Confirmed value |
| --- | --- |
| AWS account | `240571105849` |
| Region | `eu-central-1` |
| Terraform state bucket | `mays-ris-tf-state-dev` |
| State key | `env:/ris-dev/dev/terraform.tfstate` |
| Workspace | `ris-dev` |
| State serial | **83** |
| State lineage | `9cec61e5-c036-1ad5-6ae4-8b48a50122a4` |
| Terraform version in state | `1.16.1` |
| State resources | **271** |
| State last modified | `2026-11-18T14:07:45Z` |

### 2.2 Lambda

| Item | Confirmed value |
| --- | --- |
| Function | `ris-dev-dev-agent` |
| Active version | `$LATEST` |
| State | Active |
| Last modified | `2026-11-17T18:16:03Z` |
| Runtime | `python3.14` |
| Code SHA-256 | matches the state `source_code_hash` |
| Published versions | none |
| Aliases | none |

Environment flags:

| Variable | Live value |
| --- | --- |
| `APPLICATION_CONSENT_ENFORCED` | `true` |
| `CV_STORAGE_CONSENT_ENFORCED` | `true` |
| `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | `true` |
| `CONSENT_NOTICE_STATE_ENFORCED` | **`true`** |
| `CONSENT_PILOT_ALLOWLIST` | present, non-empty, 2 entries; values withheld |
| `PARTNER_SURFACE_ENABLED` | `true` |
| `ERASURE_APPLICATIONS_ENABLED` | `false` |
| `ERASURE_S3_EXECUTION_ENABLED` | `false` |

**Important discrepancy:** the previous report recorded
`CONSENT_NOTICE_STATE_ENFORCED=false`. The current live value is **`true`**.
The historical value is superseded.

### 2.3 API / authorizer

| API | Route | Auth |
| --- | --- | --- |
| `ris-dev-jobsearch-api` `c7e9pdwe78` | `POST /v1/partner/me/erasure` | JWT, authorizer `e6inno` |
| `ris-dev-jobsearch-api` | consent GET/POST/withdraw/history | JWT, authorizer `e6inno` |
| `ris-dev-dev-api` `g6901and25` | `POST /me/erasure` | JWT, authorizer `3hy7kc` |
| `ris-dev-dev-api` | consent GET/POST/withdraw/history | JWT, authorizer `3hy7kc` |

Both APIs use `AWS_PROXY` integrations to
`ris-dev-dev-agent`; the partner and kernel erasure routes are present in
live API Gateway and in Terraform state. Unauthenticated GET probes returned
`401`, not `503` or `5xx`.

### 2.4 Consent table

Table `ris-dev-dev-consents`: 50 current rows, `PAY_PER_REQUEST`, ACTIVE.

| Purpose / status | Count |
| --- | --- |
| `application-storage` GRANTED | 7 |
| `application-storage` WITHDRAWN | 5 |
| `cv-storage` GRANTED | 11 |
| `cv-storage` WITHDRAWN | 3 |
| `search-profile-storage` GRANTED | 16 |
| `search-profile-storage` WITHDRAWN | 8 |
| `analysis-processing` | 0 |

`cv-storage` proof:

- 14 / 14 current rows have `specialCategoriesConsent=true`.
- 14 / 14 carry the approved external text version
  `cv-storage-consent-2026-11-08-v1`.
- 14 / 14 carry the pinned SHA-256
  `2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036`.
- No legacy `cv-storage` row without proof was found in this table.

Adjacent observation, not changed in this task:

- `application-storage`: 7 GRANTED, but only 5 have an explicit Art. 9 proof;
  2 active legacy rows have no proof.
- `search-profile-storage`: proof fields are not Art. 9 (expected for this
  professional-metadata purpose).

### 2.5 Effective enforcement scope

This is critical for the decision:

- `APPLICATION_CONSENT_ENFORCED=true` has **no allowlist boundary** in
  `_application_consent_error`; it gates every user, not only the two
  allowlist entries.
- `CV_STORAGE_CONSENT_ENFORCED=true` and
  `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED=true` are combined with an explicit
  allowlist check in `_cv_storage_consent_error` /
  `_search_profile_storage_consent_error`; non-listed identities receive
  `403 CV_STORAGE_PILOT_NOT_ALLOWED` or
  `SEARCH_PROFILE_STORAGE_PILOT_NOT_ALLOWED`.
- `CONSENT_NOTICE_STATE_ENFORCED=true` is global (`notice_state_enforced()`),
  not allowlist-scoped.

Therefore the current deployment is:

- **CV/search:** limited-pilot scope plus global flag.
- **ApplicationV1:** global consent gate, not a two-user pilot.
- **Notice state:** globally enforced; only APPROVED/ACTIVE notices are
  grantable.

## 3. Consent/notice decision matrix

### Variant A — Preserve current live configuration

Keep `APPLICATION=true`, `CV=true`, `SEARCH=true`, `NOTICE=true` and the
non-empty allowlist. No Terraform change, no plan/apply.

| Dimension | Assessment |
| --- | --- |
| Privacy risk | Lowest of the three: all three storage gates remain active, notice enforcement remains active, Art. 9 required for new `cv-storage` grants. Open: global application gate vs "pilot" wording; 2 legacy application grants without proof. |
| Security effect | No weakening; allowlist remains a CV/search boundary; no IAM, Cognito or CloudFront change. |
| Operational effect | Existing grants remain usable; withdrawal remains available; no migration. `analysis-processing` draft grants remain blocked. |
| Backward compatibility | Existing storage consents are APPROVED and remain valid; no automatic changes. |
| Migration need | None for configuration. Legal decision needed for legacy application rows and consent retention. |
| Approvals | Privacy/Legal, Security, and a separate no-change plan review. |

**Recommended variant: A**, with an explicit confirmation that the global
application-storage gate is intended. Do not lower any gate merely to make the
term "pilot" fit.

### Variant B — Enable notice enforcement

This is **already live** (`CONSENT_NOTICE_STATE_ENFORCED=true`).

| Dimension | Assessment |
| --- | --- |
| Privacy risk | Positive: no DRAFT/SUPERSEDED notice can be granted. |
| Security effect | No weakening. |
| Operational effect | `application-storage`, `cv-storage` and `search-profile-storage` v1 are APPROVED and grantable. `analysis-processing` v1 is DRAFT and rejected for new grants. Withdrawals are unaffected. Re-grants of a superseded historical notice would fail; no such current storage version is live. |
| Backward compatibility | Existing APPROVED grants and withdrawals remain valid. |
| Migration need | None. |
| Approvals | None for the current state; already active. |

If the flag were ever set back to `false`, that would be a weakening and
requires explicit Security/Privacy approval.

### Variant C — End the pilot

Clearing only `CONSENT_PILOT_ALLOWLIST` is **not** a safe way to end the pilot:

- Terraform preconditions reject an empty allowlist while CV/search gates are
  `true`.
- If forced around the guard, CV/search would become global rather than end.
- Ending the pilot requires explicitly setting the CV/search (and possibly
  application) gates to `false`, which weakens enforcement for all users.

| Dimension | Assessment |
| --- | --- |
| Privacy risk | High: storage writes become ungated; existing consent data remains. |
| Security effect | Explicit weakening; requires separate approval. |
| Operational effect | No automatic deletion or migration; existing data stays; users are no longer blocked. |
| Backward compatibility | Existing consents remain; future writes no longer require them. Re-enabling later requires a coherent re-consent plan. |
| Migration need | None automatic; a legal retention/erasure decision is still required. |
| Approvals | Privacy/Legal and Security; separate activation decision. |

**Not recommended** without an explicit end-of-pilot decision.

## 4. Art. 9 decision template for Privacy/Legal

The technical control is implemented, but it does not create a legal basis.

### 4.1 Decision required

1. Is explicit Art. 9 consent, bound to the approved
   `cv-storage-consent-2026-11-08-v1` text and hash, the intended legal basis
   for special-category data in durable CVs?
2. Who is controller/processor for RIS-side CV storage and for the
   Jobsearch BFF boundary?
3. Are the two active `application-storage` grants without Art. 9 proof
   acceptable to retain, or must they be re-consented/withdrawn?
4. How long must consent rows/events be retained after account erasure?
   The erasure lifecycle currently does not delete the consent table or its
   history. A legal retention/anonymisation decision is required.
5. Does the current physical-deletion boundary satisfy the deletion right?
   `ERASURE_S3_EXECUTION_ENABLED=false` and no live erasure run mean no
   physical-purge claim is made here.

### 4.2 Technical behavior already in place

- New `cv-storage` grants require explicit Art. 9 consent, categories and the
  approved text/hash.
- Existing `cv-storage` rows are not migrated or inferred; all 14 current rows
  already satisfy the proof.
- Read and withdrawal paths remain available.
- Jobsearch BFF and RIS now enforce the same proof for new cv-storage grants.

## 5. Terraform / installer safety

The Security-Gate-03 `--var-file` mechanism is present and tested:

- mode 0600 or stricter;
- no symlink;
- readable, regular file;
- absolute path forwarded;
- `-var-file` before `-var`, so project identity wins;
- `consent_pilot_allowlist` rejected via `--var` and overlay;
- path redacted in command logs; contents never read or logged.

Synthetic example only:

```hcl
# /secure/consent-pilot.auto.tfvars  (chmod 600)
consent_pilot_allowlist = "https://issuer.example|synthetic-subject-01"
```

Do not put this file, its values or a real allowlist into Git or reports.

### Future plan prerequisites

No plan was generated. A future authorized plan must demonstrate:

- 0 delete;
- 0 replace;
- no unexpected IAM expansion;
- no removal of `APPLICATION_CONSENT_ENFORCED`,
  `CV_STORAGE_CONSENT_ENFORCED`,
  `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED`,
  `CONSENT_NOTICE_STATE_ENFORCED` or `CONSENT_PILOT_ALLOWLIST`;
- no enforcement weakening or pilot deactivation;
- no Cognito or CloudFront change;
- Lambda code/env and API routes match the intended release;
- state serial/lineage and plan SHA are recorded and reviewed.

A plan is not an apply approval.

## 6. Erasure dependencies

Read-only/live and local checks:

- Partner erasure route `POST /v1/partner/me/erasure` exists with JWT.
- Kernel `POST /me/erasure` exists with JWT.
- Search-profile erasure, CVDocument metadata erasure, partner/tenant/issuer
  isolation, idempotency and withdraw-without-consent `409` are present.
- No real erasure was executed.
- Live `ERASURE_APPLICATIONS_ENABLED=false` disables the legacy application
  deleter; the dedicated `ApplicationErasureExecutor` remains wired.
- Live `ERASURE_S3_EXECUTION_ENABLED=false`; physical S3 purge/retention is not
  verified.
- The consent table and consent history are not deleted by the current
  erasure lifecycle; this is a Privacy/Legal retention decision.
- No consent configuration change in this task affects erasure routes or
  access paths.

## 7. Tests

| Check | Result |
| --- | --- |
| Focused consent/installer/erasure | **224 passed / 103 subtests** |
| Full suite | **3392 passed / 129 skipped / 18 environment failures** |
| Baseline `3ff903f` / `8d15c82` | **3381 passed / 129 skipped / 18 failures** |
| `terraform fmt -check -recursive` | PASS |
| Root `terraform validate` | pre-existing `module.mays_orders[0].iam_handler_role_name` failure; same on parent |
| `modules/lambda` validate | PASS |
| `modules/api` validate | PASS |
| `modules/partner_edge` validate | PASS |
| `git diff --check` | PASS |
| Secret scan | PASS; no real allowlist value or secret |

The 18 failures are the documented wrapper/composite argument-order group and
the missing `terraform/lambda.zip` artifact. No new failure was introduced.

## 8. Open risks

1. **Global application gate vs pilot wording.** `APPLICATION_CONSENT_ENFORCED=true`
   gates every user, while CV/search are allowlist-scoped. This must be
   confirmed as intentional.
2. **Two legacy application-storage grants without proof.** They remain active;
   no migration was performed. Legal disposition required.
3. **Consent retention after erasure.** Consent rows/events are not deleted by
   the current erasure lifecycle.
4. **S3 physical purge.** `ERASURE_S3_EXECUTION_ENABLED=false`; no physical
   purge claim.
5. **No immutable Lambda release.** `$LATEST` is active, with no published
   version or alias. A future apply has no Lambda-version rollback point;
   publish a version/alias or record an equivalent rollback artifact before
   deployment.
6. **No full drift plan.** Lambda code/env and API routes match state; a full
   Terraform drift proof requires a separately authorized plan.

## 9. Recommended decision

**Recommended: Variant A — keep the current live values and do not change or
re-plan them in this task.**

Reasons:

- Current live values already satisfy the Terraform preconditions
  (`CV/SEARCH=true`, `NOTICE=true`, non-empty allowlist).
- It is the only variant that does not weaken enforcement.
- All 14 current `cv-storage` rows already carry the required Art. 9 proof.
- Notice enforcement is already active and only APPROVED storage notices are
  grantable.

Condition: Privacy/Legal and Security must explicitly confirm that the global
application-storage gate is intended, and decide the legacy application rows
and consent-retention questions.

Before any deployment decision, a separate authorized plan review must show
0 delete / 0 replace and no enforcement weakening. This report does not
authorize that plan or any apply.

## 10. Required approvals

- Privacy/Legal: Art. 9 legal basis, controller/processor boundary, legacy
  application rows, consent retention and deletion rights.
- Security: global application gate, allowlist scope, Lambda `$LATEST`
  rollback risk.
- AWS/Terraform: explicit authorization for a fresh `ris-dev` plan; then a
  separate apply approval.
- Synthetic live E2E after any apply: grant/withdraw/regrant, CV/search reads,
  erasure route and consent gates; no real user data.

## 11. Branch / status

- Branch: `feature/ris-p0-consent-deployment-decision-04`
- Base: `3ff903f`
- Report commit: recorded on this branch
- No main merge, no force-push, no branch deletion, no AWS mutation.

**READY FOR DEPLOYMENT DECISION**

The decision basis is complete; activation and Terraform apply remain
unauthorized and require the approvals above.
