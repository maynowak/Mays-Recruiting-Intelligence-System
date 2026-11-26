# RIS-P0-SECURITY-GATE-03 — CONSENT ENFORCEMENT, ERASURE & DEPLOYMENT SAFETY

**Status: READY FOR P0 SECURITY REVIEW**

- Repository: `maynowak/Mays-Recruiting-Intelligence-System`
- Base: `integration/xrepo-ris-p0-lifecycle-02` at `8d15c82`
- Work branch: `feature/ris-p0-security-gate-03`
- Implementation commit: `e370567`
- No main merge, no deployment, no Terraform plan/apply, no AWS mutation and
  no real erasure or real user data.

## 1. Preflight

- Read `AGENTS.md` and `docs/AI_AUDITLOG.md`.
- Verified `origin/main` `97a60df` and the P0 integration head `8d15c82`.
- Reused the existing erasure route/lifecycle and consent-IaC work; no
  duplicate implementation.
- Created the worktree from `8d15c82` with the new branch
  `feature/ris-p0-security-gate-03`.
- No other worktree, branch or production value was overwritten.

## 2. Art. 9 enforcement for `cv-storage`

The existing contract already supported an explicit Art. 9 proof, but a new
`cv-storage` grant without proof was accepted and stored as
`specialCategoriesConsent=false`. This gate closes that gap.

Implemented in `jobsearch/consent_contract.py`:

- `SPECIAL_CATEGORY_REQUIRED_PURPOSES = frozenset({"cv-storage"})`.
- Every new `cv-storage` grant must provide:
  - `specialCategoriesConsent=true`;
  - a non-empty, duplicate-free subset of the stable Art. 9 codes;
  - `externalTextVersion=cv-storage-consent-2026-11-08-v1`;
  - `externalTextSha256=2fe65fd158a3a2953cf3869ff864aae626971012d68cfb8849db84e04579d036`.
- Missing proof → `422 SPECIAL_CATEGORIES_REQUIRED`.
- Explicit Art. 9 consent without external text → `422
  EXTERNAL_TEXT_REQUIRED_FOR_SPECIAL_CATEGORIES`.
- Wrong/historical/purpose-foreign text → the existing `422
  EXTERNAL_TEXT_NOT_ART9` / external-text code.
- Existing rows without proof are **not migrated, upgraded or inferred**.
  Reads and withdrawal remain available.
- `search-profile-storage` remains ordinary profile metadata and does not
  require Art. 9 consent.

This mirrors the already-approved `cv-storage` v1 notice and Jobsearch BFF
proof contract. It does not create a new legal basis.

Negative tests added at contract, repository and handler level:

- missing `specialCategoriesConsent`;
- consent without external text;
- application-storage text used for cv-storage;
- repository grant leaves no row after rejection;
- legacy row without proof remains readable and withdrawable;
- HTTP route returns `422 SPECIAL_CATEGORIES_REQUIRED`.

## 3. Consent / notice deployment safety

Compared:

- Terraform root and Lambda-module variables;
- Lambda environment wiring;
- installer overlay rules;
- consent registry and notice states;
- documented plan preconditions.

Existing protections retained:

- All enforcement variables are wired from Terraform variables, never
  hard-coded `true`.
- Defaults remain `false`; no enforcement is enabled by this branch.
- `consent_pilot_allowlist` is `sensitive`, format-validated and not an
  installer-overlay key.
- Plan preconditions:
  - any storage gate requires `consent_notice_state_enforced=true`;
  - `cv_storage_consent_enforced` / `search_profile_storage_consent_enforced`
    require a non-empty allowlist.

Known live-vs-default diff (recorded from prior evidence, **not re-read in
this run** because no AWS access was authorized):

| Variable | Branch default | Recorded live `ris-dev` | Effect of a defaults-only plan |
| --- | --- | --- | --- |
| `CV_STORAGE_CONSENT_ENFORCED` | `false` | `true` | would disable the pilot gate |
| `SEARCH_PROFILE_STORAGE_CONSENT_ENFORCED` | `false` | `true` | would disable the pilot gate |
| `CONSENT_NOTICE_STATE_ENFORCED` | `false` | `false` | unchanged, but conflicts with the new precondition when the live gates are supplied |
| `CONSENT_PILOT_ALLOWLIST` | `""` | non-empty (value withheld) | would clear the pilot scope |
| `APPLICATION_CONSENT_ENFORCED` | `false` | not independently re-read | plan must verify; no value changed here |

Consequence: there is currently **no safe plan from this branch alone**:

- supplying the recorded live values violates the
  notice-state precondition;
- omitting them would disable CV/search enforcement and clear the allowlist.

This is an activation/migration decision, not a code-only fix. The plan and
environment diff are therefore **PENDING AUTHORIZATION**.

## 4. Installer — protected variables

Implemented:

- New repeatable `--var-file` CLI option.
- Validation before any AWS/Terraform call:
  - path exists;
  - regular file, no symlink;
  - readable;
  - no group/other permission bits (0600 or stricter);
  - resolved absolute path is forwarded.
- `-var-file` is passed before ordinary `-var` values, so project identity and
  explicit non-sensitive values still win.
- `consent_pilot_allowlist` is refused on `--var` and in the overlay.
- `_redact_command` hides both `-var` values and `-var-file` paths.
- The file content is never read, copied or logged by the installer.
- `plan`, `apply`, `destroy` and `install` paths forward the protected file.

Synthetic tests cover missing/unreadable/world-readable files, symlinks,
sensitive `--var` rejection, absolute path resolution, command ordering and
log redaction.

## 5. Erasure regression

Re-ran the existing P0 protections without any real deletion:

- partner erasure route;
- search-profile erasure;
- CVDocument metadata erasure after S3 success;
- partner/tenant/issuer isolation;
- idempotency and repeatability;
- application erasure scope;
- `withdraw` without active consent → documented `409`.

Result: **75 passed**. No AWS call and no deletion.

## 6. Terraform validation

| Check | Result |
| --- | --- |
| `terraform fmt -check -recursive` | PASS |
| Root `terraform init -backend=false` | PASS |
| Root `terraform validate` | FAIL — pre-existing `module.mays_orders[0].iam_handler_role_name` missing |
| Parent `8d15c82` root validate | same failure |
| `modules/lambda` validate | PASS |
| `modules/api` validate | PASS |
| `modules/partner_edge` validate | PASS |

The root failure exists on the parent baseline and is not introduced by this
branch. No state, backend migration, plan or apply was executed.

## 7. Tests

Focused:

| Suite | Result |
| --- | --- |
| Consent / cv-storage contract | 144 passed / 103 subtests |
| Art. 9 contract + repository + handler | 50 passed |
| Installer / consent IaC / overlay / deployment unblock | 86 passed / 24 subtests |
| Erasure / privacy / isolation | 75 passed |
| Consent gates / fail-closed / surface / application security | 33 passed / 60 subtests |

Full suite:

- **3392 passed / 129 skipped / 18 environment failures**
- Parent baseline `8d15c82`: **3381 passed / 129 skipped / 18 failures**
- No new failures. The 18 failures are the documented wrapper/composite
  argument-order group plus the missing `terraform/lambda.zip` artifact.

`git diff --check` and secret scan: PASS. No real allowlist value, secret or
credential is present.

## 8. Open blockers and required approvals

### Privacy/Legal

- Confirm the legal basis and controller/processor responsibility for
  Art. 9 special-category data in durable CVs.
- Confirm handling of legacy `cv-storage` consents that were granted without
  explicit proof. No automatic migration is performed.

### Deployment / AWS

- Explicit decision on the live consent/notice activation model and the
  recorded `CV=true` / `SEARCH=true` / `NOTICE=false` / allowlist combination.
- Fresh authorized plan against the deployed `ris-dev` lineage.
- Plan review must show:
  - 0 delete;
  - 0 replace;
  - no unexpected IAM expansion;
  - no removal of existing consent environment variables;
  - no enforcement weakening;
  - no accidental pilot deactivation.
- Synthetic live E2E after any apply.

### Security review

- Confirm that the `cv-storage` Art. 9 requirement matches the approved
  partner contract.
- Confirm the protected `--var-file` operational process (0600, no secrets in
  logs/reports).

## 9. Branch and status

- Branch: `feature/ris-p0-security-gate-03`
- Implementation commit: `e370567`
- Base: `8d15c82`
- No main merge, no force-push, no branch deletion.

**READY FOR P0 SECURITY REVIEW**

The technical local implementation is complete. Legal confirmation, the live
consent/notice activation decision and a fresh authorized Terraform plan
remain required before any rollout.
