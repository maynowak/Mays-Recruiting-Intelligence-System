# RIS-JOBSEARCH-APPLICATION-EXT-01 — Baseline

## Ergebnis

```text
BASELINE VERIFIED — SAFE DOCUMENTATION BRANCH CREATED
```

No product implementation, deployment, AWS mutation, or Jobsearch change was
performed.

## RIS Git preflight

| Check | Evidence | Result |
|---|---|---|
| Repository | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1` | verified checkout |
| Branch before | `feature/ris-application-persistence-v1` | inspected only |
| HEAD before | `b001cbd68ee491244ed792eb2a3ae248d2425cbc` | clean |
| Working tree | `git status --short --untracked-files=all` | clean |
| `origin/main` | `37782f8462f515e0d860ba1ba64e976c7e14b8b9` | fetched and verified |
| PR #3 merge | merge commit `37782f8`, parents `26b3660` and `b001cbd` | verified |
| old feature relation | `origin/main...feature/ris-application-persistence-v1 = 7 0` | seven behind, no extra commits |
| requested branch | no local or remote `feature/ris-jobsearch-application-ext-01` | available |
| branch after | `feature/ris-jobsearch-application-ext-01` | created from `origin/main` |
| HEAD after | `37782f8462f515e0d860ba1ba64e976c7e14b8b9` | clean, tracks `origin/main` |

The local `main` ref was `a3f3c7863ac5f47850f7334975ad3154ef956d28`; it was not
checked out or modified. No reset, clean, stash, rebase, merge, push, or force
operation was used.

## Jobsearch read-only reference

The local checkout is
`C:\Users\DCI-Student\projekte\mays-jobsearch` on
`feature/arbeit`, HEAD `0c97827`, with a clean working tree. Its only local
commit beyond the fetched `origin/main` is:

```text
0c97827 fix(jobsearch): align cv document size contract with ris
```

Fetched Jobsearch `origin/main` is `0fa799e66f056d68e2bb49075fbeaf14f6f5f8a0`.
The requested application UX is present in that remote ref, not in the local
feature worktree. The feature branch was not changed or checked out.

Relevant `origin/main` evidence:

| Scope | Commit | Reference status |
|---|---|---|
| UX-04A details editing | `65e314a` | in Jobsearch `origin/main` |
| UX-04B responsive manager | `f5dd90a` | in Jobsearch `origin/main` |
| UX-04C detail tabs/history | `aac997b` | in Jobsearch `origin/main` |
| UX-04D follow-ups | `1d1eccd` | in Jobsearch `origin/main` |
| UX-04E consolidation | report evidence | in Jobsearch `origin/main` |
| UX-05A cockpit metrics/filters | `11815ad` | in Jobsearch `origin/main` |
| UX-05B compact cards | `9643dd1` | in Jobsearch `origin/main` |
| cover-letter full display | `a1b2588`, report `4364eab` | in Jobsearch `origin/main` |

Read-only snapshots were staged outside both repositories at
`C:\Users\DCI-Student\AppData\Local\Temp\opencode\jm-origin-main-read`.
No Jobsearch file was created, modified, deleted, built, tested, committed, or
pushed.

## RIS implementation baseline

The current RIS `origin/main` contains an ApplicationV1 repository and routes:

- Contract: `jobsearch/application_contract.py` — statuses are
  `DRAFT`, `READY`, `SUBMITTED`, `WITHDRAWN`, `ARCHIVED`; current create and
  patch payloads only accept `job`, `profileRef`, `cvRef`, and version/idempotency
  metadata.
- Persistence: `jobsearch/application_repository.py` — server UUIDs,
  owner-scoped reads, signed cursor tokens, idempotent create, conditional
  version writes, history/cover-letter child items, export and delete.
- Handler: `lambda/handler.py` — partner routes under
  `/v1/partner/me/applications`; context is derived through the existing
  partner-profile boundary.
- Gateway: `terraform/modules/api/main.tf` — explicit CRUD, status, history,
  cover-letter, export and delete routes.
- Storage: `terraform/modules/dynamodb/main.tf` — dedicated applications table
  with `gsi-owner`; IAM wiring is in `terraform/modules/lambda/main.tf`.

The implementation exists in code and has historical local test evidence in the
audit log, but no live API or deployment verification is claimed for this
planning phase. The new branch is therefore suitable for analysis only.

## Safety gate

The baseline is unblocked for documentation. Implementation remains out of
scope until the open items and plan below are reviewed.
