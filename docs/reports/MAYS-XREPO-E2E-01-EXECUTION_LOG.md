# MAYS-XREPO-E2E-01 — Execution Log

## Status

`PREFLIGHT COMPLETE — E2E BLOCKED FOR LIVE`
Steps E2E-01B to E2E-01F: `NOT EXECUTED` at preflight time.

## 1. Repository baselines

| Item | Jobsearch | RIS |
| --- | --- | --- |
| Canonical path | `repos/mays-jobsearch` | `repos/Mays-Recruiting-Intelligence-System` |
| Branch | `feature/mays-xrepo-orchestration-01` | `feature/mays-xrepo-orchestration-01` |
| HEAD | `75f5cae` | `2b8cc42` |
| `origin/main` | `7a3d2ea` | `c28c668` |
| Ahead / behind | 12 / 0 | 10 / 0 |
| Working tree | clean (no untracked files) | clean (no untracked files) |

Both checkouts are inside `/home/dci-student/projects/mays-xrepo-orchestration`.

## 2. Step E2E-01A — Preflight

### Pull requests

| Repo | PR | State | Mergeability | Checks |
| --- | --- | --- | --- | --- |
| Jobsearch | #2 | OPEN, draft | `MERGEABLE` / `UNSTABLE` | Vercel failures |
| RIS | #6 | OPEN, draft | `MERGEABLE` / `CLEAN` | none |

### Test issues

- Jobsearch #3 — OPEN — `MAYS-XR-E2E-001 — controlled cross-repo handoff (A/source)`
- RIS #7 — OPEN — `MAYS-XR-E2E-001 — controlled cross-repo handoff (B/destination)`

### Workflows and contract

- Jobsearch has `.github/workflows/xrepo-send.yml` and `xrepo-receive.yml` in addition to `codeql.yml`.
- RIS has `.github/workflows/xrepo-send.yml` and `xrepo-receive.yml` in addition to `ci-cd.yml`.
- Both receiver workflows trigger on `repository_dispatch: [mays_xrepo_v1]`.
- Both use the same `MAYS-XREPO-V1` protocol, schema, validator, and status enum.
- Existing `ci-cd.yml` (RIS) and `codeql.yml` (Jobsearch) are unchanged.

### Local test coverage

At preflight: `python3 -m unittest discover -s scripts/xrepo -p 'test_*.py'` → **54/54 PASS** in both repositories.

The PR body still said `53/53`; that number was stale after the marker-trust hardening. The latest verified count at preflight was 54/54. The count is updated again after the E2E-01B/C hardening.

### GitHub App readiness

- `repos/{jobsearch,RIS}/actions/secrets` → `total_count: 0`.
- No `XREPO_APP_ID` or `XREPO_APP_PRIVATE_KEY` is configured.
- The current `gh` token is a user token (`maynowak`, scopes `gist`, `read:org`, `repo`, `workflow`). It cannot list GitHub App installations; `/user/installations` returns 403.
- No app installation can be confirmed from this environment.
- Result: **BLOCKED FOR LIVE** until an approved app and both secrets exist.

### Vercel status (Jobsearch PR #2)

- `Vercel Deployments – Maymilly`: FAILURE.
- `Vercel – mays-job-matcher`: FAILURE (`dpl_54EYrEJHqN5Cu7N7uJjSQ31hnbmN`).
- `Vercel – mays-jobsearch`: FAILURE (`dpl_W1ndUvFfV6G7cTZK2ygG1RbzHGs6`).
- Build logs show `npm run build` and Vite build completing, then **`Deploying outputs... status ● Error`**.
- The failure is in the deployment/output stage, not a TypeScript/Vite build error.
- No Vercel configuration or production deployment was changed by this task. The PR-triggered preview is a platform side effect.

## 3. Findings

1. The local feature branches are clean and synchronized with their remote feature branches.
2. The protocol/workflow files exist in both repositories and use the same version.
3. The last verified local count was 54/54, not the stale 53/53 in the PR body.
4. GitHub App secrets are absent; live dispatch is blocked.
5. Jobsearch PR #2 is mergeable but unstable due to Vercel preview deployment failures.
6. RIS PR #6 is clean and mergeable.
7. An explicit rollout approval has not been given; no merge or live dispatch is allowed.

## 4. Next steps

- E2E-01B: harden status transitions/rework/rejection behavior.
- E2E-01C: run the expanded local QA and record the new count.
- E2E-01D: document GitHub App setup requirements.
- E2E-01E: assess rollout gate without merging.
- E2E-01F: `NOT EXECUTED` until approval and credentials exist.
