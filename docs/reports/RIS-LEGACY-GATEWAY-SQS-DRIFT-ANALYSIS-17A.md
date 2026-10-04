# RIS-LEGACY-GATEWAY-SQS-DRIFT-ANALYSIS-17A — Legacy Gateway & SQS Mapping Drift

STATUS: YELLOW — Runtime-Pfad gesund, aber **State-Drift mit Kollisionsrisiko**; kein Apply in diesem Gate

- Datum: 2026-10-04 UTC
- Branch/HEAD: `main`, `3355a6e`
- Account/Region/Workspace: `240571105849` (`user/Mayaws`) / `eu-central-1` / `mays-ris`
- **READ-ONLY-Gate: keine AWS-Mutation, kein Apply, kein Import, keine Löschung.**

## 1. Context

| Prüfung | Ergebnis |
|---|---|
| Branch / HEAD | `main` / `3355a6e` |
| `git status` | tracked clean (nur 9 vorbestehende untracked) |
| `AWS_PROFILE` | `mayaws` für alle Reads |
| Account | `240571105849` ✔ |
| Region | `eu-central-1` ✔ |
| Workspace | `mays-ris` ✔ |

## 2. Live Gateway Inventory

API `mays-ris-dev-api` (`aboqolpm0f`), 20 Routen, Stage `$default` (AutoDeploy).

| Route | RouteId | Authz | Target |
|---|---|---|---|
| `GET /health` | `wv3znst` | NONE | `ewy9u57` |
| `GET /me` | `nzmp4se` | JWT/`9ghezn` | `ewy9u57` |
| `GET /me/profile` | `ezrgj81` | JWT/`9ghezn` | `ewy9u57` |
| `POST /me/profile` | `r5atqmf` | JWT/`9ghezn` | `ewy9u57` |
| `PUT /me/profile` | `sysdyq6` | JWT/`9ghezn` | `ewy9u57` |
| `GET /me/documents` u.a. (3) | — | JWT/`9ghezn` | `ewy9u57` |
| `GET /v1/introspection` | `zmli1kf` | JWT/`9ghezn` | `ewy9u57` |
| 7× `/v1/apiprofiles/…/credentials` | — | JWT/`9ghezn` | `ewy9u57` |
| 4× `/orders*` | — | JWT/`9ghezn` | `8yo7f44` |

Integration `ewy9u57` = AWS_PROXY → `mays-ris-dev-agent`; `8yo7f44` → `mays-ris-dev-orders-reader`.

## 3. Analyse der 6 Legacy-Routen

**Zentrale Korrektur der Gate-Prämisse:** die im Auftrag genannten Pfade `/me/profile/create` und `/me/profile/update` existieren live **nicht**. Die Schreibrouten heißen `POST /me/profile` und `PUT /me/profile`. Von den 6 genannten Routen sind zudem nur **4** live; `GET /platform` und `GET /agents` fehlen.

| # | Route (Gate-Angabe) | Live | Code | Docs | Tests | Bewertung |
|---|---|---|---|---|---|---|
| 1 | `GET /platform` | **FEHLT** | `modules/api/main.tf:49-55` | `API-STANDARD.md:12`, `SYSTEM-ARCHITECTURE.md:23`, `README.md:11` | `test_platform_handlers.py:38,79` | **MIGRATE** |
| 2 | `GET /me` | live `nzmp4se` | `:57-63` | `API-STANDARD.md:12`, `README.md:11` | `test_platform_handlers.py` | **RECONCILE** |
| 3 | `GET /me/profile` | live `ezrgj81` | `:65-71` | `API-STANDARD.md:12`, `SYSTEM-ARCHITECTURE.md:63` | `test_platform_handlers.py:137,154`, `test_identity_registration.py` | **RECONCILE** |
| 4 | `POST /me/profile/create` | **FEHLT** (Pfad existiert nicht) | Realität: `POST /me/profile` `:73-79` | `API-STANDARD.md:16,25` | `test_identity_registration.py:21` | **RECONCILE** |
| 5 | `PUT /me/profile/update` | **FEHLT** (Pfad existiert nicht) | Realität: `PUT /me/profile` `:81-87` | `API-STANDARD.md:17` | `test_platform_handlers.py` | **RECONCILE** |
| 6 | `GET /agents` | **FEHLT** | `:89-96` | `API-STANDARD.md:12`, `README.md:11`, `SYSTEM-ARCHITECTURE.md:23` | `test_platform_handlers.py:178,196,215` | **MIGRATE** |

### Begründung

**RECONCILE (4 Routen)** — fachlich gültig **und** live, aber nicht im Terraform-State (`terraform state list` enthält nur `health`, `introspection`, 7× `credentials_*` und 4× orders_reader). Kein `REMOVE-CANDIDATE`: jede Route hat einen existierenden Handler (`_handle_me`, `_handle_me_profile`, `_handle_me_profile_create`, `_handle_me_profile_update` — alle vorhanden und im Router `lambda/handler.py:244-254` verdrahtet), einen dokumentierten Vertrag in `docs/api/API-STANDARD.md` und Tests. `POST /me/profile` ist laut Standard-Doku sogar der **explizite Registrierungsweg** (`:25-26`: „NIEMALS Auto-Provisioning durch Reads").

**MIGRATE (2 Routen)** — `GET /platform` und `GET /agents` sind im aktuellen Vertrag fully documented, getestet und im Handler verdrahtet, fehlen aber live. Sie sind keine Legacy-Routen, sondern **fehlende aktuelle Vertragsrouten**; der Begriff „legacy" trifft hier nicht zu.

**Kein einziger REMOVE-CANDIDATE.** Keine der 6 Routen ist fachlich überholt.

### Kritischer Nebenbefund: Apply-Kollision

Terraform plant für alle 6 Adressen `create`. Für die **4 bereits live existierenden** Routen würde ein Apply `CreateRoute` auf einen bereits belegten `RouteKey` senden → **ConflictException**. Das ist kein kosmetischer Drift, sondern ein Apply-Blocker. Ein Full Apply ist damit aktuell **nicht** durchführbar; es braucht zuerst einen Import der 4 Live-Routen (separates Gate).

## 4. SQS Event Source Mapping — Live Readback

| Attribut | Wert |
|---|---|
| `UUID` | `7cc946b9-1c32-4f84-88b4-6f0918e486e7` |
| `EventSourceArn` | `arn:aws:sqs:eu-central-1:240571105849:mays-ris-dev-work-queue` |
| Queue-Name | `mays-ris-dev-work-queue` |
| `FunctionArn` | `…/function:mays-ris-dev-agent` |
| `State` | `Enabled` |
| `StateTransitionReason` | `USER_INITIATED` |
| `BatchSize` | `5` |
| `MaximumBatchingWindowInSeconds` | `0` |
| `FunctionResponseTypes` | `[]` |
| `LastModified` | `2026-10-01T18:04:22+02:00` |

Queue live: `VisibilityTimeout 300`, `ReceiveMessageWaitTimeSeconds 20`, `MessageRetentionPeriod 1209600`, `RedrivePolicy` → `mays-ris-dev-dlq`, `maxReceiveCount 3`.

## 5. SQS Terraform State und Code

**State:** `terraform state list | grep event_source_mapping` → **leer**. Das Mapping ist **nicht im State** → State-Drift, kein Import in diesem Gate.

**Code:** genau **eine** deklarative Definition, `terraform/modules/lambda/main.tf:327-331`:

```hcl
resource "aws_lambda_event_source_mapping" "sqs_mapping" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.agent.arn
  batch_size       = 5
}
```

Verdrahtung: `terraform/main.tf:124` (`module.sqs.work_queue_arn`) → `modules/lambda/variables.tf:125`. Keine historischen/deprecated Definitionen, keine Mehrfachdefinition.

**Code vs. Live:** `batch_size 5` = Live `5` ✔; Event-Source = `mays-ris-dev-work-queue` ✔; Function = `mays-ris-dev-agent` ✔. **Inhaltlich deckungsgleich** — die Drift ist rein der fehlende State-Eintrag. Live-`LastModified` (2026-10-01) liegt vor der Terraform-Provisionierung der Instanz.

## 6. Runtime-Vertragsanalyse

Die im Gate skizzierte Kette ist im Code **vollständig vorhanden**:

```
POST /work (Handler :1247ff)  →  DynamoDB WorkItem (put_item)  →  SQS send_message (:1254-1263)
   → Event Source Mapping (Batch 5)  →  _handle_sqs_event (:157)  →  _process_work_item
   → agents.runtime.pipeline.process_record
   → DynamoDBEntitlementResolver (Execution-Time-Re-check, Gate 08)
   → Agent Ecosystem → Agent Body
```

Belege: `lambda/handler.py:1254-1263` sendet an `WORK_QUEUE_URL`; `_handle_sqs_event:157` iteriert `Records` und ruft `_process_work_item`; `_process_work_item` injiziert `DynamoDBEntitlementResolver()` (Entitlement Re-check) und delegiert an `process_record`.

**Einschränkung:** Der Produzenten-Pfad `POST /work` und `/api/agents/*` ist im Handler-Router (`:287-296`) verdrahtet, hat aber **keine Gateway-Route** — weder live (alle 8 geprüft: FEHLT) noch in `terraform/modules/api/main.tf`. Die Queue kann derzeit nur via Direct-Invoke oder externem Producer gefüllt werden. Das Mapping selbst ist für den Worker-Pfad erforderlich und korrekt konfiguriert; es ist **kein** funktionaler Defekt, aber sein Upstream ist nicht HTTP-erreichbar.

## 7. Drift-Klassifizierung (Teil C — strikt getrennt)

| # | Kategorie | Befund |
|---|---|---|
| 1 | **Funktionaler Legacy-Vertrag** | **Leer.** Keine der 6 Routen ist fachlich überholt; alle 6 sind in `API-STANDARD.md` als aktueller Vertrag geführt. |
| 2 | **State-Drift** | 4 Routen (`me`, `profile`, `profile_create`, `profile_update`) + 1 ESM live, aber nicht im State. |
| 3 | **Code-Drift** | **Leer.** `modules/api/main.tf` und `sqs_mapping` entsprechen dem Live-Zustand inhaltlich. |
| 4 | **Tatsächlicher Runtime-Defekt** | **Leer.** Handler, Worker-Pipeline, Entitlement-Re-check und ESM sind konsistent; B3-Index-Fix ist deployed. |
| 5 | **Historischer/ungenutzter Gateway-Vertrag** | `/health` **live**, aber der Handler enthält keinen `/health`-Pfad (aus P16-Gate bekannt) → Route ungenutzt, kein Handler-Defekt in diesem Scope. |
| 6 | **Plan-Artefakt** | `module.iam.aws_iam_role_policy.lambda_policy` — **andere Rolle** (`lambda_role`, Logs+S3) als der Agent; nicht Teil dieses Gates, hier nur als Plan-Rest benannt. |

Der Drift ist damit **reine State-Lücke plus 2 fehlende aktuelle Routen** — kein Runtime-Defekt.

## 8. Entscheidungen

**Routen:** `GET /me`, `GET /me/profile`, `POST /me/profile`, `PUT /me/profile` → **RECONCILE** (Import, da live + gültig). `GET /platform`, `GET /agents` → **MIGRATE** (Create, da gültig aber fehlend). **Kein REMOVE-CANDIDATE.**

**SQS Mapping:** **RECONCILE.** Live-Zustand ist korrekt und produktiv erforderlich (Worker-Pfad), Terraform-Code stimmt überein, es fehlt nur der State-Eintrag. Kein MIGRATE (nicht ersetzbar), kein REMOVE (Pfad benötigt), kein UNRESOLVED (alle Quellen belastbar).

## 9. P17 Readiness

**GREEN.**

Beide P17-Blocker aus `RIS-CREDENTIAL-MANAGEMENT-LIVE-DEPLOYMENT-17.md` sind aufgelöst: Blocker A (Entitlement-`IndexName`) durch B3 `028a24d` + P19-Deploy, Blocker B (fehlende Tabellen) durch P18/P18B (provisioniert, State-Parity) + P19 (Env 3/3).

Das P17-E2E (Credential-Lifecycle) benötigt die 7 Credential-Routen + Handler + Tabellen + IAM + Env — **alle** vorhanden. Der Credential-Pfad braucht **keine** der 6 hier analysierten Routen und **kein** SQS.

Ausdrücklich: Der Terraform-Plan zeigt 8 `create`-Einträge, aber das ist **kein** P17-Blocker. Ein P17-E2E testet Runtime-Verhalten, nicht State-Synchronität. Nur wenn P17 ein `terraform apply` einschließt, wäre die Kollision aus §3 relevant — dann aber als separates Reconcile-Gate vorher.

## 10. Offene Punkte

1. **Reconcile-Gate empfohlen:** Import der 4 Live-Routen + des ESM in den State, danach `create` nur für `platform` und `agents`. Ohne das scheitert jeder Full Apply an `ConflictException`.
2. `GET /platform` und `GET /agents` sind aktueller Vertrag, aber nicht erreichbar — bis zum Reconcile-Gate fehlen sie live.
3. `POST /work` und `/api/agents/*` sind im Handler vorhanden, aber ohne Gateway-Route; der SQS-Produktionsweg ist damit nicht HTTP-erreichbar.
4. `GET /health` live ohne Handler-Pfad (aus P16 bekannt, unverändert).
5. `module.iam.aws_iam_role_policy.lambda_policy` bleibt als Plan-Rest bestehen, betrifft eine andere Rolle und ist nicht Teil dieses Gates.
