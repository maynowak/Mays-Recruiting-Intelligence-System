# Mays-RIS Runtime Path — Detail je Stufe (konsolidiert, Gates 5–9)

Ergänzt `SYSTEM-ARCHITECTURE.md`. Jede Stufe: Verantwortung, Input/Output,
Persistenz, Fehler, Idempotency/Retry, Tenant/Security, AWS-Komponente.
Keine zweite Queue, kein paralleles Runtime-Modell.

## 1. API (HTTP API V2, Payload 2.0)

- Verantwortung: Auth (JWT ausser `GET /health`), Routing, synchrone Responses.
- Input: HTTP-Request + `Authorization: Bearer <JWT>`. Output: JSON (Erfolg/Fehler-Schema s. API-Standard).
- Persistenz: keine (ausser Orders-Reader: DDB-PUT bei POST).
- Fehler: 400 Validierung, 401/403 Auth, 404, 409 Transition, 500 intern.
- Idempotency: HTTP-seitig keine Keys (OPEN); POST erzeugt je Call neue ID.
- Tenant/Security: Authorizer prüft Audience/Issuer; Claims im Context.
- AWS: `mays-ris-dev-api` (aboqolpm0f), Stage `$default` (AutoDeploy).

## 2. WorkItem (gemeinsame Queue)

- Verantwortung: Bestand an Arbeit (DDB) + Aktivierungsimpuls (SQS-Nachricht).
- Input: SQS-Record-Body (JSON). Output: validiertes WorkItem-Dict.
- Persistenz: `mays-ris-dev-work-items` (Hash workId) — Registrierung VOR Ausführung (Conditional Write `attribute_not_exists`).
- Fehler: ungültig → keine Registrierung → Exception → Redelivery → DLQ(3).
- Idempotency: Duplikat (gleiche workId, COMPLETED) → kein neuer Run.
- Tenant: Pflichtfeld tenantId + userId; Isolation im Repository.
- AWS: `mays-ris-dev-work-queue` (Visibility 300s, SSE) + `mays-ris-dev-dlq`.

## 3. Worker (Lambda `mays-ris-dev-agent`, Mapping Batch 5, Enabled)

- Verantwortung: Records → Pipeline; Fehler-Re-Raise (sonst löscht SQS trotz Fehler).
- Input: SQS-Event. Output: 200 pro Batch oder Raise (Redelivery).
- Persistenz: via Pipeline (s. 4). Fehler: s. Retry-Regel Gate 5.
- Retry: Exception → Redelivery → neuer Attempt (attempt+1, gleiche processing_id).
- Security: Rolle mit DDB/SQS/Logs-Least-Privilege; Env nur Tabellennamen/URLs.

## 4. Ecosystem (Registry/Discovery/Eligibility/Selection)

- Verantwortung: zentrale Agent-Auswahl (Worker kennt keine Agenten).
- Input: ProcessingEnvelope (Event→Hook). Output: RoutingDecision (agent_id + reason).
- Persistenz: keine (Runtime-Registry, In-Memory; Katalog-Adapter lädt DDB-Katalog beim Start).
- Fehler: keine Kandidaten → ValueError (kontrolliert, kein Run).
- Tenant: tenant_id fliesst in Envelope/Eligibility-Kontext (harte Entitlement-Regeln: OPEN).
- Registriert: reference_agent, orders_function, ats-agent, jobsearch-agent, dummy-a/b (DEV).

## 5. Agent Body (Context/Router/Executor/Invoker)

- Verantwortung: technische Ausführung (Validierung → Routing → Handler → Result + Metriken).
- Input: WorkItem (+ Decision-Kontext). Output: Result `{success, data/error, metrics}`.
- Persistenz: keine eigene (Result persistiert Pipeline in Work-Items-Tabelle + `result_reference`).
- Fehler: Business-Codes (VALIDATION/NOT_FOUND/INVALID_TRANSITION/…) vs Exceptions (Retry via Raise).
- Idempotency: identitätserhaltend (workId aus Contract-Payload, parent=processing_id).

## 6. Domain Agents

| Agent | Capability | I/O | Persistenz | Extern |
|---|---|---|---|---|
| reference | reference.echo | beliebig → Echo | keine | nein |
| ats | analyze.job | job{title,description}+profile → analysis | keine | ATS-API (urllib-Fallback) |
| jobsearch | create/get/list | Name/IDs → JobSearch-Datensätze | jobsearches-Tabelle (Tenant-isoliert) | nein |
| orders-function | orders.* | Delegation an Port | keine | via Adapter |
| dummy-a/b | dummy-a/b | Marker+Echo (DEV) | keine | nein |

## 7. OrdersPort + RealMaysOrdersAdapter

- Verantwortung: fachliche Order-Operationen (create/status/cancel) gegen live Mays-Orders-Contract (eigene API-Routen als Ziel).
- Fehler: 400/401/403/404/409 kontrolliert; 429/5xx/Timeout (ausser POST) retrybar; POST-Unsicherheit kontrolliert (`safe_to_retry: False`, kein blindes Re-POST).
- Idempotency: OPEN serverseitig (jedes POST neue ID — belegt); Retry erzeugt keine zweite Order (Adapter wirft bei POST nie Transient).
- Tenant: kein MO-Feld (Isolation unsere Aufgabe); Korrelation via workId/processing/result_reference.

## 8. Installer / Projektmodell

- Verantwortung: reproduzierbare Installation in beliebigem Account (Profil = Kontext, kein fester Account in Identität).
- Mechanik: `project_name` → Workspace/Präfix; S3-Backend + Lock-Tabelle; Lifecycle validate→plan→apply (install kapselt); gezielte Applies dokumentiert (Full-Plan-`lambda.zip`-Lücke: OPEN).
- Pinning: je Projekt `{project, git_url, branch, pinned_commit(+subject), clone_path, date, kind}` getrackt; Clones ignoriert; Verify erkennt Drift.
- Projekte: mays-orders@9c61237 (installable), mays_jobsearch@3cd58b81 (reference/Frontend).

## 9. Observability

CloudWatch-Logs pro Funktion (7–14 Tage Retention), Metriken/Alarme (Plattform), Trace-Ids in Logs (workId/processing/agent/capability — nie Secrets/Tokens/PII-Testdaten ausser synthetisch).
