# RIS-JOBSEARCH-APPLICATION-EXT-01 — Implementation Plan

Progress below is evidence-based. Local Moto/runtime evidence is now available;
live deployment and authorized identity evidence remain outside this branch.

| Step | Prompt-ID | RIS-Modul | Beschreibung | Abhängigkeiten | Tests | Status | Fortschritt | Commit |
|---|---|---|---|---|---|---|---:|---|
| 0 | EXT-01-PREFLIGHT | Git/docs | Verify merge baseline, create branch from `origin/main`, preserve Jobsearch read-only boundary | PR #3 merge and clean tree | `git status`, ancestry, merge commit evidence | DONE | 100% | `d4b1188` |
| 1 | EXT-01-STATUS / EXT-02 | `jobsearch/application_contract.py`, repository, handler, API docs | Additive `stage` contract with legacy compatibility, transitions, history fields and status/stage filters | GAP-01 decision | Contract, repository, security and export tests | DONE | 100% | `8ea5918`, `40a00b6` |
| 2 | EXT-01-DETAILS | contract/repository/handler | Add application date, channel, contact, notes, salary and safe null-removal patch semantics | Step 1, GAP-02 | Contract + Moto round-trip passed | DONE | 100% | `e3f352d`, `8db5bbf`, `5a67804` |
| 3 | EXT-01-FOLLOWUP | contract/repository/API | Persist validated `followUp`; support open/completed, `completedAt`, reopen and remove | Step 2, GAP-03 | Moto lifecycle, UTC overdue and stale version passed | DONE | 100% | `76848a1`, `e065a9f` |
| 4 | EXT-01-METRICS | repository, DynamoDB schema, handler | Provide complete owner-scoped metrics independent of cursor page; define stable snapshot/filter semantics | Steps 1–3, GAP-04 | Moto multi-page metrics passed; snapshot limit documented | DONE | 100% | `6c1344c`, `e065a9f` |
| 5 | EXT-01-DOCUMENTS | contract/repository/export, CV boundary | Align cover-letter draft/versions and CV references without PDF/S3 duplication or key disclosure | Steps 2–4, GAP-05 | Metadata/export and configured resolver evidence passed; live fixture open | PARTIAL | 85% | `ce9ef29` |
| 6 | EXT-01-API | handler, `terraform/modules/api/main.tf`, API docs, fixtures | Finalize request/response/error envelopes, routes, pagination, idempotency and OpenAPI-equivalent docs | Steps 1–5, GAP-06 | API/OpenAPI: 47 passed, 301 subtests; resumable delete locally covered | DONE | 95% | `5786cfd`, `006876d` |
| 7 | EXT-01-REGRESSION | tests, IAM, privacy/erasure seams | Verify cross-user/tenant/partner isolation, stale requests, session changes, delete and no credential leakage | Steps 1–6, OI-08/09 | Application 48 passed; security 18 passed; full suite triaged | DONE LOCAL | 90% | `ce9ef29`, `006876d`, `22d09fe`, `1939425` |
| 8 | EXT-01-HANDOFF | docs/reports, release gate | Produce RIS-DEV handoff, package/plan evidence and explicit deployment-readiness decision; keep ris-dev2 separate | Step 7, OI-10 | PR readiness prepared; deployment GO blocked by live/retention gates | BLOCKED EXTERNAL | 75% | ORCH-03 reports |

## Sequencing and gates

Steps 1–3 must precede metrics because status and follow-up semantics determine
the counts. Step 5 must precede export and transfer. Step 6 is not complete
until the API error and cursor contracts are stable. Step 7 must prove fail
closed behavior without weakening Cognito, tenant or partner boundaries. Step 8
may document readiness only; deployment remains a separate authorized action.

## Proposed next implementation step

Review and approve GAP-01. Then implement the versioned status contract and
round-trip fixtures on this branch, without migration or deployment until the
compatibility strategy is approved.
