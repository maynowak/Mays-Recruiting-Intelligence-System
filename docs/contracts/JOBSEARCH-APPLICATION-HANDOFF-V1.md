# Jobsearch → RIS ApplicationV1 Handoff

Jobsearch remains unchanged in this phase. The adapter is a client-side or
integration-layer contract, not a new RIS identity boundary.

## Mapping

| SessionApplicationV1 | ApplicationV1 create input |
|---|---|
| `sessionId` | client-side correlation only; never persisted as identity |
| `job.id` / `job.source` | `job.jobId` / `job.source` |
| `job.title`, `company`, `location`, `url` | same fields under `job` |
| selected profile | existing `profileRef` only |
| selected CV | existing `cvRef` only |
| generated letter | explicit `cover-letter-versions` request after user choice |

The adapter sends `POST /v1/partner/me/applications` with an idempotency key
derived from the local handoff attempt. It must not send `userId`, `tenantId`,
`ownerId`, `issuer`, partner IDs, tokens, credentials or raw CV bytes.

## Handoff protocol

1. Keep the SessionApplicationV1 draft unchanged locally.
2. Request explicit user confirmation to persist/submit.
3. Create once with an idempotency key.
4. Store the returned server `applicationId` locally only after a successful
   response.
5. On timeout, retry the same idempotency key; never create a new key.
6. On conflict, fetch the server application and present a merge decision; do
   not overwrite silently.
7. On offline/failure, retain the session draft and expose a retry action.

`SUBMITTED` is never inferred from a successful create. It requires the
separate status call with `confirm: true` and the returned `expectedVersion`.

## Document and status references

The handoff carries CV/profile references and versions, not files. Cover-letter
versions are explicit text records with server-generated version IDs. The
adapter treats `DRAFT`, `READY`, `SUBMITTED`, `WITHDRAWN`, and `ARCHIVED` as
server-owned status values and handles `409 VERSION_CONFLICT` by re-reading.
