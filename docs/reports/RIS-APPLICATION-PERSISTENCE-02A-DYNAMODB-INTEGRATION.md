# RIS-APPLICATION-PERSISTENCE-02A — DynamoDB Integration

**Status:** PASS in isolated Moto DynamoDB; no production table used

## Evidence

The repository integration suite now uses `moto[dynamodb]` and creates an
ephemeral composite-key table named `applications` inside the test process.
The fixture contains only synthetic IDs and text.

Covered:

- create/get/list/update/status/delete lifecycle;
- server-generated IDs;
- idempotent retry and same-key/different-payload conflict;
- conditional version conflict;
- owner-GSI pagination across multiple pages;
- HMAC cursor tampering and wrong-user rejection;
- user, tenant, partner and issuer isolation;
- transactional status/history writes.

## Test result

`tests/test_application_repository.py`: **2 passed** with Moto 5.2.5.

The tests are explicitly local/mocked DynamoDB evidence, not evidence from
`ris-dev2`. No AWS credentials or production table names are used.

## Remaining repository gate

Transient service failure behavior is fail-closed at the API boundary and
returns `503`; a live retry/backoff policy remains an operational deployment
decision and is not exercised against AWS in this task.
