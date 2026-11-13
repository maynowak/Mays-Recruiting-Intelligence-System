# RIS-MO-ADDITION-AGENT-E2E-01 — G00 Baseline & Architekturvertrag

**Datum:** 2026-11-13
**Typ:** Read-only Bestandsaufnahme (keine AWS-Mutation, kein Deployment, kein Apply)
**Ergebnis:** G00 abgeschlossen. G03 ist lokal umsetzbar. **G05/G07/G08 sind BLOCKED** ohne
Vertragserweiterung in Mays-Orders.

## 0. Repositories und Git-Zustand (gemessen)

| Repo | Branch | HEAD | Working Tree |
|---|---|---|---|
| RIS | `feature/ris-mo-addition-agent-e2e-01` (neu, von `main`) | `2d0c67d` | clean (dieses Dokument) |
| RIS (separat) | `deploy/ris-agent-test-2026-11-12` | `394d290` | Testinstallation `ris-agent`, gepusht |
| Mays-Orders | `feature/mo-module-contract-ris-dev2-2026` | `9627eb2` | clean |
| Jobsearch | nicht gelesen | — | nicht benötigt |

Der RIS-Hauptcheckout `projekte/Mays-Recruiting-Intelligence-System` bleibt auf
`feature/ris-partner-profile-persistence-v1 @ ef5d884` mit 39 vorbestehenden untracked
Dateien und einer vorbestehenden Löschung. Er wurde **nicht** angefasst.

## 1. IST — Mays-Orders (autoritativ für Order)

### 1.1 Öffentliche API

| Methode | Pfad | Auth | Ergebnis |
|---|---|---|---|
| POST | `/orders` | Cognito JWT | 201 + Order |
| GET | `/orders/{orderId}` | Cognito JWT | 200 + Order |
| GET | `/orders` | Cognito JWT | paginierte Liste |
| PATCH | `/orders/{orderId}/status` | Cognito JWT | Statuswechsel |

Quelle: `api/endpoints.md`, `lambda/src/index.py` (`handler`, `route_key`).

### 1.2 Request-Vertrag ist strikt geschlossen

`validation.validate_create_order` erlaubt **nur**:

```
customer{name,email}, items[{sku,quantity,unitPrice}], currency
```

`reject_unknown_keys` liefert bei jedem weiteren Feld `400 VALIDATION_ERROR`.
Damit ist **`math.add` heute nicht transportierbar**: weder `capability`, noch `agentId`,
noch Operanden, noch `orderId`-Vorabreferenz passen in den Body.

### 1.3 Angebundene Queue und ihr echter Consumer

- Producer: `index.py::_send_to_sqs` publiziert nach `SQS_QUEUE_URL`:
  `{orderId, status:"CONFIRMED", metadata:{reason:"order_created"}}`.
- Consumer: `lambda/src/sqs_handler.py` (`worker`).
- **Der Worker interpretiert ausschließlich `status` als Statusübergang.**
  `payload` wird gelesen, aber nicht verwendet. Es gibt keine Ergebnisübernahme,
  keine Nachrichtentyp-Prüfung und keinen Idempotenz-Guard
  (`update_item` ohne `ConditionExpression`).

Folge: Eine RIS-Ergebnismeldung auf dieser Queue würde entweder als Statusübergang
fehlschlagen oder — bei passendem `status`-Feld — den Order-Status verfälschen.
**Diese Queue ist als Rückkanal ungeeignet.**

### 1.4 Statusmodell und Ergebnis

`order_types.ORDER_STATUSES = PENDING, CONFIRMED, PROCESSING, SHIPPED, DELIVERED, CANCELLED`
`state_machine.TRANSITIONS`: `PENDING→CONFIRMED|CANCELLED`, `CONFIRMED→PROCESSING|CANCELLED`,
`PROCESSING→SHIPPED`, `SHIPPED→DELIVERED`, `DELIVERED/CANCELLED` terminal.

- Es gibt **kein** `result`-Feld, **kein** `resultStatus`, **keine** `workId`-Korrelation.
- `PROCESSING → CANCELLED` ist nicht erlaubt (relevant für G07 „kein Abschluss nach Stornierung").
- `PROCESSING → DELIVERED` existiert nicht; ein Abschluss müsste über `SHIPPED→DELIVERED`
  laufen oder das Modell bewusst erweitert werden.

### 1.5 Eigentümerschaft — kritische Lücke

In `lambda/src/index.py` wird **keine** JWT-Claim-Auslesung durchgeführt:

- `service.create_order(parse_body(event))` — `subject_id` wird nie übergeben.
- `get_order(order_id)` prüft **keinen** Eigentümer.
- `list_orders` liest `gsi1pk = "LIST"`, also **alle** Orders des Systems.
- `subjectId`/GSI2 existieren im Modell, werden aber nur vom Privacy-Pfad genutzt.

Damit kann heute **jeder authentifizierte Aufrufer jede Order per ID lesen**.
Das verletzt G08 („Partner B erhält keinen fremden Auftrag") direkt.

### 1.6 Dateien aus dem Auftrag, die in dieser Revision nicht existieren

`lambda/src/identity.py`, `order_handlers.py`, `processing_result.py` existieren nicht.
Vorhanden sind: `errors.py`, `index.py`, `order_service.py`, `order_types.py`,
`sqs_handler.py`, `state_machine.py`, `validation.py`.
Die Auftragsbeschreibung ist damit gegenüber `9627eb2` **nicht** deckungsgleich; es wird
keine dieser Dateien erfunden.

## 2. IST — RIS (autoritativ für Agent, Key, Freigabe)

### 2.1 M2M-Ausführungspfad

`POST /v1/m2m/agents/{agentId}/execute` (`lambda/handler.py::_machine_execute_agent`):

1. Cognito-M2M-JWT (`token_use=access`, Scope `ris-api/m2m/execute`) — Gateway + In-Lambda.
2. `X-Api-Credential: ris_...` → `verify_api_credential` (ein zentraler Verifier).
3. Partner-Application-Bindung: `client_id` → `apiProfileId` + `tenantId`, beide müssen
   dem Credential-Kontext entsprechen. Kein Env-Bypass.
4. `_enqueue_agent_work` → WorkItem persistieren + Work-Queue → `202`.

Ergebnissemantik: `401` ungültig/unbekannt, `403` bekannt-aber-unbrauchbar,
`503` Store nicht erreichbar.

### 2.2 WorkItem-Schema (Ist)

```
workId, type, tenantId, userId, requestedBy, agentId, capability,
idempotencyKey, payloadVersion, agentVersion, requestId, status,
attempt, payload, createdAt, expiresAt
```

**Nicht enthalten:** `apiProfileId`, `orderId`, `partnerApplicationId`, `issuer`.

Damit ist die in G04 geforderte Propagation credential→WorkItem→Worker **nicht** erfüllt.
Der Worker liest `work.get("apiProfileId")` für den Execution-Time-Entitlement-Re-Check
(`pipeline.py:412`); der Wert ist heute immer `None`.

### 2.3 Worker und Ergebnisablage

`ris-agent-dev-agent` ← SQS `work-queue` (Batch 5) → `process_record`:

Envelope (`event_hook.ProcessingEnvelope`) übernimmt `order_id` aus
`work["orderId"]` — der Kanal existiert also, wird aber nicht befüllt.
Ergebnis: `_persist_result` setzt `status=COMPLETED`,
`result_reference="work:{workId}:attempt:{n}"`, `result={...}`.
Fehler: `_persist_failure` → `status=FAILED`, `error`.

Idempotenz: `put_item` mit `attribute_not_exists(workId)`; Duplikat mit terminalem Status
erzeugt keinen neuen Run. Das ist die belastbare Basis für G06.

### 2.4 Agent-Katalog und Queues

Katalog-Seeds (Terraform): `reference_agent`, `jobsearch-agent` — beide ACTIVE.
**Kein `math.add`, kein Addition-Agent.**

Queues: `work`, `cv`, `ats`, `match`, `dlq`. **Kein Ergebnis-/Outbox-Kanal.**

### 2.5 Bestehende Orders-Brücke ist unidirektional

`agents/orders/adapter.py` definiert `OrdersPort` mit
`submit_order`, `get_order_status`, `can_handle` (+ `cancel` im Real-Adapter).
`RealMaysOrdersAdapter` ist ein **HTTP-Client** gegen die Orders-API.
Es gibt **keinen** SQS-Rückkanal und keine `orderId` im WorkItem.

## 3. Antworten auf die G00-Fragen

| Frage | Befund | Status |
|---|---|---|
| Installierte Orders-Version für isoliertes Testziel | `9627eb2` (Branch `feature/mo-module-contract-ris-dev2-2026`); im `ris-agent`-Stack ist Orders **deaktiviert** (`orders_lifecycle=disabled`). Keine belegte Live-Orders-Instanz für dieses Ziel. | BLOCKED für Live |
| Queue für Order-Zustellung | `SQS_QUEUE_URL` → `<project>-mays-orders-orders-queue` | IST |
| Tatsächlicher Empfänger | `sqs_handler` (Statusübergang, kein Ergebnis) | IST |
| APIs für Erstellen/Status/Ergebnis | Erstellen/Status ja; **Ergebnis nein** | Lücke |
| Sicherer SQS-Rückkanal | **Nicht vorhanden** | BLOCKED |
| Verifizierte Bindung Auftraggeber↔Agent↔Order | Nicht vorhanden: keine `subjectId`-Bindung, keine `orderId` im WorkItem | BLOCKED |
| `math.add` über generischen Auftragsvertrag transportierbar | **Nein** (strikte Validierung) | BLOCKED |
| Was verhindert das E2E | 3 Vertragslücken (Payload, Eigentum, Rückkanal) + fehlender Agent | siehe §5 |

## 4. GEPLANT — kleinste kompatible Ergänzungen

Alle Punkte sind Vorschläge, **nicht** implementiert. Reihenfolge ist abhängig.

### E1 — Payload-Transport (Orders, additiv)
Optionales Feld `processing` in `POST /orders`:

```json
{ "capability": "math.add", "payload": { "left": 17, "right": 25 } }
```

- additiv in der Allowlist, weiterhin `reject_unknown_keys` für alles andere;
- Default aus (Feature-Flag `CAPABILITY_EXECUTION_ENABLED=false`), bestehende Clients unverändert.

### E2 — Eigentümerbindung (Orders, Sicherheitsfix)
`subjectId` aus dem verifizierten JWT-`sub` bei `create_order` setzen und bei
`get_order`/`list_orders`/`PATCH` erzwingen. Für Altdaten ohne `subjectId`:
fail-closed nur für neue Orders, Legacy-Rows explizit als migrierbar markieren.

### E3 — Ergebnis-Rückkanal (neu, getrennt)
Neue Queue `<project>-processing-results-queue` + eigener Consumer.
Nachrichtentyp explizit (`processing.result.v1`), nie auf der bestehenden Orders-Queue.
Der bestehende Worker bleibt unverändert und interpretiert weiterhin nur `status`.

### E4 — Ergebnisablage (Orders)
Intern: `processing{workId, executionId, attemptId, resultStatus, result, completedAt}`.
Öffentlich nur über autorisierten `GET /orders/{orderId}`.

### E5 — RIS-Kontextpropagation
`apiProfileId`, `partnerApplicationId`, `issuer` in `_enqueue_agent_work` und ins
WorkItem/Envelope übernehmen; `orderId` aus dem Auftrag durchreichen.

### E6 — Addition-Agent (RIS, lokal sofort möglich)
`addition_agent` / `math.add`, deterministisch, ohne DB und ohne Credentials.

## 5. BLOCKED — Entscheidungen, die vor G05/G07 nötig sind

| # | Entscheidung | Warum blockierend |
|---|---|---|
| B1 | Darf `POST /orders` additiv um `processing` erweitert werden? | Orders-Vertragsänderung, heute strikt geschlossen |
| B2 | Wird `subjectId`-Eigentum jetzt erzwungen (Breaking Change für Altdaten)? | Sicherheitsfix mit Bestandswirkung |
| B3 | Neue Ergebnis-Queue + neuer Consumer — oder Erweiterung von `sqs_handler`? | Prinzip 5/6: definierter Consumer, kein stilles Mitlesen |
| B4 | Bleibt der fachliche Status unverändert und das Ergebnis ein Zusatzfeld? | Sonst wird die Order-State-Machine umgedeutet |
| B5 | Live-E2E (Phase C) braucht eine aktive Orders-Instanz + Freigabe | kein Apply/Deploy ohne Freigabe |

**STOP-Kriterium erreicht:** G05/G07/G08 erfordern eine freigegebene Orders-Vertragserweiterung.
Ohne B1–B4 wird nicht implementiert.

## 6. Nächster freigegebener Schritt

**G03 ist unabhängig von B1–B5 und lokal umsetzbar.** Vorschlag: G03 (Addition-Agent +
Tests) jetzt umsetzen, G01/G02 (Demo + Auth-Contracts) parallel lokal mit Fakes,
danach B1–B4 entscheiden und erst dann G05/G07.

## 7. Tests und Evidenz

In G00 wurden **keine** Tests ausgeführt und **keine** AWS-Aufrufe gemacht.
Alle Aussagen stammen aus gelesenem Code/Config der genannten Commits.
Bereits separat belegte Basis: `ris-agent` deployt (`394d290`), Drift 0,
`reference_agent`/`jobsearch-agent` ACTIVE, Work-ESM Enabled/Batch 5.
