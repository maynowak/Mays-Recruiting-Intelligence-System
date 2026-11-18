# <Agent> — Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Shared transport change affects all agents | Medium | Validate ats-agent first; do not change transport per agent |
| No request-level idempotency on the facade | Medium | Unique requestId; duplicate dispatch safe, duplicate create not |
| <agent-specific risk> | <level> | <mitigation> |

Stop conditions: non-zero DLQ, work row not `COMPLETED`, missing Orders
`processing`, owner boundary failure.
