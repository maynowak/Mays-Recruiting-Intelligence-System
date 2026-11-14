# MAYS-XREPO-R4-LIVE-HANDOFF-PREFLIGHT-05

**Status:** `MAYS-XREPO-R4-LIVE-HANDOFF-PREFLIGHT-05 — READY / HUMAN DISPATCH AUTHORIZATION PENDING`

**Date:** 2026-11-14

**Task:** `MAYS-SCV-RC3-001`

**Mode:** READ-ONLY PREFLIGHT — no live dispatch, no merge, no AWS/Terraform.

## 1. Git baselines

| Repository | Main HEAD | RC1 |
|---|---|---|
| Jobsearch | `a5640d12dba8ca39258484f5212def17eabf4eca` | n/a |
| RIS | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` | `release/structured-cv-rc1 @ 4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1` |

All requested baselines match exactly. RIS RC1 is unchanged.

## 2. Issue histories

- Jobsearch #17: open; title/body contain `MAYS-SCV-RC3-001`; the issue
  comments link `maynowak/Mays-Recruiting-Intelligence-System#8`.
- RIS #8: open; title/body contain `MAYS-SCV-RC3-001`; body/comments link
  `maynowak/mays-jobsearch#17`.
- Mutual issue-pair binding therefore passes the receiver's task-token and
  cross-link checks.
- Neither issue contains any `mays-xrepo:state`, `mays-xrepo:event`, or
  `mays-xrepo:rejected` marker. No manual status marker exists.
- No issue was modified during this preflight.

## 3. Workflow readiness

Both repositories have active default-branch workflows:

- Jobsearch: `MAYS XRepo Send`, `MAYS XRepo Receive`.
- RIS: `MAYS XRepo Send`, `MAYS XRepo Receive`.

Both receiver scripts on main are byte-identical after the controlled merge
(SHA-256 `979297ef71b851ed94e5cd7dc2e04d3021f04003442b572ccb04809772af0d87`):

- exact source/destination task binding;
- mutual issue-link check;
- shared trusted bot history from both issues;
- sequence/event/replay conflict handling;
- destination-only marker writes;
- terminal `COMPLETED` and rework limit enforced.

Event schema was not changed. Source commit verification and both repository
allowlists remain active.

## 4. GitHub App / permission evidence

- `XREPO_APP_ID` and `XREPO_APP_PRIVATE_KEY` secret **names** exist in both
  repositories. Secret values were not read.
- Existing 2026-11-07 sender runs succeeded in both repositories, demonstrating
  historical app-token operation.
- A direct `/user/installations` query with the current user token returns 403;
  the current App installation cannot be independently enumerated with the
  available user credential. This is a preflight evidence limitation, not a
  proven failure.
- Required permission model remains: target Contents write + Issues read;
  source Contents read + Issues read. No new secret or broader permission is
  proposed.
- Real permission proof is deferred to the first authorized R4 sender run;
  any 403/app-token failure stops the handoff.

## 5. RIS CI/CD finding

Run `43482788367`:

- workflow `.github/workflows/ci-cd.yml`;
- push on `main` at `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9`;
- conclusion failure;
- **0 jobs**, no job logs, annotations endpoint returns 404.

The same zero-job pattern occurs on earlier main commits, including
`43483164760`, `43473623845`, `43441188315`, `43440891065`, and
`43440656979`. It therefore predates the XRepo merge and is not caused by the
receiver correction. The workflow contains an `on: plan` trigger, which is not
a standard GitHub Actions event; this is a plausible workflow-validation
configuration cause, but no job log exists to prove it.

**Classification:** `UNRELATED TO XREPO / EVIDENCE CONFIRMED` (zero-job pattern
pre-exists; XRepo Send/Receive are separate workflows). CI root cause remains a
separate GitHub workflow-maintenance issue and is not fixed here.

## 6. Preflight event validation

A local illustrative event was built with the actual future sender baseline:

```json
{
  "taskId": "MAYS-SCV-RC3-001",
  "status": "REQUESTED",
  "sequence": 1,
  "source": {
    "repository": "maynowak/mays-jobsearch",
    "issue": 17,
    "commit": "a5640d12dba8ca39258484f5212def17eabf4eca"
  },
  "destination": {
    "repository": "maynowak/Mays-Recruiting-Intelligence-System",
    "issue": 8
  },
  "evidence": []
}
```

`build_event.py` and `validate_event.py --expected-source
maynowak/mays-jobsearch --expected-target
maynowak/Mays-Recruiting-Intelligence-System` both passed.

The generated local event ID
`ba52b8be-c713-43fa-9474-3e85931ca243` is **illustrative only**. At execution,
the actual sender workflow generates the event ID and `source.commit` from its
real `github.sha`; do not reuse this local ID as a real event.

## 7. Sequential live runbook

Controlled mode only: one dispatch, wait for both sender/receiver evidence, then
the next. No simultaneous cross-repo dispatches.

### Status 1 — REQUESTED (Jobsearch → RIS)

Inputs: task `MAYS-SCV-RC3-001`, source issue `17`, target
`maynowak/Mays-Recruiting-Intelligence-System#8`, sequence `1`, evidence `[]`.
Source commit is the actual Jobsearch sender workflow SHA.

### Status 2 — ACCEPTED (RIS → Jobsearch)

Destination `maynowak/mays-jobsearch#17`, source issue `8`, sequence `2`.
Source commit is the actual RIS sender workflow SHA.

### Status 3 — IMPLEMENTING (Jobsearch → RIS)

Sequence `3`, target RIS #8.

### Status 4 — IMPLEMENTATION_READY (RIS → Jobsearch)

Sequence `4`; include commit evidence exactly matching the actual RIS source
commit.

### Status 5 — INTEGRATING (Jobsearch → RIS)

Sequence `5`, target RIS #8.

### Status 6 — VERIFIED (RIS → Jobsearch)

Sequence `6`; commit evidence must exactly match the actual RIS source commit.

### Status 7 — COMPLETED (Jobsearch → RIS)

Sequence `7`; commit evidence must exactly match the actual Jobsearch source
commit.

If correction is required:

`REWORK_REQUIRED` → `IMPLEMENTATION_READY`; maximum three rework rounds. A
fourth is rejected and requires human `BLOCKED` decision.

For **each** status verify:

1. sender workflow run ID/conclusion and actual `source.commit`;
2. receiver workflow run ID/conclusion;
3. event ID and sequence in both runs;
4. applied state marker on the destination issue;
5. both issue histories agree;
6. no duplicate/stale/rejected marker;
7. only then dispatch the next status.

No live dispatch is part of this preflight.

## 8. Recovery

- **Missing app permission (403/401):** stop before sending; verify App
  installation and secret names; do not create a PAT or new secret.
- **Invalid transition:** do not resend; inspect both histories and human
  decide.
- **Duplicate event ID:** no state change; if state/sequence differ, conflict.
- **Stale sequence:** no state change; next valid sequence only after human
  review.
- **Contradictory markers:** fail closed as `state_unreadable`; no automatic
  repair or hand-written marker.
- **Interrupted sender/receiver run:** check whether the receiver applied a
  marker; resend only with the same event ID if it was the same attempt, or
  follow the decided sequence after verifying state.
- **Incomplete history:** stop; manual recovery required.
- Any ambiguous state: `STOP / HUMAN RECOVERY REQUIRED`.

## 9. Open risks / gates

- Current App installation could not be enumerated with the user token; first
  live sender run is the permission proof.
- RIS CI/CD zero-job workflow failure is pre-existing and separate; do not
  treat it as XRepo receiver evidence.
- R4 authorization is not given by this preflight.
- Sequential mode only; concurrent dispatch is unsupported.
- No AWS, Terraform, consent, product or production gate is advanced.

## 10. R4 decision

**Preflight status:** `READY / HUMAN DISPATCH AUTHORIZATION PENDING`.

R4 dispatch requires a separate explicit human approval naming the event,
sender, receiver, and sequence 1. After approval, execute only the sequential
runbook above and record real run IDs, event IDs and issue-comment URLs.

**STOP before R4 live dispatch.**
