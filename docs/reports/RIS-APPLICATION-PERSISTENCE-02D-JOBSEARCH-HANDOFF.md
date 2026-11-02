# RIS-APPLICATION-PERSISTENCE-02D — Jobsearch Handoff

**Status:** READY as an integration contract; Jobsearch source unchanged

## Contract

The handoff maps `SessionApplicationV1` job/profile/CV references into the
existing RIS ApplicationV1 create contract. `sessionId` is correlation only;
RIS creates the durable `applicationId` and derives ownership from verified
context.

## Safety behavior

- No automatic migration at login.
- User explicitly selects a session draft and confirms persistence.
- Failed or offline migration leaves the local session draft intact.
- Retries reuse the same idempotency key.
- Same-key/different-payload and stale-version responses are surfaced as
  conflicts, never silently overwritten.
- `SUBMITTED` requires a separate explicit confirmation.
- Raw CV files, tokens and partner credentials never cross the fixture or
  ApplicationV1 request.

## Auth adapter requirement

Jobsearch must use a trusted server-side mediation path for the RIS partner
credential. A static credential in the browser is prohibited. The adapter
configuration and offline/session fallback are specified in
`JOBSEARCH-APPLICATION-HANDOFF-V1.md`.

## Test evidence

`tests/test_application_handoff_fixture.py`: **3 passed** with synthetic data.
The fixture covers create mapping, explicit submit, conflict handling,
pagination shape and secret/document exclusion. Browser E2E is planned only
after a separately approved mediation endpoint exists.
