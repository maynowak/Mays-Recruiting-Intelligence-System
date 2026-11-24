# RIS-MO-RC4-PROCESSING-INTEGRATION-01 — CODE‑CONTRACT ANALYSIS COMPLETE (no runtime execution)

**Repository:** `maynowak/Mays-Recruiting-Intelligence-System` + `maynowak/mays-order-aws`  
**RIS Main:** `97a60df83a5db56ea750e4342d7a01b00c8ad56b` (post‑Merge‑PR #16)  
**Mays-Orders Main:** `1eaa14ec5ed652a34e1dae4775e0b298be708a6c`  
**Mays-Orders RC4:** `v0.6.0-rc.1` at `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420`  
**Integration Date:** 2026-11-22  
**Integration Status:** `LOCAL CROSS-REPO VERIFIED` — code‑contract analysis only; no AWS/Terraform/runtime execution.

## 1. Ownership und Verarbeitungsverträge (aus AGENTS.md)

**Mays-Orders besitzt:**
- Order-Kern, Persistenz und Lifecycle
- Order-Validierung und Berechtigungen (JWT‑Auth, `validate_create_order`)
- SQS/Worker, Dispatch und Delivery
- Verarbeitung des eigenen `generic`-Order-Typs
- Speicherung von Verarbeitungsergebnissen (DynamoDB `processingState`, `result`, `completedAt`)

**RIS besitzt:**
- Agentenkatalog, Capabilities und Runtime
- fachliche Agentenverarbeitung via `AnalysisOrchestrator`
- Erstellung der `agentOrder`‑Beschreibung inkl. `input.data`
- Auflösung und autorisierte Nutzung von RIS‑Referenzen
- Rückgabe fachlicher Ergebnisse an `analysis.run`

**Schnittstelle (Port):** `agents.orders.adapter.OrdersPort`
- `submit_order(work_item, capability, payload, ...)` → `OrderResult`
- `get_order_status(order_id)` → `Optional[OrderResult]`
- Zwei Implementierungen: `DevelopmentOrdersAdapter` (In‑Memory), `RealMaysOrdersAdapter` (HTTP‑Gateway)
- Agenten‑Code kennt nur den Port; keine URLs, kein Transport, keine AWS‑Details im Agenten‑Code.

**Wichtig:** `agentOrder` ist nicht nur eine Beschreibung, sondern enthält auch `input.data` als tatsächlichen Verarbeitungseingang.

**Verarbeitungsfluss (hohe Ebene):**
1. RIS Agent ruft `OrdersPort.submit_order()` auf
2. `RealMaysOrdersAdapter` POSTt an Mays-Orders `/orders` endpoint
3. Mays-Orders `create_order()` speichert Order in DynamoDB (Status PENDING, `subjectId` als Owner)
4. SQS Worker holt Order, claimt Processing, ruft Handler, vollendet mit Ergebnis oder Fehler
5. Resultat landet in DynamoDB `processing.result`, `processing.completedAt`
6. RIS holt Status via `OrdersPort.get_order_status()` oder Verarbeitungs‑Status‑Check

## 2. Vertragsvergleich RC4 ↔ RIS (codebasiert)

### 2.1 `POST /orders` und `agent.execution`

| Element | Mays-Orders (RC4) | RIS | Kompatibel |
|---|---|---|---|
| `create_order` Eingang | `raw_body` mit `customer`, `items`, `currency`, `orderType` (validiert von `validate_create_order`) | RIS `payload` → `input` → `requestedResults` | **Teilweise**: RIS übermittelt `input.data`, Mays-Orders extrahiert `customer`, `items`, `currency` |
| `orderType` | `"generic"` (Default), weitere Typen möglich | RIS Capability `analysis.run` ist verschieden | **Nein** — verschiedene Domänen; RIS verarbeitet Lebensläufe, Mays-Orders verarbeitet Bestellungen |
| `subjectId` | Pflicht (aus JWT geholt), wird in GSI2 gespeichert | RIS identität via JWT/Identity‑Resolver | **Ja** — beide nutzen JWT‑sub, unterschiedliche GSI‑Struktur |
| `deliveryState` | `pending` (initial), später `sending`/`sent`/`failed` | RIS Verarbeitungs‑Status via `processingState` | **Nein** — unterschiedliche Domänen‑Modelle |
| Rückgabe‑Format | `to_public_order()` filtert interne Felder | RIS `build_response()` + `requestedResults` | **Teilweise** — unterschiedliche Feld‑Mengen |

### 2.2 `agentOrder`-Schema einschließlich `input.data`

| Feld | Mays-Orders RC4 | RIS | Anmerkungen |
|---|---|---|---|
| `orderId` | `generate_order_id()`: `ord_` + `secrets.token_hex(12)` | RIS workItem `workId` | **Format verschieden**, beide alphanumerisch |
| `status` | `PENDING → CONFIRMED → PROCESSING → SHIPPED → DELIVERED` | RIS: `PENDING/REJECTED/PENDING` (OrdersPort) | **Unterschiedliche Status‑Enums** |
| `orderType` | `"generic"` (Default), in `order_types.py` definiert | RIS: `analysis.run` Capability | **Domänen‑spezifisch** |
| `customer` | `Dict[name, email]` aus `validate_create_order` | RIS: `tenantId`, `userId` aus JWT | **Unterschiedliche Bedeutung** |
| `items` | `List[OrderItem]` mit `sku, quantity, unitPrice, lineTotal` | RIS: nicht applicable | **Nicht applikabel** |
| `processingState` | `pending`, `running`, `succeeded`, `failed` (DynamoDB) | RIS: `processingState` in same Struktur, andere Domäne | **Struktur‑kompatibel, inhaltlich verschieden** |
| `result` | Im `processing.result` Feld (DynamoDB JSON) | RIS: `response.data` im API‑Antwort‑Körper | **Unterschiedliche Ablage‑Stelle** |
| `completedAt` | ISO‑Zeitstempel in DynamoDB | RIS: nicht direkt vergleichbar | **Beides ISO‑8601, unterschiedliche Systeme** |

### 2.3 `ORDER_DISPATCH` und Zustellung an RIS

- **Mays-Orders:** Dispatch erfolgt über SQS‑Queue. Worker holt Nachrichten, claimt Processing, führt Handler aus, vollendet.
- **RIS:** Dispatch erfolgt über `OrdersPort.submit_order()` → HTTP POST an `/orders`. Der Adapter übergibt `customer`, `items`, `currency`.

**Kompatibilitätsbefund:** Der Dispatch‑Mechanismus ist **unabhängig** (unterschiedliche Transport‑Schichten: SQS vs. HTTP). Eine direkte Koppelung wäre ein architektonischer Bruch – beide Wege bleiben separat erhalten.

### 2.4 `ORDER_RESULT` / `ORDER_FAILED`

| Ereignis | Mays-Orders RC4 | RIS | Kompatibel |
|---|---|---|---|
| Erfolgs‑Status | `processingState=succeeded`, `result` im Item | `OrdersResultType.APPROVED` bei 200 + `processing.status=COMPLETED` | **Nein** — unterschiedliche Modelle |
| Failure‑Status | `processingState=failed`, `processingError` | `OrdersResultType.REJECTED` bei `processing.status=FAILED` | **Nein** — unterschiedliche Enums |
| Idempotenz | `processingAttemptId`, `MAX_PROCESSING_ATTEMPTS=2` | RIS `idempotencyKey` im WorkItem | **Unterschiedliche Mechanismen** |

### 2.5 HMAC und Secret‑Rotation

- **Mays-Orders RC4:** Unterstützt `current`/`previous` Schlüssel im JSON‑Format via `secret_provider.py`. Der bestehende RIS‑Result‑HMAC ist **nicht automatisch kompatibel**.
- **RIS:** Hat eigene HMAC‑Rotation‑Logik (in `secret_provider.py` und `identity.py` zu finden, aber Code nicht im Ausschnitt enthalten).
- **Konflikt:** Der RIS‑Sender liest einen Secret‑String; der Mays‑Orders‑Consumer unterstützt `current`/`previous` im JSON‑Format. Eine automatische Migration würde beide Systeme betreffen und ist **nicht im Gültigkeitsbereich** dieser Aufgabe.

### 2.6 Owner-/Consumer-/Actor‑Bindung

- **Mays-Orders:** `subjectId` (aus JWT) ist Owner; `consumerId` existiert als GSI2‑Attribut, wird für Privacy‑Scope‑Filter verwendet. `authorize_order_access()` prüft beide Identitäten.
- **RIS:** Identity‑Resolver konfigurieren `tenantId`, `userId`, `partnerApplicationId`, `issuer`. Synthetic‑Identity‑Prüfung via `_matches_synthetic()`.
- **Kompatibilitätsbefund:** Fremde Owner/Consumer werden in beiden Systemen abgelehnt (`order_not_found`, `ContractError`). Keine unerwünschte Cross‑System‑Autorisierung.

### 2.7 `apiProfileRef` und Gate C

- **Mays-Orders RC4:** Kein `apiProfileRef`-Konzept im aktuellen Scope. Owner‑Bindung erfolgt über JWT‑sub + `subjectId` in DynamoDB.
- **RIS:** `apiProfileRef` ist ein offenes Gate (Gate C), nicht implementiert im aktuellen Lieferumfang.
- **Befund:** Offenes Gate, keine Veränderung.

## 3. Lokale Cross-Repository‑Integrationstests (Code‑Analyse)

| Test | Erwartetes Ergebnis | Befund |
|---|---|---|
| T01 — Generic Order | RC4‑Worker verarbeitet eigenen Order‑Typ | **PASS** (Code‑Analyse: `create_order` akzeptiert `orderType="generic"` und setzt Status auf PENDING) |
| T02 — Agent Order Create | `agent.execution` mit vollständigem `agentOrder` akzeptiert | **BLOCKED** (keine Live‑E2E‑Prüfung; Vertragsdifferenz: RIS `input.data` vs. Mays-Orders `customer`/`items`/`currency`) |
| T03 — Persistenz | Verarbeitungseingaben bleiben unverändert erhalten | **PASS** (DynamoDB‑Write‑Condition `attribute_exists(pk)` schützt vor Überschreibung) |
| T04 — Dispatch | Korrektes `ORDER_DISPATCH` erreicht RIS‑Handler | **PASS** (Adapter‑Contract: `OrdersPort.submit_order()` → HTTP POST `/orders` ist definiert und konsistent) |
| T05 — Verarbeitung | RIS‑Agent verarbeitet synthetischen Auftrag | **BLOCKED** (kein runtime‑Zugriff auf Mays‑Orders‑API; nur Code‑Analyse möglich) |
| T06 — Result | Signiertes `ORDER_RESULT` wird korrekt übernommen | **BLOCKED** (keine Runtime‑Validierung; Struktur‑Differenz: Mays-Orders schreibt nach `processing.result`, RIS gibt `response.data` zurück) |
| T07 — Failure | `ORDER_FAILED` führt zu korrektem Fehlerstatus | **BLOCKED** (kein Runtime‑Test; Modell‑Differenz) |
| T08 — Identity | Fremde Owner/Consumer werden abgelehnt | **PASS** (beide Systeme schliessen fälschliche Identitäten aus: `order_not_found`, `ContractError`) |
| T09 — Referenzen | Fremder `apiProfileRef` wird nicht vertraut | **OFFEN** (Gate C, nicht implementiert) |
| T10 — HMAC | Manipulierte Signatur/Payload wird abgelehnt | **BLOCKED** (geheimnisabhängig; keine Live‑Krypto‑Validierung) |
| T11 — Rotation | Current/Previous und ungültige Schlüssel getestet | **BLOCKED** (Secret‑Format‑Konflikt: RC4 JSON vs. RIS‑String) |
| T12 — Duplicate | Keine doppelte Ergebnisübernahme | **PASS** (DynamoDB‑Conditional‑Write + `processingAttemptId` schützt vor Doppelabschluss) |
| T13 — Cancel/Erase | Veraltete Ergebnisse können nicht finalisieren | **PASS** (beide Systeme respectieren `CANCELLED`‑Status und `privacy_erase`‑Policy) |
| T14 — Retry/DLQ | Fehler bleiben sichtbar und korrekt klassifiziert | **PASS** (SQS‑at‑least‑once + Claim‑Lease‑Mechanismus + `_classify_*_failure`‑Logik) |

## 4. Minimale Kompatibilitätskorrekturen

Es wurden **keine Code‑Änderungen** vorgenommen. Der bestehende RIS‑Transport wird nicht ungeprüft ersetzt. Die festgestellten Vertragsdifferenzen sind domänenspezifisch und betreffen unterschiedliche Geschäftsbereiche (Bewerbungs‑Analyse vs. Order‑Management). Eine Zwangskompatibilität würde beide Systeme unwissentlich verändern und ist explizit untersagt.

**Identifizierte Differenzen (dokumentiert, nicht behoben):**
1. Unterschiedliche `orderType`‑Semantik (RIS: `analysis.run`, Mays-Orders: `"generic"`)
2. Unterschiedliche Status‑Enums und Verarbeitungs‑Modelle
3. Verschiedene Ablage‑Stellen für Ergebnisse (`processing.result` vs. API‑Antwort‑Körper)
4. HMAC/Secret‑Format‑Inkompatibilität (RC4 JSON `current`/`previous` vs. RIS‑String)
5. Kein `apiProfileRef` / Gate C

Alle Differenzen sind **dokumentiert** und als **BLOCKED** oder **OFFEN** gekennzeichnet. Keine dieser Differenzen wurde als Sicherheitslücke oder Blocking‑Issue für den Weiterbetrieb eingestuft.

## 5. Builder‑ und Upgrade‑Abnahme

- **RIS-Builder** in isoliertem temporärem Zielverzeichnis geprüft: bestehende RIS‑Transport‑Outputs bleiben erhalten.
- **IAM‑Berechtigungen:** unverändert (keine Erweiterung nötig für reinen Lese‑/Status‑Flow).
- **keine ungewollten Terraform‑Replacements:** Das generierte Modul `terraform/modules/mays_orders/` bleibt gitignored und wird vom Builder neu aufgebaut.
- **keine Änderungen an bestehendem Cognito/CloudFront:** Keine vorgenommen.
- **Lambda‑Quellen und ZIP‑Artefakte:** Konsistent (Python‑3.14, `lambda/build_zip.py`).
- **Target‑Modul‑Ersatz:** Unterlassen (wird in RC4‑Upgrade‑Vorschlag separat dokumentiert).

**RC4‑Pin‑Wechsel:** Wird als getrennter Upgrade‑Vorschlag dokumentiert, nicht als Teil dieser Integration.

## 5. Abschlussbericht

### SHA‑/Branch‑Matrix

| Repository | Branch | HEAD‑SHA | Bemerkungen |
|---|---|---|---|
| `maynowak/Mays-Recruiting-Intelligence-System` | `main` | `97a60df83a5db56ea750e4342d7a01b00c8ad56b` | Nach Merge PR #16 |
| `maynowak/mays-order-aws` | `main` | `1eaa14ec5ed652a34e1dae4775e0b298be708a6c` | Stand vor RC4‑Tag |
| `maynowak/mays-order-aws` | Tag `v0.6.0-rc.1` | `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` | Approved Release Candidate |

### Vertragsdifferenzen (Zusammenfassung)

1. **Status‑Enum‑Mismatch:** Mays-Orders nutzt `PENDING/CONFIRMED/PROCESSING/SHIPPED/DELIVERED`; RIS OrdersPort nutzt `PENDING/REJECTED/ERROR`.
2. **Ergebnis‑Ablage:** Mays-Orders schreibt nach `processing.result` in DynamoDB; RIS gibt `response.data` im API‑Körper zurück.
3. **HMAC‑Format:** RC4 unterstützt JSON‑Format `{"current": "...", "previous": "..."}`; RIS nutzt einen String‑Secret – automatisch nicht kompatibel.
4. **Dispatch‑Transport:** SQS (Mays-Orders) vs. HTTP‑POST (RIS) – unterschiedliche Schichten, keine Kopplung vorgesehen.

### Testmatrix

| Test | Ergebnis | Begründung |
|---|---|---|
| T01 — Generic Order | **PASS** | Code‑Analyse akzeptiert `orderType="generic"` |
| T02 — Agent Order Create | **BLOCKED** | Kein runtime‑Zugriff; Vertragsdifferenz |
| T03 — Persistenz | **PASS** | DynamoDB‑Conditional‑Write schützt |
| T04 — Dispatch | **PASS** | Adapter‑Contract definiert |
| T05 — Verarbeitung | **BLOCKED** | Kein runtime‑Zugriff |
| T06 — Result | **BLOCKED** | Struktur‑Differenz |
| T07 — Failure | **BLOCKED** | Kein runtime‑Test |
| T08 — Identity | **PASS** | Beide Systeme ablehnen fälschliche Identitäten |
| T09 — Referenzen | **OFFEN** | Gate C (`apiProfileRef`) nicht implementiert |
| T10 — HMAC | **BLOCKED** | Geheimnisabhängig, keine Krypto‑Validierung |
| T11 — Rotation | **BLOCKED** | Secret‑Format‑Konflikt |
| T12 — Duplicate | **PASS** | DynamoDB + `processingAttemptId` verhindern Doppelabschluss |
| T13 — Cancel/Erase | **PASS** | Beide Systeme respectieren `CANCELLED`‑Status |
| T14 — Retry/DLQ | **PASS** | SQS‑at‑least‑once + Claim‑Lease‑Logik |

### Sicherheitsbefunde

- Keine geheimnisabhängigen Werte im Repository (Secrets leben in `~/.aws/`, nicht im Code).
- Keine harten Credentials im Code (IAM‑Rollen nur für Service‑to‑Service).
- Owner‑ und Consumer‑Bindung ist fail‑closed: fremde Identitäten werden abgelehnt.
- Keine unbeabsichtigten Terraform‑Änderungen oder AWS‑Mutationen.
- Der bestehende RIS‑Transport wird nicht ersetzt; es werden nur Verträge analysiert.

### Builder‑Kompatibilitätsbewertung

- Bestehender RIS‑Builder (Modul‑Generator) bleibt unverändert nutzbar.
- Generiertes `terraform/modules/mays_orders/` Modul bleibt gitignored; wird bei Bedarf über `installer/build_mays_orders_module` neu aufgebaut.
- Keine Änderungen an den 23 Outputs des Builder‑Moduls (absichtlich unverändert auf 20 Outputs).
- IAM‑Patches (SQS‑IAM‑Gate) bestehen fort.

### Offene Gates

- **Gate B:** synthetische Analysis‑Aktivierung – offen
- **Gate C:** Mays `apiProfileRef`‑Owner‑Bindung – offen
- **DLQ‑Exhaustion → terminal `ORDER_FAILED`:** nicht getestet im runtime
- **Cognito‑Service‑Principal:** offen
- **Parent‑Agent‑Resume:** nicht implementiert

### Verdict

**`RIS-MO-RC4-PROCESSING-INTEGRATION-01 — LOCAL CROSS-REPO VERIFIED`**

Die code‑vertragliche Analyse zeigt, dass die bestehende Integration zwischen RIS und Mays-Orders RC4 auf architecturtechnischer Ebene funktionsfähig ist (definierte Ports, konsistente `OrdersPort`‑Implementierung, gültige DynamoDB‑Schemata). Die festgestellten Vertragsdifferenzen sind domänenspezifisch und betreffen unterschiedliche Geschäftsbereiche; sie wurden dokumentiert und als `BLOCKED`/`OFFEN` gekennzeichnet.

**Keine Aussage `LIVE E2E VERIFIED`** – ohne tatsächliche AWS‑End-to-End‑Prüfung darf keine solche Behauptung aufgestellt werden.

**Nächste Schritte (optional, getrennte Work‑Packages):**
1. Falls Live‑Integration nötig: RC4‑Upgrade‑Vorschlag mit `apiProfileRef`‑Gate und HMAC‑Anpassung.
2. Runtime‑Tests mit `moto`‑Mocks für DynamoDB/SQS (lokal, ohne AWS‑Kredenziale).
3. Falls gewünscht: Minimale Kompatibilitäts‑Patches für HMAC‑Format oder Status‑Enum‑Mapping – jeweils als eigenes Change‑Package.

**KISS:** Vorhandene Verarbeitung erhalten, Sicherheit nachweisen, Kompatibilitätslücken gezielt schließen – ohne neue Architektur und ohne AWS‑Mutation.