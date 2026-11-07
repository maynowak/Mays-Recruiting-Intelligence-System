# MAYS-XREPO-APP-SETUP-01 — Execution Log

## Status

`BLOCKED FOR LIVE`
The GitHub App and both required secrets are not present/verifiable. No live
dispatch, merge, deployment, or infrastructure change was performed.

## 1. Repository baselines

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Canonical path | `repos/mays-jobsearch` | `repos/Mays-Recruiting-Intelligence-System` |
| Branch | `feature/mays-xrepo-orchestration-01` | `feature/mays-xrepo-orchestration-01` |
| HEAD | `67913ec` | `438fa4f` |
| `origin/main` | `7a3d2ea` | `c28c668` |
| Ahead / behind | 17 / 0 | 15 / 0 |
| Working tree | clean | clean |

All work and checks were performed under
`/home/dci-student/projects/mays-xrepo-orchestration`.

## 2. Step 01 — Preflight

- Jobsearch PR #2: OPEN, **draft**, `MERGEABLE` / `UNSTABLE`, head `67913ec`.
- RIS PR #6: OPEN, **draft**, `MERGEABLE` / `CLEAN`, head `438fa4f`.
- Jobsearch issue #3: OPEN (`MAYS-XR-E2E-001`, A/source).
- RIS issue #7: OPEN (`MAYS-XR-E2E-001`, B/destination).
- Both repositories contain `xrepo-send.yml` and `xrepo-receive.yml`.
- Existing workflows `codeql.yml` (Jobsearch) and `ci-cd.yml` (RIS) are unchanged.
- Local QA at preflight: **69/69 PASS** in both repositories.

## 3. Step 02 — App configuration check

### Required configuration (from the existing contract)

| Setting | Required value |
| --- | --- |
| App name | `Mays Cross-Repository Orchestrator` |
| Installation owner | `maynowak` only |
| Repository access | Only `maynowak/mays-jobsearch` and `maynowak/Mays-Recruiting-Intelligence-System` |
| Contents | Read and write |
| Issues | Read-only |
| Actions / Administration / Workflows | None |
| Webhooks | None |

The sender requests `Contents: write` + `Issues: read`; the receiver requests
`Contents: read` + `Issues: read`. Destination issue comments use the receiver's
own `GITHUB_TOKEN` with `issues: write`. This matches the contract.

### Current state

- No configured GitHub App can be verified with the available user token.
- `GET /app` → 401 (`A JSON web token could not be decoded`), as expected without an app JWT.
- `GET /users/maynowak/installations` → 404 with the current user token.
- Candidate public app URLs returned 404 (private apps also return 404 when unauthenticated):
  - `/apps/mays-cross-repository-orchestrator`
  - `/apps/mays-xrepo-orchestration`
  - `/apps/mays-xrepo-orchestrator`
- Conclusion: app creation/installation is **not confirmed**.

### Manual setup steps

1. Create a GitHub App named `Mays Cross-Repository Orchestrator` under `maynowak`.
2. Set repository access to only `mays-jobsearch` and `Mays-Recruiting-Intelligence-System`.
3. Grant repository permissions: `Contents: Read and write`, `Issues: Read-only`.
4. Grant no Actions, Administration, Workflows, or other permissions.
5. Disable webhooks.
6. Install the app on both repositories.
7. Add the two secrets from Step 03 to both repositories.
8. Re-run this preflight and verify installation/permissions with an app-authenticated check.

## 4. Step 03 — Secrets check

Existence-only check; no values were read, printed, or stored.

| Repository | `actions/secrets.total_count` | `XREPO_APP_ID` | `XREPO_APP_PRIVATE_KEY` |
| --- | --- | --- | --- |
| `maynowak/mays-jobsearch` | 0 | absent | absent |
| `maynowak/Mays-Recruiting-Intelligence-System` | 0 | absent | absent |

- No `XREPO_APP_ID` / `XREPO_APP_PRIVATE_KEY` in the shell environment either.
- No alternative PAT or replacement credential was created.
- The repository owner must add both secrets manually in each repository.

## 5. Step 04 — Credential/permission verification

| Check | Result |
| --- | --- |
| Installation exists | NOT VERIFIED — user token cannot list app installations |
| Both repositories assigned | NOT VERIFIED |
| Permissions match contract | NOT VERIFIED — no app token available |
| Both secret names exist | FAIL — 0 secrets in both repositories |
| Sender/receiver use app tokens | PASS by static workflow inspection |
| No unnecessary permissions/PATs | PASS by static inspection; no PAT references found |
| No production dispatch sent | CONFIRMED — none sent |

Static workflow checks:

- Sender uses `actions/create-github-app-token@v1`, scoped to the target
  repository, with `permission-contents: write` and `permission-issues: read`.
- Receiver uses the same action scoped to the source repository, with
  `permission-contents: read` and `permission-issues: read`.
- Destination issue writes use `${{ github.token }}`.
- No `XREPO_PAT`, `GH_PAT`, or personal-access-token reference exists in the
  xrepo workflows.

## 6. Step 05 — Local verification

```text
./scripts/xrepo/run_local_qa.sh
```

| Repository | Tests | FAIL | SKIP | JSON/YAML/diff |
| --- | --- | --- | --- | --- |
| Jobsearch | 69 PASS | 0 | 0 | PASS |
| RIS | 69 PASS | 0 | 0 | PASS |

No product, infrastructure, or deployment change was made.

## 7. Step 06 — Rollout readiness

- Jobsearch PR #2 is a draft, `MERGEABLE` / `UNSTABLE` because Vercel preview
  deployments fail in the output stage after a successful build
  (`dpl_54EYrEJHqN5Cu7N7uJjSQ31hnbmN`, `dpl_W1ndUvFfV6G7cTZK2ygG1RbzHGs6`).
- RIS PR #6 is a draft, `MERGEABLE` / `CLEAN`.
- Neither PR has a review approval.
- **No merge is authorized or performed.** Local tests are not a merge approval.
- No AWS, Terraform, Cognito, CloudFront, Vercel production, or Mays-Orders
  change was made.

## 8. Step 07 — Documentation

This report is committed in both repositories. The E2E-01 report remains the
source for the planned A→B→A runbook and controlled issues #3/#7.

## 9. Security findings

- No secrets, credentials, tokens, private keys, PII, CVs, or candidate data
  were read, printed, or stored.
- Secret existence was checked through the repository secret metadata only.
- No live dispatch was sent.
- No PAT or substitute credential was created.
- The app permission model remains least-privilege as documented.

## 10. Blocker and recovery point

**Blocker:** app not confirmed/installed; `XREPO_APP_ID` and
`XREPO_APP_PRIVATE_KEY` absent in both repositories.

**Recovery point:** both draft PRs, the hardened xrepo implementation, issues
#3/#7, this report, and the E2E-01 report. Resume after the repository owner
creates/installs the app and adds both secrets.

## 11. Final status

`BLOCKED FOR LIVE`

`APP CONFIGURED / SECURITY VERIFIED / AWAITING ROLLOUT APPROVAL` is not reached.
