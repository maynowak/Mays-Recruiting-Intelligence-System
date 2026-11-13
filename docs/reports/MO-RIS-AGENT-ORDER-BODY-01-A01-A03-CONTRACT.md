# MO-RIS-AGENT-ORDER-BODY-01 — A01–A03 Agent Order Body V1

**Datum:** 2026-11-13
**Typ:** Lokale Implementierung + Tests (kein Orders-Change, keine AWS-Mutation)
**Ergebnis:** Contract V1 implementiert, gemappt, `17 + 25 = 42` über den
bestehenden AgentBody belegt. A04–A07 bleiben BLOCKED (siehe A00).

## 1. Git

| Feld | Wert |
|---|---|
| Branch | `feature/ris-mo-addition-agent-e2e-01` |
| Parent | A00-Commit (Baseline-Bericht) |
| Basis | `d137267` |

## 2. Implementierte Datei

`agents/orders/agent_order.py` — fachlicher Contract plus Mapping. Keine
Persistenz, keine Zustellung, keine Berechtigungsentscheidung.

## 3. Contract

```
orderType: "agent.execution"
agentOrder:
  schemaVersion  "1.0"      (akzeptiert: "1.0", "1")
  target         agentId, capability, agentVersion?
  input          schemaVersion, data (fachlich opak)
  metadata       source?, partnerApplicationRef?, apiProfileRef?,
                 requestId?, idempotencyKey?
  processing     trigger?, parentOrderId?, parentWorkId?, executionProfile?
  resultContract schemaVersion, format, expectedCapability, delivery
```

Defaults (dokumentiert, getestet):

| Feld | Default |
|---|---|
| `metadata.source` | `ris-agent-ecosystem` |
| `processing.trigger` | `ORDER_CREATED` |
| `processing.executionProfile` | `default` |
| `resultContract.format` | `json` |
| `resultContract.delivery` | `order-result` |
| `resultContract.expectedCapability` | `target.capability` |

Ablehnungen mit stabilem Code:

`unsupported_agent_order_version`, `unknown_field`, `invalid_target`,
`invalid_capability`, `invalid_input`, `unsupported_result_format`,
`unsupported_delivery`, `result_contract_mismatch`, `capability_mismatch`,
`target_mismatch`, `secret_in_transport`, `identity_mismatch`,
`invalid_order_id`, `invalid_result`, `result_shape`, `missing_agent_order`,
`unsupported_order_type`.

## 4. Versionierung (A02)

Drei **unabhängige** Versionen, per `version_matrix()` sichtbar:

| Ebene | Version | Quelle |
|---|---|---|
| Mays-Orders-Modul | extern, `None` | nicht Teil dieses Contracts |
| Transport Envelope | `"1"` | `agents/transport/order_transport.py` |
| Agent Order Body | `"1.0"` | dieses Modul |

Ein Upgrade der einen Ebene ändert die andere nicht — es gibt keine gemeinsame
Konstante und keinen Kopplungscode.

**Unveränderlichkeit:** `fingerprint()` hasht `schemaVersion + target + input`.
Korrelationsfelder (`requestId`, `idempotencyKey`) sind bewusst ausgenommen, ein
Retry ist also keine andere Ausführung. Der Fingerprint wird im WorkItem als
`agentOrderFingerprint` mitgeführt, sodass eine spätere Abweichung nachweisbar ist.

## 5. Mapping (A03)

| agentOrder | Ziel |
|---|---|
| `target.agentId` / `capability` | `agentId` / `capability`, `type=agent_<id>` |
| `input.data` | `payload` (unverändert) |
| `metadata.idempotencyKey` | `idempotencyKey` |
| `metadata.requestId` | `requestId` (Fallback: `correlationId`) |
| `processing.parentWorkId` | `parentWorkId` |
| `metadata.apiProfileRef` / `partnerApplicationRef` | **geprüft gegen** `VerifiedContext`, nicht übernommen |
| — | `orderId`, `correlationId`, `agentOrderVersion`, `agentOrderFingerprint` |

`processingId`, `executionId` und Attempts bleiben Runtime-Eigentum und werden
vom Contract nicht gesetzt.

## 6. Tests

`tests/test_agent_order_body.py` — **43 passed**

| Gruppe | Inhalt |
|---|---|
| Gültig | volles Dokument, Minimaldokument mit Defaults, Version `1.0`/`1`, Determinismus |
| Ungültig | 5 Versionen, unbekannte Felder (top + nested), fehlender Target/Capability, Format, 4 Secret-Varianten, fehlender agentOrder, Retail-orderType |
| Versionierung | Unabhängigkeit der drei Versionen, Fingerprint stabil/ändernd, Korrelationsfelder ignoriert |
| Mapping | Target/Input/Processing, Identität aus Kontext statt Metadata, Mismatch-Ablehnung, Fingerprint im WorkItem, ungültige orderId |
| End-to-End | `17+25=42` über den bestehenden AgentBody, `0.1+0.2=0.3`, Result-Secret-Ablehnung, Result-Shape |

Regression: **235 passed, 11 subtests** (Agent Order Body, Transport V1,
Addition-Agent, G04-Propagation, G02-Matrix, Demo, Worker-Recheck, p21, Routing,
Pipeline).

## 7. Warum A04–A07 hier enden

A00 hat belegt: Mays-Orders hat **kein** `orderType`, **kein** `agentOrder`,
**keine** Handler-Registry und **keine** Result-/Attempt-Persistenz — auf `main`,
auf dem Feature-Branch und auf RC4. Der Auftrag setzt diese Bausteine voraus.

Der Contract ist deshalb bewusst **RIS-seitig** gebaut: er validiert, was ein
Orders-Body künftig tragen muss, und bildet es auf die vorhandene Runtime ab.
Es wurde **keine** Ersatz-Persistenz und **keine** simulierte Order gebaut.

Für A04–A07 sind vier additive Orders-Punkte nötig (A00 §6): optionales
`agentOrder`-Feld in der Allowlist, Persistenz am Order-Item, Eigentümerbindung
aus dem JWT, Ergebnis-Feld mit autorisiertem Abruf. Punkte 3 und 4 sind
Sicherheits-/Vertragsentscheidungen (B2/B4), nicht bloß Fleißarbeit.

## 8. Status

| Gate | Status |
|---|---|
| A00 | COMPLETE |
| A01 | COMPLETE (Contract + Schema-Tests) |
| A02 | COMPLETE (Versionierung, Fingerprint) |
| A03 | COMPLETE (Mapping, `42` belegt) |
| A04 | **BLOCKED** — Orders-Vertrag |
| A05 | **BLOCKED** — kein Dispatch-Consumer |
| A06 | **BLOCKED** — keine Result-Persistenz |
| A07 | **BLOCKED** — hängt an A04–A06 |

Kein Live-E2E, kein Deployment, kein Merge. Mays-Orders unverändert.
