# MAYS-XREPO-ORCHESTRATION-01 — E2E Readiness

## Status

`IMPLEMENTED / LOCAL VERIFIED / E2E PENDING / BLOCKED FOR LIVE`

No live `repository_dispatch` was sent. Both test issues exist and are open, but
the workflows are not on the default branches and no GitHub App credentials are
configured.

## Controlled test issues

| Role | Issue |
| --- | --- |
| A / source (jobsearch) | https://github.com/maynowak/mays-jobsearch/issues/3 |
| B / destination (RIS) | https://github.com/maynowak/Mays-Recruiting-Intelligence-System/issues/7 |

Task ID: `MAYS-XR-E2E-001`

## Readiness checklist

- [x] Versioned contract, validator, event builder.
- [x] Manual sender and idempotent receiver workflows implemented.
- [x] Local QA 53/53 PASS; JSON/YAML/diff check PASS.
- [x] Two separate draft PRs created.
- [x] Two controlled test issues created and cross-linked.
- [ ] Workflows merged to both default branches (requires rollout approval).
- [ ] GitHub App installed/approved on both repositories.
- [ ] `XREPO_APP_ID` / `XREPO_APP_PRIVATE_KEY` configured in both repositories.
- [ ] Live A→B→A dispatch executed.
- [ ] Rework cycle and stale/duplicate behavior verified live.

## Blockers

1. `repository_dispatch` only triggers when `xrepo-receive.yml` exists on the
   receiver's default branch. It currently exists only on
   `feature/mays-xrepo-orchestration-01`.
2. The GitHub App installation and the two repository secrets are missing.
   The sender/receiver intentionally stop with `BLOCKED FOR LIVE`; no substitute
   PAT or secret may be created.

## Live runbook (after approved rollout)

Dispatch from the **jobsearch** workflow `MAYS XRepo Send`:

| Input | Value |
| --- | --- |
| `target_repository` | `maynowak/Mays-Recruiting-Intelligence-System` |
| `target_issue` | `7` |
| `task_id` | `MAYS-XR-E2E-001` |
| `status` | `REQUESTED` |
| `source_issue` | `3` |
| `sequence` | `1` |
| `summary` | `E2E requested; see source issue.` |
| `evidence_json` | `[{"kind":"issue","url":"https://github.com/maynowak/mays-jobsearch/issues/3"}]` |

Then dispatch from **RIS** to jobsearch:

| Input | Value |
| --- | --- |
| `target_repository` | `maynowak/mays-jobsearch` |
| `target_issue` | `3` |
| `task_id` | `MAYS-XR-E2E-001` |
| `status` | `ACCEPTED` |
| `source_issue` | `7` |
| `sequence` | `2` |
| `summary` | `Scope accepted; implementation starts on a feature branch.` |
| `evidence_json` | `[{"kind":"issue","url":"https://github.com/maynowak/Mays-Recruiting-Intelligence-System/issues/7"}]` |

For `IMPLEMENTATION_READY`, replace the evidence with the actual source commit
and test/workflow URL from the source repository. The workflow automatically
uses its `github.sha` as `source.commit`; the evidence commit URL must match it.

Expected next sequence: `IMPLEMENTING` (3), `IMPLEMENTATION_READY` (4),
`INTEGRATING` (5), `REWORK_REQUIRED` (6), `IMPLEMENTATION_READY` (7),
`VERIFIED` (8), `COMPLETED` (9). One rework round is intentional. Stop after
three automatic rework rounds and mark `BLOCKED`.

## Expected live assertions

- Each event produces exactly one destination issue comment.
- A repeated `eventId` produces no second comment.
- A lower `sequence` produces a stale comment without a state marker and does
  not change the latest applied sequence.
- A different `eventId` at the same sequence fails with a conflict.
- `REWORK_REQUIRED` preserves the evidence/commit that triggered it.
- `COMPLETED` only appears after `VERIFIED` and both issues are cross-linked.
- Markers in user-authored comments are ignored; only `github-actions[bot]` markers count.
- No payload text executes as a shell command.

## Recovery point

Local implementation and both draft PRs are complete. The next safe action is a
separate, explicitly approved rollout: merge both PRs, install the app, add the
secrets, then run the runbook above and update both execution logs with real
issue comment URLs and run IDs.

## Non-actions

No merge, deployment, Terraform, AWS, Cognito, CloudFront, Vercel configuration,
Mays-Orders, or product-code change was performed. Creating the jobsearch PR
triggered its existing Vercel preview integration as a platform side effect.
