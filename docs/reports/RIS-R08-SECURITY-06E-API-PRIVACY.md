# RIS-R08-SECURITY-06E — API Privacy Review

The central personal-response boundary applies `Cache-Control: no-store,
private` to personal `/me*` and `/v1/partner/me/*` responses, including early
errors and exception-generated 500 responses. Health and unknown public paths
are not modified. Application response helpers also emit the same header.

Local API/cache and ApplicationV1 contract tests passed. No live API Gateway or
intermediary cache was inspected; legal RG-09 approval remains separate.
