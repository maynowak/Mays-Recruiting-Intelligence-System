# RIS-R08-SECURITY-04E — Public API and Cache Boundary

## Result: PASS LOCAL for RIS Lambda personal paths

`lambda/handler.py` now routes API events through a central personal-response
finalizer. Subject-bearing `/me*`, `/agents` and `/v1/partner/me/*` responses,
including early errors and Lambda exceptions, receive:

`Cache-Control: no-store, private`

Health, platform, unknown non-personal paths and SQS dispatch are not changed.
Existing response headers are preserved. API Gateway-generated JWT failures
occur before Lambda and cannot receive a Lambda-added header; that limitation
remains explicit.

The separate `lambda/orders_reader.py` boundary was not changed because Orders
is outside this RIS-only scope.
