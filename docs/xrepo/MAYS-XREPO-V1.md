# MAYS-XREPO-V1 — Cross-Repository Handoff Contract

Status: **IMPLEMENTED LOCALLY / E2E PENDING**. No live `repository_dispatch`
was executed from this branch. `repository_dispatch` only starts a workflow that
already exists on the receiver's default branch.

## Scope

This contract exchanges *signals and evidence references* between
`maynowak/mays-jobsearch` and `maynowak/Mays-Recruiting-Intelligence-System`.
It does not move candidate data, CVs, tokens, credentials, or product code. The
actual Git state and CI/test evidence remain authoritative; an event is not a
test proof.

## Event shape

The JSON schema is `docs/xrepo/MAYS-XREPO-V1.schema.json`. There is exactly one
dispatch event type, `mays_xrepo_v1`; the payload's `status` distinguishes the
workflow step.

```json
{
  "protocol": "MAYS-XREPO-V1",
  "taskId": "MAYS-XR-001",
  "eventId": "f4e87f3a-5ca5-4dca-a6c8-55d5d8f697a5",
  "status": "IMPLEMENTATION_READY",
  "source": {
    "repository": "maynowak/Mays-Recruiting-Intelligence-System",
    "issue": 42,
    "commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "destination": {
    "repository": "maynowak/mays-jobsearch",
    "issue": 117
  },
  "summary": "Receiver validator and tests implemented locally.",
  "evidence": [
    {
      "kind": "commit",
      "url": "https://github.com/maynowak/Mays-Recruiting-Intelligence-System/commit/0123456789abcdef0123456789abcdef01234567"
    }
  ],
  "sequence": 3
}
```

Limits: 9 top-level properties, fewer than 64 KiB, at most 10 evidence items,
summary at most 500 characters. Unknown fields are rejected.

## Status values

`REQUESTED`, `ACCEPTED`, `IMPLEMENTING`, `IMPLEMENTATION_READY`, `INTEGRATING`,
`REWORK_REQUIRED`, `VERIFIED`, `COMPLETED`, `BLOCKED`.

`IMPLEMENTATION_READY`, `VERIFIED`, and `COMPLETED` require at least one
`commit` or `test` evidence item. `REWORK_REQUIRED` requires `commit`, `test`, or
`issue` evidence. `BLOCKED` may be sent with no evidence. The sender still
supplies `source.commit` for every event.

## Allowlist and source verification

The only accepted repositories are:

- `maynowak/mays-jobsearch`
- `maynowak/Mays-Recruiting-Intelligence-System`

The sender must pass `--expected-source`; the receiver must pass
`--expected-target`. Both checks fail closed. `source.repository` is not an
identity proof: the receiver verifies the source issue and commit through the
source repository API before accepting an event. Evidence URLs must belong to
the source repository; a `commit` evidence URL must match `source.commit`
exactly.

## Sequence and idempotency

- Key: `taskId` + `eventId`.
- Each task has a monotonically increasing `sequence`.
- A repeated `eventId` is ignored (no second issue comment).
- A lower `sequence` is logged as stale and does not overwrite state.
- A different `eventId` at the same sequence is a conflict and fails closed.
- Receiver comments carry `<!-- mays-xrepo:event:<eventId> -->` and
  `<!-- mays-xrepo:state:<taskId>:<sequence> -->` markers. Do not hand-edit them.
- `concurrency` in the receive workflow serializes events per `taskId`.

## Workflows

- `.github/workflows/xrepo-send.yml` — manual `workflow_dispatch`, validates the
  event, checks the source issue, obtains a least-privilege GitHub App token,
  and calls the target's `repository_dispatch` endpoint.
- `.github/workflows/xrepo-receive.yml` — triggered by
  `repository_dispatch: [mays_xrepo_v1]`, validates again, verifies the source
  issue/commit, applies the idempotent issue update, and never executes payload
  text as shell.

### Sender inputs

`xrepo-send.yml` is manual only. It takes `target_repository`, `target_issue`,
`task_id`, `status`, `source_issue`, `sequence`, `summary`, and optional
`evidence_json`. `source.repository` is the repository running the workflow;
`source.commit` is its `github.sha`. The sender verifies the source issue and
the target issue before dispatching, and records the dispatch on the source
issue only after the API call succeeds.

Build an event locally with:

```bash
python3 scripts/xrepo/build_event.py \
  --task-id MAYS-XR-001 --status REQUESTED \
  --source-repository maynowak/mays-jobsearch \
  --source-issue 117 --source-commit <40-char-sha> \
  --target-repository maynowak/Mays-Recruiting-Intelligence-System \
  --target-issue 42 --summary "Handoff requested." \
  --evidence-json '[]' --sequence 1 --output event.json
```

### Required repository secrets

Set these in **both** repositories (Settings → Secrets and variables → Actions):

- `XREPO_APP_ID` — GitHub App ID.
- `XREPO_APP_PRIVATE_KEY` — GitHub App private key.

The app needs, on the target repository, `Contents: write` (to create the
dispatch) and `Issues: read`; on the source repository, `Contents: read` and
`Issues: read` for verification. It must not receive account-wide permissions.
If either secret is missing, the workflow stops with an explicit
`BLOCKED FOR LIVE` error. Do not substitute a PAT or generate a replacement
secret.

The receiving workflow uses its own `GITHUB_TOKEN` (`issues: write`) for the
destination issue and the app token only for source verification.

## Local checks

```bash
./scripts/xrepo/run_local_qa.sh
python3 -m unittest scripts/xrepo/test_validate_event.py -v
python3 scripts/xrepo/validate_event.py docs/xrepo/fixtures/valid-requested.json \
  --expected-source maynowak/mays-jobsearch \
  --expected-target maynowak/Mays-Recruiting-Intelligence-System
```

## Test matrix

| Case | Covered by |
| --- | --- |
| valid event | validator + fixtures |
| invalid schema / unknown field | validator tests |
| spoofed source / wrong target | validator tests |
| unauthorized repository | validator tests |
| wrong target | validator tests |
| stale sequence | receiver state tests |
| duplicate event | receiver state tests |
| evidence absent | validator tests |
| retry cycle | receiver state tests |
| A → B → A | receiver state tests + documented E2E path |
| live `repository_dispatch` | **E2E PENDING** until workflows are on both default branches and app credentials exist |

## Security notes

- No payload value is interpolated into a shell command.
- No secrets, tokens, candidate data, or PII belong in an event.
- Evidence URLs are restricted to `https://github.com/<source-repo>/...`.
- The receiver is fail-closed on missing credentials, invalid schema, unauthorized
  repositories, wrong targets, missing evidence, stale/conflicting sequences, and
  unverifiable source issues or commits.
- No automatic merge, branch deletion, deployment, Terraform, AWS, Cognito,
  CloudFront, Vercel, or Mays-Orders mutation is performed by this contract.

## Rollout / E2E status

Local contract tests are implemented. The true dispatch E2E remains pending until
these workflows are intentionally merged into both default branches and the
GitHub App installation/secrets are approved. Until then the only honest status
is **IMPLEMENTED / E2E PENDING**.
