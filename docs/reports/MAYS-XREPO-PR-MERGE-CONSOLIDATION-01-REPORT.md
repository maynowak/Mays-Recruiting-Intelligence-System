# MAYS-XREPO — PR/MERGE CONSOLIDATION 01

**Status:** `INTEGRATION PREPARED — GO FOR HUMAN MERGE REVIEW`
**NO AUTOMATIC MERGE / NO DEPLOYMENT**
**Date:** 2026-11-09

## Scope

Preparation only: refresh remote baselines, integrate the pushed Jobsearch and
RIS feature branches in isolated worktrees, fix the four Jobsearch CI failures
in `StorageConsentSection.active.test.tsx`, align the RIS audit log/OpenAPI
checks, and update Jobsearch PR #9. No merge to `main`, no push of an
integration branch, no AWS/Vercel mutation, no deployment.

## Baselines and branches

| Repo | Remote `main` | Feature branch head |
| --- | --- | --- |
| Jobsearch | `c3da077` | `e034070` |
| RIS | `f830a5e` | `9c39316` |

Both repositories were fetched with `--prune` before integration. No existing
branch was overwritten and no force-push was used.

## Isolated integration worktrees

| Repo | Worktree | Integration branch | Head at test time |
| --- | --- | --- | --- |
| Jobsearch | `worktrees/integration-jobsearch-p3` | `integration/mays-p3-jobsearch` | `1e6dd34` |
| RIS | `worktrees/integration-ris-p3` | `integration/mays-p3-ris` | `6d123b4` |

- Jobsearch: `--no-ff` merge of `origin/feature/jm-ris-cv-storage-integration-01`
  into `origin/main`; no conflicts.
- RIS: `--no-ff` merge into `origin/main`; one conflict in
  `docs/AI_AUDITLOG.md`, resolved by retaining both sides in full. Integration
  fixes were then cherry-picked: installer overlay allowlist and a whitespace-
  tolerant Terraform contract assertion.

## Jobsearch CI fix

The four failing tests in `StorageConsentSection.active.test.tsx` rendered
`AccountErasureAction`, which called `useAuth()` outside an `AuthProvider`.
The component is now rendered only when `VITE_RIS_ACCOUNT_ERASURE_ENABLED` is
true, and the token access is defensive. The four target tests pass.

| Check | Result |
| --- | --- |
| Targeted consent/erasure tests | **14 passed** |
| Full Jobsearch suite | **1645 passed**, 5 skipped |
| Production build | **PASS** |
| PR #9 checks at `e034070` | CodeQL **SUCCESS**, Vercel previews **SUCCESS**, merge state **CLEAN** |

PR #9 remains open on `feature/jm-ris-cv-storage-integration-01`; checks are
green. The PR body is updated to describe the full P3 branch. No auto-merge.

## RIS checks

| Check | Result |
| --- | --- |
| Privacy/erasure/OpenAPI focused | **111 passed** |
| Full suite (`tests --ignore=tests/integration`) | **2568 passed**, 17 skipped |
| Baseline comparison on `origin/main` | same **6** pre-existing failures |
| `terraform fmt -check -recursive` | **PASS** |

The 6 failures are reproduced on unmodified `origin/main`: composite lifecycle
argument ordering (3), health-plane entitlement denial (1), lambda packaging
exclusions (1), and agent API execution (1). No new failure was introduced by
the integration.

OpenAPI: the platform contract tests pass. The new partner-edge
`POST /v1/partner/me/erasure` route is not part of the platform OpenAPI route
inventory; the kernel `/me/erasure` lifecycle remains documented. No OpenAPI
drift was introduced. The RIS audit log retains both the `origin/main` and
feature-branch entries.

## Privacy and production boundaries

- Account erasure remains default-off/pilot-scoped; no feature flag changed.
- No real user or operator data was deleted.
- RIS state remains serial **61**; production Jobsearch remains `dpl_6DiP...`.
- S3 object versions, backups/PITR and physical purge remain explicitly
  unclaimed.
- No merge, deployment, AWS/Terraform apply, Vercel mutation or force-push.

## Recommendation

**GO for human merge review.** PR #9 is CI-green and mergeable for Jobsearch;
the RIS integration branch is test-clean with only the six pre-existing
baseline failures. **NO-GO for automatic merge or deployment** — both require
separate human approval.
