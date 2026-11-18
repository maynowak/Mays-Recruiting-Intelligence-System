# ATS Agent — Operations

## Health checks

- Dispatch queue/DLQ depth, result queue/DLQ depth: expected 0 at rest.
- Work items with `orderResultDelivery` in `RETRYING`/`REJECTED`/`NOT_CONFIGURED`.
- Lambda errors/duration for `ris-dev2-dev-agent`, `…-agent-dispatch-ingress`, `…-agent-result-consumer`.
- Secret `ris-dev2-mays-orders-agent-result-hmac`: exactly one `AWSCURRENT`; no `AWSPENDING`.

## Activation

1. Apply reviewed plan with both flags true.
2. Provision secret as bare 64-hex; verify one `AWSCURRENT`.
3. Provision test user, ACTIVE profile (`ownerUserId=sub`), user-wide entitlement (`ats-agent`).
4. Run one synthetic agent order; verify work `COMPLETED`/`SENT`, Orders `processing=COMPLETED`/`2.0`, owner 200/foreign 404.
5. Keep partner traffic disabled until separate approval.

## Deactivation

1. Stop partner traffic.
2. Reviewed plan with `orders_agent_result_enabled=false` and `enable_agent_transport=false`.
3. Revoke test profile/entitlement; delete test users.
4. Keep or delete the secret only via a reviewed procedure.

## Rotation

1. Quiesce traffic; verify all queues 0.
2. Put a new bare-hex value (AWSPREVIOUS holds the old version).
3. Recycle the worker and result consumer (no cache TTL).
4. Run one canary; roll back by moving `AWSCURRENT` to the previous version and recycling again.

## Recovery

- Producer failure: work row shows `RETRYING`; SQS redelivers; after 3 receives the work/dispatch DLQ holds it. Fix secret/config, redrive.
- Consumer signature failure: permanent reject, no DLQ copy; inspect result consumer logs for `invalid service signature`; verify the secret format and envelope messageId basis.
- Stuck `RUNNING` work item: wait for the visibility timeout; if repeated, inspect ingress duration and ATS latency.
