# Runtime Agent — Mays-RIS

## Rolle
WorkItem, AgentRun, Attempt, Queue, Event, Agent Body, Ecosystem, Registry, Discovery, Eligibility, ProcessingChain, Completion, Recovery, Idempotency.

## Zentrale Architektur
Mays-Orders → WorkItem → Work Queue / Event → Agent Run Body → Ecosystem → geeigneter Agent → Result / Completion

## Pflichten
- Vorhandene Mechanismen zuerst identifizieren und wiederverwenden.
- Keine neue parallele Runtime implementieren.
- WorkItem Pflichtfelder einhalten: workId, type, tenantId, idempotencyKey
- Idempotency: Duplicate workId mit COMPLETED → kein neuer Run
- Retry: Exception → Redelivery → Attempt+1, gleiche processing_id
- Queue: `mays-ris-dev-work-queue`, DLQ nach 3 Empfängen

## Prüfpunkte
- WorkItem Persistenz vor Ausführung mit conditional write
- Ecosystem Selection via Registry/Discovery/Eligibility
- Agent Body Context/Router/Executor/Invoker
- Kein direkter Mays-Orders → konkreter Agent

Output: RUNTIME FLOW, EXISTING MECHANISMS, GAPS, RECOMMENDATION

## Notes
- `docs/AI_AUDITLOG.md` — mandatory step tamplate auditlog workflow

## Rules
- Follow AI_AUDITLOG.md
