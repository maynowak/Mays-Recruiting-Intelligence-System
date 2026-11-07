# MAYS-XREPO-ROLLOUT-01C — GitHub App Smoke Test

## Result

`PASS` — the GitHub App installation token was created successfully and both
repositories were confirmed through the actual GitHub Actions run
`42272286516`.

The smoke test ran in the **RIS** repository, not Jobsearch. A Jobsearch branch
push was deliberately avoided because the Vercel project is configured to
create preview deployments for branch pushes, which would have violated the
task's “no deployment / avoid unwanted side effects” boundary. The RIS
repository has no Vercel integration; the same app secrets and the same
cross-repository token request were used.

## 1. Test branch and commits

| Item | Value |
| --- | --- |
| Repository | `maynowak/Mays-Recruiting-Intelligence-System` |
| Branch | `test/xrepo-app-auth-smoke-01` |
| Workflow commit | `36e54db` |
| Permission-probe fix commit | `13021ee` |
| Workflow file | `.github/workflows/xrepo-app-auth-smoke.yml` |
| Trigger | `push` on `test/xrepo-app-auth-smoke-01` only |

The workflow was **not** added to Jobsearch. Jobsearch's feature branch was not
pushed during this task.

## 2. Actual GitHub Actions evidence

- Run: https://github.com/maynowak/Mays-Recruiting-Intelligence-System/actions/runs/42272286516
- Run ID: `42272286516`
- Event: `push`
- Conclusion: **success**
- Jobs: `Verify GitHub App installation token and permissions` → success

Actual log lines (no token values):

```text
installation repositories: maynowak/Mays-Recruiting-Intelligence-System,maynowak/mays-jobsearch
issues read PASS: maynowak/mays-jobsearch
issues read PASS: maynowak/Mays-Recruiting-Intelligence-System
contents read PASS: maynowak/mays-jobsearch
contents read PASS: maynowak/Mays-Recruiting-Intelligence-System
Token creation succeeded with requested Contents: write and Issues: read.
No write operation was performed by this smoke test.
App token and private key were not printed.
```

The runner masked the app ID, private key, and installation token. A scan of the
public run log for `ghs_`, `ghp_`, `github_pat_`, and private-key headers found
no credential material.

## 3. PASS/FAIL matrix

| Check | Result | Evidence |
| --- | --- | --- |
| GitHub Actions started | **PASS** | Run `42272286516`, event `push` |
| Installation token created | **PASS** | `Create installation token for both repositories` step succeeded |
| App assignment | **PASS** | `/installation/repositories` returned exactly both repositories |
| Jobsearch reachable | **PASS** | Issues/content probes succeeded |
| RIS reachable | **PASS** | Issues/content probes succeeded |
| Contents write requested and granted | **PASS** | Token step requested `permission-contents: write` and succeeded; GitHub rejects ungranted permissions |
| Issues read requested and granted | **PASS** | Token step requested `permission-issues: read`; issues probes succeeded |
| Secret leak | **NONE** | Masked logs; credential-pattern scan clean |
| API write operations | **NONE** | Only token creation plus GET requests; no repository writes |
| Merge to `main` | **NONE** | Not performed |
| Live dispatch | **NONE** | Not performed |

Note: `Contents: write` was granted at token creation, but the smoke test did
not perform a write operation. “Granted” is evidenced by successful token
creation with the requested permission; an installation without that permission
would reject the request.

## 4. Unwanted side effects

### Jobsearch push avoided

Vercel project `mays-jobsearch` has:

- `gitProviderOptions.createDeployments = enabled`
- `commandForIgnoringBuildStep = null`
- multiple historical branch previews without PRs and with
  `githubDeployment = 1`

A Jobsearch test-branch push would therefore create a Vercel preview
deployment. That is why the smoke test ran in RIS.

### RIS CI/CD side effect

The RIS branch push triggered the pre-existing `.github/workflows/ci-cd.yml`
despite its `branches: [main]` filter. It failed in 0 seconds with zero jobs:

- https://github.com/maynowak/Mays-Recruiting-Intelligence-System/actions/runs/42272050582
- https://github.com/maynowak/Mays-Recruiting-Intelligence-System/actions/runs/42272284039

No job ran, so there was no Terraform/AWS activity. The workflow was not
modified. This appears to be a pre-existing workflow-definition issue and should
be investigated separately.

## 5. Remaining blockers / recommendation

- Jobsearch PR #2 is now `CONFLICTING`/`DIRTY`: `origin/main` advanced from
  `7a3d2ea` to `a2225c4` after the earlier checks. It was already unstable due
  to Vercel preview output failures.
- RIS PR #6 is now `CONFLICTING`/`DIRTY`: `origin/main` advanced from `c28c668`
  to `fdc6fc9`. No merge was attempted.
- No merge, deployment, live dispatch, issue change, secret output, or permission
  expansion was performed.
- Recommendation: the GitHub App authentication is technically verified. Before
  a controlled rollout, reconcile both feature branches with the current
  `origin/main` (normal merge, no force-push), resolve or explicitly accept the
  Vercel preview failure, then obtain the separate rollout/merge approval. Do
  not merge based on this smoke test alone.

## 6. Recovery point

- Test branch: `test/xrepo-app-auth-smoke-01` at `13021ee` (RIS).
- Passing run: `42272286516`.
- Draft PRs: jobsearch #2, RIS #6.
- Prior reports: `MAYS-XREPO-ROLLOUT-01A-EXECUTION_LOG.md`,
  `MAYS-XREPO-ROLLOUT-01B-EXECUTION_LOG.md`.
- This report is committed on the RIS feature branch and copied to the
  workspace.

## 7. Final status

`PASS` for GitHub App authentication. Rollout remains `BLOCKED` pending the
Vercel/approval gates; no merge or live dispatch is authorized.


## 8. Post-run repository drift

After the successful smoke test, both remote default branches advanced:

| Repo | Previous `origin/main` | Current `origin/main` | PR state |
| --- | --- | --- | --- |
| Jobsearch | `7a3d2ea` | `a2225c4` | #2 `CONFLICTING` / `DIRTY` |
| RIS | `c28c668` | `fdc6fc9` | #6 `CONFLICTING` / `DIRTY` |

This drift is unrelated to the app-authentication proof. No merge, rebase,
force-push, or conflict resolution was performed. The feature branches must be
reconciled with the new `origin/main` in a separately approved rollout step.
