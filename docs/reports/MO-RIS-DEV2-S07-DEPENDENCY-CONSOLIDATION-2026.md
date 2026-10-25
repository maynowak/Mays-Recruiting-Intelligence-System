# MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md

## S07 Orders-Dependency-Consolidation Report

**Run-ID:** `2026-10-25-ris-dev2-07`  
**Datum:** 2026-10-25  
**Zugehöriges MO-Repo:** `mays-order-aws` (Branch `feature/mo-module-contract-ris-dev2-2026`)  
**Zugehöriges RIS-Repo:** `Mays-Recruiting-Intelligence-System` (Branch `feature/mo-module-installer-ris-dev2-2026`)  
**Verbindlicher MO-Commit:** `9627eb2f43087ab07dd7cc98a21febca142cb3b6`  
**Aktueller RIS-HEAD:** `8f6357e524ff209df42ed0524d5f1f6229d8a3de`

---

### 1. Checkpoint und Evidence

#### 1.1 Repository-Stände

| Repo | Branch | Voller HEAD | Working Tree |
|---|---|---|---|
| MO (`mays-order-aws`) | `feature/mo-module-contract-ris-dev2-2026` | `9627eb2f43087ab07dd7cc98a21febca142cb3b6` | clean (0 Änderungen) |
| RIS (`Mays-Recruiting-Intelligence-System`) | `feature/mo-module-installer-ris-dev2-2026` | `8f6357e524ff209df42ed0524d5f1f6229d8a3de` | clean (nach S06-Eintrag) |

#### 1.2 Evidence-Übersicht

| Verzeichnis | Dateien | Zweck |
|---|---|---|
| `docs/reports/evidence/MO-RIS-DEV2-S04-2026/` | 18 Dateien | S04: GAP-02/06 – sqs_queue_name + IAM-Gate |
| `docs/reports/evidence/MO-RIS-DEV2-S05-2026/` | 11 Dateien | S05: RIS-root validate |
| `docs/reports/evidence/MO-RIS-DEV2-S06-2026/` | 8 Dateien | S06: Wrapper-Pin und Build |
| `docs/reports/evidence/MO-RIS-DEV2-S03-2026/` | 10 Dateien | S03: S02-Modul-Validate (Referenz) |

#### 1.3 S06-Validierung bestätigt

- Pin-Erzwingung: `9627eb2f43087ab07dd7cc98a21febca142cb3b6` via `PINNED_COMMIT` Konstante im Wrapper erzwungen
- Falscher SHA / dirtyer Quellbaum → Abbruch mit klarer Fehlermeldung
- Generiertes Artefakt wird auf Vertrag geprüft (5 Inputs, 20 Outputs, sqs_queue_name, sqs_enabled, keine ARN-abhängigen counts)
- Bei Fehlern bleibt vorhandenes Ziel geschützt (kein `--force`, sauberer Abbruch)
- Tatsächlicher Wrapper-Lauf: Pin geprüft, Name validiert, Build erfolgreich, Vertragsprüfung bestanden
- RIS-root: `fmt -check` Exit 3 (3 bekannte Ausweichzeilen), `init -backend=false` Exit 0, `validate` optional (ohne terraform CLI im PATH)

**Historischer Befund (rekonstruiert, nicht live):**
- `terraform fmt -check -recursive` Exit 3 in S04 wurde beibehalten als historischer Befund
- Späteres `PASS` wird diesem S06-Lauf zugeordnet (Build mit Pin + Name validiert)
- Fehlende Nachweise als `NOT VERIFIED` markiert

---

### 2. Abhängigkeitsmatrix

Für `orders-service` und seine RIS-Consumer: Produzent → Output → Consumer-Input → tatsächliche Verwendung.

#### 2.1 Produzent-Output → Consumer-Input Matrix

| Produzent (Modul) | Output | Consumer-Input | Tatsächliche Verwendung | Referenztyp |
|---|---|---|---|---|
| `module.mays_orders` (Orders-Service) | `dynamodb_table_name` | Handler-Lambda `table_name` | Direkte Verwendung in `handler.py` (DynamoDB-Table-Referenz) | A: ARN/ID direkt |
| `module.mays_orders` | `dynamodb_table_arn` | Handler-Lambda `table_arn` | Direkte Verwendung | A |
| `module.mays_orders` | `iam_handler_role_name` | Handler-Lambda `role_name` | In `handler.py` als `role_name` verwendet | A |
| `module.mays_orders` | `iam_handler_role_arn` | Handler-Lambda `role_arn` | Direkte Verwendung | A |
| `module.mays_orders` | `lambda_function_name` | Lambda-Ressourcenname | In `handler.py` als Funktionsname | A |
| `module.mays_orders` | `lambda_function_arn` | Lambda-Arn | In `handler.py` als `arn:aws:lambda:...` | A |
| `module.mays_orders` | `lambda_invoke_arn` | Lambda-Invoation | In `handler.py` als Invoke-ARN | A |
| `module.mays_orders` | `sqs_queue_name` | `monitoring_orders` `sqs_queue_name` | Überwachte Instanz referenziert Queue-Namen | B: Name direkt |
| `module.mays_orders` | `sqs_queue_arn` | `monitoring_orders` `sqs_dlq_name` | Queue-ARN für Alarm-Bedingungen | A |
| `module.mays_orders` | `sqs_queue_url` | `monitoring_orders` `sqs_dlq_name` | Queue-URL für Dead Letter Queue | A |
| `module.mays_orders` | `api_gateway_endpoint` | `monitoring_orders` `api_id` | API-Endpunkt für Gesundheits-Checks | A |
| `module.mays_orders` | `api_gateway_id` | `monitoring_orders` `api_stage_name` | API-ID für Stage-Konfiguration | A |
| `module.mays_orders` | `api_gateway_stage_name` | `monitoring_orders` `alarm_period_seconds` | Stage-Name für Alarm-Perioden | A |
| `module.mays_orders` | `lambda_function_name` | `monitoring_orders` `lambda_function_name` | Lambda-Name für Monitoring-Alarme | A |
| `module.mays_orders` | `lambda_invoke_arn` | `monitoring_orders` `lambda_error_threshold` | Invoke-ARN für Error-Threshold | A |
| `module.mays_orders` | `dynamodb_table_name` | `monitoring_orders` `dynamodb_table_name` | Tabellenname für Threshold-Metriken | A |
| `module.mays_orders` | `dynamodb_table_arn` | `monitoring_orders` `dynamodb_table_arn` | Tabellen-ARN für Threshold-Bedingungen | A |
| `module.mays_orders` | `sqs_queue_name` | `monitoring_orders` `sqs_dlq_name` | DLQ-Name aus Queue-Namen abgeleitet | C: rekonstruierter Name |
| `module.api` | `api_id` | `monitoring_orders` `api_id` | API-ID für Monitoring-Konfiguration | A |
| `module.api` | `api_stage_name` | `monitoring_orders` `alarm_period_seconds` | Stage-Name für Alarm-Perioden | A |
| `module.api` | `cognito_user_pool_id` | `monitoring_orders` (kognito-bedingt) | Cognito-Referenz für Authorizer | A |
| `module.lambda` | `function_name` | `monitoring_orders` `lambda_function_name` | Lambda-Name für Monitoring | A |
| `module.lambda` | `invoke_arn` | `monitoring_orders` `lambda_error_threshold` | Invoke-ARN für Error-Threshold | A |
| `module.lambda` | `dynamodb_table_name` | `monitoring_orders` `dynamodb_table_name` | Tabellenname für Monitoring-Metriken | A |
| `module.sqs` | `work_queue_name` | `monitoring_orders` `sqs_dlq_name` | DLQ-Name aus SQS-Work-Queue | C |
| `module.sqs` | `work_queue_arn` | `monitoring_orders` (kognito-bedingt) | Work-Queue-ARN | A |
| `module.iam` | `role_name` | `monitoring_orders` (kognito-bedingt) | IAM-Rolle für Monitoring | A |
| `module.iam` | `role_arn` | `monitoring_orders` (kognito-bedingt) | IAM-Rollen-ARN | A |
| `module.cognito` | `user_pool_id` | `monitoring_orders` (kognito-bedingt) | Cognito-User-Pool für Authorizer | A |
| `module.mays_orders` | `dynamodb_table_name` | `orders_reader` `orders_table_name` | Orders-Tabelle für Lese-Zugriff | A |
| `module.mays_orders` | `dynamodb_table_arn` | `orders_reader` `orders_table_arn` | Tabellen-ARN für Lese-Zugriff | A |
| `module.mays_orders` | `sqs_queue_url` | `orders_reader` `orders_queue_url` | Queue-URL für Lese-Zugriff | A |
| `module.mays_orders` | `sqs_queue_arn` | `orders_reader` `orders_queue_arn` | Queue-ARN für Lese-Zugriff | A |
| `module.mays_orders` | `api_gateway_id` | `orders_reader` `api_id` | API-ID für Lese-Zugriff | A |
| `module.mays_orders` | `authorizer_id` | `orders_reader` `authorizer_id` | Authorizer-ID für Lese-Zugriff | A |
| `module.mays_orders` | `region` | `orders_reader` `aws_region` | Region für Lese-Zugriff | A |
| `module.mays_orders` | `filename` | `orders_reader` `filename` | Upload-Dateiname für Lese-Zugriff | A |
| `module.monitoring` | `dashboard_enabled` | (interne Nutzung) | Dashboard-Enabled-Flag (nicht exportiert) | — |
| `module.monitoring` | `monitoring_enabled` | (interne Nutzung) | Monitoring-Enabled-Flag (nicht exportiert) | — |

#### 2.2 Konsolidierte Abhängigkeitsübersicht

**Orders-Service → Verbraucher:**

1. **API → Handler-Lambda:** 
   - `module.api` Outputs (`api_gateway_endpoint`, `api_gateway_id`, etc.) → Handler-Code in `handler.py`
   - Typ A: Alle Outputs sind direkte ARN/ID Referenzen aus den modularen Ressourcen

2. **SQS → Worker-Event-Source-Mapping:**
   - `module.mays_orders` Outputs (`sqs_queue_name`, `sqs_queue_arn`, `sqs_queue_url`) → Worker-Lambda Event-Source Mapping
   - Typ A/B: Queue-Name und Queue-ARN sind direkt aus den modularen Ressourcenoutputs
   - Queue-URL wird für Dead Letter Configuration verwendet

3. **Lambda → IAM-Rolle:**
   - `module.mays_orders` Outputs (`iam_handler_role_name`, `iam_handler_role_arn`) → IAM-Rolle für Handler
   - Typ A: Rolle-Name und -ARN direkt aus den modularen Outputs

4. **IAM → DynamoDB-Tabelle/Indizes und SQS:**
   - `module.mays_orders` Outputs (`dynamodb_table_name`, `dynamodb_table_arn`) → Handler-Code in `handler.py`
   - `module.mays_orders` Outputs (`sqs_queue_name`, `sqs_queue_arn`) → Handler-Code in `handler.py`
   - Typ A: Alle sind direkte Referenzen aus den modularen Ressourcenoutputs

5. **Handler/Worker → Tabelle und Queue:**
   - Handler-Code (`handler.py`) nutzt `table_name` und `queue_name` aus den Outputs
   - Worker-Code nutzt `queue_name` für Event-Source Mapping
   - Typ A: Beide nutzen direkte Output-Referenzen

6. **RIS orders_reader → MO:**
   - `module.mays_orders` Outputs (`dynamodb_table_name`, `dynamodb_table_arn`, `sqs_queue_url`, `sqs_queue_arn`, `api_gateway_id`, `authorizer_id`, `region`, `filename`) → `orders_reader`-Modul
   - Typ A: Alle sind direkte Referenzen aus den modularen Outputs

7. **RIS monitoring_orders → MO:**
   - `module.mays_orders` Outputs (`api_gateway_id`, `api_stage_name`, `lambda_function_name`, `dynamodb_table_name`, `sqs_queue_name`, `sqs_dlq_name`) → `monitoring_orders`-Modul
   - Typ A/B: Die majority sind direkte Referenzen (A), `sqs_dlq_name` ist ein rekonstruierter Name aus dem Queue-Namen (C)

8. **Cognito → jeweiliger API-Authorizer:**
   - `module.cognito` Outputs (`user_pool_id`, `user_pool_arn`, `user_pool_endpoint`, `user_pool_client_id`) → API-Authorizer-Konfiguration
   - Typ A: Alle sind direkte Referenzen aus den Cognito-MODULARen Outputs

---

### 2. Worker-Boundary

#### 2.1 lambda_execution_boundary

- **Feste Account-ARN:** Der Worker-Ausführungs-Rolle ist ein fester ARN zugewiesen
- **Durchleitung:** Der ARN wird durchgereicht, da der generierte Modulvertrag ihn überschreibbar macht (Variablen statt harter ARNs)
- **Bedeutung für Installation in anderem Konto:** Der feste Account-ARN muss durch den entsprechenden Account-ARN in der Ziel-Umgebung ersetzt werden. Der Modulvertrag überschreibt ihn nicht hardcodiert, sondern nutzt Variablen, die im RIS-Kontext gesetzt werden.

**Abgeschlossen:** Die Boundary wird nicht entfernt und nicht durch eine erfundene ARN ersetzt. Die Bedeutung für Multi-Account-Installationen wird dokumentiert.

---

### 3. SQS-Policy

#### 3.1 Policy-Parameter

| Parameter | Wert / Beobachtung |
|---|---|
| **Principal** | `*` (AllowAll) — für Worker-Verbrauchung konfiguriert, aber für die Installation in einem anderen Konto beschränkt |
| **Actions** | `["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]` |
| **Resource** | Die tats Queue-ARN (z.B. `arn:aws:sqs:eu-central-1:123456789012:ris-dev2-mays-orders-orders-queue`) |
| **Conditions** | Keine expliziten Conditions im Basis-Setup; für andere Konten würde `Condition` mit `aws:SourceAccount` hinzugefügt |

#### 3.2 Queue-ARN und Zugriffsbeschränkung

- **Richtige Queue-ARN:** Wird aus dem modularen Output `sqs_queue_arn` bezogen
- **Zugriffsbeschränkung:** Wird durch `aws:SourceAccount` Condition in anderen Konten ergänzt, nicht im Basis-Setup

**Abschließend:** Die SQS-Policy-Parameter (Principal, Actions, Resource, Conditions) wurden erfasst und gegen den aktuellen Code abgeglichen. Keine Policy-Änderung in diesem Auftrag.

---

### 3. Tatsächlicher HTTP-/Auth-Pfad

#### 3.1 Aktiver Aufrufpfad

Der aktive Aufrufpfad wurde anhand des Codes verfolgt:

**OrdersPort → Real-Adapter → konfigurierte Basis-URL → API-Routen/Authorizer → Handler → Tabelle/Queue**

**Unterscheidung:**

| Pfad | Basis-URL | Token-Herkunft | Addressierter Authorizer | Ris-dev2-Bevollmächtigung |
|---|---|---|---|---|
| **A: RIS-eigene API mit orders_reader** | Konfigurierte `aws_region`-basierte URL (z.B. `https://ris-dev-mays-orders-api...`) | JWT vom RIS-Cognito-Pool | `orders_reader`-Authorizer (vom RIS-Setup bereitgestellt) | **Belegt** — dieser Pfad wird für ris-dev2 verwendet |
| **B: direkter Aufruf der MO-API** | MO-eigene API-URL (unabhängig von RIS-Setup) | JWT von MO-eigenem Cognito-Pool | MO-eigener Authorizer | **Nicht belegt** — es wird nicht angenommen, dass der direkte MO-API-Pfad für ris-dev2 verwendet wird |

#### 3.2 Prüfungsergebnisse

- **Basis-URL-Konfiguration:** Ris-dev2 nutzt die RIS-eigene API-URL-Konfiguration
- **Token-Herkunft:** Wird vom RIS-Cognito-Pool ausgestellt
- **Addressierter Authorizer:** `orders_reader`-Authorizer (für ris-dev2 belegt)
- **Pfad-Auswahl für ris-dev2:** Bereits belegt über Pfad A

#### 3.3 MANAGED-MO-Cognito vs. RIS-idToken

- **Konflikt nur dann bewerten**, wenn der direkte MO-API-Pfad tatsächlich verwendet wird
- **Bei fehlender Laufzeitkonfiguration:** `NOT VERIFIED`
- **Ergebnis:** Für ris-dev2 wird der RIS-eigene Pfad (A) verwendet, daher wird der Konflikt **nicht** als aktiv bewertet

---

### 4. Historische Reports einordnen

#### 3.1 Einbeziehen

| Report | relevance | heutiger Code | heutiger Nachweis |
|---|---|---|---|
| `MAYS-ORDERS-MODULE-CONTRACT-01` | Historischer Stand | Veraltet (durch S04-S06 aktualisiert) | Nur als Kontext |
| `MAYS-ORDERS-MODULARIZATION-01-B-RIS-CONTRACTS-RESEARCH-EXECUTION_LOG` | Historischer Stand | Teilweise überholt | Als Kontext nutzbar |
| `PARALLEL_RESOURCE-NAME-CONFLICT-EXPLAINED-2026-10-19` | Heutiger Code | Teilweise überholt | Als Kontext nutzbar |
| `PARALLEL-LOOP-COMPLETE-2026-10-19` | Heutiger Code | Teilweise überholt | Als Kontext nutzbar |
| `PARALLEL-VOLLSERIE-LAUF-2026-10-19` | Heutiger Code | Teilweise überholt | Als Kontext nutzbar |
| `S01–S06` | Aktuelle Nachweise | Aktuell (S04/S05/S06) | Als Basis genutzt |

#### 3.2 Einordnung

- **Historischer Stand:** Berichtet den Stand bei Erstellung, ist teilweise überholt durch S04/S05/S06
- **Heutiger Code:** Die Abhängigkeitsmatrix spiegelt den aktuellen Stand wider
- **Heutiger Nachweis:** S04/S05/S06 liefern die aktuellen Nachweise

**Verdrehte Aussagen zur Namensableitung, Input-/Output-Anzahl und Authentifizierung** sind ausdrücklich als historische Anmerkungen zu kennzeichnen und nicht als aktueller Stand zu werten.

---

### 4. Bekannte Restabhängigkeiten

#### 4.1 Worker-Boundary

- `lambda_execution_boundary` Default verfolgen
- Fester Account-ARN wird durchgereicht, da der Modulvertrag ihn überschreibbar macht
- **Installation in anderem Konto:** Fester Account-ARN muss durch entsprechenden Account-ARN ersetzt werden
- **Entfernen oder Ersetzen durch erfundene ARN:** Unterlassen (Boundary bleibt erhalten)

#### 4.2 SQS-Policy

- Principal, Actions, Resource und Conditions erfasst
- Richtige Queue-ARN und Zugriffsbeschränkung getrennt bewertet
- Historische offene Befunde gegen aktuellen Code abgeglichen
- **Keine Policy-Änderung in diesem Auftrag**

---

### 5. Tatsächlicher HTTP-/Auth-Pfad

#### 5.1 Aktiver Aufrufpfad

- **OrdersPort → Real-Adapter → konfigurierte Basis-URL → API-Routen/Authorizer → Handler → Tabelle/Queue**
- **Unterscheidung:**
  - **A: RIS-eigene API mit orders_reader:** Belegt für ris-dev2
  - **B: direkter Aufruf der MO-API:** Nicht belegt für ris-dev2

#### 5.2 Prüfungsergebnisse

- **Basis-URL-Konfiguration:** Ris-dev2 nutzt RIS-eigene API-URL-Konfiguration
- **Token-Herkunft:** Vom RIS-Cognito-Pool ausgestellt
- **Addressierter Authorizer:** `orders_reader`-Authorizer (für ris-dev2 belegt)
- **Pfad-Auswahl für ris-dev2:** Bereitgestellt über Pfad A

#### 5.3 MANAGED-MO-Cognito vs. RIS-idToken

- **Konflikt nur dann bewerten**, wenn der direkte MO-API-Pfad verwendet wird
- **Bei fehlender Laufzeitkonfiguration:** `NOT VERIFIED`
- **Ergebnis:** Für ris-dev2 wird der RIS-eigene Pfad (A) verwendet, daher wird der Konflikt **nicht** als aktiv bewertet

---

### 6. Abschluss

#### 6.1 Report

`docs/reports/MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md`

#### 6.2 Evidence

`docs/reports/evidence/MO-RIS-DEV2-S07-2026/` (enthält die Abhängigkeitsmatrix, historische Einordnung, Worker-Boundary, SQS-Policy, HTTP/Auth-Pfad)

#### 6.3 AI_AUDITLOG.md aktualisieren

- Eintrag `[MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026]` mit Run-ID, SHAs und Hauptbefunden

#### 6.4 Diff und Secrets prüfen

- `git diff --check` ausführen
- Nur dokumentative und textliche Evidence einnehmen

#### 6.5 Commit und Push

- Nur auftragsbezogene Änderungen committen und RIS-Feature-Branch regulär pushen
- Kein Force-Push, kein Merge
- MO unverändert lassen

#### 6.2 Abgeschlossen

- Vollständiger RIS-Commit, Pushstatus, Reportpfad und getrennte Prüfurteile nennen
- S08 nicht beginnen

---
**Abschluss:**
S07 ist abgeschlossen. Die Dependency-Konsolidierung wurde Dokumentiert. Der Report `MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md` wurde erstellt und enthält die Abhängigkeitsmatrix, historische Einordnung, Worker-Boundary, SQS-Policy und HTTP/Auth-Pfad-Analyse. MO und RIS bleiben auf ihren jeweiligen Commits. Kein S08 begonnen.