# RIS-R08-RG09 — Metrics Privacy Assessment

## Technical result: PASS LOCAL / LEGAL REVIEW REQUIRED

`GET /v1/partner/me/applications/metrics` is implemented in the active RIS
checkout:

- Handler: `lambda/handler.py:619-620`
- Context: `lambda/handler.py:553-560`, existing verified partner boundary
- Terraform: `terraform/modules/api/main.tf:511-517`, JWT authorizer
- Repository: `jobsearch/application_repository.py:264-292`
- OpenAPI: `docs/API/openapi-platform.yaml` and `jobsearch/openapi.yaml`
- Hardening: `lambda/handler.py:541-549`, `Cache-Control: no-store, private`

The response contains only aggregate counts: `total`, `drafts`, `submitted`,
`interviews`, `openFollowUps`, `overdueFollowUps`. It consumes all owner-scoped
pages and does not accept client identity selectors.

## Privacy assessment

| Check | Result | Evidence |
|---|---|---|
| User/tenant/partner/issuer binding | PASS LOCAL | `_partner_profile_context`, `ApplicationContext`, owner scope |
| Cross-user/tenant isolation | PASS LOCAL | Application ownership/security tests |
| Raw CV/job/credential/token output | PASS LOCAL | Aggregate response and export/security tests |
| Pagination completeness | PASS LOCAL | Metrics all-page Moto test |
| Unauthorized/error behavior | PASS LOCAL | Existing auth/security/route tests |
| Cache control | PASS LOCAL | `no-store, private`; commit `ed521f3` |
| Logging minimization | PARTIAL | Generic method/path logging; no metric payload logging found; deployed log retention not proven |
| Art.13/14 notice and purpose | REVIEW REQUIRED | Processing-purpose and transparency matrices are proposals, not legal approval |
| Legal basis/retention | REVIEW REQUIRED | `RIS-JOBSEARCH-PROCESSING-PURPOSES-V1.md`, retention policy |

Metrics are personal or indirectly identifying operational data because counts
describe one authenticated subject's application activity. They must remain
purpose-bound and must not be expanded with application IDs, tenant IDs, raw
payloads, CV content, model prompts or credential material without a new review.

## Verification

- Application/API/security/privacy focused reconciliation: **95 passed, 301
  API subtests** across the selected suite.
- Targeted cache-control hardening: **79 passed, 301 API subtests**.
- No AWS call or live metrics request was made.

## Legal separation

This is a technical privacy assessment only. It does not approve Art. 6, Art.
9, Art. 13/14, retention, DSFA or production release.
