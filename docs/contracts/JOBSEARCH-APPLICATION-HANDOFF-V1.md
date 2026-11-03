# Jobsearch → RIS ApplicationV1 Handoff

Jobsearch remains unchanged in this phase. The adapter is a client-side or
integration-layer contract, not a new RIS identity boundary.

## Adapter configuration

- `RIS_APPLICATION_API_BASE_URL` is supplied by deployment configuration; it
  is never hardcoded into a browser bundle or fixture.
- The adapter sends the existing Cognito access token to the trusted RIS
  boundary. It does **not** manufacture or persist `X-Api-Credential`.
- A server-side broker/integration proxy must attach the partner credential
  from its protected runtime configuration. Direct browser calls are allowed
  only when an already-approved short-lived mediation mechanism exists.
- Session mode remains local-only when the broker is unavailable.

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

## End-to-end readiness matrix

| Flow | Required behavior |
|---|---|
| login/reload/logout/login | remote ID is reloaded only for the authenticated subject |
| create/save | explicit user action, same idempotency key on retry |
| status/history/letter | expectedVersion required; 409 triggers re-read/merge UI |
| pagination/export/delete | cursor and application ID remain server-scoped |
| offline/network error | session draft is retained; remote state is not guessed |

## Document and status references

The handoff carries CV/profile references and versions, not files. Cover-letter
versions are explicit text records with server-generated version IDs. The
adapter treats `DRAFT`, `READY`, `SUBMITTED`, `WITHDRAWN`, and `ARCHIVED` as
server-owned status values and handles `409 VERSION_CONFLICT` by re-reading.
