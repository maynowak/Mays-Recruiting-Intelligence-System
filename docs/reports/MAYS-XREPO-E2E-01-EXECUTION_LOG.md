# MAYS-XREPO-E2E-01 — Execution Log

## Status

`HARDENING COMPLETE — LOCAL VERIFIED — E2E BLOCKED FOR LIVE`
Step E2E-01F: `NOT EXECUTED` (no rollout approval or app credentials).

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

- `maynowak/{jobsearch,RIS}/actions/secrets` → `total_count: 0`.
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


## 5. Step E2E-01B — Protocol hardening

- Commit: `5d49399` (`feat(xrepo): enforce status transitions and rework limits`)
- Changes:
  - Added an explicit receiver state machine with `REQUESTED`/`BLOCKED` as the only initial states; `BLOCKED` and `COMPLETED` are terminal.
  - Enforced `COMPLETED` only after `VERIFIED`.
  - Allowed the controlled E2E sequence `IMPLEMENTATION_READY -> VERIFIED` after rework, while still rejecting skips such as `REQUESTED -> COMPLETED`.
  - Enforced a maximum of three applied `REWORK_REQUIRED` events; a fourth is rejected.
  - Applied events now store the status in the trusted state marker:
    `<!-- mays-xrepo:state:<taskId>:<sequence>:<status> -->`.
  - Conflict, invalid-transition, and rework-limit outcomes post a rejection comment with
    `<!-- mays-xrepo:rejected:<eventId>:<reason> -->` and no state marker, then fail closed.
  - Rejected-event retries are rejected without a second comment.
  - Legacy state markers without a status fail closed as `state_unreadable`.
  - Issue evidence is verified through the source API; commit evidence must match the verified source SHA.
  - `IMPLEMENTATION_READY`, `VERIFIED`, and `COMPLETED` now require commit evidence, not test-only evidence.
  - Event JSON format and the existing sender/receiver interfaces were kept compatible.

## 6. Step E2E-01C — Local verification

- Commands executed in both repositories:
  - `./scripts/xrepo/run_local_qa.sh`
  - included `python3 -m unittest discover -s scripts/xrepo -p 'test_*.py' -v`
- Result: **69 tests PASS**, **0 FAIL**, **0 SKIP**; JSON, workflow YAML, and `git diff --check` PASS.
- Affected files: `scripts/xrepo/validate_event.py`, `scripts/xrepo/apply_event.py`, `scripts/xrepo/test_validate_event.py`, `scripts/xrepo/test_apply_event.py`, `docs/xrepo/MAYS-XREPO-V1.md`, `docs/xrepo/fixtures/valid-implementation-ready.json`.
- New test coverage:
  - initial status rules and full sequence;
  - rejected status skips;
  - `COMPLETED` only after `VERIFIED`;
  - three-rework limit;
  - duplicate/stale/conflict and rejected duplicates;
  - rejection markers and fail-closed behavior;
  - legacy state markers;
  - commit-only evidence and issue-evidence verification;
  - untrusted marker injection remains ignored.

| Requirement | Test evidence | Result |
| --- | --- | --- |
| Allowed status transitions | `test_full_sequence_applies`, `test_skipping_statuses_rejected` | PASS |
| `COMPLETED` only after `VERIFIED` | `test_completed_requires_verified` | PASS |
| Max three rework rounds | `test_rework_limit` | PASS |
| Repeated events without duplicate state | `test_duplicate_event_is_idempotent`, `test_duplicate_posts_nothing` | PASS |
| Same sequence / different event ID | `test_same_sequence_different_event_conflicts`, `test_conflict_posts_rejection_then_fails` | PASS |
| Stale events | `test_stale_sequence`, `test_stale_posts_stale_comment` | PASS |
| Evidence authenticity / repository mapping | validator evidence tests, `test_verify_evidence_accepts_issue`, `test_verify_evidence_rejects_pull_request` | PASS |
| Error handling / recovery | `test_previously_rejected_event_is_rejected_duplicate`, `test_legacy_state_marker_without_status_fails_closed`, `test_missing_source_token_is_blocked_for_live` | PASS |
| A → B → A (local state machine) | `test_full_sequence_applies` | PASS (local only) |
| Live A → B → A | not executed | NOT EXECUTED |

## 7. Open risks

- The live A→B→A path is still unverified.
- GitHub App installation and secrets are absent.
- Jobsearch PR #2 remains unstable because of Vercel preview deployment failures after a successful build.
- Test/document evidence is repository-bound but not independently executed; commit evidence is the authoritative implementation anchor.

## 8. Step E2E-01D — GitHub App readiness

### Required permissions (existing contract)

| Scope | Permission | Purpose |
| --- | --- | --- |
| Target repository | Contents: write | `repository_dispatch` |
| Target repository | Issues: read | target issue verification |
| Source repository | Contents: read | source commit verification |
| Source repository | Issues: read | source issue/evidence verification |

Destination issue updates use the receiver repository's own `GITHUB_TOKEN`
(`issues: write`). No PAT is used or created.

### Current state

- `maynowak/mays-jobsearch/actions/secrets` → `total_count: 0`.
- `maynowak/Mays-Recruiting-Intelligence-System/actions/secrets` → `total_count: 0`.
- No `XREPO_APP_ID` or `XREPO_APP_PRIVATE_KEY` is configured.
- The available `gh` credential is a user token for `maynowak`; it cannot list GitHub App installations (`/user/installations` → 403). App installation is therefore unverified.
- No secret values, tokens, or private keys were printed or stored.

### Required setup steps

1. Create or approve a least-privilege GitHub App with access to both repositories.
2. Grant the permissions above only; do not grant account-wide permissions.
3. Install the app on both repositories.
4. Add `XREPO_APP_ID` and `XREPO_APP_PRIVATE_KEY` to both repositories' Actions secrets.
5. Re-run the local preflight and confirm the app/secret readiness.
6. Only then request the separate rollout approval.

**Result: BLOCKED FOR LIVE.**

## 9. Step E2E-01E — Rollout gate

| Repo | PR | Draft | Mergeability | Checks | Merge allowed? |
| --- | --- | --- | --- | --- | --- |
| Jobsearch | #2 | yes | `MERGEABLE` / `UNSTABLE` | Vercel failures/pending | NO |
| RIS | #6 | yes | `MERGEABLE` / `CLEAN` | none | NO |

- No review approval is present.
- Jobsearch PR #2 remains unstable because the Vercel preview deployment outputs fail after a successful build.
- RIS PR #6 is technically clean, but the live prerequisites are missing.
- **No merge was performed.** A successful local test is not a merge approval.
- No AWS, Terraform, Cognito, CloudFront, Vercel production, or Mays-Orders change was made.

**Result: NOT MERGE READY / AWAITING APPROVAL.**

## 10. Step E2E-01F — Controlled live test

`NOT EXECUTED`.

Reasons:

1. No explicit rollout approval.
2. Workflows are not on the default branches.
3. GitHub App secrets are absent.
4. Jobsearch PR #2 is not stable due to Vercel preview failures.

Expected sequence for the later controlled run:

```text
REQUESTED
ACCEPTED
IMPLEMENTING
IMPLEMENTATION_READY
INTEGRATING
REWORK_REQUIRED
IMPLEMENTATION_READY
VERIFIED
COMPLETED
```

The live run must use test issues jobsearch #3 and RIS #7 only, record actual
GitHub run IDs, event IDs, commit SHAs, and issue-comment URLs, and verify
duplicate/stale/conflict/recovery behavior. No live event was sent.

## 11. Security findings

- No secrets, tokens, private keys, PII, CVs, or candidate data were added to the repositories or reports.
- The receiver trusts markers only from `github-actions[bot]`.
- Issue evidence is verified through the source API; commit evidence is bound to the verified source SHA.
- Test/document evidence is repository-bound but not executed; commit evidence is the authoritative implementation anchor.
- No payload value is passed as a shell command.
- No alternative PAT was created.

## 12. Blocker and recovery point

**Primary blocker:** missing GitHub App installation and `XREPO_APP_ID` /
`XREPO_APP_PRIVATE_KEY`, plus the requirement for an explicit rollout approval.

**Secondary blocker:** Jobsearch Vercel preview deployments fail in the output
stage after a successful build (`dpl_54EYrEJHqN5Cu7N7uJjSQ31hnbmN`,
`dpl_W1ndUvFfV6G7cTZK2ygG1RbzHGs6`).

**Recovery point:** both draft PRs, the hardened tests, this report, the
controlled issues #3/#7, and the local QA reports. Resume at E2E-01D setup or
E2E-01E after approval.

## 13. Final status

`IMPLEMENTED / LOCAL VERIFIED / E2E NOT EXECUTED / BLOCKED FOR LIVE`

Pre-live target: `E2E READY / AWAITING APPROVAL` is **not** reached because the
app/secret prerequisite is missing. No merge, deployment, live dispatch, branch
deletion, or infrastructure change was performed.
