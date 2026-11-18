# ATS Agent — Handoff

- **Agent:** `ats-agent`, capability `analyze.job`, runtime version 1.0.0.
- **Source:** mays-ris `f0c707c6e80638a6489194b3be98374718a6a522`; Orders pin `016cdfd6ac62565dcec9a2fee78cb898fb919e59`.
- **Live status (ris-dev2, 2026-11-18):** deployed and live-E2E PASS with synthetic data.
- **Observed evidence:** work `COMPLETED` + `orderResultDelivery=SENT`; Orders `processing=COMPLETED`, `bodyVersion=2.0`, score 67, order status `PENDING`; owner 200 / foreign 404 / invalid token 401; duplicate no second write; retail 201/200; queues/DLQs 0.
- **Test data:** synthetic users/entitlement deleted; profiles revoked; two test orders and work rows remain as evidence only.
- **Not enabled:** partner traffic; production `ris-dev`.
- **Open decisions for ris-dev:** enable partner traffic, add DLQ alarms/SNS actions, decide `ORDER_FAILED`, raise result visibility, provide a non-production ATS endpoint.
- **Do not:** point at Orders `main` without reworking the result consumer contract; seed secrets via Terraform; print or store the HMAC value.
