# RIS-APPLICATION-PERSISTENCE-01 — Phase 02 Report

**Result:** ApplicationV1 repository and DynamoDB wiring implemented.

## Implemented

- `jobsearch/application_contract.py`: server-owned identity validation,
  status transitions and optimistic-version contract.
- `jobsearch/application_repository.py`: server UUIDs, scoped reads, owner GSI
  pagination, idempotent create, conditional/transactional writes, history,
  cover-letter metadata versions, export and delete.
- New `${project_name}-${environment}-applications` table with composite key
  `applicationId/entityKey` and `gsi-owner(ownerKey, updatedAt)`.
- Lambda IAM/environment wiring and nine JWT-protected API routes.
- No access tokens, credentials or CV raw bytes are persisted.

## Validation

| Check | Result |
|---|---|
| Contract tests | PASS — 4 |
| Repository integration test | SKIPPED — moto unavailable in local environment |
| Python compile | PASS |
| Terraform validate | PASS |
| Terraform fmt | PASS after formatting |
| AWS mutation | NOT RUN |

The DynamoDB-local/moto evidence remains an explicit follow-up gate; pure unit
tests must not be represented as local DynamoDB integration evidence.
