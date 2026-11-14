# MAYS-XREPO-SHARED-STATE-RECONCILIATION-02

**Status:** `MAYS-XREPO-SHARED-STATE-RECONCILIATION-02 — LOCAL VERIFIED / READY FOR CONTROLLED ROLLOUT`

**Date:** 2026-11-13

**Task:** `MAYS-SCV-RC3-001`

## 1. Git baseline

| Repository | Main | Working branch |
|---|---|---|
| `maynowak/mays-jobsearch` | `854da7725ad62a85f5877e8ec041431b8d459bb5` | `feature/mays-xrepo-shared-state-reconciliation-02` |
| `maynowak/Mays-Recruiting-Intelligence-System` | `f830a5edc63fc0b91203073a288bb60d374b413f` | `feature/mays-xrepo-shared-state-reconciliation-02` |

The correction is isolated from RIS RC1
`release/structured-cv-rc1 @ 4bfd08f`; that branch was not read-modified,
rebased or recreated.

## 2. Reproduced defect

Synthetic receiver evidence:

```text
RIS destination history:
  mays-xrepo:state:MAYS-SCV-RC3-001:1:REQUESTED

Jobsearch destination history before correction:
  empty

Incoming ACCEPTED sequence 2 at Jobsearch:
  invalid_transition
  initial status must be one of ['BLOCKED', 'REQUESTED']
```

The existing receiver called `last_state()` only with comments from
`event["destination"]`. It never read the source issue, so the prior
`REQUESTED` marker was invisible after the direction changed.

## 3. Correction

In both receivers, `apply_event()` now:

1. verifies the destination issue;
2. verifies the source issue and source commit;
3. checks that both issue title/body contain the exact task ID;
4. reads comments from the destination with `GITHUB_TOKEN`;
5. reads comments from the verified source with the existing app token
   (`Issues: read`);
6. combines only trusted `github-actions[bot]` comments;
7. runs `decide()` against the combined history;
8. writes applied/rejected/stale markers only to the destination issue.

No event-schema change, new secret, new app permission or second state store was
introduced. The source issue is never written by the receiver.

## 4. Security model

- `source.repository`, `source.issue` and `destination.issue` must be verified
  through their respective GitHub APIs.
- Source and destination issue title/body must contain the exact task ID;
  foreign/unrelated issues fail with `issue_binding_invalid`.
- Only `github-actions[bot]` comments supply event/state markers.
- Ordinary issue text, user-authored marker text and unverified issue content
  are ignored.
- A state marker without status fails closed as `state_unreadable`.
- Multiple event/state markers in one trusted comment fail closed.
- Same sequence with different statuses fails closed.
- Same sequence with different event IDs is a conflict.
- A duplicate event ID is idempotent only when its status/sequence match; a
  conflicting replay is rejected.
- Missing source read access/source issue is `BLOCKED`/failure with no
  destination write.
- Terminal `COMPLETED` remains terminal.

## 5. Shared-state semantics

The state history is now the union of trusted markers from the verified issue
pair. This supports the actual alternating flow:

```text
Jobsearch → RIS   REQUESTED      (RIS issue marker)
RIS → Jobsearch   ACCEPTED       (Jobsearch issue marker; source RIS marker read)
Jobsearch → RIS   IMPLEMENTING   (combined history continues)
...
```

State markers remain stored only on the destination issue. Combining the two
issue histories is read-only and task-scoped.

## 6. Concurrency boundary

The receive workflows' `concurrency` groups are repository-local. GitHub does
not provide a cross-repository lock from this setup. Therefore:

- **Supported mode:** controlled sequential handoff — one dispatch at a time,
  wait for the receiver's applied/rejected comment before the next dispatch.
- **Unsupported:** simultaneous cross-repository dispatches. If they race, both
  receivers may read the same pre-event history, and a later combined history
  can be stale/conflicting.
- A conflicting/unreadable combined history fails closed; no automatic repair,
  no fabricated marker and no `COMPLETED` transition is permitted.
- Recovery is a human decision: inspect both issues, choose the authoritative
  state, and start a new correctly sequenced event only after explicit approval.

This limitation is documented in both `docs/xrepo/MAYS-XREPO-V1.md` files. It is
a rollout constraint, not a claim of global atomicity.

## 7. Tests

Both receivers:

```text
python3 -m pytest -q scripts/xrepo
76 passed, 4 subtests passed
```

New/covered cases include:

- reverse `REQUESTED` → `ACCEPTED` using source issue state;
- full status matrix through terminal `COMPLETED`;
- duplicate event idempotency and conflicting replay;
- stale sequence no state change;
- same sequence/different event conflict;
- mixed source/destination same-sequence markers fail closed;
- untrusted marker ignored;
- task binding rejection at source and destination;
- missing source read/verification failure;
- fourth rework rejection;
- terminal transition rejection.

No real dispatch, AWS call or issue mutation was performed in this correction.

## 8. Protocol compatibility

- `MAYS-XREPO-V1` event shape is unchanged.
- `validate_event.py` is unchanged.
- Existing `XREPO_APP_ID`/`XREPO_APP_PRIVATE_KEY` secrets and the existing
  source `Issues: read` permission are reused.
- Destination remains `Issues: write`; source remains read-only.
- No Terraform, AWS, RIS product code, Jobsearch product code or RIS RC1 changes.

## 9. Rollout plan

### Phase A — local/review

- branches and commits listed below;
- 76 receiver tests in each repository;
- independent security/architecture review;
- PRs prepared, no merge.

### Phase B — controlled main integration (separate approval)

- merge PRs to both `main` branches in a coordinated window;
- verify receiver workflow files and app permissions on both default branches;
- no other product changes in the merge.

### Phase C — controlled live handoff (separate approval)

- use `MAYS-SCV-RC3-001` issues `mays-jobsearch#17` and RIS#8;
- send one fresh `REQUESTED` sequence 1;
- wait for verified receiver result before each next status;
- record workflow run IDs, event IDs, sequences and applied comments;
- no automatic dispatch is part of this correction.

## 10. Commits and PRs

- Jobsearch correction: `785ac68` on
  `feature/mays-xrepo-shared-state-reconciliation-02`.
- RIS correction: `d44b804` on
  `feature/mays-xrepo-shared-state-reconciliation-02`.
- Jobsearch PR: https://github.com/maynowak/mays-jobsearch/pull/18
- RIS PR: https://github.com/maynowak/Mays-Recruiting-Intelligence-System/pull/9
- No PR was merged and no live dispatch was sent.

## 11. Open approvals

- independent review of the two PRs;
- controlled main rollout approval;
- controlled live handoff approval;
- explicit human reconciliation procedure owner for concurrent conflicts;
- all prior AWS/legal/consent gates remain unchanged.

## 12. RIS RC1 preservation

`release/structured-cv-rc1 @ 4bfd08f` remains unchanged. It was not rebased,
recreated or overwritten. Its prior evidence (2582 RIS PASS / 56 skipped / 19
baseline failures; preview-verified BFF) remains separate from this XRepo
protocol correction.

**No main merge, live dispatch, AWS/Terraform, consent activation or production
deployment was performed.**
