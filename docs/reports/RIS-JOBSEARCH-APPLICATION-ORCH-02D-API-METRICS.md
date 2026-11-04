# RIS-JOBSEARCH-APPLICATION-ORCH-02D — API and Metrics

## Result: PASS for local API/contract gates

All ten Terraform ApplicationV1 routes are JWT-protected, including:

`GET /v1/partner/me/applications/metrics`

The OpenAPI specification and ApplicationV1 contract route table now declare
the metrics route. Metrics consume complete owner-scoped cursor traversal and
return total, drafts, submitted, interviews, open follow-ups and overdue
follow-ups. Overdue classification uses `datetime.now(timezone.utc).date()`;
the date-only contract therefore has an explicit UTC basis.

## Evidence

- OpenAPI/route consistency: **47 passed, 301 subtests passed**.
- API security/auth/privacy selection: **18 passed**.
- Metrics Moto runtime path: included in **11 passed** repository/E2E tests;
  direct metrics runtime test is `test_metrics_runtime_traverses_owner_scoped_moto_pages`.
- Cursor tampering, identity binding, filters and pagination remain covered by
  the ApplicationV1 runtime selection.

## Consistency boundary

Metrics are a complete traversal, not a transactional snapshot. Concurrent
mutations during traversal can produce a mixed-time result; this is documented
and is not represented as snapshot consistency.
