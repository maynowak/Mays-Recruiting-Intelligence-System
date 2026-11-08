# RIS-ACCOUNT-ERASURE-SEARCH-PROFILES-01 — Execution Report

**Status:** `IMPLEMENTED / VERIFIED LOCAL`  
**Date:** 2026-11-08  
**Scope:** account erasure of persisted partner search profiles (P3)

No AWS mutation, Terraform apply, deployment, global erasure-flag activation,
Cognito/CloudFront/DNS/ACM change or Mays-Orders change was performed.

## 1. Changed files

- `agents/ecosystem/privacy_erasure.py`
  - new `partner_profile_erasure` collaborator and
    `erase-partner-search-profiles` lifecycle step;
  - identity parameters `partner_application_id` / `issuer` for the step;
  - `searchProfilesDeleted` result field;
  - document phase now distinguishes deletion from an open/pending S3 phase.
- `agents/ecosystem/privacy_profile_erasure.py`
  - new `AccountSearchProfileErasure` adapter and
    `SearchProfileErasureResult`;
  - transient checkpoint sink for one account-erasure invocation;
  - pagination guard.
- `lambda/documents.py`
  - `delete_all_for_user_report()` returns `(deleted, pending)` and keeps
    `delete_all_for_user()` as a compatibility wrapper.
- `lambda/handler.py`
  - constructs the profile adapter from the existing
    `PartnerProfileRepository`;
  - passes verified user/tenant/partner/issuer context;
  - requires `PARTNER_PROFILE_TABLE`;
  - uses the report-returning document deletion path.
- `tests/test_account_search_profile_erasure.py`
  - new synthetic coverage.
- `tests/test_public_application_erasure.py`,
  `tests/test_terraform_plan_reconciliation_06.py`
  - compatibility updates for the new required table and Terraform formatting.

## 2. Reused components

- `PrivacyErasure` (existing G5 lifecycle).
- `ProfileOnlyErasureExecutor` / R08-C1A (existing category ordering,
  pagination, identity-scoped repository calls, conflict handling).
- `PartnerProfileRepository` (existing `list_by_user` / `delete`).
- `ProfileOnlyErasureExecutor`'s ATS → CV-search → manual ordering.
- Existing ApplicationV1 and document erasure collaborators.
- Existing privacy inspect/export contracts (already expose
  `manualSearchProfiles`, `cvSearchProfiles`, `atsSearchProfiles`).

No second deletion engine and no new deletion UI were introduced.

## 3. Implemented deletion logic

For the verified `(user, tenant, partner, issuer)` identity:

1. ATS search profiles (`ATSSearchProfile`) are deleted first.
2. CV search profiles (`CVSearchProfile`) are deleted next, after their ATS
   children.
3. Manual search profiles (`ManualSearchProfile`) are deleted last.

The existing repository performs version-conditioned deletes. Pagination is
bounded; a non-advancing cursor fails closed. An already-deleted item is
treated as an idempotent replay. A version conflict or repository failure keeps
the account-erasure result `complete: false`; a retry re-lists the remaining
items and resumes.

The profile adapter deliberately does **not** delete CVDocument metadata, S3
objects or the UserProfile row; those remain owned by the existing
`PrivacyErasure` document/profile phases. It does not claim completion of those
phases.

## 4. Security properties

- Every repository list/delete receives user, tenant, partner application and
  issuer; tests cover cross-user, cross-tenant, cross-partner and cross-issuer
  isolation.
- Missing identity context fails closed.
- Missing/unavailable profile storage fails closed.
- Version conflicts and concurrent mutations are reported, not swallowed.
- Repeated identical erase calls are idempotent.
- Open S3/document work is now reported as `ok: false` / `documents remain`
  instead of a false success.
- No physical purge of backups/PITR is claimed.

## 5. Tests actually executed

```bash
pytest -q tests/test_account_search_profile_erasure.py
# 14 passed

pytest -q \
  tests/test_privacy_erasure_security.py \
  tests/test_application_erasure.py \
  tests/test_r08_c1a_profile_only_erasure.py \
  tests/test_r08_c1b_document_erasure_integration.py \
  tests/test_r08_c0e_g5_authorization.py \
  tests/test_account_search_profile_erasure.py \
  tests/test_application_privacy_contract.py \
  tests/test_privacy_lifecycle_evidence.py \
  tests/test_privacy_erasure_repository.py \
  tests/test_partner_privacy_inspection.py
# 103 passed

pytest -q tests --ignore=tests/integration
# 2550 passed, 17 skipped, 16 pre-existing failures
```

The 16 full-suite failures are the existing project-config/composite/health/
platform set in this worktree; none concern the erasure path.

## 6. Cross-repository result

Jobsearch currently has only the disabled privacy-action placeholder
(`privacyStorage.actions.erasure`); it does not call `/me/erasure`. No new
deletion UI or client was added, per the task. This remains an integration
follow-up before a user-facing erasure flow can be claimed end-to-end.

The RIS endpoint itself now includes search profiles when the verified partner
identity context is present.

## 7. Open limits

- Deployment of this local change requires a separate reviewed plan/GO.
- Existing S3/document phases may still be pending; no physical purge or
  backup/PITR erasure is claimed.
- Jobsearch's user-facing erasure action remains unwired/disabled.
- General rollout of search-profile storage still requires its own approval.

## 8. Commits

- RIS implementation: `30668ff` — `feat(privacy): erase persisted search profiles on account erasure`
- Report/auditlog: this documentation commit.

