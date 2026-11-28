# RIS-DEV2-ORDER-API-READ-01

**Datum:** 2026-11-25  
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`  
**Branch:** `feature/ris-analysis-integration-07`  
**Baseline:** `71e537ad0435577b19f19c4df81fb1510880fb62`  
**Modus:** Implementierung + Tests + neuer Plan; **kein Apply, keine AWS-Mutation, kein Main-Merge**

## Ergebnis

Die Architekturentscheidung ist umgesetzt und belegt:

- **Order-Daten:** Die Analysis-Runtime liest **keine** Orders. Sie benötigt
  heute keine Order-Werte oder Order-Status; damit entfällt jeder Bedarf für
  einen direkten oder indirekten Order-Lesezugriff aus der Analysis-Lambda.
  Für eine spätere Nutzung ist `GET /orders/{orderId}` der verbindliche Weg.
- **WorkItem-Verifikation:** Es existiert **kein** geeigneter interner,
  autorisierter RIS-Endpunkt. Der direkte WorkItems-`GetItem` bleibt deshalb
  bestehen; die Verifikation bleibt fail-closed. Die benötigte Schnittstelle
  ist in §5 beschrieben.
- **IAM:** `dynamodb:Query` und `index/*` für PartnerProfiles wurden entfernt.
  `GetItem` (PartnerProfiles) und `GetItem` (WorkItems) bleiben.

## 1. Bestehender Order-Leseweg

`GET /orders/{orderId}` (`terraform/modules/orders_reader`, `lambda/orders_reader.py`):

| Prüfung | Ergebnis |
| --- | --- |
| Route | `GET /orders/{orderId}`, API Gateway HTTP API, `authorization_type = JWT` |
| Authentifizierung | Cognito-Issuer und Client-ID aus `ORDERS_COGNITO_ISSUER` / `ORDERS_COGNITO_CLIENT_ID`; `token_use` muss `id`/`access` sein |
| Eigentümerprüfung | Owner-Bindung aus verifizierten Claims; fremde, fehlende oder legacy-ungebundene Orders → **404 `ORDER_NOT_FOUND`** (keine Existenzleckage) |
| Antwort | öffentliche Projektion ohne interne Felder; `orderDescription` als opaker Client-Text (siehe Privacy-Gate 02) |
| Tenant-Grenze | gepinnter Issuer/Client, da Order-Items kein `tenantId` tragen |

Dieser Weg ist der **einzige** autorisierte Order-Leseweg. Er liefert
`orderType`, `status`, `customer`, `items`, `currency`, `totalAmount` und
`orderDescription` — mehr, als die Analysis heute bräuchte.

## 2. Analysepfade mit Order-Bedarf

Geprüft wurden `lambda/analysis_runner.py`, `agents/analysis/*` und
`agents/analysis_agent/agent.py`:

| Pfad | Order-Werte/Status | Ergebnis |
| --- | --- | --- |
| `AnalysisAgent` / `AnalysisOrchestrator` | keine | verarbeitet WorkItem-Payload (CV, Job, Profile) |
| `cv_bridge` | keine | liest CV-Referenz/Profil, kein Orderbezug |
| `job_store`, Parser-Adapter | keine | nur S3/Job-Parser |
| `analysis_runner.handler` | keine | WorkItem-/SQS-Pfad, Result-Transport liegt beim Worker |

Kein Analysepfad referenziert `orderId`, Order-Status oder die Orders-Tabelle.
Die bestehenden Boundary-Tests (`tests/test_analysis_order_boundary.py`) pinnen
das bereits; zusätzlich pinnt der neue Test in §4 die Abwesenheit von
`ORDERS_TABLE`/`mays-orders` in Modul und Quellen.

**Konsequenz:** Es wird **kein** Order-API-Aufruf eingeführt. Ein solcher wäre
heute toter Code und würde eine Service-Authentifizierung erfordern, die es
nicht gibt (siehe §3). Die Entscheidung „Orders über die Order-API“ ist damit
eingehalten: kein direkter DynamoDB-Zugriff auf Orders, und der benannte
Leseweg bleibt der einzige.

## 3. Serverseitiger Auth-Weg: nicht vorhanden

Für einen Aufruf aus der Analysis-Lambda müsste ein **tatsächlich vorhandener**
autorisierter Weg existieren. Prüfung:

- `GET /orders/{orderId}` verlangt ein Cognito-JWT eines **Eigentümers**. Die
  Analysis-Lambda hat keinen Benutzerkontext und keinen Service-Token; ein
  eigener M2M-Client für diese Route existiert nicht.
- Die vorhandene M2M-Route ist **nur** `POST /v1/m2m/agents/{agentId}/execute`
  (dedizierter `jwt_m2m`-Authorizer + opake `ris_…`-Credential). Sie ist eine
  Ausführungs-, keine Leseschnittstelle und als Order-/WorkItem-Nachweis
  ungeeignet.
- Ein Service-Identity-Weg (Client-Credentials-Token, mTLS, signierter
  Service-Header) ist für die Analysis-Lambda **nicht** konfiguriert.

Damit gilt: **keine JWT-Umgehung, keine ungeprüfte Service-Identität.** Ein
Order-Aufruf aus der Analysis ist heute nicht autorisiert möglich und wird
nicht gebaut.

## 4. WorkItem-Verifikation

### Bestehende Lage

`SyntheticWorkItemReadback` prüft `workId`, `status=RUNNING` und die
Identitätsfelder gegen die **persistierte** Zeile (`lambda/analysis_runner.py`,
`_build_synthetic_verifier`, `GetItem` mit `ConsistentRead`). Der Pfad ist nur
bei aktivem synthetischem Modus erreichbar; `ANALYSIS_SYNTHETIC_MODE=false`.

### Gibt es einen internen Service-Endpunkt?

**Nein.**

| Kandidat | Befund |
| --- | --- |
| `GET /work/{workId}` | Handler-Zweig existiert, aber **keine Gateway-Route** (`API-STANDARD` OPEN-5: `/work*` liefert live 404). Zusätzlich hat `_get_work` **keine** Eigentümer-/Tenant-Prüfung und liefert nur `workId`/`status` – nicht die benötigten Identitätsfelder |
| `GET /api/agents/{agentId}/work/{workId}` | Legacy-Handler, ebenfalls **keine** Gateway-Route (OPEN-5) |
| `POST /v1/m2m/agents/{agentId}/execute` | vorhandene, autorisierte M2M-Route, aber Ausführung statt Verifikation; liefert keine WorkItem-Identität |
| `/v1/introspection`, `/me` | menschenbezogene Kontexte, kein WorkItem-Nachweis |

Die WorkItem-**Tabelle** ist damit weiterhin die einzige belastbare Quelle.
`GetItem` bleibt bestehen; die Prüfung bleibt fail-closed (unbekannt, falscher
Status, Identitäts-Mismatch oder Lesefehler → keine synthetische Identität).

### Benötigte minimale Schnittstelle (Vorschlag, nicht implementiert)

Ein interner, autorisierter Read-Endpunkt, z. B.:

```text
GET /v1/internal/work-items/{workId}/verification
Auth: vorhandener jwt_m2m-Authorizer (Audience = M2M-Client)
      + opake Service-Credential (X-Api-Credential)
Scope: ris-api/internal/work-item-verify
Antwort: {workId, status, tenantId, userId, partnerApplicationId, issuer}
         (kein payload, kein Ergebnis, kein CV-Inhalt)
```

Minimaler Änderungsumfang: eine Route + ein Handler-Zweig mit strikter
Projektion, ein M2M-Client/Secret für die Analysis-Lambda, `execute-api:Invoke`
auf genau diese Route in der Analysis-Rolle und Token-Beschaffung im Runner.
Das sind **neue** Ressourcen und Berechtigungen und benötigen eine gesonderte
Freigabe; sie wurden hier bewusst nicht angelegt. Eine Order-API ist **kein**
Ersatz für diesen Nachweis.

## 5. Umgesetzte Änderung (IAM)

`terraform/modules/analysis_runtime/main.tf`, Policy
`ris-dev2-dev-analysis-runtime-data`:

| Vorher | Nachher |
| --- | --- |
| `OwnedPartnerProfiles`: `dynamodb:GetItem`, `dynamodb:Query` auf Tabelle **und** `index/*` | `OwnedPartnerProfiles`: nur `dynamodb:GetItem` auf der Tabelle |
| `SyntheticWorkItemReadback`: `dynamodb:GetItem` auf WorkItems | unverändert |

Begründung: Der einzige Lesezugriff ist `PartnerProfileRepository.get()` →
`table.get_item` (Basis-Tabelle, Schlüssel `resourceId`). `Query`/`index/*`
werden von der Analysis-Runtime nicht verwendet. Die Owner-/Tenant-Prüfung
erfolgt weiterhin in der Anwendung (`_identity_ok`), da IAM `GetItem` nicht
itemgenau einschränken kann.

## 6. Tests

| Lauf | Ergebnis |
| --- | --- |
| `tests/test_analysis_runtime_terraform.py` | **17 passed** (inkl. neuer GetItem-only- und Order-Boundary-Tests) |
| `tests/test_analysis_synthetic_profile.py`, `tests/test_analysis_runner_pipeline.py` | passed |
| Fokussiert gesamt: `test_analysis_order_boundary`, `test_analysis_apply_16c2`, `test_orders_reader`, `test_orders_reader_agent_gate`, `test_agent_order_order_description`, `test_order_transport_contract`, `test_work_queue`, `test_dispatch_ingress_lambda`, `test_agent_order_dispatch_e2e` | **173 passed, 7 subtests** |
| ORDER_RESULT-E2E gegen MO `db4f9e7` (`MO_ORDERS_SRC`) | im Lauf enthalten, **passed** (Roundtrip, Duplicate, falsche Korrelation/Work-ID, Signatur, fremder Owner 404) |
| `terraform fmt -check -recursive modules/analysis_runtime` | PASS |
| `terraform validate` (Root) | PASS (nur vorbestehende `hash_key`-Deprecation-Warnungen) |
| Bundles neu gebaut | unverändert: agent `d767a198…`, analysis `e268b028…`, reader `610004f6…` |

## 7. Neuer Plan (nicht angewendet)

| Feld | Wert |
| --- | --- |
| Datei | `C:\tmp\ris-dev2-order-api-read-01.tfplan` |
| Größe | 251 645 Bytes |
| SHA-256 | `279a530fa957a0547a355cb94822e42d4639128d315712eac6faa2fbceea1184` |
| Terraform | 1.17.0; `applyable=true`, `complete=true` |
| Summary | **0 Add / 8 Change / 0 Destroy / 0 Replace** (264 No-op) |
| Workspace / Konto / Region | `ris-dev2` / `262370457690` / `eu-central-1` |
| State | Lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, Serial **69** |

Acht Änderungen:

1. `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]` —
   `policy` (GetItem-only für PartnerProfiles).
2. `module.lambda.aws_lambda_function.agent` — `source_code_hash`, `last_modified`
3. `module.agent_transport[0].aws_lambda_function.dispatch_ingress` — dito
4. `module.analysis_runtime.aws_lambda_function.analysis[0]` — dito
5. `module.orders_reader[0].aws_lambda_function.reader` — dito
6. `module.mays_orders[0].module.lambda.aws_lambda_function.handler` — dito
7. `module.mays_orders[0].module.sqs_worker.aws_lambda_function.worker` — dito
8. `module.mays_orders[0].module.agent_transport[0].aws_lambda_function.result_consumer` — dito

Keine Änderung an Environment, Role-Trust, Cognito, CloudFront, DNS, ACM,
DynamoDB-Ressourcen, SQS-Ressourcen, Secrets oder Event-Source-Mappings.

`resource_drift` enthält erneut die drei aus `RIS-DEV2-DRIFT-FORENSICS-01`
bekannten Refresh-Beobachtungen (zwei `aws_iam_role.inline_policy`-Aggregate,
einmal `layers` `null`/`[]`). Beide Rollen sind in `resource_changes` **No-op**;
die beabsichtigte Änderung betrifft die separate Policy-Ressource.

## 8. Nicht ausgeführt

Kein `terraform apply`, keine AWS-Mutation, kein State-Write, kein Main-Merge.
Der bisherige Plan `2bbf8142…` bleibt gesperrt; der neue Plan
`279a530f…` ist ein Kandidat für eine **neue** menschliche Freigabe.
