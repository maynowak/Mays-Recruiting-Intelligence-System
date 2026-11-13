# MO-RIS-AGENT-ORDER-BODY-01 — A00 Bestandsanalyse (IST/SOLL/GAP)

**Datum:** 2026-11-13
**Typ:** Read-only Bestandsaufnahme, keine Produktänderung
**Kernbefund:** Die Auftragsannahme über Mays-Orders setzt vier Bausteine voraus,
die im geprüften Code **nicht existieren**. A04–A07 sind ohne Orders-Vertrags­
entscheidung nicht implementierbar.

## 1. Git-Baseline (gemessen)

| Repo | Branch | HEAD | Working Tree |
|---|---|---|---|
| RIS | `feature/ris-mo-addition-agent-e2e-01` | `d137267` | clean, Remote identisch |
| Mays-Orders | `feature/mo-module-contract-ris-dev2-2026` | `9627eb2` | clean, keine Änderung |

Geprüfte Orders-Refs (alle drei): `origin/main`, lokaler Feature-Branch,
`origin/feature/mo-rc4-kms-privacy-retention`.

## 2. Evidence — was Mays-Orders tatsächlich hat

`git ls-tree` listet in `lambda/src/` auf **allen drei Refs** exakt sieben Dateien:

```
errors.py  index.py  order_service.py  order_types.py
sqs_handler.py  state_machine.py  validation.py
```

`git grep -i 'orderType|agentOrder'` über alle drei Refs: **keine Treffer**.
Ebenso keine Treffer für `HandlerRegistry`, `resultStatus`, `processingId`,
`attemptNo`, `processing_result`.

Konkret gelesen:

| Bereich | Befund |
|---|---|
| `POST /orders` | `validate_create_order` erlaubt **nur** `customer{name,email}`, `items[{sku,quantity,unitPrice}]`, `currency`; `reject_unknown_keys` → 400 bei allem anderen |
| `orderType` | existiert nicht — Orders sind implizit Retail |
| Handler-Registry | existiert nicht |
| SQS | `index._send_to_sqs` publiziert `{orderId, status:"CONFIRMED"}`; `sqs_handler` deutet `status` als Statusübergang, ohne Payload-Semantik, ohne Conditional Write |
| Result-Persistenz | keine — es gibt kein `result`-Feld und keinen Ergebnis-Endpunkt |
| Attempt-Persistenz | keine |
| Statusmodell | `PENDING→CONFIRMED→PROCESSING→SHIPPED→DELIVERED`, `CANCELLED` nur aus `PENDING/CONFIRMED`; `PROCESSING→DELIVERED` existiert nicht |
| Eigentümerbindung | **fehlt vollständig**: `lambda/src` liest keinen JWT-Claim; `create_order` bekommt nie `subjectId`; `get_order`/`list_orders` prüfen keinen Besitzer |

## 3. Evidence — was RIS tatsächlich hat

| Baustein | Befund |
|---|---|
| Generic Transport V1 | vorhanden (`agents/transport/order_transport.py`), 53 Contract-Tests grün |
| WorkItem (kanonisch) | `agents/runtime/work_item.py`, `apiProfileId`/`partnerApplicationId`/`issuer` seit `d137267` propagiert |
| ProcessingEnvelope / EventHook | vorhanden; `envelope.input` ist das **gesamte** WorkItem |
| Registry / Discovery / Eligibility / Selection | vorhanden |
| Agent Run Body | vorhanden; Addition-Agent liefert `42` |
| Agent-Katalog | `reference_agent`, `jobsearch-agent`, `addition_agent` (Runtime-Registrierung) |
| OrdersPort | HTTP-Client, unidirektional; kein SQS-Rückkanal |

## 4. IST / SOLL / GAP

| # | Baustein | SOLL laut Auftrag | IST | Status |
|---|---|---|---|---|
| 1 | `orderType` | vorhanden, erweiterbar | nicht vorhanden | **GAP** |
| 2 | `agentOrder` als Order-Bestandteil | Erweiterungspunkt nutzen | kein Erweiterungspunkt; strikte Allowlist | **GAP** |
| 3 | Handler-Registry | vorhanden | nicht vorhanden | **GAP** |
| 4 | Processing-Lifecycle/Result-Persistenz | vorhanden, wiederverwenden | nicht vorhanden (nur 6-Werte-Status) | **GAP** |
| 5 | Attempt-Persistenz | vorhanden | nicht vorhanden | **GAP** |
| 6 | Eigentümerbindung (Partner-Isolation) | vorhanden | fehlt vollständig | **GAP (Sicherheit)** |
| 7 | SQS-Rückweg Orders→RIS | bestehender Vertrag | nur RIS-seitig definiert, kein Consumer | **GAP** |
| 8 | Transport Envelope V1 | vorhanden | vorhanden | **OK** |
| 9 | Registry/Entitlement/APIProfile | vorhanden | vorhanden | **OK** |
| 10 | Addition-Agent / `math.add` | vorhanden | vorhanden, `42` belegt | **OK** |
| 11 | Testpartner-Demo | vorhanden | vorhanden (Fakes) | **OK** |

## 5. Konsequenz für die Gate-Reihenfolge

| Gate | Bewertung |
|---|---|
| A01 Agent Order Body Contract | **GO** — reiner RIS-seitiger Vertrag, unabhängig von Orders |
| A02 Versionierung/Austauschbarkeit | **GO** — dito |
| A03 RIS-Ecosystem-Mapping | **GO** — nutzt vorhandene Runtime, `42` nachweisbar |
| A04 Orders-Integration | **BLOCKED** — erfordert additive Orders-Vertragsänderung (neues optionales Feld + Persistenz + Eigentümerbindung) |
| A05 Orders→RIS Dispatch | **BLOCKED** — kein Consumer, keine Dispatch-Persistenz |
| A06 RIS→Orders Result | **BLOCKED** — kein Result-Feld, kein Empfänger |
| A07 Voll-E2E mit echter Order | **BLOCKED** — hängt an A04–A06 |

**Keine Ersatzarchitektur.** Es wird kein zweiter Order-Store, keine zweite
State-Machine und keine simulierte Orders-Persistenz gebaut. Die Demo bleibt bei
Fakes und behauptet keinen Live-Pfad.

## 6. Minimale Orders-Erweiterung (Vorschlag, nicht umgesetzt)

Damit A04–A07 überhaupt möglich werden, braucht es genau vier additive Punkte —
alle ohne RC3/RC4-Migration:

1. **`agentOrder` als optionales Feld** in der Create-Allowlist, strikt validiert
   gegen den A01-Contract; Retail-Orders bleiben byte-identisch.
2. **Persistenz** des validierten Bodys am Order-Item (internes Feld, nicht in
   `items`/`customer` verpackt).
3. **Eigentümerbindung**: `sub` aus dem verifizierten JWT beim Create setzen und
   bei Read/Patch erzwingen. Ohne diesen Punkt ist A07 („Partner B darf nicht")
   nicht erfüllbar; er ist ein Sicherheitsfix mit Bestandswirkung.
4. **Ergebnis**: eigenes Feld + autorisierter Abruf über die bestehende
   `GET /orders/{orderId}`-Antwort; kein neuer Statuswert, solange nicht
   entschieden (B4).

Offene Entscheidungen bleiben B1 (Payload-Transport), B2 (Eigentümer-Erzwingung),
B3 (Ergebnis-Queue/Consumer), B4 (Status vs. Zusatzfeld).

## 7. Abnahme A00

- Baseline beider Repos belegt.
- Alle drei Orders-Refs geprüft; Befund reproduzierbar.
- IST/SOLL/GAP vollständig.
- Keine Datei im Orders-Repo verändert.
- Keine AWS-Aufrufe.
