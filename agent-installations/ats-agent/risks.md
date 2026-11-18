# ATS Agent — Risks

| Risk | Severity | Mitigation |
|---|---|---|
| ATS upstream is the production contract host `mays-jobsearch.vercel.app`; no non-prod endpoint exists | High for hermetic tests | Synthetic job/profile only; verify contract 1.2; accept as documented canary dependency |
| ATS client timeout 30 s vs Lambda execution | Mitigated in 08 | Worker and dispatch ingress set to 60 s (30 s headroom) |
| Result visibility 60 s vs consumer timeout 30 s | Medium | Accepted debt; raise visibility in a separate reviewed change |
| No DLQ alarms/SNS actions for dispatch/result queues | High operational | Add alarms before partner traffic; manual queue checks until then |
| No `ORDER_FAILED` emission | High product | Failed agent runs leave no Orders trace; do not enable partner traffic until decided |
| Reader `POST /orders` has no request-level idempotency | Medium | Do not retry blindly; use unique `requestId`; duplicate dispatch is safe, duplicate create is not |
| Inline dispatch execution inside a 60 s Lambda | Medium | Keep ATS fast; batch 5; monitor duration; timeouts can leave `RUNNING` rows |
| Secret cache without TTL | Medium | Recycle both Lambdas after rotation; use bare hex only |
| Orders main branch replaced the consumer contract | High for upgrades | Pin 016cdfd; no pin bump toward main without producer rework |
| Permanent ingress rejects are only logged | Medium | Check logs/queue depths; no DLQ artifact for permanent rejects |

Stop conditions: any DLQ message, work row `FAILED`/`DEAD_LETTER`/stuck `RUNNING`, `orderResultDelivery` not `SENT`, or missing Orders `processing`.
