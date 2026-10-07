# P3 — HEALTH / TRACEABILITY

Package owner: OWNER-P3. Started from verified state `803f89f`.

Status: **GREEN** (local).

---

## Gap confirmed

`TriggerType.HEALTH_HEARTBEAT`, `HEALTH_DEGRADED`, `HEALTH_RECOVERED` were
added in `5f52357` and referenced by **nothing**. Verified before starting:

```
$ grep -rn "HEALTH_HEARTBEAT\|HEALTH_DEGRADED\|HEALTH_RECOVERED" --include=*.py .
agents/ecosystem/event_hook.py:39:    HEALTH_HEARTBEAT = "HEALTH_HEARTBEAT"
agents/ecosystem/event_hook.py:40:    HEALTH_DEGRADED = "HEALTH_DEGRADED"
agents/ecosystem/event_hook.py:41:    HEALTH_RECOVERED = "HEALTH_RECOVERED"
```

Enum members, zero emitters.

## What `/health` does and does not prove

Unchanged and deliberately so. `_handle_health` is dependency-free liveness
("is the Lambda running?") and performs no I/O. It says nothing about whether
the runtime can process work. The health plane is the operational half and is
kept separate — no I/O was added to `/health`, and no existing contract was
changed.

## Implementation

New module `agents/ecosystem/health_plane.py`:

| Element | Purpose |
|---|---|
| `HealthTracker` | per-(component, tenant) state machine |
| `Component` | `WORKER`, `AGENT_EXECUTION` |
| `HealthState` | `HEALTHY`, `DEGRADED` |
| `HealthEvent` | frozen observation, identifiers only |
| `HealthTracker.snapshot()` | operational view for a future health endpoint |

**No new infrastructure.** No new queue, no new table, no new monitoring
platform. Events are *returned* to the caller; nothing is persisted. The
existing EventHook vocabulary is reused rather than a parallel one invented.

### Transition semantics — enforced, not documented

1. `record_failure` emits `HEALTH_DEGRADED` **only on the transition** out of
   HEALTHY. 50 consecutive failures produce 1 event.
2. `record_success` emits `HEALTH_RECOVERED` **only** if this tracker observed
   a degradation. Ten successes from a healthy component produce nothing.
3. After recovery the state is HEALTHY, so a second success emits nothing —
   `RECOVERED` can never repeat.
4. `heartbeat` is rate-limited to one event per `heartbeat_interval`
   (default 5 min), so idle components cannot flood the plane.

### Metadata constraints

Health events carry `eventId, eventType, occurredAt, component, state,
tenantId, workId, agentId, attemptId, reason, consecutiveFailures` and nothing
else.

`reason` is a **closed vocabulary** (`AGENT_ERROR`, `ENTITLEMENT_DENIED`,
`ENTITLEMENT_UNAVAILABLE`, `INFRASTRUCTURE`). An unrecognized reason is
coerced to `INFRASTRUCTURE` rather than passed through — otherwise a raw
exception string containing a connection string or token would become a
data-exfiltration path into the health plane. Tested explicitly with
`postgres://user:hunter2@host/db`.

`_assert_minimal()` re-checks the serialized form against a forbidden-key set.
It cannot fire today (the dataclass has no payload fields); it exists so that
adding such a field later fails loudly in tests.

### Tenant isolation

State is keyed by `(component, tenant_id)`. A degradation in tenant A does not
mark tenant B degraded, and recovery in tenant B does not clear tenant A.

## Runtime wiring

`agents/runtime/pipeline.py::process_record` gains an optional
`health_tracker` parameter (default `None`, so all existing callers and tests
behave exactly as before). Events are emitted at the boundaries that already
exist:

| Boundary | Event |
|---|---|
| entitlement store unreachable | `HEALTH_DEGRADED` (`ENTITLEMENT_UNAVAILABLE`) |
| agent execution raises | `HEALTH_DEGRADED` (`AGENT_ERROR`) |
| agent reports failure result | `HEALTH_DEGRADED` (`AGENT_ERROR`) |
| successful completion | `HEALTH_RECOVERED` (only if degraded) |

**Entitlement DENIED deliberately emits nothing.** A denial is the system
working correctly, not an operational failure. Marking it degraded would
produce noise for every authorization rejection and would mask real failures.
Pinned by test.

### Instrumentation is fail-safe

Health recording is wrapped so that a broken tracker can never fail a user's
job. Verified by `TestInstrumentationIsFailSafe`.

This caught a real bug during development: the first implementation passed
`health_tracker.record_success` (an attribute access evaluated at the call
site) into the wrapper, which raised `AttributeError` on `None` before the
`if health_tracker is None` guard could apply. My own integration test
`test_absent_tracker_preserves_legacy_behaviour` caught it. Fixed by passing
the method *name* and resolving it inside the guard.

## Traceability

Existing identifiers only; **no new correlation identifier introduced**:
`tenantId`, `workId`, `agentId`, `attempt` already propagate through the
pipeline, and health events reference them directly. `workId` is the natural
correlation handle and a new `correlationId` would have been redundant.

## TESTS

`tests/test_health_plane.py` — 19 tests, state machine in isolation
(transition, anti-flooding, heartbeat rate limit, tenant isolation, metadata
leakage, reason coercion, fail-safe).

`tests/test_health_plane_integration.py` — 7 tests, real `process_record`
calls against a fake DynamoDB table, proving the pipeline actually emits:

- successful run emits no degradation
- fail-then-succeed emits exactly `DEGRADED`, `RECOVERED`
- no duplicate `RECOVERED` across successive successes
- events carry the real `workId` / `tenantId`
- serialized events contain neither the payload message nor the word `payload`
- `health_tracker=None` preserves legacy behaviour
- entitlement denial does not degrade the runtime

```
FULL SUITE  1111 collected / 1103 passed / 0 failed / 8 skipped / 236 warnings
```

Baseline moved 1085 → 1111 collected (+26, all new).

## FILES CHANGED

- `agents/ecosystem/health_plane.py` — NEW
- `agents/runtime/pipeline.py` — optional tracker + 4 emission points
- `tests/test_health_plane.py` — NEW, 19 tests
- `tests/test_health_plane_integration.py` — NEW, 7 tests

## NOT DONE

- Health events are not persisted or routed anywhere. They are returned to
  the caller; wiring them to CloudWatch or a store is a separate decision that
  should follow a real consumer existing.
- No `/health/runtime` endpoint was added. `snapshot()` is the groundwork, but
  a new read endpoint needs its own route, auth decision and governance —
  not something to bolt on inside P3.
- AWS live verification of health wiring remains part of the suspended
  AWS branch.