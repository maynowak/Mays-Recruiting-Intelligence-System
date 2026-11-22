# RIS-ATS-TRANSPORT-APPLY-05 — Controlled Rollout (Vorbereitung)

**Status:** Apply-Vorbereitung abgeschlossen. **Kein AWS Apply, keine
Secret-Mutation, keine Benutzeranlage, kein Main-Merge, kein Push.**
**Datum:** 2026-11-17
**RIS-Baseline:** `feature/ris-dev2-ats-agent-pinned-core-01` @ `6bb5250`
**Orders-Pin:** `016cdfd6ac62565dcec9a2fee78cb898fb919e59`

## 1. Baseline und Reconciliation

| Prüfung | Wert |
|---|---|
| STS | `arn:aws:iam::262370457690:user/devnemo` |
| Workspace / Region | `ris-dev2` / `eu-central-1` |
| Orders-Lifecycle | `managed` |
| Backend / Key | `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate` |
| Lineage / Serial | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / **58** |
| State-Objekt | 730.545 B, ETag `3736b32b…`, VersionId unverändert |
| Lock | `ris-dev2-tf-lock`, nur MD5-Digests, **keine aktive Lock** |
| Pin / Clone / Manifest | `016cdfd…` / clean / `source.commit=016cdfd…` |
| Modul-Artefakt | `lambda/dist/lambda.zip` = `48ddd5e5…a05f94`, 23 Outputs |
| Drift | **keine** – Live-Code-Hashes und Env von Agent/Reader identisch zum State |

**Plan-SHA-256:** `9A2DA4209AB002E7DDB10D8F1BE9334910A587DB07F59469340285BE9FE8BC3A`
**Umfang:** **13 add / 4 change / 0 destroy / 0 replace**
Keine Cognito-, CloudFront-, Route53/DNS-, ACM- oder S3-Änderung; kein
`aws_secretsmanager_secret_version`; kein Secret-Wert im Plan.

## 2. Exakte Ressourcenänderungen

### Adds (13)

| # | Ressource | Kernkonfiguration |
|---|---|---|
| 1 | `module.dynamodb.aws_dynamodb_table_item.agent_catalog_seed["ats-agent"]` | Tabelle `ris-dev2-dev-agent-catalog`, `agentId=ats-agent`, Capability `analyze.job`, Status `ACTIVE`, Version 1.0.0 |
| 2 | `module.lambda.aws_iam_role_policy.lambda_order_result_send[0]` | Rolle `ris-dev2-dev-agent`, nur `sqs:SendMessage` auf die Result-Queue |
| 3 | `module.lambda.aws_iam_role_policy.lambda_order_result_secret[0]` | Rolle `ris-dev2-dev-agent`, nur `secretsmanager:GetSecretValue` auf das Result-Secret |
| 4 | `…agent_transport[0].aws_cloudwatch_log_group.result_consumer` | `/aws/lambda/ris-dev2-mays-orders-agent-result-consumer`, 14 Tage |
| 5 | `…agent_transport[0].aws_iam_role.result_consumer` | Consumer-Ausführungsrolle |
| 6 | `…agent_transport[0].aws_iam_role_policy.result_consumer` | DDB Get/Update + `GetSecretValue` + Receive/Delete auf der Result-Queue |
| 7 | `…agent_transport[0].aws_lambda_event_source_mapping.results` | Batch 10, Fenster 0, `ReportBatchItemFailures`, enabled |
| 8 | `…agent_transport[0].aws_lambda_function.result_consumer` | Handler `result_consumer.handler`, 30 s, 256 MB, Hash `SN3V5S0H…` |
| 9 | `…agent_transport[0].aws_secretsmanager_secret.result_hmac` | `ris-dev2-mays-orders-agent-result-hmac`, **container only**, kein KMS-Key |
| 10 | `…agent_transport[0].aws_secretsmanager_secret_policy.result_hmac` | `GetSecretValue` nur für `ris-dev2-dev-agent` |
| 11 | `…agent_transport[0].aws_sqs_queue.results` | `…-agent-results`, Visibility 60 s, Retention 4 d, SSE, Redrive auf DLQ (`maxReceiveCount=3`) |
| 12 | `…agent_transport[0].aws_sqs_queue.results_dlq` | `…-agent-results-dlq`, Retention 14 d, SSE |
| 13 | `…agent_transport[0].aws_sqs_queue_policy.results` | `SendMessage` nur für `ris-dev2-dev-agent`, kein Wildcard |

### Changes (4)

| Lambda | Hash alt → neu | Änderung |
|---|---|---|
| RIS Agent `ris-dev2-dev-agent` | `94ex…` → `SmYD4MMW…` | Code + Env `ORDERS_BASE_URL`, `ORDER_RESULT_QUEUE_URL`, `ORDER_RESULT_SECRET_ARN` |
| RIS Reader `ris-dev2-dev-orders-reader` | `omwZ…` → `QX5bX1g…` | Code + Env `ORDERS_COGNITO_ISSUER/CLIENT_ID` |
| Orders Handler `ris-dev2-mays-orders-handler` | `GAHp…` → `SN3V5S0H…` | **nur `source_code_hash`** (gemeinsamer Bundle) |
| Orders Worker `ris-dev2-mays-orders-sqs-worker` | `GAHp…` → `SN3V5S0H…` | **nur `source_code_hash`** (gemeinsamer Bundle) |

Handler/Worker behalten ihre Umgebung und Konfiguration; der neue Bundle
enthält den Consumer-Fix, wird aber von allen drei Orders-Lambdas geteilt.

## 3. Zero-Traffic-Nachweis (vor Apply)

| Prüfung | Wert |
|---|---|
| Work-Queue sichtbar/in-flight | **0 / 0** |
| Result-Queue | **existiert nicht** |
| Orders-Queue | 0 / 0 / 0 |
| Orders-Tabelle | **0 Items** |
| Bestehende Work-Items | 3, alle ohne `orderId` (`NOT_ORDER`) |
| Cognito-Benutzer | **0** in allen Pools |
| Partner-Surface | `PARTNER_SURFACE_ENABLED=false` |
| Result-DLQ-Alarm | keiner vorhanden |

Damit ist Partner-Traffic heute sowohl durch die fehlende Identität als auch
durch die Konfiguration blockiert; die Result-Queue ist leer.

## 4. Aktivierungsreihenfolge (nur nach einem GO)

**Dieser Ablauf ist derzeit nicht freigegeben (siehe §7).** Er beschreibt die
Reihenfolge, falls ein späteres Gate Ingress und Identität bereitstellt.

1. **Pre-Apply:** Plan gegen freigegebenen Commit neu erzeugen, SHA prüfen,
   `13/4/0/0`, State/Lineage/Serial/Lock unverändert, Queue-Depths 0,
   Orders-Tabelle 0, Consumer/Queue/Secret weiterhin abwesend.
2. **Apply genau des gespeicherten Plans.** Erwartete Wirkung: ESM beginnt auf
   der leeren Result-Queue zu pollen; Worker-Env wird gesetzt; Secret-Container
   entsteht **ohne Version**.
3. **Unmittelbar danach (gleiches Betriebsfenster):** Secret-Wert setzen.
   - 32 Byte CSPRNG → **64 lowercase Hex**, kein JSON, kein Newline.
   - Datei mit restriktiven Rechten, `put-secret-value --secret-string file://…`,
     Datei sofort löschen.
   - Verifikation ohne Wert: genau eine Version, `AWSCURRENT`, kein
     `AWSPENDING`, `RotationEnabled=false`.
   - Shape: `len=64`, `^[0-9a-f]{64}$`, `parse_secret(raw)` liefert genau 1 Key.
4. **Blockierung bis hierhin:** Ohne Secret-Version kann der Producer nicht
   signieren/senden (Exception → Work-Item-Retry); der Consumer hat keinen Key
   und meldet `batchItemFailures` statt Erfolg. Es gibt keine stillen Erfolge.
   Partner-Traffic bleibt operativ gesperrt.
5. **Canary ohne Orders-Persistenz (optional):** synthetische `ORDER_RESULT`
   mit dem In-Memory-Key signieren; Consumer-Log muss
   `order_not_found` (Signatur gültig) zeigen, **nicht**
   `invalid service signature`.
6. **Erst nach erfolgreicher Secret-Verifikation** Partner-Traffic freigeben.

Ein zweiter Terraform-Apply ist für die Secret-Provisionierung **nicht**
vorgesehen (kein `secret_version`-Resource, kein Wert im State). Ein zweiter
Apply wäre nur für `partner_surface_enabled=true` oder einen Rollback nötig.

## 5. E2E-Erreichbarkeit — mit diesem Plan nicht gegeben

Der Audit hat einen entscheidenden Pfadfehler gefunden: Die dokumentierte Kette
`Partner-Execute → WorkItem → ATS → ORDER_RESULT → Orders-Persistenz` ist mit
dem aktuellen Plan **nicht auslösbar**.

| Glied | Befund | Evidenz |
|---|---|---|
| Partner-Execute | erzeugt ein WorkItem **ohne** `orderId`/`correlationId` | `lambda/handler.py:1955-1966`, `:3270-3308` |
| Forwarder | ohne `orderId` → `NOT_ORDER`, kein SQS-Send, kein Delivery-Marker | `agents/runtime/pipeline.py:847-849` |
| Einziger order-korrelierter Ingress | `ORDER_DISPATCH` → `dispatch_ingress` → `dispatch_to_work_item` setzt `orderId`/`correlationId` | `lambda/dispatch_ingress.py:96-128`, `agents/transport/order_transport.py:321-381` |
| Ist dieser Ingress im Plan? | **Nein.** `enable_agent_transport` (RIS-Dispatch-Queue) ist `false` und nicht Teil der 13 Adds | `terraform/variables.tf:599-603`, `terraform/main.tf:416-434` |
| Orders-seitiger Dispatch-Trigger | `prepare_dispatch`/`dispatch_envelope`/`mark_dispatch_sent` sind Library-only, keine Route, kein Trigger | `mays_orders/lambda/src/index.py:161-170`, `order_service.py:322-436` |
| RIS-Fassade `POST /orders` | validiert nur Retail, ignoriert `agentOrder`/`orderType` → legt still eine Retail-Order an | `lambda/orders_reader.py:382-407` |

Damit würde der Apply zwar Queue, Secret, Consumer und Worker-Env erzeugen, aber
**kein Live-Endpunkt kann ein Result erzeugen**. Die tatsächliche
Orders-Persistenz (`processing.result`) ist so nicht nachweisbar.

### Kanonische Kette (nur lokal belegt)

`Orders legt agent.execution-Order an` → `prepare_dispatch` bindet
`expectedWorkId` → `ORDER_DISPATCH` → RIS `dispatch_ingress` → WorkItem → ATS
`analyze.job` → Row `COMPLETED` + `orderResultDelivery=SENT` → signiertes
`ORDER_RESULT` → Consumer schreibt `processing{status:COMPLETED,result}`,
Order-`status` bleibt unverändert → Owner-Read 200 / fremd 404.
Evidenz: `tests/test_mo_dispatch_handoff.py:87-110`,
`tests/test_ats_result_link.py:172-218`, `order_service.py:442-521`.

### Erwartete Persistenzfelder (für einen späteren, erreichbaren E2E)

| Ort | Feld | Erwartung |
|---|---|---|
| Work-Row | `status` / `orderResultDelivery.status` | `COMPLETED` / **`SENT`** |
| Work-Row | `orderId`, `correlationId`, `apiProfileId` | vorhanden |
| Results-SQS | `serviceSignature` über Envelope-`messageId` | gültig |
| Orders-Item | `processing.status` | `COMPLETED` |
| Orders-Item | `processing.result.bodyVersion` | `"2.0"` |
| Orders-Item | `analysis.score`/`sum` | numerisch, kein String |
| Orders-Item | fachlicher `status` | unverändert (`PENDING`/`PROCESSING`) |
| Reader | Owner / fremd / fremder Issuer / ohne Env | 200 / 404 / 401 / 503 |

## 6. Blocker und Risiken

1. **Kein order-korrelierter Live-Ingress:** Partner-Execute setzt keine
   `orderId`; der `ORDER_DISPATCH`-Ingress ist nicht deployt und nicht Teil des
   Plans. Ohne ihn erzeugt der Apply eine ungenutzte Result-Kette.
2. **RIS-Fassade kann keine Agent-Order anlegen:** `POST /orders` ignoriert
   `agentOrder`/`orderType` und legt still eine Retail-Order an.
3. **Secret-Wert** existiert erst nach dem Apply; ohne sofortige Provisionierung
   läuft ein Work-Item in Retry/Work-DLQ.
4. **Keine Identität:** 0 Benutzer, M2M wird vom Reader-Audience-Check
   abgelehnt; ohne separate Entscheidung kein E2E.
5. **`ORDERS_ID_TOKEN`** ungesetzt für Work-Items ohne `auth.idToken`.
6. **Zwei-Pool-Modell:** Orders-API-Orders tragen den Orders-Issuer und sind
   für den RIS-Reader nicht lesbar.
7. **Visibility 60 s** vs. Consumer-Timeout 30 s (2×); keine DLQ-Alarmierung.
8. **Kein `ORDER_FAILED`** durch die RIS-Pipeline.
9. **Secret-Cache ohne TTL:** eine falsche, aber parsebare Version bleibt in
   warmen Consumer-Environments; Korrektur erfordert Recycling.
10. **Upstream-Divergenz:** Orders-`main` ist weit voraus und nutzt einen
    anderen Consumer-Vertrag; der Pin bleibt bewusst auf dem deployten
    `dad69ea`-Stand plus Fix.
11. **Override-Falle:** die Projekt-Config setzt
    `orders_agent_result_enabled=false`; der Apply muss den Wert explizit auf
    `true` setzen, sonst entstehen keine der 13 Ressourcen. Der 13/4-Plan ist
    damit nicht ohne dokumentierten Override aus dem Repo reproduzierbar.
12. **ATS-Ziel:** ohne `ATS_API_BASE_URL` fällt der Agent auf den externen
    Produktionshost `https://mays-jobsearch.vercel.app` zurück; das ist für
    einen kontrollierten E2E zu klären.
13. **Generiertes Modul:** vor jedem Plan neu bauen; der getrackte
    `variables.tf`-Stub bleibt unverändert.

## 7. Freigabeentscheidung

**NO-GO für den Transport-Apply.**

Der Plan ist technisch sauber und nicht destruktiv, aber der beworbene
Produktpfad ist mit ihm nicht auslösbar: Es gibt keinen live erreichbaren
order-korrelierten Ingress, die RIS-Fassade legt keine Agent-Orders an, und es
fehlt eine Identität. Ein Apply würde Queue, Secret, Consumer und Worker-Env
erzeugen, aber keine tatsächliche Orders-Persistenz ermöglichen; das Secret
müsste ohne Nutzen provisioniert und gepflegt werden.

**Bedingungen für ein späteres GO:**

1. Freigegebener order-korrelierter Ingress (RIS-Dispatch-Queue/-Ingress oder
   ein Orders-seitiger Dispatch-Trigger) als eigener, geprüfter Plan.
2. Entscheidung und Freigabe für eine Testidentität (Benutzer oder
   M2M-Audience) inklusive Entitlement/API-Profil/Partner-Application.
3. `orders_agent_result_enabled=true` reproduzierbar im freigegebenen
   Plan-Input (nicht nur als ad-hoc-Override).
4. Secret-Prozedur und sofortige Verifikation nach dem Apply.
5. Neuer Plan gegen den dann freigegebenen Commit mit `13/4/0/0` (oder dem
   erwarteten erweiterten Umfang) und erneuter Prüfung.

**NO-GO für Partner-Traffic/Produkt-Abnahme** bleibt bestehen, bis Ingress,
Identität und Secret verifiziert sind.

**HARD STOP vor jedem AWS Apply und vor jeder Secret-Mutation.**
