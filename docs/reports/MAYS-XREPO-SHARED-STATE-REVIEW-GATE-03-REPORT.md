# MAYS-XREPO-SHARED-STATE-REVIEW-GATE-03

**Status:** `MAYS-XREPO-SHARED-STATE-REVIEW-GATE-03 — SECURITY REVIEW PASS / MAIN ROLLOUT APPROVAL PENDING`

**Date:** 2026-11-13

**Task:** `MAYS-SCV-RC3-001`

## 1. Git baselines

| Repository | Main | Feature branch | Feature HEAD | PR |
|---|---|---|---|---|
| Jobsearch | `854da77` | `feature/mays-xrepo-shared-state-reconciliation-02` | `bda0017` | #18 |
| RIS | `f830a5e` | `feature/mays-xrepo-shared-state-reconciliation-02` | `80d36a9` | #9 |

Protection: `release/structured-cv-rc1 @ 4bfd08f` remains unchanged.

## 2. Reproduced historical-integrity defect

The prior implementation could hide a conflict:

```text
sequence 1 REQUESTED
sequence 2 ACCEPTED
sequence 2 IMPLEMENTING   ← contradictory
sequence 3 IMPLEMENTATION_READY
```

The higher sequence 3 replaced the invalid sequence-2 state, so the conflict
was not necessarily visible. Correction: any historical integrity error sets
the final status to unreadable at the highest observed sequence; a later valid
marker cannot repair an earlier contradiction.

Additional reproduced/covered cases:

- malformed marker before a later valid marker → `state_unreadable`;
- two event IDs at the same sequence → conflict/fail closed;
- multiple event/state markers in one trusted comment → fail closed;
- duplicate event ID with different status/sequence → conflict;
- duplicate event ID with a contradictory surrounding history → fail closed
  before positive duplicate confirmation;
- a stale event cannot hide a conflicting earlier history;
- terminal `COMPLETED` still accepts no further transitions.

## 3. Issue binding

The previous substring check accepted a task ID embedded in a longer token
(`MAYS-XR-001-TEST`). It now requires an exact standalone task token with
non-identifier boundaries. Both source and destination issue title/body must
contain the exact task ID.

A second binding check requires the source issue to reference the destination
issue by repository and number, and vice versa, in the issue body or comments.
The actual pair still links correctly:

- Jobsearch #17 contains `MAYS-SCV-RC3-001` and
  `Mays-Recruiting-Intelligence-System#8`.
- RIS #8 contains `MAYS-SCV-RC3-001` and `mays-jobsearch#17`.

Missing/unlinked/foreign issues fail as `issue_binding_invalid`. No issue was
modified during this review.

## 4. Shared-state correctness

Receivers now read trusted `github-actions[bot]` comments from both issues and
combine the histories by task. Applied markers remain destination-only. The
source app token remains `Issues: read`; no new secret or write permission was
added.

Full sequence is covered across a split source/destination history, including
`REQUESTED`, `ACCEPTED`, `IMPLEMENTING`, `IMPLEMENTATION_READY`, `INTEGRATING`,
`REWORK_REQUIRED`, `IMPLEMENTATION_READY`, `VERIFIED`, `COMPLETED`.

## 5. Concurrency assessment

The workflow concurrency groups remain repository-local. There is no
cross-repository atomic lock. Therefore:

- controlled sequential handoff is the only supported live mode;
- simultaneous cross-repo dispatches are unsupported and must be prevented by
  the operator;
- a race/conflicting combined history fails closed;
- no automatic repair, no invented marker, no `COMPLETED` from a conflict;
- recovery requires human inspection and a new correctly sequenced event.

This is documented in both `docs/xrepo/MAYS-XREPO-V1.md` files. It is not a
claim of global atomicity.

## 6. Tests

Both repositories:

```text
python3 -m pytest -q scripts/xrepo
82 passed, 4 subtests passed
```

The matrix includes all status transitions, reverse shared-state handoff,
nonce/idempotency, stale/conflict cases, malformed history, exact task binding,
mutual issue links, untrusted comments, rework limit and terminal state.

No live dispatch, AWS call, Terraform plan/apply/state access, consent
activation or production deployment was performed.

## 7. Rollout gates

| Gate | Status |
|---|---|
| R1 — PRs and tests reviewed | PASS locally; human PR review pending |
| R2 — human main rollout approval | PENDING |
| R3 — both default-branch receivers verified | PENDING |
| R4 — separate real sequential dispatch approval | PENDING |

PRs are open and MERGEABLE; no merge was performed. R2 must be given after
independent human review. R3 requires both corrected receivers on the default
branches. R4 is a separate live-dispatch approval.

## 8. Rollback / recovery

- Keep the pre-correction receiver commit and both PR branches.
- If a rollout introduces a regression, revert the receiver changes by a
  reviewed PR; do not force-push.
- If a live history conflicts, stop dispatching. Inspect both issues and the
  highest trusted sequence; mark the task for human recovery. Do not add
  hand-written markers.
- Do not claim completion from a conflicted history.
- RIS RC1 remains untouched; this correction is independent of RC1 and AWS
  gates.

## 9. Commits

- Jobsearch correction: `bda0017` (prior shared-state commit `785ac68`).
- RIS correction: `80d36a9` (prior shared-state commit `d44b804`).
- Documentation commit follows this report.
- PRs: jobsearch#18, RIS#9. No PR merged.

**STOP before main rollout and live dispatch.**
