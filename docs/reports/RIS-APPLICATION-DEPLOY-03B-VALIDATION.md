# RIS-APPLICATION-DEPLOY-03B — Offline Validation

**Status:** PASS

## Executed checks

| Check | Result |
|---|---|
| ApplicationV1 repository and Moto DynamoDB | PASS |
| Auth/API security | PASS |
| Privacy/erasure integration | PASS |
| API/OpenAPI contract parity | PASS |
| Partner profile/CV/ATS regression | PASS |
| Python compilation | PASS |
| Terraform init `-backend=false` | PASS |
| Terraform `fmt -check -recursive` | PASS |
| Terraform `validate` | PASS, with provider deprecation warnings only |
| `git diff --check` | PASS |

The focused run completed with **224 passed** and **297 API-contract
subtests passed** in 13.58 seconds. It used synthetic/local Moto data only and
did not access AWS. Python compilation covered the ApplicationV1 repository,
Lambda handler and privacy/erasure modules.

Terraform validation initialized provider AWS `6.67.0` without a backend.
Terraform emitted existing `aws_dynamodb_table.range_key` deprecation
warnings; validation still succeeded. The generated local provider-lock
change was discarded and the worktree remains clean apart from this report.

## Scope checks

- ApplicationV1 table/GSI, Lambda environment/IAM wiring, API routes,
  JWT/partner boundary, OpenAPI and privacy/erasure code are covered by the
  focused suites.
- No Jobsearch source or connection was used.
- No real credentials, access tokens, applications, documents, model calls or
  global privacy/erasure flags were used.
- No Terraform remote plan or Apply was performed in 03B.

## Known unrelated full-suite baseline

The previously recorded full repository run remains **not a PASS**: 2266
passed, 56 skipped, 395 subtests passed and 29 Windows/environment failures.
Those failures concern unrelated platform assumptions and are kept separate
from this focused ApplicationV1 validation result.
