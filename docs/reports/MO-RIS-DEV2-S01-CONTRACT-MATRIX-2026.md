# MO-RIS-DEV2-S01-CONTRACT-MATRIX-2026 — Statische Vertragsmatrix

**Datum (tatsächliche Ausführung):** 2026-10-25
**Run-ID:** `2026-10-25-ris-dev2-02`
**Status:** COMPLETE (statische Analyse) — keine Implementierung, kein Builder-Lauf, kein Terraform, kein AWS
**Eingang:** `docs/reports/MO-RIS-DEV2-S00-BASELINE-2026.md` (Commit `b194b8096a69cfe2ffc5fe8cbdb83e3d3def634a`)

---

## 1. Ausgangslage

### 1.1 Git-Stand

| Repo | Branch | Vollständiger SHA | Commit-Betreff | Status |
|---|---|---|---|---|
| RIS | `feature/mo-module-installer-ris-dev2-2026` | `b194b8096a69cfe2ffc5fe8cbdb83e3d3def634a` | `MO-RIS-DEV2-S00-BASELINE-2026: Baseline-Ausgangsstand fuer ris-dev2 dokumentiert` | clean (0) |
| MO | `main` (nur lesend) | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` | `docs: module builder invocation discoverability MAYS-ORDERS-MODULE-DOC-INTEGRATION-01` | clean (0) |

### 1.2 Abweichungen gegenüber S00

| Punkt | S00 | S01 | Bewertung |
|---|---|---|---|
| RIS-HEAD | `e8a2ed8a5bcb5c795200defb18e1d1e10c1277df` (Basis) | `b194b8096a69cfe2ffc5fe8cbdb83e3d3def634a` | **erwartete** Abweichung: der S00-Doku-Commit liegt auf dem Branch |
| MO-HEAD | `2d5cf2de…` | `2d5cf2de…` | unverändert |
| Branch | neu angelegt, nicht gepusht | gepusht, Tracking aktiv | erwartete Abweichung |

Keine inhaltlichen Abweichungen. Die in S00 dokumentierten Blocker (Terraform, pytest/moto/boto3,
Python 3.14, Vorgabedokumente, Konto/Profil, Backendwerte) bleiben unverändert bestehen und
**blockieren diese statische Analyse nicht** (§9).

---

## 2. Input-Vertrag

### 2.1 Herleitung

Der Generator für das Preset `orders-service` (`module_builder/builder.py:806-1027`) erzeugt
`variables.tf` **nicht** durch Kopie der Root-Datei, sondern durch:

1. Blockfilter auf `ORDERS_SERVICE_VARIABLES` (`module_builder/spec.py:98-103`):
   `project_name`, `tags`, `monitoring_enabled`, `log_retention_days`
2. Substitution des `project_name`-Defaults auf den Consumer-Namen
   (`substitute_project_name()`, `builder.py:740-756`)
3. Anhängen der generierten Vertragsvariable `external_cognito`
   (`EXTERNAL_COGNITO_VARIABLE`, `builder.py:649-673`)

Damit hat das generierte Modul **genau 5 Variablen**. Die Root-Variablen `aws_region`,
`environment`, `filename`, `dashboard_enabled`, `alarm_*`, `seed_*`, `enable_cognito_backup*`
sind **kein** Bestandteil des Vertrags (Region kommt vom Provider des Consumers).

### 2.2 Input-Matrix

| Name | Typ | Default/Pflicht | Validierung | Herkunft | RIS-Übergabe | Urteil |
|---|---|---|---|---|---|---|
| `project_name` | `string` | Default `mays-orders` in der Quelle, **vom Builder auf den Consumer-Namen ersetzt** (`substitute_project_name`, `builder.py:740-756`) | `length >= 3` und `^[a-z0-9][a-z0-9-]*$` (`terraform/variables.tf:1-14`) | Hersteller | `terraform/main.tf:174` → `"${var.project_name}-mays-orders"` = `ris-dev2-mays-orders` (19 Zeichen, valide) | **MATCH** |
| `tags` | `map(string)` | `{}` | keine | Hersteller | `terraform/main.tf:175` → `var.tags` | **MATCH** |
| `monitoring_enabled` | `bool` | `true` | keine | Hersteller | `terraform/main.tf:176` → `var.monitoring_enabled` | **MATCH** |
| `log_retention_days` | `number` | `7` | keine | Hersteller | `terraform/main.tf:177` → `var.lambda_config.log_retention_days` | **MATCH** |
| `external_cognito` | `object({user_pool_endpoint = string, user_pool_client_id = string})` | `null` = MANAGED | Regex `^cognito-idp\.[a-z0-9-]+\.amazonaws\.com/[a-zA-Z0-9_-]+$` **und** `client_id != ""`; fail-closed (`builder.py:657-672`) | **vom Builder generiert** (kein Root-Bestand) | auskommentiert (`terraform/main.tf:178`) → effektiv `null` | **MATCH** (MANAGED) |

**Keine neue Variable wird als bestehender Herstellervertrag ausgegeben:**
`external_cognito` ist nachweislich **generiert** (String-Konstante im Builder, nicht in
`terraform/variables.tf` des Herstellers). `sqs_enabled` (§4) ist **RIS-seitig** eingeführt.

### 2.3 Integrationsfall MANAGED (erster Fall, verbindlich)

- `external_cognito = null`
- Das Modul erzeugt eigenen Cognito User Pool, App Client und Gruppe `staff`
  (`terraform/modules/cognito/main.tf:9,33,48`)
- Die Orders-API autorisiert gegen **diesen** Pool (`terraform/modules/api/main.tf:30,89`)
- RIS setzt nichts → Default greift. **Kein Handlungsbedarf in S01.**

### 2.4 Integrationsfall EXTERNAL (separat, keine Migration)

- Consumer übergibt `{user_pool_endpoint, user_pool_client_id}` eines bestehenden Pools
- `count = var.external_cognito == null ? 1 : 0` auf `module "cognito"` (`builder.py:900-909`)
- Outputs werden auswertungssicher auf `one(module.cognito[*].…)` bzw. `local.cognito_*` umgestellt
  (`EXTERNAL_COGNITO_OUTPUT_REPLACEMENTS`, `builder.py:678-689`)
- **In S01 wird keine Migration vorbereitet oder ausgeführt.** Relevanz entsteht erst durch
  Befund CONFLICT-02 (§7).

---

## 3. Output-Vertrag

### 3.1 Hersteller-Outputs des Presets

Der Generator filtert `terraform/outputs.tf` auf Outputs, deren Modulreferenzen vollständig in
der Kernmenge `{api, cognito, dynamodb, iam, lambda, sqs, sqs_worker}` liegen
(`builder.py:949-957`). Ergebnis: **19 offizielle Outputs**.

| # | Offizieller Output | Hersteller-Ausdruck |
|---|---|---|
| 1 | `dynamodb_table_name` | `module.dynamodb.table_name` |
| 2 | `dynamodb_table_arn` | `module.dynamodb.table_arn` |
| 3 | `iam_handler_role_name` | `module.iam.role_name` |
| 4 | `iam_handler_role_arn` | `module.iam.role_arn` |
| 5 | `lambda_function_name` | `module.lambda.function_name` |
| 6 | `lambda_function_arn` | `module.lambda.function_arn` |
| 7 | `lambda_invoke_arn` | `module.lambda.invoke_arn` |
| 8 | `cognito_user_pool_id` | `module.cognito.user_pool_id` |
| 9 | `cognito_user_pool_arn` | `module.cognito.user_pool_arn` |
| 10 | `cognito_user_pool_endpoint` | `module.cognito.user_pool_endpoint` |
| 11 | `cognito_user_pool_client_id` | `module.cognito.user_pool_client_id` |
| 12 | `cognito_user_pool_group_name` | `module.cognito.user_pool_group_staff_name` |
| 13 | `api_gateway_endpoint` | `module.api.api_endpoint` |
| 14 | `api_gateway_id` | `module.api.api_id` |
| 15 | `api_gateway_stage_name` | `module.api.api_stage_name` |
| 16 | `api_gateway_authorizer_id` | `module.api.authorizer_id` |
| 17 | `sqs_queue_url` | `module.sqs.queue_url` |
| 18 | `sqs_queue_arn` | `module.sqs.queue_arn` |
| 19 | `sqs_worker_lambda_arn` | `module.sqs_worker.function_arn` |

Nicht enthalten (bewusst, da Module nicht im Preset): `cloudtrail_*`, `monitoring_*`,
`cognito_backup_*`.

### 3.2 Consumer-Matrix

Grundlage: vollständige Suche nach `module.mays_orders.<feld>` im gesamten RIS-Checkout.
Einzige Fundstellen außerhalb der Dokumentation sind `terraform/main.tf:164-167` (Modul
`orders_reader`) und `terraform/main.tf:229-233` (Modul `monitoring_orders`).

| RIS-Consumer | Benötigtes Feld | Hersteller-Ausdruck | Vorhanden? | Wrapper-Anpassung | Auswirkung bei Fehlen | Empfohlene Zuständigkeit |
|---|---|---|---|---|---|---|
| `module.orders_reader` (`main.tf:164`) | `dynamodb_table_name` | `module.dynamodb.table_name` | ja (offiziell) | keine | Bindungsfehler im Reader (`ORDERS_TABLE` leer → Runtime-Abbruch) | MO (Vertrag halten) |
| `module.orders_reader` (`:165`) | `dynamodb_table_arn` | `module.dynamodb.table_arn` | ja (offiziell) | keine | IAM-Policy des Readers ohne Tabellen-Scope → fail-closed | MO |
| `module.orders_reader` (`:166`) | `sqs_queue_url` | `module.sqs.queue_url` | ja (offiziell) | keine | Reader kann `SendMessage` nicht adressieren | MO |
| `module.orders_reader` (`:167`) | `sqs_queue_arn` | `module.sqs.queue_arn` | ja (offiziell) | keine | Reader-IAM ohne Queue-Scope | MO |
| `module.monitoring_orders` (`:229`) | `api_gateway_id` | `module.api.api_id` | ja (offiziell) | keine | Monitoring-Alarme ohne Dimensionswert | MO |
| `module.monitoring_orders` (`:230`) | `api_gateway_stage_name` | `module.api.api_stage_name` | ja (offiziell) | keine | falsche/leere Stage-Dimension | MO |
| `module.monitoring_orders` (`:231`) | `lambda_function_name` | `module.lambda.function_name` | ja (offiziell) | keine | keine Lambda-Metriken | MO |
| `module.monitoring_orders` (`:232`) | `dynamodb_table_name` | `module.dynamodb.table_name` | ja (offiziell) | keine | keine DDB-Metriken | MO |
| `module.monitoring_orders` (`:233`) | `sqs_queue_name` | **kein offizieller Output** | **nein** | **vom RIS-Wrapper ergänzt** (`build_module()`, `build_mays_orders_module.py:75-96`) | `terraform validate` schlägt fehl (undefiniertes Attribut) → Monitoring-Kette blockiert | **MO** (offizieller Output) + RIS (Übergangspatch) |
| — (kein Consumer) | `sqs_worker_lambda_arn` | `module.sqs_worker.function_arn` | ja (offiziell) | keine | — | MO |
| — (kein Consumer) | `api_gateway_endpoint` | `module.api.api_endpoint` | ja (offiziell) | keine | **ungenutzt**: keine Verdrahtung von `ORDERS_BASE_URL` (siehe GAP-04) | **RIS** |
| — (kein Consumer) | `cognito_user_pool_*`, `iam_handler_role_*`, `lambda_function_arn`, `lambda_invoke_arn`, `api_gateway_authorizer_id` | div. | ja (offiziell) | keine | derzeit nicht benötigt | — |

### 3.3 Klassifikation der Outputs

| Klasse | Felder |
|---|---|
| **Offizieller Hersteller-Output** | 19 Felder aus §3.1 |
| **Vom RIS-Wrapper hinzugefügt** | ausschließlich `sqs_queue_name` (`output "sqs_queue_name" { value = module.sqs.queue_name }`) |
| **Aus vorhandenen Outputs ableitbar** | Queue-Name aus `sqs_queue_url`/`sqs_queue_arn` (letztes Pfadsegment) — **derzeit nicht genutzt**; Worker-Lambda-Name aus `sqs_worker_lambda_arn` (ARN-Suffix) |
| **Fehlend/widersprüchlich** | `sqs_queue_name` als *offizieller* Vertrag; kein Output für den Worker-**Namen**; kein Output für API-Endpoint-Bedarf des RIS-Agenten (vorhanden, aber unverdrahtet) |

**`sqs_queue_name` wird hier ausdrücklich nicht als offizieller Hersteller-Output gezählt**:
Der Builder-Quelltext enthält keinen Treffer (`module_builder/*.py`), der Output entsteht erst
durch den RIS-Patch. Damit ist der Patch eine **notwendige, aber herstellerseitig ungedeckte**
Vertragslücke — und der Patch ist rebuild-abhängig (kein Upstream-Schutz, anders als beim
IAM-Gate mit Fail-closed-Prüfung).

---

## 4. IAM-SQS-Gate

### 4.1 Herkunft und Übergabe von `sqs_queue_arn`

```
module "sqs"  →  queue_arn
                     │
                     ▼
module "iam" { sqs_queue_arn = module.sqs.queue_arn }   (terraform/main.tf, IAM-Block)
                     │
                     ▼
data "aws_iam_policy_document" "sqs" { resources = [var.sqs_queue_arn] }
```

- `terraform/variables.tf` (IAM-Modul): `sqs_queue_arn`, Typ `string`, **Default `""`**
- Root-Übergabe: IAM-Block in `terraform/main.tf` (`sqs_queue_arn = module.sqs.queue_arn`)
- Im generierten Modul identisch, da der Builder Modulblöcke bis auf benannte Transforms
  verbatim übernimmt (`builder.py:891-919`)

### 4.2 Beide ARN-abhängigen `count`-Ausdrücke (Herstellerstand)

| Datei:Zeile | Ausdruck | Ressource |
|---|---|---|
| `terraform/modules/iam/main.tf:83` | `count = var.sqs_queue_arn != "" ? 1 : 0` | `data "aws_iam_policy_document" "sqs"` |
| `terraform/modules/iam/main.tf:96` | `count  = var.sqs_queue_arn != "" ? 1 : 0` | `resource "aws_iam_role_policy" "sqs"` |

Beide hängen am **Wert** der Queue-ARN. Wird die Queue im selben Apply erzeugt, ist der ARN-Wert
zum Planzeitpunkt unbekannt; `count` muss jedoch plan-bekannt sein. Der Herstellerkommentar
(`:77-81`) beschreibt die Semantik: ohne ARN **keine** SQS-Berechtigung (`count = 0`), Handler
läuft dann synchron.

*Hinweis: Eine konkrete Terraform-Fehlermeldung wird hier nicht behauptet — sie wurde in S01
nicht gemessen. Die Aussage ist rein statisch aus dem Ausdruck ableitbar.*

### 4.3 Bestehender Kompatibilitätspatch (RIS)

`patch_iam_sqs_gate()` (`installer/build_mays_orders_module.py:114-168`) ersetzt **beide**
Schreibweisen (`count = …` und `count  = …`) durch `count = var.sqs_enabled ? 1 : 0`, ergänzt
`variable "sqs_enabled"` (bool, Default `false`) im IAM-Modul und setzt im Modul-Root
`sqs_enabled = true` neben `sqs_queue_arn`.

**Fail-closed:** Bleibt nach dem Patch eine Zeile übrig, die `count` **und** `sqs_queue_arn`
enthält, wirft der Wrapper `RuntimeError` (Zeilen 132-140). Damit ist ein Upstream-Rückfall
laut, nicht still.

### 4.4 Gate-Bedingung vs. tatsächlicher Resource-Scope

| Aspekt | Ist-Zustand nach Patch |
|---|---|
| Gate | `var.sqs_enabled` (bool) — **konfigurationsbekannt**, plan-stabil |
| Resource-Scope | `resources = [var.sqs_queue_arn]` — ARN bleibt der Policy-Scope (darf unbekannt sein) |
| Least Privilege | unverändert: genau eine Queue, nur `sqs:SendMessage` |
| Default | `sqs_enabled = false` im Modul (sicher), Root setzt `true` für die RIS-Integration |
| Doppel-Gate | `data` und `resource` werden konsistent gepatcht (beide Vorkommen) |

**Konfigurationsbekannt vs. erst beim Apply bekannt:**

| Wert | Zeitpunkt |
|---|---|
| `sqs_enabled` | Planzeitpunkt (Variable) |
| `sqs_queue_arn` Inhalt | erst nach Apply des `sqs`-Moduls (unbekannt im Plan) |
| `aws:SourceArn`-artige Bedingungen | nicht vorhanden (kein Condition im Statement) |

### 4.5 Semantik, die ein Hersteller-Fix erhalten muss

1. Gate muss **plan-bekannt** sein (bool oder gleichwertig), nicht ARN-abgeleitet.
2. Resource-Scope bleibt **exakt** `[var.sqs_queue_arn]` (Least Privilege, keine Wildcards).
3. Deaktiviert ⇒ **keine** SQS-Policy (`count = 0`), Handler synchron.
4. Beide Objekte (`data` + `resource`) werden **gemeinsam** gegatet.
5. Default muss sicher sein (`false`), Aktivierung erfolgt durch den Consumer.

### 4.6 Später erforderliche Tests (nicht ausgeführt)

| Art | Test | Erwartung |
|---|---|---|
| positiv | `sqs_enabled = true`, Queue im selben Apply | Plan ohne `count`-Fehler; Policy existiert; `resources` == Queue-ARN |
| positiv | `sqs_enabled = true`, Queue bereits vorhanden | identisches Ergebnis, keine Drift |
| negativ | `sqs_enabled = false` | keine `aws_iam_role_policy.sqs`; Handler erhält keine SQS-Rechte |
| negativ (Regression) | Upstream bringt ARN-`count` zurück | Wrapper bricht mit `RuntimeError` ab (Fail-closed) |
| Randfall | `sqs_enabled = true`, `sqs_queue_arn = ""` | derzeit **nicht** abgefangen → potenziell Policy mit leerem `resources` (siehe GAP-06) |

---

## 5. Namens- und Identitätsvertrag

### 5.1 Drei Ebenen der Namensbildung (getrennt geprüft)

| Ebene | Mechanik | Wert für dev2 | Quelle |
|---|---|---|---|
| **Wrapper-CLI** | `--project-name <p>`, Default `mays-ris`; wird **unverändert** an `module_builder --project-name` durchgereicht | `ris-dev2` **oder** `ris-dev2-mays-orders` — je nach Aufruf (keine Validierung, siehe GAP-05) | `build_mays_orders_module.py:180-186`, `build_module():55-73` |
| **Builder-Default** | `variable "project_name"` Default `mays-orders`, wird auf den übergebenen Namen ersetzt | ersetzt | `builder.py:740-756` |
| **Effektive RIS-Modulübergabe** | `project_name = "${var.project_name}-mays-orders"` | `ris-dev2-mays-orders` | `terraform/main.tf:174` |

**Kritische Konsequenz:** Wird der Wrapper mit `ris-dev2` (dem RIS-Projektnamen) aufgerufen,
entstehen Ressourcen unter `ris-dev2-*`, nicht unter `ris-dev2-mays-orders-*` — während RIS den
Consumer mit `ris-dev2-mays-orders` verdrahtet. Der Name ist ein **doppelter** Parameter
(Wrapper-CLI und RIS-Modulübergabe) ohne gemeinsame Quelle. Das ist GAP-01.

### 5.2 Namenslängen gegen `docs/installer/AWS-NAME-LIMITS.md`

Bezugsname: `ris-dev2-mays-orders` = **19 Zeichen**. Ressourcen des Presets
`orders-service` (§3.1/`ORDERS_SERVICE_MODULES`):

| Ressource | Muster | Länge bei 19 | AWS-Limit | Max. project_name |
|---|---|---|---|---|
| DynamoDB-Tabelle | `<project>` | 19 | 255 | 255 |
| SQS-Queue | `<project>-orders-queue` | 32 | 80 | 67 |
| Lambda Handler | `<project>-handler` | 27 | 64 | 56 |
| Lambda SQS-Worker | `<project>-sqs-worker` | 30 | 64 | 53 |
| IAM-Rolle Handler | `<project>-handler-role` | 32 | 64 | 51 |
| IAM-Rolle SQS-Worker | `<project>-sqs-worker-role` | 34 | 64 | **49** |
| IAM-Policy Handler | `<project>-handler-policy` | 34 | 128 | 113 |
| IAM-Policy SQS-Worker | `<project>-sqs-worker-policy` | 36 | 128 | 111 |
| Cognito User Pool | `<project>-users` | 25 | 128 | 122 |
| Cognito Client | `<project>-client` | 27 | 128 | 120 |
| API Gateway API | `<project>-api` | 23 | 128 | 124 |
| JWT-Authorizer | `<project>-jwt-authorizer` | 35 | 128 | 112 |

**Ergebnis:** alle Namen liegen deutlich unter den Limits.

### 5.3 Grenzen ausgeschlossener Module **nicht** übertragen

`docs/installer/AWS-NAME-LIMITS.md` erklärt den **CloudTrail-S3-Bucket** (max. 39) und das
**optionale Cognito-Backup** (max. 23) zu den bindenden Grenzen. Beide Module sind **nicht**
Teil des Presets `orders-service` (`ORDERS_SERVICE_MODULES` = api, cognito, dynamodb, iam,
lambda, sqs, sqs_worker).

| Grenze | Gilt für dieses Preset? | Begründung |
|---|---|---|
| 39 (CloudTrail-Bucket) | **nein** | `terraform/modules/cloudtrail` nicht im Preset |
| 23 (Cognito-Backup-Bucket) | **nein** | `cognito_backup*` nicht im Preset |
| **49 (IAM-Rolle SQS-Worker)** | **ja** — tatsächlich bindend hier | `sqs-worker/iam.tf:51` |

Der RIS-Installer prüft `ORDERS_PROJECT_NAME_MAX_LENGTH = 39` (`installer/ris.py:268-270`,
`validate_orders_aws_name_limits`), also **strenger als nötig** für dieses Preset. Für
`ris-dev2-mays-orders` (19) ist die Prüfung unkritisch. Der Wrapper ruft diese Prüfung jedoch
**gar nicht** auf (GAP-05).

### 5.4 Identitätsvertrag

| Zweck | Feld | Vom Hersteller? | Hinweis |
|---|---|---|---|
| Lambda-Identität/IAM | `lambda_function_arn`, `sqs_worker_lambda_arn`, `iam_handler_role_arn` | ja | ARN als Identität; Rollenname zusätzlich als `iam_handler_role_name` |
| SQS-IAM | `sqs_queue_arn` | ja | Policy-Resource (siehe §4) |
| SQS-Aufruf | `sqs_queue_url` | ja | Env `ORDERS_SQS_QUEUE_URL` im Reader |
| DynamoDB-IAM | `dynamodb_table_arn` | ja | inkl. `…/index/*` im Reader (`orders_reader/main.tf:49-50`) |
| DynamoDB-Aufruf | `dynamodb_table_name` | ja | Env `ORDERS_TABLE`; Tabellenname == `project_name` verbatim |
| API-Integration | `api_gateway_id`, `api_gateway_stage_name`, `api_gateway_endpoint` | ja | Endpoint wird von RIS **nicht** verdrahtet (GAP-04) |

**Namensbasierte ARN-Rekonstruktionen** (als solche gekennzeichnet, nicht als Messung):

- `installer/ris.py:542-549` `derive_orders_queue_arn()` → `arn:aws:sqs:{region}:{account}:{project}-orders-queue`
- `installer/ris.py:703-712` `derive_orders_table_arn()` → `arn:aws:dynamodb:{region}:{account}:table/{table_name}`
- Diese Funktionen gehören zum **Composite-Handoff** (`orders_handoff_vars`, `ris.py:777`, Aufruf `:2229`).
  Im Module-Builder-Pfad wird **keine** ARN rekonstruiert — dort kommen ARN/URL aus Modul-Outputs.
  Die Rekonstruktion bleibt als Altpfad vorhanden und ist damit eine doppelte Wahrheitsquelle.

---

## 6. RIS-Laufzeitgrenze

### 6.1 Pfad A — Agent → OrdersPort → HTTP (der Integrationspfad des Moduls)

| Station | Datei / Funktion | Konkretes Detail |
|---|---|---|
| Einstieg | `agents/orders/function.py:72` `process_orders_work()` | Capabilities `orders.create`, `orders.status`, `orders.cancel` |
| Adapter-Auswahl | `agents/orders/function.py:58-69` `_adapter_from_work_item()` | `base_url = os.environ.get("ORDERS_BASE_URL", DEFAULT_BASE_URL)` |
| Port | `agents/orders/adapter.py:45` `class OrdersPort(ABC)` | `submit_order`, `get_order_status`, `can_handle`, `port_id` |
| Real-Adapter | `agents/orders/real.py:75` `class RealMaysOrdersAdapter` | HTTP via `urllib.request` |
| Ziel-URL (Default) | `agents/orders/real.py:34` | `DEFAULT_BASE_URL = "https://aboqolpm0f.execute-api.eu-central-1.amazonaws.com"` (hartkodierte API-ID eines **Alt-Stacks**) |
| Authentifizierung | `agents/orders/function.py:52-56`, `real.py:99-103` | `Authorization: Bearer <idToken>` aus `work_item.auth.idToken`, sonst `ORDERS_ID_TOKEN` |
| HTTP-Routen | `real.py:169,187,194` | `POST /orders`, `PATCH /orders/{orderId}/status`, `GET /orders/{orderId}` |
| Fehlerklassen | `real.py:43-45,145-151` | 4xx kontrolliert; 429/5xx/Timeouts retrybar; **POST nie blind wiederholt** (`safe_to_retry: False`) |

**Nicht konfiguriert:** `ORDERS_BASE_URL` und `ORDERS_ID_TOKEN` werden in **keinem** Terraform-Modul
gesetzt (Suche über `*.tf`, `*.py`, `*.sh`: nur Code-Fundstellen). Der Agent würde daher gegen die
hartkodierte Alt-API laufen (GAP-04).

### 6.2 Pfad B — RIS-API → orders_reader → direkter AWS-Zugriff

| Station | Datei / Funktion | Konkretes Detail |
|---|---|---|
| Einstieg | `terraform/main.tf:154-168` `module "orders_reader"` | RIS-API-Routen mit **RIS**-Authorizer (`authorizer_id = module.api.authorizer_id`) |
| Routen | `terraform/modules/orders_reader/main.tf:113-142` | `POST /orders`, `GET /orders`, `GET /orders/{orderId}`, `PATCH /orders/{orderId}/status` |
| Handler | `lambda/orders_reader.py` | `boto3` DynamoDB (`Table(ORDERS_TABLE)`) + `boto3` SQS (`SendMessage` an `ORDERS_SQS_QUEUE_URL`) |
| Env-Bindung | `terraform/modules/orders_reader/main.tf:86-87` ← `main.tf:164-167` | `ORDERS_TABLE`, `ORDERS_SQS_QUEUE_URL` aus `module.mays_orders.*` |
| Authorization | RIS-JWT (RIS-Pool) | **umgeht** die Orders-API vollständig |
| Fail-closed-Guard | `lambda/orders_reader.py:26-36` | Abbruch bei fehlender/inkonsistenter Bindung (`ORDERS_TABLE`/`ORDERS_SQS_QUEUE_URL`) |

### 6.3 Gegenüberstellung und offene Architekturentscheidung

| Kriterium | Pfad A (HTTP über Modul-API) | Pfad B (orders_reader direkt) |
|---|---|---|
| Nutzt Modul-API | **ja** (beweist `api`, `lambda`, `cognito`, `iam`) | nein (nutzt nur Tabelle/Queue) |
| Nutzt Modul-Queue aktiv | ja (Worker-Consumer) | ja (`SendMessage`) |
| Authentifizierung | Orders-eigener Cognito-Pool (MANAGED) | RIS-Pool |
| Token-Kompatibilität MANAGED | **nicht gegeben**: RIS-`idToken` stammt aus dem RIS-Pool, die Orders-API erwartet das Audience ihres eigenen Clients | gegeben |
| Verdrahtung vorhanden | **nein** (`ORDERS_BASE_URL` fehlt) | ja (`main.tf:164-167`) |
| Aussagekraft für den Integrationsnachweis | hoch | mittel (prüft Modul-Outputs, nicht Modul-API) |

**Welchen Pfad muss der spätere RIS-E2E nachweisen?**
Für den Nachweis der **Modul-Integration** ist Pfad A maßgeblich, weil nur er das generierte API-,
Lambda- und Cognito-Wiring des Moduls berührt. Pfad B ist bereits heute verdrahtet und würde auch
ohne Modul-Upstream-Änderung funktionieren — er beweist die Integration nicht.

**Offene Architekturentscheidung (nicht in S01 entschieden):**
Wie erhält der RIS-Agent ein für die Orders-API gültiges Token?
(a) `external_cognito` mit dem RIS-Pool (EXTERNAL-Variante), (b) Machine-to-Machine-Credential,
(c) RIS nutzt für den E2E bewusst Pfad B und erklärt Pfad A zum Nicht-Ziel.
Ohne diese Entscheidung ist Pfad A nicht nachweisbar (CONFLICT-02).

---

## 7. Befunde

Klassifikation: **MATCH** | **GAP** | **CONFLICT** | **NOT VERIFIED**

### 7.1 MATCH (bestätigt)

| ID | Befund | Beleg |
|---|---|---|
| M-01 | Input-Vertrag = 5 Variablen, RIS übergibt 4 + `external_cognito` implizit `null` | `spec.py:98-103`, `builder.py:649-673`, `terraform/main.tf:172-179` |
| M-02 | 19 offizielle Outputs decken **alle** RIS-Consumer außer `sqs_queue_name` vollständig ab | §3.1/§3.2 |
| M-03 | Identitätsfelder (ARN für IAM, URL für SQS-Aufruf, Name für SDK) korrekt getrennt | §5.4 |
| M-04 | Namensableitung `RIS → Orders` ist deterministisch und in beiden Pfaden identisch (`-mays-orders`) | `ris.py:149`, `terraform/main.tf:174` |
| M-05 | Alle Namen für `ris-dev2-mays-orders` liegen innerhalb der AWS-Limits | §5.2 |
| M-06 | IAM-Gate-Patch hält Least-Privilege-Scope (`resources = [var.sqs_queue_arn]`) | `iam/main.tf:91`, `build_mays_orders_module.py:114-130` |
| M-07 | MANAGED ist der Default und erfordert von RIS keine Eingabe | `builder.py:663`, `main.tf:178` |

### 7.2 GAP (fehlend / ungesichert)

**GAP-01 — Projektname wird an zwei Stellen unabhängig gesetzt**
- Beleg: `build_mays_orders_module.py:180-186` (`--project-name`, Default `mays-ris`) vs.
  `terraform/main.tf:174` (`"${var.project_name}-mays-orders"`)
- Auswirkung: Aufruf mit `ris-dev2` erzeugt `ris-dev2-*`-Ressourcen; RIS erwartet
  `ris-dev2-mays-orders-*`. Falscher Name ⇒ Ressourcen-Duplikate/Drift, Monitoring-Dimensionen leer.
- Zuständigkeit: **RIS**
- Kleinste Änderung: Wrapper leitet den Namen selbst ab (`f"{project_name}-mays-orders"`) oder
  verlangt den vollen Komponentennamen mit Validierung gegen `terraform/main.tf`.
- Späterer Test: Build mit `--project-name ris-dev2` ⇒ Manifest `project_name == ris-dev2-mays-orders`.
- Blockiertes Gate: S02 (Build-Vertrag)

**GAP-02 — `sqs_queue_name` ist kein offizieller Output**
- Beleg: 0 Treffer in `module_builder/*.py`; Patch in `build_mays_orders_module.py:75-96`
- Auswirkung: ohne Patch ist `terraform/main.tf:233` ungültig; der Patch ist rebuild-abhängig und
  hat **keine** Fail-closed-Prüfung (anders als das IAM-Gate).
- Zuständigkeit: **MO** (primär), RIS (Übergang)
- Kleinste Änderung: MO ergänzt `output "sqs_queue_name" { value = module.sqs.queue_name }` im
  Preset; RIS prüft danach fail-closed, dass der Patch **nicht mehr nötig** ist.
- Späterer Test: Build ohne Patch ⇒ `sqs_queue_name` vorhanden; `--check` erkennt es.
- Blockiertes Gate: S04 (Plan/Validate)

**GAP-03 — kein wirksamer Builder-Pin**
- Beleg: `PIN_FILE` (`:27`) unbenutzt; `ensure_repo()` macht `fetch` + `checkout main`, dirty nur Warnung
- Auswirkung: nicht reproduzierbare Builds; ein MO-`main`-Push ändert den RIS-Build unbemerkt.
- Zuständigkeit: **RIS**
- Kleinste Änderung: Pin (SHA) im Wrapper auswerten und `checkout <sha>` erzwingen, oder
  Entscheid „main bewusst" dokumentieren und Manifest-Commit als Gate prüfen.
- Späterer Test: Build zweimal ⇒ identischer `source.commit` im Manifest.
- Blockiertes Gate: S02, S03

**GAP-04 — `ORDERS_BASE_URL` / `ORDERS_ID_TOKEN` sind nicht verdrahtet; Default zeigt auf Alt-Stack**
- Beleg: `real.py:34` (`aboqolpm0f…`), `function.py:65`; keine Terraform-Env-Variable im Repo
- Auswirkung: Pfad A spricht die falsche (alte) API an; ein E2E würde einen fremden Stack testen.
- Zuständigkeit: **RIS**
- Kleinste Änderung: Agent-Lambda erhält `ORDERS_BASE_URL = module.mays_orders.api_gateway_endpoint`
  (Output existiert bereits, wird nur nicht konsumiert).
- Späterer Test: E2E-Aufruf trifft `ris-dev2-mays-orders-api` (Stage/Endpoint aus Output).
- Blockiertes Gate: S05 (E2E)

**GAP-05 — keine Namens-/Formatprüfung im Wrapper**
- Beleg: `build_module()` übergibt `project_name` ungeprüft; `validate_orders_aws_name_limits`
  (`ris.py:429-432`) wird nicht aufgerufen
- Auswirkung: ungültige Namen fallen erst im Terraform-Plan auf (nach Backend-Init).
- Zuständigkeit: **RIS**
- Kleinste Änderung: Wrapper ruft die bestehende Prüfung auf (mit presetspezifischer Regelmenge).
- Späterer Test: `--project-name "Bad Name"` ⇒ früher, klarer Abbruch.
- Blockiertes Gate: S02

**GAP-06 — `sqs_enabled = true` mit leerem ARN ungeprüft**
- Beleg: Patch gatet nur auf den Bool; ein leerer `sqs_queue_arn` bei aktivem Gate erzeugt eine
  Policy mit leerem `resources`-Eintrag (statisch ableitbar, nicht gemessen)
- Auswirkung: ungültige bzw. wirkungslose Policy ohne klaren Fehler.
- Zuständigkeit: **MO** (Variablen-Validierung) / RIS (Patch)
- Kleinste Änderung: `validation` in `variable "sqs_enabled"`: bei `true` muss `sqs_queue_arn != ""` sein.
- Späterer Test: negativer Test §4.6, Randfall.
- Blockiertes Gate: S04

**GAP-07 — `var.orders_*` in RIS sind deklariert, aber nicht mehr verdrahtet**
- Beleg: `terraform/variables.tf:343-383` (fail-closed-Doku), Verwendung nur in
  `terraform/modules/orders_reader/*` und `installer/ris.py` (Composite); `main.tf:164-167`
  übergibt stattdessen direkt `module.mays_orders.*`
- Auswirkung: irreführender Vertrag — ein gesetzter `-var orders_table_name` hat keine Wirkung.
- Zuständigkeit: **RIS**
- Kleinste Änderung: Variablen entfernen oder auf Modul-Outputs abbilden (Bevorzugung: entfernen
  im Module-Pfad).
- Späterer Test: `terraform validate` + gezielter Negativtest „Variablen werden nicht mehr genutzt".
- Blockiertes Gate: S04 (Doku-Konsistenz)

### 7.3 CONFLICT (widersprüchlich)

**CONFLICT-01 — Wrapper-Docstring widerspricht dem Code**
- Beleg: `build_mays_orders_module.py:1-12` („into `installer/projects/mays_orders` (pinned commit)")
  vs. `:25` (`mays_order_builder`) und `:38-53` (`main`, kein Pin)
- Auswirkung: Fehlannahme „gepinnt" bei Reviews/Audits.
- Zuständigkeit: **RIS**
- Kleinste Änderung: Docstring auf tatsächliches Verhalten korrigieren.
- Späterer Test: Review-Kriterium (kein Testfall).
- Blockiertes Gate: keines (Doku)

**CONFLICT-02 — MANAGED-Cognito vs. RIS-Token (Architekturkonflikt)**
- Beleg: `terraform/modules/api/main.tf:30,89` (Authorizer gegen Modul-Pool);
  `agents/orders/function.py:52-56` (Token aus WorkItem/`ORDERS_ID_TOKEN`, d. h. RIS-Kontext)
- Auswirkung: Im MANAGED-Fall ist ein RIS-`idToken` für die Orders-API nicht gültig ⇒ Pfad A
  ist ohne Zusatzentscheidung nicht testbar (401).
- Zuständigkeit: **RIS** (Entscheidung) + **MO** (EXTERNAL-Variante existiert bereits)
- Kleinste Änderung: **keine Codeänderung in S01** — Entscheidung dokumentieren (EXTERNAL vs. M2M
  vs. Pfad B als E2E-Ziel).
- Späterer Test: E2E-Login → `POST /orders` gegen Modul-API mit gültigem Token (200/201).
- Blockiertes Gate: S05 (E2E)

**CONFLICT-03 — Namensgrenzen-Doku begründet eine Grenze mit ausgeschlossenen Modulen**
- Beleg: `docs/installer/AWS-NAME-LIMITS.md` („bindend ist der CloudTrail-S3-Bucket mit 39") vs.
  `ORDERS_SERVICE_MODULES` ohne `cloudtrail`/`cognito_backup`
- Auswirkung: Für das Preset gilt faktisch 49 (IAM-Rolle SQS-Worker), nicht 39/23. Die strengere
  Prüfung ist harmlos, aber die Begründung ist für diesen Integrationsweg falsch.
- Zuständigkeit: **RIS** (Doku) — MO-Grenzen selbst sind korrekt
- Kleinste Änderung: Doku-Abschnitt „presetspezifische Grenzen" ergänzen.
- Späterer Test: keiner (Doku).
- Blockiertes Gate: keines

### 7.4 NOT VERIFIED

| ID | Aussage | Grund |
|---|---|---|
| NV-01 | Terraform-Planverhalten des IAM-Gates (Fehler/Erfolg) | kein Terraform, kein Lauf (S00/S01) |
| NV-02 | Tatsächliche 34-Datei-Ausgabe und Manifest-Inhalt | kein Builder-Lauf |
| NV-03 | 87 Builder-Tests „bestanden" | kein pytest, keine Lauf-Evidenz |
| NV-04 | AWS-Identität/Zielkonto `ris-dev2` | keine AWS-Aufrufe |
| NV-05 | Verhalten des Patches bei künftigem MO-`main` | Upstream-Stand zeitabhängig |

---

## 8. Grenzen des statischen Nachweises

1. Alle Aussagen beruhen auf Quelltext, Doku und Dateisystem — **keine** Laufzeitmessung.
2. Es wurde **kein** Modul generiert; Output-/Dateilisten sind aus dem Generatorcode abgeleitet.
3. Es wurde **kein** Terraform initialisiert/validiert/geplant; Aussagen zum Gate sind statisch.
4. Es wurden **keine** AWS-Aufrufe gemacht; Konto, Region-Zugehörigkeit und Backend bleiben offen.
5. Der MO-Checkout wurde nicht verändert (kein Checkout eines anderen Standes, kein Merge).
6. Die EXTERNAL-Cognito-Variante ist beschrieben, **nicht** bewertet und **nicht** migriert.

---

## 9. Voraussetzungen späterer Ausführung (kein Blocker dieser Matrix)

| # | Voraussetzung | Status | Nötig ab |
|---|---|---|---|
| V-01 | Terraform `>=1.6,<2.0` installiert | fehlt | S03/S04 |
| V-02 | pytest/moto/boto3 gemäß `requirements.txt` | fehlt | S03+ |
| V-03 | Python 3.14 (aktuell nur 3.15) | Abweichung | S03+ |
| V-04 | Konto/Profil für `ris-dev2` geklärt | widersprüchlich/offen | S05 |
| V-05 | Backend-Bucket/Key/Lock/`TF_DATA_DIR` für `ris-dev2` | offen | S04 |
| V-06 | Pin-Entscheid (GAP-03) | offen | S02 |
| V-07 | Entscheidung CONFLICT-02 | offen | S05 |

---

## 10. Priorisierte Aufträge

### 10.1 Hersteller (MO)

| Prio | Auftrag | Bezug | Kleinste Änderung |
|---|---|---|---|
| 1 | `output "sqs_queue_name"` in das Preset aufnehmen | GAP-02 | 3 Zeilen in `module_builder/builder.py`, ein Test |
| 2 | `sqs_enabled`-Semantik upstream übernehmen (plan-bekanntes Gate, ARN als Scope) | §4 | Gate-Ausdruck ersetzen + Validierung (GAP-06) |
| 3 | Optionaler Output für Worker-`function_name` | §3.3 | ein Output ergänzen |

### 10.2 Consumer (RIS)

| Prio | Auftrag | Bezug |
|---|---|---|
| 1 | Projektnamen-Ableitung im Wrapper zentralisieren | GAP-01 |
| 2 | Builder-Pin erzwingen oder bewusst „main" dokumentieren | GAP-03 |
| 3 | `ORDERS_BASE_URL` aus `api_gateway_endpoint` verdrahten | GAP-04 |
| 4 | Namensprüfung im Wrapper aufrufen | GAP-05 |
| 5 | `var.orders_*`-Altvertrag bereinigen | GAP-07 |
| 6 | Docstring + Namensgrenzen-Doku korrigieren | CONFLICT-01/03 |
| 7 | Architekturentscheidung Token/Cognito treffen | CONFLICT-02 |

---

## 11. Nächster Schritt S02

**S02-BUILD-CONTRACT (statisch + optionaler lokaler Build, kein AWS):**

1. Vertrag für den **Build-Aufruf** festlegen: exakter Befehl, `--project-name`-Ableitung
   (GAP-01), `--force`-Semantik, Ziel-Verzeichnis.
2. **Pin-Entscheid** herstellen (GAP-03): SHA festlegen oder „main + Manifest-Gate" beschließen;
   Entscheid im Report belegen.
3. Erwartete **Dateiliste** (34) als Soll-Liste vorab festhalten, damit der Build deterministisch
   geprüft werden kann (Soll/Ist inkl. Manifest `files_written`).
4. Vorbedingungen aus §9 trennen: Welche S02-Schritte laufen ohne Terraform, welche nicht.
5. **S02 führt weiterhin keinen AWS-Aufruf aus.** Ein lokaler Builder-Lauf ist nur zulässig, wenn
   der Auftrag ihn ausdrücklich freigibt.

Report: `docs/reports/MO-RIS-DEV2-S02-BUILD-CONTRACT-2026.md`

---

## 12. Checkpoint

| Prüfung | Ergebnis |
|---|---|
| Quell-SHAs dokumentiert | RIS `b194b80…`, MO `2d5cf2de…` (§1.1) |
| `git diff --check` | ohne Befund |
| Secret-Audit | nur Doku; keine Keys/Tokens/State; keine Kontonummern ergänzt |
| Geänderte Dateien | `docs/reports/MO-RIS-DEV2-S01-CONTRACT-MATRIX-2026.md` (neu), `docs/AI_AUDITLOG.md` (ergänzt) |
| MO | unverändert (`git status` leer, HEAD unverändert) |
| Commit/Push | siehe Chat-Abschluss (kein Force-Push) |
