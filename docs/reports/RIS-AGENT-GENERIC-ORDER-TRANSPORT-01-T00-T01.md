# RIS-AGENT-GENERIC-ORDER-TRANSPORT-01 — T00 Baseline & T01 Contract-Inventur

**Datum:** 2026-11-13
**Typ:** Read-only Bestandsaufnahme, keine Produktänderung
**Ergebnis:** Baseline verifiziert. Ein Befund aus G00 wird korrigiert.

## 1. T00 — Git-Baseline (gemessen, nicht übernommen)

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| HEAD | `bb77498` |
| Working Tree | clean |
| Remote | `origin/feature/ris-mo-addition-agent-e2e-01` identisch (`bb77498`) |
| Merge-Basis | `main` @ `2d0c67d` |

Commits vorhanden und inhaltlich geprüft:

| Gate | Commit | Inhalt vorhanden | Status |
|---|---|---|---|
| G00 | `c48164b` | Report + Auditlog | **DOCUMENTED ONLY** |
| G03 | `c3b64b2` | `agents/addition_agent/` (3 Dateien), Pipeline-Wiring, 29 Tests | **IMPLEMENTED + TESTED** |
| G02 | `b2fe6ee` | `tests/test_mo_addition_authorization_matrix.py`, 16 Tests | **IMPLEMENTED + TESTED** (Tests, kein Produktcode) |
| G01 | `bb77498` | `examples/partner-addition-demo/`, 15 Tests | **IMPLEMENTED + TESTED** (lokal, Fakes) |

Weitere Einstufung:

| Bereich | Status |
|---|---|
| Generischer Transportvertrag | **NOT PRESENT** — grep über `*.py` fand kein `messageType`/`ORDER_DISPATCH`/`TransportEnvelope`; alle `schemaVersion`-Treffer betreffen Jobsearch-/Profile-Contracts |
| `work-system/work-item.md` | **DOCUMENTED ONLY** und driftet vom Code (siehe §4.1) |
| Orders→RIS-Transport | **BLOCKED** (kein Rückkanal, keine Eigentümerbindung) |
| Orders-Ergebnisabholung | **BLOCKED** |
| `ris-agent`-Deployment | separates Ergebnis, hier nicht verändert |

## 2. Korrektur an G00

G00 (gegen den älteren Checkout `ef5d884` gelesen) behauptete, das WorkItem
enthalte **kein** `partnerApplicationId` und **kein** `issuer`. Für diese
Baseline (`main` @ `2d0c67d`) ist das **falsch**:

```python
# lambda/handler.py::_enqueue_agent_work  (vor dieser Task)
'partnerApplicationId': partner_application_id or '',
'issuer': issuer or '',
```

Zusätzlich fail-closed vorhanden:

- `WORK_ITEMS_TABLE` fehlt → `RuntimeError`
- `user_id` oder `tenant_id` fehlt → `RuntimeError`
- `transact_write_items` mit `ConditionCheck` auf den Subject-Fence + `Put`
  mit `attribute_not_exists(workId)`

**Weiterhin korrekt** ist: `apiProfileId` fehlt im WorkItem. Der Worker liest
`work.get("apiProfileId")` für den Execution-Time-Entitlement-Re-Check und
bekommt `None`. Genau das adressiert der neue Vertrag.

Ebenfalls korrekt bleibt: die Fallbacks `tenantId='default'` und
`requestedBy='agent-invocation'` existieren — aber in
`InvocationContract.to_work_item` (Agent-zu-Agent-Pfad), **nicht** im
Partner-/M2M-Pfad. Sie sind damit kein Beweis für einen unsicheren
Partner-Order-Pfad, wohl aber ein Risiko, sobald dieser Pfad den
Invocation-Contract wiederverwendet.

## 3. T01 — Ist-Beziehung der Modelle

Kette:

```
Order (Orders, autoritativ)
  → Transport Envelope (neu, Korrelation/Zustellung)
    → WorkItem (RIS-Persistenz + SQS-Payload)
      → ProcessingEnvelope (Ecosystem-Sicht)
        → Agent Body (Routing/Context/Execution)
          → Result (work_items.result / result_reference)
```

### 3.1 Verantwortlichkeiten

| Modell | Datei | Eigentümer | Verantwortung |
|---|---|---|---|
| Order | Orders-Repo | Mays-Orders | Fachlicher Lifecycle, Annahme, Abholung |
| Transport Envelope | `agents/transport/order_transport.py` (neu) | RIS (Transport) | Zustellung, Typ, Korrelation, Schema-Version |
| WorkItem | `agents/runtime/work_item.py` (neu, extrahiert) | RIS Runtime | Persistenz, Idempotenz, Attempt, SQS-Payload |
| ProcessingEnvelope | `agents/ecosystem/event_hook.py` | RIS Ecosystem | Discovery/Eligibility-Sicht, Trigger |
| InvocationContract | `agents/agent_body/invocation.py` | Agent Body | Agent-zu-Agent-Aufruf |
| Result | `agents/runtime/pipeline.py::_persist_result` | RIS Runtime | `status=COMPLETED`, `result`, `result_reference` |

### 3.2 Kanonische Feld-Mapping-Tabelle

| Bedeutung | Order | Envelope | WorkItem | ProcessingEnvelope | Body-Context |
|---|---|---|---|---|---|
| Fachliche Order-ID | `orderId` | `orderId` | **fehlte**, jetzt `orderId` | `order_id` | — |
| Technische Ausführung | — | `execution.workId` | `workId` | `processing_id`, `execution_id`, `attempt_id` | `workId` |
| Korrelation | — | `correlationId` | `requestId`, `correlationId` | `parent_id` | — |
| Dedup | `orderId` | `idempotencyKey` | `idempotencyKey` | **nicht vorhanden** | `idempotencyKey` |
| Lifecycle-Status | `PENDING…DELIVERED` | `messageType` | `QUEUED/RUNNING/COMPLETED/FAILED` | `PENDING` | — |
| Ziel | — | `recipient.agentId/capability` | `agentId/capability` | `agent_id`, `body_version` | `agentId/capability` |
| Tenant | — | `identity.tenantId` (Claim) | `tenantId` | `tenant_id` | `tenantId` |
| Auftraggeber | Kunde | `sender.reference` | `userId` | — | `userId` |
| Actor | — | `identity.contextRef` | `requestedBy` (+ neu `actor`) | — | — |
| APIProfile | — | `identity.apiProfileId` | **fehlte**, jetzt `apiProfileId` | — | — |
| Partner-App | — | `identity.partnerApplicationId` | `partnerApplicationId` | — | — |
| Payload | `customer/items` | `payload` \| `payloadRef` | `payload` | `input` | — |
| Ergebnis | — (heute) | `payload` von `ORDER_RESULT` | `result`, `result_reference` | `result_reference` | — |

### 3.3 Überschneidungen und Risiken (dokumentiert, nicht geändert)

1. **Drei Statusvokabulare.** Order (`PENDING…DELIVERED`), WorkItem
   (`QUEUED…DEAD_LETTER`), ProcessingEnvelope (`PENDING`). Eine Vermischung
   würde den Orders-Lifecycle verfälschen. Der Transport darf deshalb **nie**
   einen Order-Status setzen; er transportiert `messageType` + Korrelation.

2. **`envelope.input` sind nicht die Agent-Payload.** `_to_event` legt das
   **gesamte** WorkItem in `Event.payload`; `create_processing_envelope` kopiert
   das nach `envelope.input`. Die Eligibility liest
   `envelope.input.get('capability')` — das funktioniert nur wegen dieser
   Ganz-Dict-Kopie. Wer `input` auf die fachliche Payload verengt, bricht die
   Eligibility. Bewusst unangetastet.

3. **`idempotencyKey` existiert im WorkItem, nicht im ProcessingEnvelope.**
   Doppelzustellung wird heute über `attribute_not_exists(workId)` abgefangen,
   nicht über den Idempotenzschlüssel. Der Transport liefert einen stabilen
   Schlüssel, verlässt sich aber nicht darauf.

4. **`requestedBy == userId` im Handler.** Auftraggeber und Actor sind dort
   nicht unterscheidbar. Der Transport trennt beide (Owner aus verifiziertem
   Kontext, Actor separat) — ohne den bestehenden Pfad zu ändern.

5. **Doc-Drift `work-system/work-item.md`.** Das Dokument nennt `entityId`,
   `resultRef`, `claimedBy`, `claimedAt`, `completedAt` und den Status `QUEUE`.
   Der Code nutzt `userId`, `requestedBy`, `requestId`, `payload`, `expiresAt`
   und `QUEUED`. Das Dokument ist **nicht** die Quelle der Wahrheit.

6. **Keine parallele WorkItem-Implementierung.** Der Transport baut das
   WorkItem über `agents/runtime/work_item.py::build_work_item`, dieselbe
   Funktion, die `_enqueue_agent_work` jetzt nutzt. Ein Test erzwingt, dass im
   Handler kein zweites Schema-Literal entsteht.

## 4. Contract-Entwurf (Zusammenfassung)

Der V1-Envelope ist bewusst schmal: `schemaVersion`, `messageId`,
`messageType`, `orderId`, `correlationId`, `idempotencyKey`, `sender`,
`recipient`, `identity.contextRef`, optional `parentOrderId`/`parentWorkId`,
`payload` **oder** `payloadRef`, `createdAt`, optional `execution`.

Nicht enthalten: JWT, RIS-Key, Credential-IDs, fremde DB-Schlüssel,
Order-Status. Identität wird über `contextRef` **referenziert** und serverseitig
aufgelöst; Claims im Envelope sind Behauptungen, die gegen den verifizierten
Kontext geprüft werden.

## 5. Abnahme T00/T01

- Baseline nachweisbar, keine Produktänderung in diesem Schritt.
- Mapping-Tabelle je Modell vorhanden.
- G00-Fehler korrigiert statt fortgeschrieben.
- Offene Punkte klar als BLOCKED markiert.
