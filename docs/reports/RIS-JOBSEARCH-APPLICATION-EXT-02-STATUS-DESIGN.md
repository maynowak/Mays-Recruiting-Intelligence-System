# RIS-JOBSEARCH-APPLICATION-EXT-02 — Status Design

## Decision

RIS uses an **additive lifecycle/stage model**, not a lossy replacement of the
existing `status` field.

- `status` remains the legacy RIS lifecycle enum:
  `DRAFT`, `READY`, `SUBMITTED`, `WITHDRAWN`, `ARCHIVED`.
- `stage` is an optional additive Jobsearch enum:
  `draft`, `submitted`, `feedback`, `interview`, `offer`, `rejected`,
  `withdrawn`.
- The two fields are deliberately different projections. A Jobsearch stage
  keeps its exact value in `stage`; the legacy field remains a coarse lifecycle
  value for older clients.
- New creates start with `status: DRAFT` and `stage: draft`.
- No existing DynamoDB item is migrated or rewritten automatically.

This protects older clients because their existing `status` values and
transitions remain valid. Unknown additive `stage` data can be ignored by a
legacy JSON client, while a Jobsearch-aware client uses `stage` for exact
state. The status endpoint requires exactly one selector: `status` for the
legacy contract or `stage` for the Jobsearch contract.

## Lifecycle projection

| Jobsearch stage | Legacy `status` projection | Reason |
|---|---|---|
| `draft` | `DRAFT` | not submitted |
| `submitted` | `SUBMITTED` | explicitly sent |
| `feedback` | `SUBMITTED` | submitted lifecycle, response stage retained in `stage` |
| `interview` | `SUBMITTED` | submitted lifecycle, interview stage retained in `stage` |
| `offer` | `SUBMITTED` | submitted lifecycle, offer stage retained in `stage` |
| `rejected` | `SUBMITTED` | submitted lifecycle, rejection retained in `stage` |
| `withdrawn` | `WITHDRAWN` | withdrawn lifecycle |

`READY` and `ARCHIVED` have no silent Jobsearch equivalent. Existing records
remain readable with exactly their stored legacy value and without an invented
stage. A Jobsearch stage transition from such a record is rejected with
`STAGE_UNAVAILABLE` until an explicit, user-directed compatibility decision is
made. This avoids silently converting `READY` or `ARCHIVED`.

## Transition matrix

### Legacy status selector

| Current | Allowed targets | Confirmation |
|---|---|---|
| `DRAFT` | `DRAFT`, `READY`, `ARCHIVED` | `SUBMITTED` is not reachable through this row without the existing `READY` path |
| `READY` | `READY`, `DRAFT`, `SUBMITTED`, `ARCHIVED` | `SUBMITTED` requires `confirm: true` |
| `SUBMITTED` | `SUBMITTED`, `WITHDRAWN`, `ARCHIVED` | no new submission confirmation |
| `WITHDRAWN` | `WITHDRAWN`, `ARCHIVED` | none |
| `ARCHIVED` | `ARCHIVED` | none |

### Jobsearch `stage` selector

| Current | Allowed targets | Confirmation |
|---|---|---|
| `draft` | `draft`, `submitted` | `submitted` requires `confirm: true` |
| `submitted` | `submitted`, `feedback`, `interview`, `rejected`, `withdrawn` | none except initial submit |
| `feedback` | `feedback`, `interview`, `offer`, `rejected`, `withdrawn` | none |
| `interview` | `interview`, `offer`, `rejected`, `withdrawn` | none |
| `offer` | `offer`, `withdrawn` | none |
| `rejected` | `rejected` | terminal |
| `withdrawn` | `withdrawn` | terminal |

Status and stage mutations both require `expectedVersion`, retain the existing
owner/tenant/partner/issuer scope, and use the existing conditional DynamoDB
transaction. A stale write remains `409 VERSION_CONFLICT`.

## History and export

Status history remains append-only. Existing history records retain their
`status` field. New transitions additionally record `fromStatus`, `toStatus`,
and, for stage mutations, `fromStage` and `toStage`; an optional transition
note is retained. Export therefore preserves the original legacy history and
the exact Jobsearch stage path without migration.

## Filters and pagination

`GET /v1/partner/me/applications` accepts either `status` or `stage` as a
filter, never both. The signed cursor binds the owner, limit and filter values,
so a cursor cannot be replayed for another status model or identity. Existing
unfiltered cursors remain readable because absent filter claims resolve to
`null`.

This implements status filtering only. Complete cockpit aggregates remain
GAP-04 and are not claimed as completed by this change.

## Security and migration boundary

`applicationId`, identity fields, status ownership and versions remain
server-controlled. No browser credential, Jobsearch change, DynamoDB migration,
AWS mutation or deployment was performed. Existing `READY` and `ARCHIVED`
records are read-only compatible; no automatic reinterpretation is applied.
