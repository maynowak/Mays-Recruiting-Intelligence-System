# GATE-5 — Agent-Run-Body-WorkItem-Event-Idempotency

STATUS: GREEN

- Date/Time: 2026-10-01 16:35 UTC
- Branch + HEAD (RIS): main, 8d543c1 + Gate-5-Aenderungen (s. R)
- MO-Stand: unberuehrt (Clone 9c61 clean/ignoriert; fremde Lambdas Original-Bundle; keine MO-Mutation)
- Scope: vorhandenen Worker/SQS-Eingang mit vorhandenem Agent Body ueber vorhandenes Ecosystem verdrahten; Idempotency/Attempt/Retry/Result nachweisen. KEIN Parallelsystem, KEIN Foundation-Apply, KEIN MO-Adapter, KEIN neuer Domain-Agent.
- Sections: A–S unten
- Findings: Voller Runtime-Pfad live belegt (SQS→Worker→Envelope→Discovery→Eligibility→Auswahl→Engine→Invoker→Body→ReferenceAgent→Result); Duplikat- und Retry-Tests live gruen; 2 Live-Bugs gefunden+gefixt (Float-Persistenz, reservierte DDB-Woerter)
- Evidence: Unit-Tests (7 neu), Lambda-Logs (jeder Pfadschritt), DDB-Items, Queue/DLQ-Tiefen, TF-State
- Classification: GREEN
- Terraform/AWS Checks: validate GREEN; gezielte Plaene (SQS-Policy per TF; Mapping per CLI wegen vorbestehender lambda.zip-Luecke); kein Full-Apply; 0 destroys
- Git Status (RIS): nur Gate-5-Dateien (s. R); Clone/Artefakte ignoriert
- Files Changed: `agents/runtime/` (neu: pipeline), `lambda/handler.py`, `agents/agent_body/__init__.py` + `/invocation.py`, `agents/ecosystem/routing.py` (Kommentar), `tests/test_worker_pipeline.py` (neu), diese Reports
- Open Questions: s. S (Upstream-Handoff keiner noetig — alles eigener Bereich; lambda.zip-Luecke bleibt)
- Risks: keine neuen (Least-Privilege bestaetigt, DLQ bestehend genutzt, keine Secrets)
- Next Actions: Commit → Folgetor (OrdersPort/Real-Adapter auf stabilem Pfad)
- Resume Point: nach Commit HARD STOP

## A. Ausgangslage

Gate 4 GREEN (eigene Orders-Fassade live; Fremd-Projekt unberuehrt). Offener Punkt: Worker→Agent Body. Live vorgefunden (unser Bereich): Agent-Lambda `mays-ris-dev-agent` (Bundle Sep-30, Einstieg `handler.lambda_handler`), Work-Queue + DLQ (maxReceiveCount 3) vorhanden, aber KEIN Event-Source-Mapping (Config deklariert es, State/Live leer) und KEINE SQS-Policy an der Rolle (Config deklariert, nie applied). Worker-Code rief Body direkt ohne Envelope/Ecosystem/Idempotency.

## B. Vorhandener Worker

`lambda/handler.py`: `_handle_sqs_event` (Records-Loop) → `_process_work_item` → `AGENT_BODY.execute` (direkt, ohne Auswahl/Idempotency/Persistenz; Fehler geschluckt → 200 trotz Fehler). `agents/handler.py`: AgentHandler-Template (nicht live-verdrahtet). Entscheidung: `lambda/handler.py` ist der Worker-Einstieg (live Form); minimal auf Pipeline umgestellt + Fehler-Re-Raise (Retry) + `lambda_handler`-Alias (Live-Einstieg).

## C. Vorhandenes WorkItem

`agents/base.py`: WorkItem (workId/type/tenantId/idempotencyKey Pflicht; Status CREATED/QUEUED/RUNNING/COMPLETED/FAILED/RETRY/DEAD_LETTER/...) + AgentBase (process_work/validate/get_status, Retry-Delay-Helper). Wiederverwendet (Validierung = Registrierungs-Tor). Keine Felder neu erfunden; Envelope-Trace-Ids (processing/execution/attempt/parent, sequence/attempt) in DDB-Item persistiert.

## D. Agent Body

AgentBody.execute → Context → Router → Handler → Result (Harness `tests/test_agent_body.py` = Referenz, 45 Baseline-Tests gruen). Zwei minimale Korrekturen: (1) `register_agent()` reicht `agent_id` durch (Router konnte es, Body nicht). (2) `AgentInvoker.invoke` erhaelt die workId aus dem Contract-Payload (Engine mint sonst neue UUID → Traceability-Bruch, live belegt).

## E. Ecosystem

Registry/Descriptor/Status/Profile + Discovery (inkl. `find_from_envelope`, ACTIVE-Filter) + Eligibility (+Pipeline) + Auswahl (`AgentRouter.select`, first_match) + `ExecutionEngine.execute_from_decision` (RoutingDecision→Contract→Invoker→Body — dokumentiert vorgesehener Pfad). Worker codiert KEINEN Agenten (kein if): Auswahl rein ueber Capability/AgentId aus dem WorkItem.

## F. Registry / Discovery / Eligibility

Live-Log belegt: `Found 1 candidates`, `Eligibility check: 1 eligible, 0 rejected`, `Selected agent reference_agent [reason: Specific agent requested]`. Gegenprobe (Unit): zweiter Agent anderer Capability wird per Capability ausgewaehlt.

## G. Event / READY

Kein READY/COMPLETED-Notification-System im Bestand (grep leer). Entscheidung (dokumentiert, keine neue Infra): SQS-Nachricht = READY-Signal (Work Available); WorkItem in DDB = dauerhafte Repraesentation (Recovery via Reprocessing/DLQ-Move).

## H. Idempotency

Conditional Write `attribute_not_exists(workId)` auf bestehender Work-Items-Tabelle (Hash-Key workId). ERSTE Registrierung → RUNNING/Attempt 1 → Run. DUPLIKAT (COMPLETED) → `{duplicate:true}`, kein Agent-Aufruf (live-Log: "kein neuer AgentRun"). Kein neues System, keine zweite Schicht.

## I. Sequence / Attempt

sequence_no=1 (ein Schritt, im Item), attempt_no=1 + pro Retry +1 bei gleicher processing_id/execution_id-neu (live: 1→2→3). Attempt ≠ Auftrag (DDB + Tests belegt).

## J. Retry / Recovery / DLQ

Agent-Exception/unbekannter Fehlertyp → FAILED persistieren + RAISE → SQS-Redelivery → neuer Attempt. Business-Codes (VALIDATION_ERROR/NOT_FOUND/ORDER-/INVALID_TRANSITION/CONFLICT) → kontrolliert FAILED, kein Retry. Begrenzung: bestehende DLQ (maxReceiveCount 3). DLQ-Eintrag wird nicht neuer Auftrag: Move-Task zurück → gleicher Kontext, Attempt+1 (live belegt).

## K. Result

Body-Result (success/data/metrics) + `result_reference=work:{id}:attempt:{n}` in DDB persistiert (live ausgelesen: metrics/agentId/processedAt). Kein neues Result Packet.

## L. E2E (live, `gate5-e2e-001`, `reference.echo`)

POST→SQS (MessageId `668f66…`) → Mapping `7cc946b9` Enabled → Worker → Envelope `5771fb…` → Discovery/Eligibility/Select → Engine → Body → Echo → Result. Nach 2 heilbaren Live-Bugs (s. Q) + DLQ-Move: **COMPLETED, attempt 3, Referenz gesetzt**, Queue 0, DLQ 0. Test-Item danach geloescht (Tabelle leer verifiziert).

## M. Duplicate-Test (live)

Gleiche workId erneut gesendet → Log "Duplikat erkannt … kein neuer AgentRun", attempt bleibt 3, Queue entleert. GREEN.

## N. Retry-Test

Unit (fail-once Fake): Attempt 1 FAILED → Attempt 2 COMPLETED, Error-Feld geraeumt. Live: Attempts 1→2→3 nachvollziehbar (s. L). Echter Agent-Fehlschlag live nicht gestellt (Echo kann nicht fehlschlagen; kein Test-Agent erfunden — dokumentiert).

## O. Security

Keine Secrets/Tokens in Code/Logs/Reports (Test-User nur Cognito, keine Rollen-Aenderung ausser konfigurierter SQS-Policy). IAM: nur fehlende, konfigurierte SQS-Policy angebracht (Least-Privilege: nur Work-Queue). DDB-Rolle hatte Put/Get/Update bereits.

## P. AWS-Änderungen (alle unser Bereich)

- Lambda-Code `mays-ris-dev-agent`: `eiBrUZUn…` → `Q+J/XLLE…` (Bundle 78 KB: handler+agents+jobsearch; reproduzierbar dokumentiert).
- ESM `7cc946b9` erstellt (Enabled, Batch 5 — wie konfiguriert; per CLI weil TF durch lambda.zip-Luecke blockiert).
- IAM: `mays-ris-dev-lambda-sqs-send` per TF-Plan angebracht (1 added).
- MO: 0 Aenderungen. Destroys: 0.

## Q. Tests

- Neu `tests/test_worker_pipeline.py`: 7 Tests (Happy-Path+Auswahl, Capability-Routing, Duplikat, Retry, Invalid, No-Agent, Float/Reserved-Waechter) → **7/7 PASS**.
- Suite: **275 passed**; 5 vorbestehende Defekte (2 Invocation, 1 Reference-Validation, 1 Chain, 1 Platform-Collection) per Stash-Vergleich als pre-existing klassifiziert, NICHT repariert.
- Live-Bugs (gefunden+gefixt, eigene Dateien): (1) Floats in Result-Metriken → Decimal-Konvertierung; (2) reservierte DDB-Woerter `error`/`result` → `#`-Platzhalter (Fake enthaelt Regression-Waechter).

## R. Git

- M: `agents/runtime/` (neu: `__init__`, `pipeline.py`), `lambda/handler.py`, `agents/agent_body/__init__.py`, `agents/agent_body/invocation.py`, `agents/ecosystem/routing.py` (Kommentar), `tests/test_worker_pipeline.py` (neu).
- Reports: diese beiden Dateien. Sonst nichts (Clone ignoriert, Zips in /tmp, 8 Alt-Reports + lock.hcl unberuehrt).

## S. Gate Decision

| Bereich | Ergebnis |
|---|---|
| Existing Worker | GREEN |
| Existing WorkItem | GREEN |
| Agent Body | GREEN |
| Worker → Agent Body | GREEN |
| Ecosystem | GREEN |
| Registry / Discovery | GREEN |
| Eligibility | GREEN |
| READY/Event | GREEN (SQS=READY, dokumentiert) |
| Idempotency | GREEN |
| Sequence / Attempt | GREEN |
| Retry / Recovery | GREEN |
| DLQ | GREEN (bestehend genutzt) |
| Reference Agent | GREEN |
| Result | GREEN |
| Duplicate Test | GREEN (live) |
| Retry Test | GREEN (live Attempts + Unit) |
| E2E | GREEN (live COMPLETED) |
| Security | GREEN |
| Git | GREEN |

**Entscheidung: GREEN** — SQS → Worker → WorkItem → Agent Body → Ecosystem → Reference Agent → Result ist live belegt; Duplikat/Retry/DLQ nachweisbar; Fremd-Projekt unberuehrt.

- Report: `docs/reports/GATE-5-AGENT-RUN-BODY-WORKITEM-EVENT-IDEMPOTENCY-01.md` (+ Log folgt)
- Commit: folgt (nur Gate-5-Dateien)
- Offen (nicht-kritisch): `lambda.zip`-Luecke (Full-Plan); pre-existing Test-Defekte (5); Live-Retry mit echtem Agent-Fehler (Echo faehig nicht)
- Naechstes Gate: OrdersPort/RealMaysOrdersAdapter auf stabilem Runtime-Pfad (Empfehlung)

**DANN HARD STOP.**
