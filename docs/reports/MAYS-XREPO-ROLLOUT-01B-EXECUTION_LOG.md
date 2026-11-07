# MAYS-XREPO-ROLLOUT-01B — Execution Log

## Result

`NOT VERIFIED` for the technical app-authentication proof; rollout remains
`BLOCKED`.

Confirmed:

- The private GitHub App `mays-xrepo-orchestration-app` exists (public page returns
  200 and identifies it as a private GitHub App).
- `XREPO_APP_ID` and `XREPO_APP_PRIVATE_KEY` exist in both repositories.
- Both xrepo workflows are configured to use `actions/create-github-app-token`.
- Local tests pass.

Not technically verified:

- That an installation token can be issued for both repositories.
- The effective token permissions.
- The installation-to-repository assignment.

Reason: the app private key exists only as an Actions secret. It is not
available to this local user credential, and GitHub requires a
`workflow_dispatch` workflow to exist on the default branch before it can be
run. Adding such a check directly to the default branch is outside this task's
no-merge/no-deployment boundary.

## 1. Baselines

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Canonical path | `repos/mays-jobsearch` | `repos/Mays-Recruiting-Intelligence-System` |
| Branch | `feature/mays-xrepo-orchestration-01` | `feature/mays-xrepo-orchestration-01` |
| HEAD | `138297e` | `b23635b` |
| `origin/main` | `7a3d2ea` | `c28c668` |
| Working tree | clean | clean |

## 2. App and workflow checks

### App existence

- `https://github.com/apps/mays-xrepo-orchestration-app` → HTTP 200.
- Page content: “`mays-xrepo-orchestration-app` is a private GitHub App.”
- The GitHub REST app endpoint returns 404 for this private app with the
  available user token; this is expected and does not prove absence.

### Secrets

Existence-only check; no values were read, printed, or stored.

| Repository | `XREPO_APP_ID` | `XREPO_APP_PRIVATE_KEY` |
| --- | --- | --- |
| `maynowak/mays-jobsearch` | present (2026-11-06T15:11:28Z) | present (2026-11-06T15:14:24Z) |
| `maynowak/Mays-Recruiting-Intelligence-System` | present (2026-11-06T15:12:48Z) | present (2026-11-06T15:14:22Z) |

### Workflow configuration

Static inspection only:

- Sender requests `Contents: write` + `Issues: read` for the target repository.
- Receiver requests `Contents: read` + `Issues: read` for the source repository.
- Destination issue comments use `${{ github.token }}` (`issues: write`).
- No PAT references were found.

## 3. Technical verification attempts

| Check | Result | Evidence |
| --- | --- | --- |
| App installation token for both repositories | **NOT VERIFIED** | No app JWT/private key available locally. App-authenticated endpoints return 401 with the user token (`/app`, `/repos/.../installation`). |
| Effective token permissions | **NOT VERIFIED** | Requires `GET /installation` with an app/installation token. |
| Installation repository assignment | **NOT VERIFIED** | Requires `GET /installation/repositories` with an installation token. |
| Secret names present | **PASS** | Repository secret metadata lists both names. |
| Workflow uses intended app token | **PASS (static)** | `actions/create-github-app-token@v1` in sender/receiver; scoped permissions as above. |
| Local tests | **PASS** | 69/69 in both repositories. |

The operator-reported manual GitHub check (app installed, both repositories
selected, Contents Read/write, Issues Read-only, Metadata Read-only) is recorded
as context but is not independently reproduced by the API checks above.

## 4. Minimal safe GitHub Actions verification path

Because `workflow_dispatch` only receives events from a workflow file on the
default branch, this check must be added to the default branch (or run by a
trusted operator after the rollout approval) before it can execute. It must not
send a dispatch.

```yaml
name: Verify Cross-Repository App
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - name: Create installation token for both repositories
        id: app
        uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ secrets.XREPO_APP_ID }}
          private-key: ${{ secrets.XREPO_APP_PRIVATE_KEY }}
          owner: ${{ github.repository_owner }}
          repositories: "mays-jobsearch,Mays-Recruiting-Intelligence-System"
          permission-contents: write
          permission-issues: read
      - name: Show installation repositories
        env:
          GH_TOKEN: ${{ steps.app.outputs.token }}
        run: |
          gh api /installation/repositories \
            --jq '[.repositories[].full_name]'
      - name: Show effective permissions
        env:
          GH_TOKEN: ${{ steps.app.outputs.token }}
        run: |
          gh api /installation \
            --jq '.permissions'
```

Expected evidence from that run:

- `mays-jobsearch` and `Mays-Recruiting-Intelligence-System` appear in
  `/installation/repositories`.
- Permissions show `contents: write` and `issues: read` (plus the implicit
  `metadata: read`).
- No token is printed; only repository names and permission keys are shown.

This workflow was **not added** to the repository in this task and was **not
executed**, because it cannot run before being present on the default branch.

## 5. Vercel blocker (separate)

Jobsearch PR #2 remains a draft, `MERGEABLE` / `UNSTABLE`.

- `Vercel Deployments – Maymilly`: FAILURE.
- `Vercel – mays-job-matcher`: FAILURE (`dpl_CdTNAN1LuNcFGUfMPVtPuMZTq6M3`).
- `Vercel – mays-jobsearch`: FAILURE (`dpl_4mPQkgVyNvUQuJqAWn7e9WFhdsWR`).
- Logs: build succeeds, then `Deploying outputs... status ● Error`.
- No Vercel configuration or production deployment was changed.

RIS PR #6 remains a draft, `MERGEABLE` / `CLEAN`.

## 6. Security and boundaries

- No secret values or tokens were printed, logged, or stored.
- No PAT, replacement key, or additional credential was created.
- No permissions were expanded.
- No merge, deployment, live dispatch, product change, infrastructure change, or
  branch/worktree deletion was performed.
- No test issue was created or modified.

## 7. Recovery point

- Draft PRs: jobsearch #2, RIS #6.
- Test issues: jobsearch #3, RIS #7.
- Reports: `MAYS-XREPO-ROLLOUT-01A-EXECUTION_LOG.md`,
  `MAYS-XREPO-APP-SETUP-01-EXECUTION_LOG.md`, and this report.
- Next safe step: run the minimal app verification workflow after default-branch
  placement/rollout approval, then re-run ROLLOUT-01A.

## 8. Final status

`NOT VERIFIED` for app authentication. Rollout is `BLOCKED` until an
app-authenticated installation/permission check and the Vercel/approval gates
are cleared.
