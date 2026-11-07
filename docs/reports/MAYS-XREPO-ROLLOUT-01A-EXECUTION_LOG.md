# MAYS-XREPO-ROLLOUT-01A — Execution Log

## Result

`BLOCKED`

Secrets are present in both repositories and local tests pass, but the GitHub
App installation and its effective permissions cannot be verified with the
available user credential. Both PRs are still drafts and PR #2 is unstable due
to Vercel preview deployment failures. No merge, deployment, or live dispatch
was performed.

## 1. Workspace and baselines

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Canonical path | `repos/mays-jobsearch` | `repos/Mays-Recruiting-Intelligence-System` |
| Branch | `feature/mays-xrepo-orchestration-01` | `feature/mays-xrepo-orchestration-01` |
| HEAD | `13e035f` | `38d0a7e` |
| `origin/main` | `7a3d2ea` | `c28c668` |
| Ahead / behind | 18 / 0 | 16 / 0 |
| Working tree | clean | clean |

## 2. Readiness checks

| Check | Result | Evidence |
| --- | --- | --- |
| GitHub App installed | **NOT VERIFIED** | No app-authenticated credential available. `/app` → 401; `/users/maynowak/installations` → 404; `/repos/{owner}/{repo}/installation` → 401. Candidate public app pages → 404. |
| Both repositories assigned to installation | **NOT VERIFIED** | Requires app-authenticated access to the installation. |
| `XREPO_APP_ID` present | **PASS (existence only)** | Jobsearch: created/updated 2026-11-06T15:11:28Z. RIS: created/updated 2026-11-06T15:12:48Z. |
| `XREPO_APP_PRIVATE_KEY` present | **PASS (existence only)** | Jobsearch: created/updated 2026-11-06T15:14:24Z. RIS: created/updated 2026-11-06T15:14:22Z. |
| Permissions correct | **NOT VERIFIED** | Cannot query installation permissions without an app JWT. Static workflow review matches the contract: sender `Contents: write` + `Issues: read`; receiver `Contents: read` + `Issues: read`; destination issue writes use `GITHUB_TOKEN`. |
| PR #2 mergeable | **NO / UNSTABLE** | OPEN, draft, `MERGEABLE` / `UNSTABLE`; Vercel failures. |
| PR #6 mergeable | **TECHNICALLY YES / NO APPROVAL** | OPEN, draft, `MERGEABLE` / `CLEAN`; no review approval. |
| Local tests | **PASS** | `./scripts/xrepo/run_local_qa.sh` → 69/69 PASS in both repositories; JSON/YAML/diff PASS. |
| Vercel error classified | **PASS (classification)** | Build succeeds; failure occurs at `Deploying outputs... status ● Error`. See section 4. |

## 3. Secret handling

- Only secret **names** and metadata were read.
- No secret values, tokens, private keys, or credential material were printed,
  logged, or stored.
- No alternative PAT or replacement credential was created.
- `XREPO_APP_ID` and `XREPO_APP_PRIVATE_KEY` exist in both repositories, but
  their values were not accessed.

## 4. Vercel error classification (Jobsearch PR #2)

Latest checks for head `13e035f`:

- `Vercel Deployments – Maymilly`: FAILURE.
- `Vercel – mays-job-matcher`: FAILURE (`dpl_CdTNAN1LuNcFGUfMPVtPuMZTq6M3`).
- `Vercel – mays-jobsearch`: FAILURE (`dpl_4mPQkgVyNvUQuJqAWn7e9WFhdsWR`).
- Build logs for both deployments show `npm run build` and Vite completing,
  followed by `Deploying outputs...` and `status ● Error`.
- Classification: **post-build deployment/output failure**, not a TypeScript,
  Vite, or xrepo test failure.
- No Vercel configuration or production deployment was changed by this task.

## 5. Why the result is BLOCKED

1. The app installation and effective permissions are not independently
   verifiable from the available user credential. Secret existence alone does
   not prove installation, repository assignment, or granted permissions.
2. PR #2 is not stable because of Vercel preview output failures.
3. Neither draft PR has an explicit review/rollout approval.
4. No live dispatch is permitted before these prerequisites are cleared.

## 6. Required next steps

1. Verify the app with an app-authenticated check:
   - installation ID exists;
   - both repositories are in `/installation/repositories`;
   - `Contents: read/write` and `Issues: read` are granted;
   - no additional permissions.
2. Confirm the app is installed only on the intended repositories.
3. Resolve or explicitly accept the Vercel preview failure for PR #2.
4. Obtain explicit rollout approval.
5. Re-run `MAYS-XREPO-ROLLOUT-01A`; only then can the result become `READY`.
6. Do not merge, deploy, or dispatch before that approval.

## 7. Recovery point

- Draft PRs: jobsearch #2, RIS #6.
- Test issues: jobsearch #3, RIS #7.
- Prior reports: `MAYS-XREPO-E2E-01-EXECUTION_LOG.md`,
  `MAYS-XREPO-APP-SETUP-01-EXECUTION_LOG.md`.
- This report is committed in both repositories.

## 8. Final status

`BLOCKED`

No merge, deployment, live dispatch, infrastructure change, branch deletion, or
secret-value disclosure was performed.
