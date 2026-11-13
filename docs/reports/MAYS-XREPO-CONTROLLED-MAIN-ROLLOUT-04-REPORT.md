# MAYS-XREPO-CONTROLLED-MAIN-ROLLOUT-04 — POST-MERGE REPORT

**Status:** `MAYS-XREPO-CONTROLLED-MAIN-ROLLOUT-04 — R3 VERIFIED / R4 DISPATCH APPROVAL PENDING`

**Date:** 2026-11-13

## 1. R2 authorization record

The rollout was executed only after the release-owner directive
`MAYS-XREPO-CONTROLLED-MAIN-ROLLOUT-04` explicitly requested the controlled
main integration. The preceding review-gate-03 evidence was used:

- historical-integrity and issue-binding corrections;
- exact task-token and mutual issue-link tests;
- both receiver suites 82 PASS / 4 subtests.

No independent human review approval is recorded in GitHub review metadata;
the merge is therefore documented as an operator-authorized rollout, not as an
independently approved change.

## 2. Merge results

| Repository | PR | Feature HEAD | Merge commit | Main after merge |
|---|---|---|---|---|
| Jobsearch | #18 | `6d6b6095eab3c8de9936c0a51940383a19368589` | `a5640d12dba8ca39258484f5212def17eabf4eca` | `a5640d12dba8ca39258484f5212def17eabf4eca` |
| RIS | #9 | `0e59f67ddcce400dff92cd4dcf63756b98f09e2d` | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` | `df3c0329f399daa7ff0f9f0bbb71bb2a017140f9` |

Both PRs are `MERGED`; no branch was deleted and no force-push was used. The
merge commit parents are the previous main and the exact reviewed feature HEAD.

## 3. R3 verification

- Both default branches contain `scripts/xrepo/apply_event.py` with shared
  source/destination state reconstruction.
- Receiver code is byte-identical in both repositories.
- XRepo tests on the actual merged main worktrees:
  - Jobsearch: **82 PASS / 4 subtests**
  - RIS: **82 PASS / 4 subtests**
- Sender/receiver compatibility: unchanged event schema, existing source
  `Issues: read`, target `Issues: write`; no new secret or permission.
- Issue pair #17/#8 is unchanged. Their comments contain **0** trusted
  `mays-xrepo:state`, `event`, or `rejected` markers; no artificial status
  marker was created.
- No XRepo receiver run or live dispatch occurred after the merge; the latest
  receiver runs remain the historical 2026-11-07 runs.
- RIS release candidate is unchanged:
  `release/structured-cv-rc1 @ 4bfd08f7a3afa82cf788fc8da505d9cbae6b91b1`.

## 4. Rollout risks / limits

- Repository-local concurrency only: sequential dispatch is the supported
  operating mode. Simultaneous cross-repo dispatches remain unsupported.
- The GitHub App runtime permission path was not live-exercised in this rollout;
  R4 remains separate.
- No live dispatch, AWS, Terraform, consent activation, Structured-CV product
  release or production deployment was performed.

## 5. Rollback / recovery

- Revert either merge commit through a reviewed PR; do not force-push.
- If a live history conflicts after R4, stop dispatching, inspect both issues
  and the highest trusted sequence, and obtain a human recovery decision.
- Do not write hand-crafted state markers or claim completion from a
  conflicting history.
- RIS RC1 and all product/AWS gates are independent of this XRepo merge.

## 6. Gates

| Gate | Status |
|---|---|
| R1 — review/tests | PASS locally (review gate 03; 82/4 both) |
| R2 — main rollout | EXECUTED under release-owner directive |
| R3 — default-branch verification | PASS |
| R4 — real sequential dispatch | **PENDING / separate approval** |

**STOP before R4 live dispatch.**
