# RIS-ATS-ORDER-DISPATCH-LINK-06

**Status:** Lokale Integration vollständig. **Kein AWS Apply, Deploy, Destroy,
Secret-Write, Benutzeranlage, Main-Merge oder Push.**
**Datum:** 2026-11-17
**RIS-Baseline:** `feature/ris-dev2-ats-agent-pinned-core-01` @ `8820ad9`
**Orders-Pin:** `016cdfd6ac62565dcec9a2fee78cb898fb919e59`

## 1. Wiederverwendete Komponenten

| Ebene | Verwendet |
|---|---|
| Agent-Order-Vertrag | `agents/orders/agent_order.py` (Validierung, Defaults, Fingerprint), unverändert als Vertrag |
| Transport V1 | `agents/transport/order_transport.py` (Envelope-Validierung, Dispatch→WorkItem), ergänzt um einen Producer-Helper |
| RIS-Runtime | `dispatch_ingress.handler`, `process_record`, Agent-Routing/Registry, ATS-Agent, Result-Forwarder |
| Result-Transport | `agents/transport/order_result_sender.py`, Orders-Result-Consumer (Pin 016cdfd) |
| Orders-Fassade | `lambda/orders_reader.py` (Owner-Bindung, Read-back) |
| Infrastruktur | `terraform/modules/agent_transport` (Dispatch-Queue + Ingress), `modules/orders_reader`, generiertes Orders-Modul |

## 2. Fehlende und implementierte Verbindungen

1. **Dispatch-Ingress nutzbar gemacht** (`df909c9`): `resolve_context` liest
   den produktiven `DynamoDBApiProfileStore` über `get_profile` und akzeptiert
   `ownerUserId` (statt nur `userId`); Test-Doubles bleiben kompatibel.
2. **Agent-Order im Reader** (`4fb5b88`): expliziter `agent.execution`-Zweig
   statt stiller Retail-Order:
   - validiert `orderType`/`agentOrder` über den bestehenden Vertrag,
   - lehnt gemischte Retail-/Agent-Felder und unbekannte `orderType` ab,
   - verlangt `metadata.requestId` und `metadata.apiProfileRef`,
   - lädt das API-Profil, verlangt `status=ACTIVE`, `ownerUserId == JWT-sub`
     und `tenantId`,
   - bindet genau eine `workId`, persistiert Owner, `agentOrder`, Fingerprint,
     `expectedWorkId` und Dispatch-Status,
   - baut ein validiertes `ORDER_DISPATCH` und sendet es an
     `RIS_DISPATCH_QUEUE_URL`; Fehler werden als `FAILED` markiert.
3. **Transport-Producer** (`4fb5b88`): `build_dispatch_envelope` im bestehenden
   V1-Modul; keine zweite Nachrichtenarchitektur.
4. **Reader-Bundle** (`4fb5b88`): `orders_reader.py` plus flache
   `order_transport.py` und `agent_order.py` (3 Dateien), damit der Reader den
   echten Vertrag statt einer Kopie nutzt.
5. **Infrastruktur** (`5d4a3c8`): RIS-Dispatch-Queue/Ingress über das
   vorhandene Modul aktiviert; Reader erhält `RIS_DISPATCH_QUEUE_URL`,
   `API_PROFILES_TABLE`, `SendMessage` und `GetItem`; der Ingress erhält
   `ORDER_RESULT_QUEUE_URL/SECRET_ARN` plus Sende-/Secret-IAM.
6. **Testisolierung/Privacy** (`8820ad9`): Bridge-Test restauriert Env; der
   Reader enthält kein verbotenes `userId`-Literal mehr.

## 3. Lokaler Produkt-E2E

`tests/test_agent_order_dispatch_e2e.py` (6 Tests) führt ohne AWS aus:

Agent-Order (`POST /orders`, ATS-Target) → persistierte Order mit Owner-Bindung
→ `ORDER_DISPATCH` → echter `dispatch_ingress.handler` → WorkItem mit
`orderId`/`correlationId`/`apiProfileId` → ATS-Agent (Fixture Score 50) →
`ORDER_RESULT` mit `ATSAnalysisResultBody` 2.0 → echter Orders-Consumer
(`result_handler.process_records`, Signatur über Envelope-ID) →
`processing.status=COMPLETED` → Owner-Read 200 / fremder Owner 404.

Geprüft: Work-Row `COMPLETED` + `orderResultDelivery=SENT` + stabile
`messageId`; Order-`status` bleibt `PENDING`; `bodyVersion=2.0`, Score
numerisch; Duplikat ohne zweiten Write; ungültige Signatur ohne Persistenz;
fehlende Entitlement ohne Result; Retail-Order ohne Dispatch; fremdes Profil
403 ohne Persistenz.

## 4. Commits und Tests

| Commit | Inhalt |
|---|---|
| `df909c9` | Dispatch-Ingress-Profilstore-Fix |
| `4fb5b88` | Reader-Agent-Order, Dispatch-Producer, Bundle, Reader-/E2E-Tests |
| `5d4a3c8` | Terraform: Dispatch-Queue/Ingress, Reader-Env/IAM, Ingress-Result-Env/IAM |
| `8820ad9` | Testisolation + Reader-Privacy |

| Suite | Ergebnis |
|---|---|
| Neuer E2E | **6 passed** |
| Reader | **35 passed** |
| Dispatch-Ingress | **16 passed** |
| Cross-Repo gezielt (E2E, Bridge, MO-Contract, Handoff, Transport, Worker, ATS, Reader, Packaging, Static, Ingress) | **192 passed, 2 skipped** |
| Orders-Lambda | **225 passed** |
| Volle RIS-Suite ohne MO-Env | **2654 passed / 134 skipped / 434 subtests**, 29 vorbestehende Fehler, 4 Collection-Errors |

## 5. Neuer Planumfang

Der bisherige Plan `13 add / 4 change` wird um die vorhandene Dispatch-Strecke
erweitert:

**Neuer Plan:** **24 add / 4 change / 0 destroy / 0 replace**
**Plan-SHA-256:** **`6E2A1077E1459B74A015E91518CB1B302817DD9329337A18EDDEA4BCF89ED17C`**

**Zusätzliche Adds (11):**
- 10 × `module.agent_transport[0].*`: Dispatch-Queue, DLQ, Queue-Policy,
  Ingress-Log-Group, Ingress-Rolle/Policy, Result-Send/Secret-Policy,
  Ingress-Lambda, ESM.
- 1 × `module.orders_reader[0].aws_iam_role_policy.reader_agent_dispatch[0]`.

**4 Changes:** RIS-Agent (Bundle/Env), RIS-Reader (Bundle/Env), Orders-Handler
und Orders-Worker (nur `source_code_hash`).

Keine Cognito-, CloudFront-, DNS-, ACM- oder S3-Änderung; kein
`secret_version`; keine Drift (State-Serial 58, ETag unverändert).

## 6. Identitäts- und Infrastrukturblocker

1. **API-Profilzeile** (`apiProfileId`, `status=ACTIVE`, `ownerUserId=<sub>`,
   `tenantId`) muss existieren und dem JWT-Sub gehören.
2. **Entitlement** (`userId=<sub>`, `agentId=ats-agent`, `tenantId`) wird vom
   Dispatch-Ingress/Pipeline erzwungen; fehlt sie, gibt es kein Result.
3. **Dispatch-Strecke** muss per Plan aktiviert werden
   (`enable_agent_transport=true`); der Reader sendet sonst fail-closed 503.
4. **Result-Strecke/Secret:** Ergebnis-Queue/Secret werden mit demselben Plan
   erzeugt; der Secret-Wert muss nach dem Apply out-of-band gesetzt werden.
5. **Testidentität:** beide Pools haben 0 Benutzer; ohne separate Freigabe
   (Benutzer oder M2M-Audience) ist kein Live-E2E möglich.
6. **Partner-Execute bleibt separat:** Der direkte Partner-Execute-Pfad erzeugt
   weiterhin WorkItems ohne `orderId`; der order-korrelierte Pfad ist die
   Agent-Order über die RIS-Fassade + Dispatch.
7. **ATS-Ziel:** ohne `ATS_API_BASE_URL` fällt der Agent auf den externen
   Produktionshost zurück; für einen kontrollierten E2E zu klären.
8. **Betrieb:** Visibility 60 s vs. 30 s, keine DLQ-Alarmierung, kein
   `ORDER_FAILED`.

## 7. GO/NO-GO

**GO (bedingt) für den erweiterten Infrastruktur-Apply:** Der lokale Pfad ist
vollständig belegt, der Plan ist nicht destruktiv (0 Destroy/Replace) und
enthält keine geschützten Ressourcen oder Secret-Werte. Bedingungen:

- Plan gegen den freigegebenen Commit neu erzeugen und `24/4/0/0` bestätigen.
- API-Profil + Entitlement für die Testidentität bereitstellen.
- Secret unmittelbar nach dem Apply setzen und verifizieren.
- `enable_agent_transport=true` und `orders_agent_result_enabled=true` nur über
  den freigegebenen Plan.

**NO-GO für Partner-Traffic/Produkt-Abnahme**, bis Testidentität, Profil,
Entitlement und Secret verifiziert sind.

**HARD STOP vor jedem AWS Apply.**
