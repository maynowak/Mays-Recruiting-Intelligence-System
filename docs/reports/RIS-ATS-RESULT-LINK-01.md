# RIS-ATS-RESULT-LINK-01 — Produkt-Result-Pfad (lokal)

**Status:** Lokale Implementierung, Tests und Commits abgeschlossen. Kein AWS
Apply, kein Deployment, kein Merge, kein Push auf `main`.
**Datum:** 2026-11-17
**Branch:** `feature/ris-dev2-ats-agent-pinned-core-01`
**Konto/Workspace (unverändert):** `262370457690` / `ris-dev2`
**Orders-Lifecycle:** `managed` (eigene Tabelle `ris-dev2-mays-orders`)

## 1. Ergebnis in einem Satz

Die Kette Partner-WorkItem → ATS-Agent → `ATSAnalysisResultBody` 2.0 →
Persistenz → `ORDER_RESULT` über Transport V1 → eigene Orders-Fassade →
autorisierter Read-back ist lokal vollständig belegt; jeder Schritt ist
fail-closed, und der Live-Pfad bleibt bis zu einem separaten Apply bewusst
blockiert.

## 2. Commits

| Commit | Inhalt |
|---|---|
| `95dc5b3` | `feat(ats): forward ORDER_RESULT from persisted work correlation` — Phase 1+2: Korrelation auf der Work-Row, HMAC/SQS-Sender, Forwarder, Tests |
| `8336168` | `feat(orders): bind reader reads and writes to the verified JWT owner` — Phase 3: Reader-Identität, Owner-Isolation, Whitelist, `gsi3`, Terraform-Env, Docs, Tests |
| `a8264e3` | `test(ats): prove the local result link end to end with negative cases` — Phase 4: Integrationstest + Negativmatrix |

Vorherige, übernommene Basis: `ff0b3ef` (xrepo-Draft), `3296b6c`
(Catalog-Seed + Body 2.0), `cae9b36` (Continuation-Bericht).

## 3. Implementierte Änderungen

### Phase 1 — Korrelation

- `agents/runtime/pipeline.py`: `_register_processing` persistiert
  `orderId`, `correlationId` (Fallback `requestId`), `transportMessageId`,
  `apiProfileId`, `partnerApplicationId`, `issuer` auf der Work-Row.
- Bestehende WorkItems ohne Order-Korrelation bleiben gültig und werden
  definiert nicht weitergeleitet (kein Fehler, kein Retry-Sturm).
- Die Korrelation überlebt Retries, weil `_start_retry_attempt` nur
  Status/Attempt/Execution setzt und die übrigen Felder erhält.
- Kein neues Schema, kein zweiter Vertrag: die Row ist der Korrelationsspeicher.

### Phase 2 — Result-Forwarder

- Neu: `agents/transport/order_result_sender.py`
  - `sign_result(secret, messageId, body)` = `HMAC-SHA256(secret,
    messageId + "\n" + body)` hex, exakt die Regel des Orders-Consumers.
  - `make_sender(queue_url, secret_arn)` liefert einen Callable, der die
    signierte Nachricht als SQS-`serviceSignature`-Attribute sendet.
- `agents/runtime/pipeline.py`
  - `_forward_order_result` läuft **nur nach** dem konditionalen
    Result-Write; ein gefencter/erased/stale Attempt kann kein Result senden.
  - Der Carrier wird aus der persistierten Row rekonstruiert
    (`ORDER_DISPATCH`-Form mit `orderId`, `correlationId`,
    `identity.contextRef`). Es wird kein Envelope durch SQS geschleust.
  - Der Pipeline-Wrapper `{success,data,...}` wird genau einmal entpackt;
    Orders erhält den ResultBody.
  - Wiederverwendet wird ausschließlich Transport V1:
    `result_from_work_item` + `validate_envelope(expected_type=ORDER_RESULT)`.
  - Der COMPLETED-Duplikatpfad sendet dasselbe deterministische
    `messageId`/`idempotencyKey` erneut und schließt das Crash-Fenster
    zwischen Persistenz und `SendMessage`.
  - `CANCELLED`, `DEAD_LETTER` und nicht-terminale Zustände senden nie.
- Fail-closed: fehlende `orderId`, `correlationId`, `apiProfileId` oder
  `ORDER_RESULT_QUEUE_URL`/`ORDER_RESULT_SECRET_ARN` → Skip, Row bleibt
  `COMPLETED`, keine behauptete Zustellung. `TransportError` (Formfehler,
  secret-förmiges Result) wird geloggt und nie gesendet. Sender-/Secret-Fehler
  werden geworfen, damit SQS-Redelivery erneut zustellt.

### Phase 3 — Orders-Reader

- `lambda/orders_reader.py`
  - Identität ausschließlich aus den vom Gateway verifizierten Claims
    (`requestContext.authorizer.jwt.claims`).
  - Issuer und Client werden zusätzlich gegen `ORDERS_COGNITO_ISSUER` /
    `ORDERS_COGNITO_CLIENT_ID` geprüft; fehlende Konfiguration → `503`
    (nicht „Prüfung überspringen").
  - Owner-Key byte-identisch zum Orders-Modul:
    `sha256(normalize(iss) + "\x00" + sub)`, `normalize = strip().rstrip("/")`.
  - Fremder Owner, fehlender Owner und Legacy-Row ohne `ownerKey` liefern
    einheitlich `404 ORDER_NOT_FOUND` — Existenz wird nicht geleakt.
  - `GET`/`PATCH` prüfen den Owner vor jedem Statuszugriff bzw. Update.
  - `GET /orders` liest über `gsi3pk = ownerKey`; ein Indexfehler endet
    `503` und fällt niemals auf die globale `gsi1`-Liste zurück.
  - `POST` persistiert `ownerIssuer`, `ownerSubject`, `ownerKey`,
    `ownerClientId`, `actorType`, `actorId`, `gsi3pk`, `gsi3sk`.
  - Antworten sind Allowlists (Retail-Felder, `agentOrder.{target,input,
    metadata,resultContract}`, `processing.{status,attempt,completedAt,
    result,error.message}`). Nicht ausgeliefert werden `pk`, `sk`, `gsi*`,
    `version`, `subjectId`, `owner*`, `actor*`, `agentOrderFingerprint`,
    `expectedWorkId`, `dispatch` sowie Work-/Message-/Execution-IDs.
  - Ein gespeichertes Result mit credential-förmigem Schlüssel oder Wert
    wird als `500` ohne Inhalt zurückgehalten.
- Terraform: `modules/orders_reader` erhält `cognito_issuer` /
  `cognito_client_id` und die beiden `ORDERS_COGNITO_*`-Env-Variablen;
  `terraform/main.tf` verdrahtet `local.identity_issuer` und die Human-Client-ID.
- Docs: `docs/api/API-STANDARD.md` dokumentiert JWT+Owner, `401`/`503`,
  `gsi3`-Liste und die Whitelist.

### Phase 4 — Integration

- Neu: `tests/test_ats_result_link.py`. Gefälscht sind nur
  Infrastrukturgrenzen (Work-Tabelle, Order-Tabelle, Sender-Capture,
  ATS-HTTP-Client). Echt laufen Worker-Pipeline, ATS-Agent, Body-Builder,
  Transport-V1-Mapping und der reale `orders_reader.handler`.
- Positiv: ein `ORDER_RESULT` mit Dispatch-`orderId`/`correlationId`,
  `execution={workId,attempt}`, Nutzlast = Body (kein Wrapper),
  `bodyVersion 2.0`, Score 50; der Owner liest das Ergebnis mit
  `agentOrder.target.agentId=ats-agent` zurück.
- Negativ: fremder Owner (`404`, kein Leak), fremder Issuer (`401`),
  fehlende Korrelation (kein Versand), doppelte Zustellung (gleiche
  `messageId`/`idempotencyKey`), fehlende Transportkonfiguration (kein
  Versand, keine behauptete Zustellung), unbekannte Order (`404`),
  unerlaubte/secret-förmige Resultfelder (kein Versand; Reader `500` ohne Inhalt).
- Addition- und ATS-Direktpfade bleiben durch die bestehenden Suiten abgedeckt.

## 4. Testergebnisse

| Suite | Ergebnis |
|---|---|
| `tests/test_worker_pipeline.py` + `tests/test_order_transport_contract.py` | 76 passed |
| `tests/test_orders_reader.py` | 22 passed |
| `tests/test_real_orders_adapter.py` | 18 passed |
| `tests/test_ats_result_link.py` | 10 passed |
| Gezielte Regression (Worker, Transport, Reader, Lambda-Bridge, MO-Vertrag, Dispatch-Ingress, Terraform-Transport, API-Konsistenz, Privacy, Link) | 183 passed, 24 skipped, 318 subtests |
| Lambda-Packaging/ATS-Bundle | 9 passed, 2 skipped |
| Volle Suite | 2621 passed, 127 skipped, 434 subtests, 29 failed, 4 collection errors |

Die 29 Fehlschläge und 4 Collection-Errors sind **vorbestehend** (u. a.
`test_ris_admin_credentials.py`, `test_composite_lifecycle.py`,
`test_dependency_check.py`, fehlende `moto`/`requests`/`ConsentContext`).
Gegenüber der Baseline ist keine zusätzliche Regression entstanden; die drei
anfänglich neuen Reader-POST-Fehler wurden durch die Identitätsanforderung
verursacht und in `test_real_orders_adapter.py` korrekt nachgezogen.

Terraform: `terraform fmt -check -recursive` exit 0;
`terraform init -backend=false` + `terraform validate`:
„Success! The configuration is valid" (nur Warnungen).

## 5. Contract-Kompatibilität

- **Transport V1 unverändert:** gleiche `schemaVersion`/Message-Typen,
  `ORDER_RESULT` mit `sender`, `recipient`, `identity`, `execution`,
  `payload`; keine neuen Felder, keine neue Queue, kein zweiter Vertrag.
  `validate_envelope` erzwingt weiterhin Order-ID-Regex, Message-ID-Zeichen,
  16-KiB-Grenze und den rekursiven Secret-Scan.
- **HMAC-Regel gepinnt:** `sign_result` entspricht
  `result_envelope.py` des Orders-Consumers; ein Vektor-Test friert die Regel ein.
- **ATSAnalysisResultBody 2.0 unverändert** aus `3296b6c`; `titleTokens`
  bleibt bewusst draußen.
- **Orders-API:** weiterhin genau 4 Routen; Statuscodes und das duale
  Fehlerformat bleiben erhalten. Neu dokumentiert sind `401`/`503` und die
  Owner-Semantik; `404` bleibt die einzige Antwort für fremd/unbekannt.
- **Owner-Key-Kompatibilität:** identische Normalisierung und Digest-Eingabe
  wie im Orders-Modul, damit von Orders geschriebene Items für den RIS-Reader
  lesbar sind.

## 6. Offene Blocker (ehrlich)

1. **Keine produktive Result-Queue/Secret-Konfiguration in RIS.**
   `enable_agent_transport=false`; es gibt keine `ORDER_RESULT_QUEUE_URL` /
   `ORDER_RESULT_SECRET_ARN` am Worker. Der Forwarder überspringt daher live
   und die Row bleibt `COMPLETED`.
2. **Managed Orders-Modul exportiert die Result-Queue nicht.** Das Overlay
   `installer/projects/mays_order_builder/terraform` legt `agent_transport`
   nur bei `enable_agent_transport=true` an und exportiert
   `results_queue_url` / `result_hmac_secret_arn` nicht; RIS übergibt weder
   das Flag noch `ris_result_producer_role_arns`. Ohne diese Verdrahtung
   existiert keine Queue, keine Producer-Grant und kein Secret.
3. **Secret-Wert nicht gesetzt.** Das Secret ist container-only; der Wert muss
   außerhalb von Terraform/State/Git gesetzt werden.
4. **Live-Katalog noch ohne `ats-agent`.** Der Seed ist lokal in `3296b6c`;
   bis zum Apply liefert der öffentliche Execute-Pfad `403`.
5. **Live-Reader ohne Identitäts-Env.** Ohne Apply der beiden
   `ORDERS_COGNITO_*`-Variablen antwortet der Reader fail-closed mit `503`.
6. **Live-Body noch 1.1.** Erst ein Lambda-Apply bringt Body 2.0.
7. **Kein öffentlicher Result-Read-back am Execute-Pfad.** Execute bleibt
   `202`; das Ergebnis ist nur über `GET /orders/{orderId}` mit JWT+Owner
   lesbar. Eine Partner-Result-Route wäre eine neue API-Route und ist bewusst
   nicht Teil dieses Auftrags.
8. **Externe Orders-Instanz `240571105849` bleibt außen vor** (403, kein
   Cross-Account-Link). Ebenso unverändert: xrepo ohne Issues/Dispatch,
   kein Merge nach `main`.

## 7. Genau benötigte Infrastrukturänderungen (für den Apply-Gate)

Alles im Konto `262370457690`, Workspace `ris-dev2`, Managed-Orders. Keine
Cross-Account-Bindung an `240571105849`.

**A. Orders-Seite (managed Modul, gleiches Konto)**

1. `enable_agent_transport = true` an den generierten `mays_orders`-Modulaufruf
   durchreichen (neue RIS-Root-Variable, Default `false`).
2. `ris_result_producer_role_arns = [<ARN der RIS-Worker-Rolle>]` setzen; die
   Queue-/Secret-Policy erlaubt damit `sqs:SendMessage` bzw.
   `secretsmanager:GetSecretValue`.
3. `results_queue_url` und `result_hmac_secret_arn` aus dem generierten Modul
   exportieren (heute nicht in `outputs.tf` des Overlays) und an RIS
   weiterreichen.
4. Secret-Wert (`<project>-agent-result-hmac`) out-of-band setzen; niemals in
   Terraform-State, Git, Reports oder Logs.

**B. RIS-Seite (Worker)**

5. Neue Root-Variablen `agent_result_queue_url` / `agent_result_secret_arn`
   (Default `""` = aus).
6. Diese als `ORDER_RESULT_QUEUE_URL` / `ORDER_RESULT_SECRET_ARN` in die
   Worker-Lambda-Env aufnehmen (`terraform/modules/lambda/main.tf`).
7. Count-gated IAM-Policy an der Worker-Rolle:
   `sqs:SendMessage` auf die Result-Queue-ARN und
   `secretsmanager:GetSecretValue` auf das Secret-ARN (nur wenn gesetzt).
8. Keine neue Queue, kein neues DLQ, kein neuer Vertrag; die Orders-Seite
   besitzt Queue und Redrive-Policy.

**C. Bereits vorbereitete lokale Änderungen, die der Apply mitnimmt**

9. Catalog-Seed `ats-agent` (aus `3296b6c`) — behebt den Live-`403`.
10. Reader-Env `ORDERS_COGNITO_ISSUER` / `ORDERS_COGNITO_CLIENT_ID`
    (aus `8336168`) — ohne sie bleibt der Reader bewusst `503`.
11. Lambda-Bundle mit Body 2.0 — behebt die Live-Version 1.1.

## 8. Vorbereiteter separater Apply-Gate (nicht ausgeführt)

Voraussetzungen, die vor dem Gate nachzuweisen sind:

- `git rev-parse HEAD` == der freigegebene Commit; Working Tree sauber.
- STS-Konto `262370457690`, Region `eu-central-1`, Workspace `ris-dev2`,
  Backend-Key und State-Serial unverändert gegenüber der Baseline.
- `python lambda/build_zip.py --bundle all` erfolgreich; Bundle-Hashes notiert.
- `terraform fmt -check -recursive` exit 0, `terraform validate` erfolgreich.
- Plan zeigt ausschließlich: Catalog-Seed-Änderung, Reader-Env, Lambda-Bundle,
  neue Result-Queue + Secret + Policies + Worker-IAM + Worker-Env.
  Stopp bei Delete/Replace geschützter Ressourcen, bei Cognito-/DNS-/ACM-/
  CloudFront-Änderungen oder bei unerklärter Drift.
- `enable_agent_transport` wird nur für die Orders-Result-Queue aktiviert,
  nicht als Nebeneffekt anderer Flags; `orders_lifecycle` bleibt `managed`.

Nach dem Apply zu verifizieren (read-only):

1. Öffentlicher ATS-Execute liefert `202` (kein `403` mehr).
2. Work-Row hat `orderId`/`correlationId`; Result-Row ist `COMPLETED`.
3. Genau ein SQS-Result je Completion; `serviceSignature` vorhanden;
   Orders `processing.result.bodyVersion == "2.0"`, Score und Addition korrekt.
4. Duplikat-Zustellung erzeugt keinen zweiten fachlichen Abschluss.
5. `GET /orders/{orderId}` mit Owner-JWT → `200`; fremder Owner → `404`;
   fremder Issuer → `401`; fehlende Reader-Env → `503`.
6. Kein Secret, kein `ownerKey`, kein `subjectId`, kein `gsi*` in Antworten
   oder Logs.

## 9. Grenzen dieses Auftrags

- Kein AWS Apply, kein Deployment, kein Destroy.
- Kein Merge, kein Push auf `main`.
- Keine Änderung an Mays-Jobsearch, keine Cross-Account-Bindung an
  `240571105849`, keine neue Agenten-Runtime/Registry/Queue-Architektur.
- Bestehende Source-Pins unverändert.

**HARD STOP nach der lokalen Integration.**
