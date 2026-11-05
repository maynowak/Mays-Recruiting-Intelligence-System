# RIS-R08-SECURITY-04D — Erasure Resume

## Result: PASS LOCAL / LIVE ERASURE BLOCKED

The durable `ProfileOnlyErasureExecutor` now requests
`include_deleting=True` from `ApplicationRepository.list()`. An application
marked `IN_PROGRESS` before a crash or child-delete failure is therefore
visible on resume instead of being filtered as if absent.

Reduced completion scopes are guarded by a non-serializable
`LOCAL_SYNTHETIC_COMPLETION_TOKEN`; ordinary transitions require the complete
canonical category set. No public client can serialize or select the token.

Existing S3 fencing, upload-ticket cutover, live backup reconciliation and
production erasure activation remain blocked.
