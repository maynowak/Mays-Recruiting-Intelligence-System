# ATS Agent — Tests

Local (no AWS):

```powershell
$env:MO_ORDERS_SRC = "<repo>\installer\projects\mays_order_builder\lambda\src"
python -m pytest tests/test_agent_order_dispatch_e2e.py -q
python -m pytest tests/test_orders_reader.py tests/test_dispatch_ingress_lambda.py -q
python -m pytest tests/test_order_transport_contract.py tests/test_worker_pipeline.py -q
```

Expected (baseline 2026-11-18):

- E2E: 6 passed
- Reader: 35 passed
- Dispatch ingress: 16 passed
- Transport/worker: green

Live canary (approved test scope only):

1. `POST /orders` with `orderType=agent.execution`, `target={agentId: ats-agent, capability: analyze.job}`, synthetic job/profile, `metadata.requestId` and `metadata.apiProfileRef`.
2. Expect 201, order `PENDING`, `dispatch.status=SENT`.
3. Work item `COMPLETED` and `orderResultDelivery.status=SENT`.
4. Order `processing.status=COMPLETED`, `processing.result.bodyVersion=2.0`, numeric `analysis.score`, order `status` unchanged.
5. Owner read 200; foreign owner 404; invalid token 401.
6. Replay the same dispatch; no second `processing` write/version bump.
7. Dispatch and result queues/DLQs return to 0.

Never use real applicant data; use synthetic job/profile only.
