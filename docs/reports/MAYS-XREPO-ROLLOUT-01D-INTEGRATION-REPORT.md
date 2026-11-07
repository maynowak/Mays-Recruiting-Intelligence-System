# MAYS-XREPO-ROLLOUT-01D — Branch Reconciliation & Integration Readiness

## Status

`READY FOR CONTROLLED PUSH`

Both feature branches are locally reconciled with the current `origin/main`,
their XRepo tests pass, and the known Vercel root cause is fixed on `main` and
included in the reconciled branches. **Nothing was pushed, merged, deployed, or
dispatched.**

## 1. Baselines

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Branch | `feature/mays-xrepo-orchestration-01` | `feature/mays-xrepo-orchestration-01` |
| HEAD before reconciliation | `0ab510a` | `2bcfd77` |
| `origin/main` before | `7a3d2ea` | `c28c668` |
| `origin/main` current | `a2225c4` | `fdc6fc9` |
| Merge commit | `bd2c406` | `654db0a` |
| Behind `origin/main` after | 0 | 0 |
| Local commits ahead of `origin/feature/...` | 12 (unpushed) | 43 (unpushed) |

The feature branches were reconciled with a normal `git merge origin/main`.
No rebase, force-push, or merge to `main` occurred.

## 2. Conflicts and resolutions

Only one file conflicted in each repository: `docs/AI_AUDITLOG.md`.

- Cause: both the XRepo work and the advanced `origin/main` appended/prepended
  audit entries at the same location.
- Resolution: kept both sides in full. The XRepo entries and the new main
  entries are both present.
- Verification:
  - Jobsearch contains the XRepo audit entries and main entries such as
    `JM-RIS-VERCEL-SAFE-RELEASE-05`.
  - RIS contains the XRepo entries and main entries such as
    `RIS-PARTNER-USER-CONSENT-02-PROD-E2E`.
- No product code, API, Terraform, workflow, or xrepo file was overwritten.

## 3. Change surface after reconciliation

`git diff --name-status origin/main...HEAD` contains only:

- `.github/workflows/xrepo-send.yml`
- `.github/workflows/xrepo-receive.yml`
- `scripts/xrepo/*` (validator, builder, receiver, tests, runner)
- `docs/xrepo/*` (contract, schema, fixtures)
- XRepo reports and `docs/AI_AUDITLOG.md`

No product code/API/Terraform/AWS/Cognito/CloudFront/Vercel configuration or
Mays-Orders file is changed.

## 4. Local verification

| Repository | Tests | FAIL | SKIP | JSON/YAML/diff |
| --- | --- | --- | --- | --- |
| Jobsearch | 69 PASS | 0 | 0 | PASS |
| RIS | 69 PASS | 0 | 0 | PASS |

Command: `./scripts/xrepo/run_local_qa.sh` in both repositories.

## 5. Vercel finding — `RESOLVED` (root cause), preview re-run not executed

The previous preview failures were **not build failures**. They failed at the
output/deployment stage with:

- `errorCode`: `exceeded_serverless_functions_per_deployment`
- `errorStep`: `patchBuild`
- `errorMessage`: “No more than 12 Serverless Functions can be added to a
  Deployment on the Hobby plan.”
- Affected deployments:
  - `dpl_CdTNAN1LuNcFGUfMPVtPuMZTq6M3`
  - `dpl_4mPQkgVyNvUQuJqAWn7e9WFhdsWR`

Main contains the fix:

- Commit `40356e6` — “feat(ris): consolidate BFF into one Vercel function”.
- Production deployment `dpl_uAqHQqbs3yDYY6gkqqx3xaoA843Y` at `a2225c4` is
  `READY`, with commit message “Function-limit fix deployed (12 functions)”.
- Current route count under `api/` (excluding `api/_lib`) is **12**.

The reconciled Jobsearch branch now includes `a2225c4`. The known root cause is
therefore resolved on `main` and present in the branch. The preview itself was
not re-run because no push/deployment was allowed; actual preview status remains
to be verified during the controlled push.

## 6. Integration checks

| Check | Result |
| --- | --- |
| Both feature branches locally compatible with `origin/main` | **PASS** (0 behind) |
| All XRepo tests pass | **PASS** (69/69 both) |
| GitHub App permissions unchanged | **PASS** (no workflow/secret change; secrets still present in both) |
| Existing app-auth evidence reused | **PASS** (run `42272286516`, success; not re-investigated) |
| PRs prepared for later merge | **LOCAL READY**; remote PRs remain `CONFLICTING` until push |
| Live dispatch | **NONE** |
| Merge to `main` | **NONE** |

## 7. Side effects to expect on the controlled push

- **Jobsearch:** Vercel preview deployment(s) and Vercel commit/preview statuses
  will run. With the 12-function fix they are expected to succeed, but this is
  not yet verified. CodeQL is not expected to run because the changed paths do
  not match its `paths` filter.
- **RIS:** the pre-existing `ci-cd.yml` may trigger a zero-job/0s failure on a
  branch push (observed on the smoke-test branch; runs `42272050582`,
  `42272284039`). No Terraform/AWS job ran. `xrepo-send.yml` is manual-only and
  `xrepo-receive.yml` is `repository_dispatch`-only, so no live dispatch occurs
  from a push.
- No branch deletion, deployment command, or PR merge is part of the push.

## 8. Remaining blockers / recommendation

- A separate explicit push approval is still required.
- After the push, verify:
  1. both PRs become mergeable against the new `main`;
  2. Jobsearch Vercel preview is `READY` with 12 functions;
  3. RIS CI/CD does not perform any Terraform/AWS work.
- Then request the separate controlled-merge approval. Do not merge based on
  this report alone.

## 9. Recovery point

- Local merge commits: Jobsearch `bd2c406`, RIS `654db0a`.
- Report commit: see the commit containing this file (local, unpushed).
- Unpushed branches: `feature/mays-xrepo-orchestration-01` in both repositories.
- Previous app-auth evidence: run `42272286516`.
- No remote state was changed by this task.
