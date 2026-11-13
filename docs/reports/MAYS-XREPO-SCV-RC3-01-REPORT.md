# MAYS-XREPO-SCV-RC3-01 — Structured CV Release Candidate

**Status:** `MAYS-XREPO-SCV-RC3-01 — BLOCKED / XREPO CORRECTION REQUIRED`

**Date:** 2026-11-13

**RC branch:** `release/structured-cv-rc1`
**RC HEAD:** `3cc4576`

**Important:** This report does not claim a successful XRepo handoff. The RIS
release candidate is locally integrated, but the actual cross-repository status
sequence is blocked by a destination-issue-scoped state-reconstruction defect.

## 1. Git baselines

| Repository/ref | SHA |
|---|---|
| Jobsearch `origin/main` | `854da7725ad62a85f5877e8ec041431b8d459bb5` |
| Jobsearch evidence branch `feature/jm-ris-structured-cv-consent-readiness-01` | `2b830e61fbd40c5121da8f9038c616a0339ca2b3` |
| RIS `origin/main` | `f830a5edc63fc0b91203073a288bb60d374b413f` |
| RIS backend hardening | `0e088224babdaea18c2f22c7acbafe8f96d9cbc6` |
| RIS API routes | `1d65696262f85c6744884496400fce223a46840f` |
| RIS privacy package | `ea898b98979f2170b0bafa7946297bfe81868679` |
| RIS release-gate-02 | `60b47c13b6014b747361d784b65a3841d657aea0` |
| RIS RC1 | `3cc45765688fba74c0ce22a7c9a721e742bcc930` |

No remote head was rewritten and no branch was force-pushed.

## 2. XRepo readiness

- Jobsearch workflows active: `MAYS XRepo Receive`, `MAYS XRepo Send`.
- RIS workflows active: `MAYS XRepo Receive`, `MAYS XRepo Send`.
- Both repositories expose `XREPO_APP_ID` and `XREPO_APP_PRIVATE_KEY` as
  Actions secret names. Values were not read.
- Existing live runs demonstrate sender/receiver activity, but no same-task
  reverse handoff has been proven.
- Actual issue pair created:
  - Jobsearch: `maynowak/mays-jobsearch#17`
  - RIS: `maynowak/Mays-Recruiting-Intelligence-System#8`
  - Both issues cross-link each other.
- Task ID: `MAYS-SCV-RC3-001`.
- No status marker or dispatch was written to either issue.

## 3. Why the handoff is blocked

Independent read-only code audit confirmed:

- `apply_event.py:last_state()` reconstructs state only from comments on the
  **destination issue**.
- `apply_event.py:apply_event()` fetches comments from
  `event["destination"]` only and writes only there.
- The receiver app token for the source repository is read-only
  (`contents: read`, `issues: read`), so applied state is never mirrored back.
- The sender records only prose on the source issue, not a trusted
  `mays-xrepo:state:` marker.
- The receive workflow's `--expected-target "$GITHUB_REPOSITORY"` prevents
  redirecting the ACCEPTED event to the RIS issue.

Local decision simulation with the real `decide()` function:

```text
empty Jobsearch issue:
Decision(action='invalid_transition', last_sequence=None,
         reason="initial status must be one of ['BLOCKED', 'REQUESTED']")

same ACCEPTED event against a RIS issue containing
<mays-xrepo:state:MAYS-SCV-RC3-001:1:REQUESTED>:
Decision(action='apply', last_sequence=1, last_status='REQUESTED')

Jobsearch receiver does not see the REQUESTED marker:
Decision(action='invalid_transition', last_sequence=None,
         reason="initial status must be one of ['BLOCKED', 'REQUESTED']")
```

Therefore a real `ACCEPTED` sent RIS→Jobsearch for this task would be rejected
as an invalid initial transition and would burn its event id. Sending it would
not be evidence of progress. No dispatch was sent.

## 4. RIS release candidate

Created `release/structured-cv-rc1` from `60b47c1` and integrated:

- merge `296c7c4` — API Gateway routes `1d65696`;
- merge `3cc4576` — privacy approval package `ea898b9`;
- auditlog conflicts resolved append-only; both entries retained.

Included:

- Structured-CV backend `0e08822`;
- hardening/transaction/privacy work;
- six explicit API Gateway routes;
- privacy approval package;
- release-gate documentation;
- feature flags OFF;
- notice remains DRAFT with no legal approval ref.

No main merge, AWS call, Terraform plan/apply, state access, deployment or
consent activation was performed.

## 5. Local verification

RIS RC1:

- full suite: **2582 passed / 56 skipped / 19 documented baseline failures**;
- Terraform `fmt -check -recursive` PASS;
- local `terraform init -backend=false` + `validate` PASS;
- API route tests: six explicit JWT/Lambda routes, no wildcard/proxy;
- no AWS/state/apply.

Jobsearch evidence `2b830e6`:

- BFF/client/consent focused suite: **51 passed**;
- combined mock-BFF E2E: PASS (import → 71 skills/58 selected/44 review →
  durable save/reload/update; 14 mock calls);
- Vercel/UI production activation remains blocked by flags and legal gate.

Cross-repo contract checks against RC1:

- six RIS routes align with Jobsearch BFF actions;
- JWT authorizer and partner credential remain server-side;
- owner isolation and server-side consent remain authoritative;
- ETag/If-Match and Idempotency-Key behavior covered by BFF/client tests;
- 409/428/503 mapping covered;
- 71-skill/44-review DTO roundtrip covered;
- no real CV data or RIS write.

## 6. XRepo status/evidence

- `REQUESTED`: **NOT SENT** (blocked before dispatch by protocol defect).
- `ACCEPTED`, `IMPLEMENTING`, `IMPLEMENTATION_READY`, `INTEGRATING`,
  `VERIFIED`, `COMPLETED`: **NOT APPLIED / NOT CLAIMED**.
- Event IDs, sequences and workflow run links: none generated by this run.
- Issue pair exists only for evidence and future correction.

## 7. Release-gate register

| Gate | Status |
|---|---|
| G0/G1/G2 | local verified |
| XRepo RC3 | **BLOCKED / CORRECTION REQUIRED** |
| G3 Legal | PENDING |
| G4 AWS Discovery/Plan | PENDING |
| G5 Terraform Plan | NOT CREATED |
| G6 Apply | PENDING |
| G7 Flags-OFF deployment | NOT EXECUTED |
| G8 Consent activation | BLOCKED |
| G9 Live E2E | NOT EXECUTED |
| G10 Production | BLOCKED |

## 8. Required XRepo correction

A separate, explicitly authorized protocol correction is required. Options
include mirroring applied state to the source issue, sender-side state recording
with applied-outcome reconciliation, or a formally documented per-direction
sequence model. Do not modify the production workflows as part of RC3 without
that authorization.

## 9. Next steps

1. Review the RC1 and the blocked XRepo evidence.
2. Authorize a separate protocol correction task; do not invent status markers.
3. After correction, replay a real `REQUESTED`/`ACCEPTED` sequence with fresh
   issue/state handling.
4. Continue legal/AWS G4-G10 gates separately.

**STOP before AWS G4, consent activation, main merge or production.**
