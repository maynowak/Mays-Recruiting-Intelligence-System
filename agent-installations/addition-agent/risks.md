# Addition Agent — Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Shared transport misconfiguration affects all agents | Medium | Validate the ats-agent package first; transport is shared |
| No request-level idempotency on the facade | Low | Use unique requestId; duplicate dispatch is safe |

Stop conditions: non-zero transport DLQ, work row not `COMPLETED`, result `sum` not 42.
