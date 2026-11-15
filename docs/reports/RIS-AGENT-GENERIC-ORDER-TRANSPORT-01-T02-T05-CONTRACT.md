# RIS-AGENT-GENERIC-ORDER-TRANSPORT-01 — T02–T05 Contract V1

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (keine AWS-Aufrufe, kein Deployment)
**Ergebnis:** Contract V1 implementiert und getestet. **Keine Live-Integration.**

## 1. Git

| Feld | Wert |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| Parent | `4f66a6f` (T00/T01) |
| Basis | `bb77498` |

## 2. Implementierte Dateien

| Datei | Zweck |
|---|---|
| `agents/transport/order_transport.py` | Envelope V1, Validierung, Dispatch-/Result-Mapping |
| `agents/transport/__init__.py` | Öffentliche API |
| `agents/runtime/work_item.py` | **eine** kanonische WorkItem-Baufunktion |
| `lambda/handler.py` | `_enqueue_agent_work` nutzt jetzt `build_work_item` (Refactor, gleiches Ergebnis) |
| `tests/test_order_transport_contract.py` | 53 Tests |

Kein zweiter Ausführungspfad, keine zweite Registry, keine neue Queue,
keine Order-State-Machine.

## 3. Contract V1

### 3.1 Pflichtfelder

`schemaVersion`, `messageId`, `messageType`, `orderId`, `correlationId`,
`idempotencyKey`, `sender`, `recipient`, `identity.contextRef`, `createdAt`,
und genau eines von `payload` **oder** `payloadRef`.

Optional: `parentOrderId`, `parentWorkId`, `execution` (bei Result-Typen Pflicht).

### 3.2 Nachrichtentypen

| Typ | Status | Richtung |
|---|---|---|
| `ORDER_DISPATCH` | implementiert | orders → ris |
| `ORDER_RESULT` | implementiert | ris → orders |
| `ORDER_FAILED` | implementiert | ris → orders |
| `ORDER_CANCELLED` | implementiert | ris → orders |
| `ORDER_STATUS_CHANGED` | implementiert | ris → orders |
| `ORDER_PROGRESS`, `ORDER_ACK` | **reserviert, abgelehnt** | — |

Reservierte Typen werden mit `reserved_message_type` abgewiesen, unbekannte mit
`unknown_message_type` — zwei verschiedene Codes, damit ein späterer Ausbau
erkennbar bleibt.

### 3.3 Versionierung

`schemaVersion` `"1"` und `"1.0"` werden akzeptiert; alles andere →
`unsupported_schema_version`. Kein stilles Weiterreichen unbekannter Versionen.

### 3.4 Striktheit

Unbekannte Felder werden auf allen Ebenen abgelehnt (`unknown_field`) — Top-Level,
`sender`, `recipient`, `identity`, `execution`. Ein Tippfehler kann damit nicht
still ignoriert werden.

### 3.5 Secret-Grenze

Payloads werden rekursiv geprüft:

- Schlüsselnamen mit `secret|apikey|password|credential|authorization|bearer|token|jwt|privatekey` → `secret_in_transport`
- Werte mit `ris_`- oder `Bearer `-Präfix → `secret_in_transport`
- Größe > 16 384 Bytes → `payload_too_large`

### 3.6 Identität

Der Envelope trägt `identity.contextRef` plus nicht-autoritative Claims.
`dispatch_to_work_item(envelope, VerifiedContext)` baut das WorkItem
**ausschließlich** aus dem serverseitig aufgelösten Kontext:

- `contextRef` muss übereinstimmen → sonst `missing_verified_context`
- jeder abweichende Claim (`tenantId`, `apiProfileId`,
  `partnerApplicationId`, `issuer`) → `identity_mismatch`

Owner (`userId`) und Actor (`requestedBy`) bleiben unterscheidbar.

## 4. Mapping

### 4.1 `ORDER_DISPATCH → WorkItem`

| Envelope | WorkItem |
|---|---|
| `recipient.agentId` | `agentId`, `type = agent_<agentId>` |
| `recipient.capability` | `capability` |
| `payload` | `payload` |
| `idempotencyKey` | `idempotencyKey` |
| `correlationId` | `requestId` **und** `correlationId` |
| `orderId` | `orderId` (neu, stabil über die Ausführung) |
| `identity.contextRef` → Kontext | `tenantId`, `apiProfileId`, `partnerApplicationId`, `issuer` |
| Kontext-Owner | `userId` |
| Kontext-Actor | `requestedBy` |
| `messageId` | `transportMessageId` |

Ein Test vergleicht das Ergebnis feldweise mit `build_work_item` — der Transport
definiert **kein** eigenes WorkItem-Schema, er erweitert das bestehende.

### 4.2 `Agent Result → ORDER_RESULT`

| Quelle | Ziel |
|---|---|
| Dispatch-Envelope `orderId` | `ORDER_RESULT.orderId` (**nie** aus dem WorkItem) |
| `workRow.workId` | `execution.workId` |
| `workRow.attempt_no` | `execution.attempt` |
| `workRow.result` | `payload` (validiert, klein, secret-frei) |
| — | `idempotencyKey = <orderId>:<workId>:<TYPE>` (stabil) |

Regeln:

- `ORDER_RESULT` nur bei `status == COMPLETED` und vorhandenem `result`
  (`result_not_completed`)
- `ORDER_FAILED` nur bei `status == FAILED` (`result_not_failed`)
- umgekehrt ebenso: ein abgeschlossener Auftrag kann nicht als fehlgeschlagen
  gemeldet werden
- `is_stale_attempt(row, attempt)` erkennt ältere Versuche
- Fehlerpayloads laufen durch dieselbe Secret- und Größenprüfung

## 5. Tests

`tests/test_order_transport_contract.py` — **53 passed**

| Gruppe | Inhalt |
|---|---|
| Schema positiv | Dispatch, Result, Versionen `1`/`1.0`, `payloadRef`, Parent-Referenzen |
| Schema negativ | Version 2/0.9/leer/1 (int), unbekannter und reservierter Typ, fehlende `orderId`/`correlationId`/`contextRef`, ungültiges Format, unbekannte Felder, manipulierter Empfänger, falscher Sender, Payload XOR Ref, fehlende Execution, ungültiger Attempt, ungültiger Timestamp, 4 Secret-Varianten, Oversize |
| Dispatch-Mapping | Feldparität zu `build_work_item`, Order-/Korrelationserhalt, verifizierte Identität statt Claim, Owner≠Actor, Context-Mismatch, 4 Claim-Widersprüche, Result ist kein Dispatch |
| End-to-End | Dispatch → Addition-Agent → `42`, zusätzlich über `AgentBody.execute`, Result-Korrelation zur Original-Order, stabile Idempotenz, unfertige/fehlgeschlagene Aufträge, Secret im Result, Stale-Attempt |
| Single Source | Handler enthält kein zweites WorkItem-Literal mehr |

Zusätzlich: `17 + 25 = 42`, `0.1 + 0.2 = 0.3` und alle G01–G03-Tests bleiben
grün (T07, siehe §6).

## 6. T07 — Regression

| Suite | Ergebnis |
|---|---|
| `test_p21_cognito_m2m_boundary` | passed |
| `test_mo_addition_authorization_matrix` | passed |
| `test_addition_agent` | passed |
| `test_order_transport_contract` | 53 passed |
| `test_partner_addition_demo` | passed |
| `test_routing`, `test_full_pipeline`, `test_p20_api_contract_consistency` | passed |
| **Summe der gezielten Läufe** | **179 passed, 329 subtests** |
| Handler-/Entitlement-Suiten | **175 passed**, 1 vorbestehender Fehler |

**Vorbestehender Baseline-Defekt (nicht von dieser Task):**
`tests/test_platform_handlers.py::TestAgentAPI::test_execute_agent` erwartet
`202`, erhält `500`. Ursache `durable subject fence store is not configured`.
Der Guard existiert bereits in `HEAD` (per `git show HEAD:lambda/handler.py`
nachgewiesen), also kein Regress durch den WorkItem-Refactor.

Ebenfalls vorbestehend: `tests/test_consent_notice_lifecycle.py` bricht die
Collection mit `NameError: ConsentContext` ab und verhindert einen
`pytest tests/`-Volllauf.

## 7. Sicherheitsbefunde

- Kein Secret in Envelope, WorkItem oder Result (explizit getestet).
- Identität kann nicht durch SQS-Felder gesetzt werden: Claims müssen dem
  verifizierten Kontext entsprechen, sonst `identity_mismatch`.
- Richtung ist typgebunden; ein manipulierter `recipient.system` wird abgewiesen.
- Reservierte/unbekannte Typen werden kontrolliert abgelehnt, nicht ignoriert.
- Keine Schreiboperation in fremde Systeme: das Modul ist rein funktional.

## 8. Bewusste Grenzen

- **Keine Live-Integration.** Es wurde nichts an Mays-Orders gesendet, keine
  Queue erzeugt, kein AWS-Aufruf gemacht. Der Orders-Consumer kennt diesen
  Vertrag noch nicht.
- **Keine Orders-Vertragsänderung** (B1–B4 aus G00 bleiben offen).
- **Kein Terraform**, kein `addition_agent`-Katalog-Seed.
- `payloadRef` wird validiert, aber nicht aufgelöst (kein Storage-Backend).

## 9. Status der Folge-Gates

| Gate | Status |
|---|---|
| G04 Identitätspropagation | **PARTIAL** — Transport trägt `apiProfileId`/`issuer`/`partnerApplicationId` bis ins WorkItem; der M2M-Handler befüllt `apiProfileId` noch nicht |
| G05 Orders → RIS SQS | **BLOCKED** — braucht B1/B3 |
| G07 RIS → Orders SQS | **BLOCKED** — braucht B3/B4 |
| T06 Volllauf-Matrix | **PARTIAL** — 53 Transporttests decken die Contract-Ebene; die 24-Punkte-Matrix aus §9 ist zu ~80 % abgedeckt, Rest ist Integrationsverhalten |

## 10. Nächster Schritt

Contract-Freeze bestätigen, dann:
1. `_machine_execute_agent` befüllt `apiProfileId` (G04, kleine Änderung).
2. B1/B3 entscheiden → Orders-Dispatch-Adapter + Orders-Consumer.
3. T06 auf die vollständige 24-Punkte-Matrix erweitern.
