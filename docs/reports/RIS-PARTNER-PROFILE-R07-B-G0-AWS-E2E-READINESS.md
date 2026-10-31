# RIS-PARTNER-PROFILE-R07-B-G0 — AWS E2E RELEASE READINESS GATE

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD | `a6f7ff3` (`fix(ris): protect pagination cursors with scoped server-side tokens`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| AWS-API-Aufrufe in G0 | **keine** |
| Terraform Apply/Destroy/Plan | **keine** |

## 2. Tatsächliche Deployment-Architektur

### Root und Module

`terraform/main.tf` verdrahtet **alle** Module immer; es gibt keine
Enable-/Count-Schalter für RIS-Kern oder Mays-Orders.

| Terraform-Modul | Wichtige Ressourcen (Name-Template) | Abhängigkeiten | Zweck | Cleanup | Risiko |
|---|---|---|---|---|---|
| `cognito` | Pool `${p}-${e}-users`, Client `${p}-${e}-client`, Domain `${p}-${e}`, M2M-Client, Resource-Server `${p}-${e}-ris-api` | keine | Human-/M2M-JWT | Destroy Pool/Domain | Cognito-Domain ist **global eindeutig** |
| `api` | HTTP API `${p}-${e}-api`, Authorizer `-jwt-human`/`-jwt-m2m`, 54 Routen | cognito, lambda | REST-Einstieg | Destroy API | 24 `/v1/partner/*`-Routen, keine Wildcards |
| `lambda` | `${p}-${e}-agent` (python3.14, 128 MB, 30 s), 11 Inline-Policies, Loggruppe `/aws/lambda/${p}-${e}-agent` | dynamodb, documents, sqs, s3 | Handler | Destroy Lambda + Loggruppe | Policy-/Env-Kopplung |
| `dynamodb` | 13 Tabellen, u. a. `${p}-${e}-partner-profiles`, `-work-items`, `-user-profile`, `-entitlements`, `-credentials`, `-partner-applications` | keine | Persistenz | Destroy Tabellen | 13 Tabellen, on-demand |
| `documents` | Bucket `${p}-${e}-documents`, Versioning, PAB, SSE-AES256 | keine | CV-Dokumente | Bucket inkl. **aller Versionen** leeren, dann Destroy | Versionen/Delete-Marker |
| Root-S3 `data` | Bucket `${p}-${e}-data`, Versioning, PAB, SSE | keine | allg. Daten | Versionen leeren, Destroy | Versionen |
| `sqs` | `${p}-${e}-work-queue`, `-dlq`, `-cv-queue`, `-ats-queue`, `-match-queue` | keine | Worker/Queues | Destroy | 5 Queues |
| `iam` | Rolle `${p}-lambda-role`, Policy `${p}-lambda-policy` | s3, work-items | Lambda-Runtime | Destroy | **Name ohne Environment**; Projekt-ID muss eindeutig sein |
| `monitoring` (2x) | Dashboard `${p}-overview`, Alarme `${p}-api-5xx`, `-lambda-errors`, …; zweite Instanz `${p}-mays-orders-*` | api, lambda, dynamodb, sqs | Betrieb | Destroy | Dashboard/Alarme kosten auch bei kurzer Laufzeit |
| `cloudtrail` | Trail `${p}-trail`, Bucket `${p}-cloudtrail-<account>` | keine | Audit | Trail + Bucket-Versionen | **Multi-Region + global events** |
| `health_public` | Bucket `${p}-${e}-health-public`, OAC, CloudFront? | keine | Health-Status | Bucket/Verteilung | globale Bucket-Namen |
| `health_plane` | `${p}-${e}-health-writer/-publisher`, `${p}-${e}-health-state`, Schedule `rate(5 minutes)`, Alarme | iam, health_public | Health-Publishing | Destroy; Schedule stoppen | dauerhaft laufender Schedule |
| `orders_reader` | Lambda `${p}-orders-reader` | api, mays_orders | Orders-Fassade | Destroy | fremdes Projekt |
| `mays_orders` | kompletter Orders-Stack `${p}-mays-orders-*` inkl. Cognito/DynamoDB/SQS/Lambda/API | keine | Orders-Service | eigener Destroy | **fremdes Projekt, immer mitdeployt** |

- `p` = `project_name`, `e` = `environment`, Prefix `${p}-${e}`.
- Statisch ~190 `aws_`-Ressourcenblöcke (Module gezählt). Die exakte Zahl
  hängt von `count`/`for_each` und Apply-Zeitpunkten ab; ein `terraform plan`
  mit Provider-Refresh ist in G0 **AWS-REQUIRED** und wurde nicht ausgeführt.
- Region: `eu-central-1` (Default `var.aws_region`).
- Provider: `hashicorp/aws ~> 6.0` (Lock: 6.67.0), `hashicorp/time ~> 0.11`;
  Terraform `>= 1.6, < 2.0`.
- Backend: S3, `key = "terraform.tfstate"`, `encrypt = true`, Lock-Tabelle
  `mays-ris-tf-lock` als Default; der Installer überschreibt Bucket/Region/
  Lock-Tabelle und setzt `workspace_key_prefix = "env:"`.

### API-Routen (tatsächlich gezählt)

- **54** `route_key`-Ressourcen in `terraform/modules/api/main.tf`.
- **24** Routen mit `/v1/partner/`:
  - 23 Partner-Profile-/CV-Routen (Manual 5, CV 5, Dokument 3, CVSP 5, ATS 5)
  - 1 bestehende Route `POST /v1/partner/agents/{agentId}/execute`
- Keine `{proxy+}`-Route.
- Die 23 Profil-Routen verwenden den Human-JWT-Authorizer; die M2M-Route
  `/v1/m2m/...` nutzt den separaten M2M-Authorizer mit Scope
  `ris-api/m2m/execute`. Die Partner-Agent-Route nutzt Human-JWT und
  `X-Api-Credential`.

Die im Auftrag genannte Zahl „20" ist **nicht** der Ist-Stand; verbindlich
sind 24 `/v1/partner/*`-Routen (davon 23 Profil-/CV-Routen).

## 3. Isolationsnachweis

### Vorgesehene Testidentität

- Projekt-ID: `ris-r07b-<runid>` (kurz, z. B. 8 Hex-Zeichen); Environment
  `test`; Region `eu-central-1`.
- Workspace = Projekt-ID (verbatim); State-Pfad
  `env:/<project>/test/terraform.tfstate`.
- Backend-Bootstrap (falls genutzt): Bucket `<project>-tf-state-test`,
  Lock-Tabelle `<project>-tf-lock`; beides projekt-eigen.
- Kein Import, kein Zugriff auf `ris-dev`-State.

### Namensgrenzen

| Namensraum | Kollisionsrisiko | Mitigation |
|---|---|---|
| DynamoDB-Tabellen | account/region-lokal | Projekt-ID im Namen |
| Lambda/API/SQS/IAM | account/region-lokal | Projekt-ID im Namen |
| IAM-Rolle `${p}-lambda-role` | account-lokal, **ohne Environment** | Projekt-ID darf nur einmal/Environment verwendet werden |
| S3-Buckets | **global** | eindeutige Projekt-ID; read-only `head-bucket` vor Apply |
| Cognito-Prefix-Domain | **global** | eindeutige Projekt-ID; Domain `${p}-${e}` |
| CloudTrail-Trail/Bucket | account/region + globaler Bucket | eindeutige Projekt-ID; Trail `${p}-trail` |
| CloudWatch-Dashboard/Alarme | account/region-lokal | Projekt-ID im Namen |
| Terraform-State | Bucket global, Key pro Workspace | eigener Prefix + eigene Lock-Tabelle |

**Fazit:** Die Ressourcen- und State-Isolation ist durch die Projekt-ID
konstruktiv gegeben; die globale Eindeutigkeit von S3/Cognito-Domain/Trail ist
ohne AWS-Lesezugriff nicht bewiesen und bleibt ein **read-only Preflight**
(`head-bucket`, `cognito-idp describe-user-pool-domain`,
`cloudtrail describe-trails`) vor dem Apply.

### Kritischer Blocker: Root koppelt Mays-Orders

`terraform/main.tf` enthält **immer** `module "mays_orders"` und
`module "orders_reader"`; es gibt keinen `count`/`enabled`-Schalter. Ein
Apply des RIS-Roots erzeugt daher zusätzlich einen vollständigen, wenn auch
isolierten Orders-Stack `<project>-mays-orders-*`. Das ist kein RIS-only-Test.

- Entweder wird dieser isolierte Orders-Stack ausdrücklich als Teil des
  Testscopes freigegeben (Kosten/Cleanup/„Mays-Orders unverändert" bewerten),
- oder es ist ein RIS-only-Root/Flag nötig (separate Änderung).
- Das generierte `terraform/modules/mays_orders/` ist gitignored und muss aus
  dem gepinnten Fremd-Repo gebaut werden (externer Bootstrap).

Ohne diese Entscheidung ist die geforderte **vollständig isolierte
RIS-Partner-Profil-E2E** nicht belegt.

## 4. State-/Installer-Strategie

Der Installer (`installer/ris.py`) unterstützt:

- `package` → `init` → `validate` → `plan` → `apply`, dry-run per Default,
  `--yes` für Mutationen.
- Workspace = `project_name` verbatim; State-Key
  `env:/<workspace>/<environment>/terraform.tfstate`.
- Explizite Backend-Werte (Bucket/Region/Lock-Tabelle); keine Defaults für
  Bucket/Region.
- `destroy` für den Composite-Scope (RIS + Orders).
- Kein Import bestehender Infrastruktur.

Späterer Ablauf (nicht in G0 ausgeführt):

1. Read-only `sts get-caller-identity` + Account-ID bestätigen.
2. Projekt-ID/Environment/Region bestätigen.
3. Backend-/Workspace-Isolation prüfen (kein bestehender State).
4. `installer.ris package --bundle all`.
5. `installer.ris plan` (AWS-REQUIRED; Provider-Refresh).
6. Plan-Review: nur `<project>`-Ressourcen, keine `ris-dev`-Änderungen.
7. Ressourcenliste und Kostenschätzung freigeben.
8. `apply --yes` nach separater Freigabe.
9. HTTP-E2E-Matrix ausführen.
10. Inventar + Cleanup + Lösch-/Kostennachweis.

## 5. Lambda-Packaging und Runtime

Lokaler Smoke-Test (R07-B-G0):

- `python lambda/build_zip.py --bundle agent`
- 64 Dateien, 190.973 Bytes (0,73 MB), SHA256 `50cbfffcb59bec66…`
- Enthält `handler.py`, `documents.py`, `jobsearch/partner_profile_cursor.py`,
  `jobsearch/partner_profile_repository.py`, `jobsearch/partner_profile_contract.py`.
- Keine `tests/`, `.venv`, `__pycache__`, `.pyc`.
- Keine Secret-Muster (`PRIVATE KEY`, `AWS_SECRET_ACCESS_KEY`, JWT) im ZIP.
- Import-Smoke aus entpacktem ZIP **ohne boto3** erfolgreich; die
  Runtime-Abhängigkeiten sind lazy.
- Runtime laut Terraform: `python3.14`; lokale Tests laufen auf 3.15.
  Verwendete Sprachfeatures sind 3.14-kompatibel; keine nativen Module.
- `boto3`/`botocore` werden von der Lambda-Runtime bereitgestellt; sie sind
  nicht im ZIP. Das ist für die genutzten Client-APIs ausreichend.
- Keine neue Dependency, kein `cryptography`, kein natives Wheel.
- **Offen:** `terraform/modules/mays_orders/lambda/dist/lambda.zip` ist
  gitignored/generiert und wird von `--bundle all` **nicht** neu gebaut;
  der Orders-Stack braucht den Builder/Pin.

## 6. DynamoDB-/GSI-/TTL-Parität

| Aspekt | Terraform | Repository | Status |
|---|---|---|---|
| PK | `resourceId` (S) | `resourceId` | PASS |
| `gsi-user` | `userId` HASH, `resourceType` RANGE, ALL | Query `userId = :u`, Typfilter als KeyCondition | PASS |
| `gsi-parent` | `parentId` HASH, ALL | Query `parentId = :p` | PASS |
| TTL | `expiresAt`, enabled | Idempotenz + Cursor `expiresAt` | PASS (asynchron) |
| Kapazität | 10/2/5 | Counter-Transaktionen | PASS lokal |
| Transaktionen | Table + Indexe | max. 1 Aktion/Item, `TransactWriteItems` | PASS lokal |
| ConsistentRead | n/a | GetItem ja, GSI nein | PASS |
| Reservierte Wörter | n/a | `#c`/`#s`-Aliase | PASS lokal |
| Leere GSI-Keys | n/a | Counter ohne `parentId`, Cursor ohne `parentId` | PASS |
| Scans | n/a | nur Legacy-Guard `_scan_children` | **IAM-Lücke** |

**IAM-Blocker:** Die Policy `lambda_dynamodb_partner_profiles` erlaubt
`PutItem/GetItem/Query/DeleteItem/UpdateItem/TransactWriteItems`, aber **kein
`dynamodb:Scan`**. Der F-5-Legacy-Pfad (`_scan_children`, strongly consistent
paginated scan) würde in AWS mit `AccessDeniedException` scheitern. Das ist
für frische Testressourcen ohne Legacy-Counter nicht relevant, aber für den
F-5-Produktionspfad und die Release-Aussage **kritisch**.

Die 33 DynamoDB-Local-Tests decken Schema, GSIs, TTL-Feld, Counter,
Idempotenz, Cursor, Legacy-Scan und Concurrency ab. AWS-only bleiben:
echtes TTL-Löschen, reale GSI-Konvergenz unter Last, echte
`TransactionConflict`-Häufigkeit, `Scan`-IAM, Throttling.

## 7. Sichere Cursor im Cloudbetrieb

| Prüfung | Ergebnis |
|---|---|
| Zufall | `secrets.token_urlsafe(32)` |
| Speicherkey | `cursor#SHA256(token)`; kein Roh-Token |
| Klartext im Token | nein |
| Logs | Modul loggt/printet keine Tokens |
| Identität | userId/tenantId/partnerApplicationId/issuer exakt |
| Query | Scope/ResourceType/ParentId digest; Limit bewusst nicht gebunden |
| TTL | 15 min, explizite Prüfung + `expiresAt` TTL |
| Cleanup | best-effort Delete bei Ablauf |
| IAM | PutItem/GetItem/DeleteItem vorhanden |
| Listen | `CursorToken` hat kein `payload`; `attribute_exists(payload)` + Systemtyp-Ausschluss |
| Kapazität/Hierarchie | Cursor-Items haben keinen `parentId`, keinen Counter, kein `payload` |
| Wachstum | ein Item pro Seite, TTL 15 min; TTL ist **nicht** sofort |
| Fehlende Rechte | Put/Get/Delete → 5xx; kein 400 |

## 8. JWT-/Partner-Dual-Auth

- Human-Authorizer: `identity_sources = ["$request.header.Authorization"]`,
  Issuer `https://<pool-endpoint>`, Audience = Human-App-Client-ID.
- M2M-Authorizer: eigener Client, Scope `ris-api/m2m/execute`.
- Partner-Profil-Routen: Human-JWT **und** `X-Api-Credential`; Lambda prüft
  Credential-Digest/Status/Expiry, Partner-Registry (Client-ID, API-Profile,
  Tenant, ACTIVE), Tenant-Claim und Issuer.
- Keine separate Entitlements-Tabelle für Profil-Routen; die Bindung läuft
  über Credential/Profile/Registry. Das ist der bestehende Vertrag.
- CORS ist per Default **aus** (`api_cors_origins = []`); E2E per curl/SDK
  möglich, Browser-Test braucht explizite Origin.
- Fehlende Testidentitäten: Cognito-User, API-Profile, Credential und
  Partner-Application sind **nicht vorhanden** und dürfen in G0 nicht
  angelegt werden.

## 9. HTTP-E2E-Testmatrix

Klassifikation: **LV** = lokal verifiziert (Fake/DynamoDB Local),
**AWS** = AWS-E2E geplant, **ID** = synthetische Testidentität erforderlich,
**BLOCKED** = aktuell nicht durchführbar.

| # | Fall | Klasse | Anmerkung |
|---|---|---|---|
| 1 | Kein JWT | LV / AWS | Authorizer/Handler |
| 2 | Ungültiger JWT | LV / AWS | |
| 3 | Falscher Issuer | LV / AWS | |
| 4 | Fehlende/falsche Partner-Credential | LV / AWS | 401/403 |
| 5 | Gültiger Testbenutzer + Testpartner | ID / AWS | Credential/Registry nötig |
| 6 | Cross-User | LV / AWS / ID | 404/403 |
| 7 | Cross-Tenant | LV / AWS / ID | 403 |
| 8 | Cross-Partner | LV / AWS / ID | 403 |
| 9 | Cross-Issuer | LV / AWS / ID | 403/404 |
| 10 | Manual CRUD | LV / AWS | |
| 11 | CVDocument Create | LV / AWS | |
| 12 | Upload-Ticket | LV / AWS / ID | S3 presign |
| 13 | Synthetischer PDF-Upload | AWS | keine echten CVs |
| 14 | `HeadObject`-Complete | LV (Fake) / AWS | |
| 15 | CV-Download | LV (Fake) / AWS | Presigned URL |
| 16 | CVSearchProfile CRUD | LV / AWS | |
| 17 | ATSSearchProfile CRUD | LV / AWS | |
| 18 | Kanonische Jobsearch-v1-Responses | LV (ATS/CVSP) / **BLOCKED (CVDocument)** | P1-1 |
| 19 | Versionskonflikte | LV / AWS | 409 |
| 20 | 10-CV-Grenze | LV / AWS | |
| 21 | 2-CVSP-Grenze | LV / AWS | |
| 22 | 5-ATS-Grenze | LV / AWS | |
| 23 | Parallele Creates | LV (Local) / AWS | reale AWS-Concurrency |
| 24 | Idempotenter Retry | LV / AWS | 24 h |
| 25 | Stale-Version | LV / AWS | 409 |
| 26 | Parent-Delete mit Kindern | LV / AWS | 409 |
| 27 | Delete-vs-Create | LV (Local) / AWS | Guard |
| 28 | Cursor erste Seite | LV / AWS | |
| 29 | Cursor zweite Seite | LV / AWS | |
| 30 | Fremder Cursor | LV / AWS / ID | 400 |
| 31 | Abgelaufener Cursor | LV / AWS | 400 |
| 32 | Manipulierter Cursor | LV / AWS | 400 |
| 33 | Cross-Parent-Cursor | LV / AWS | 400 |
| 34 | Cross-Identity-Cursor | LV / AWS / ID | 400/404 |
| 35 | S3-Versioning aktiv | LV (TF/statisch) / AWS | |
| 36 | Soft Delete/Delete-Marker | LV (Fake) / AWS | |
| 37 | Metadaten nach Fehler | LV / AWS | 502, Retry |
| 38 | Fremdes Dokument verhindert | LV / AWS / ID | |
| 39 | Alte S3-Versionen korrekt erkannt | AWS / **R08 OPEN** | Version-Purge |
| 40 | `physicalPurge:false` | LV / AWS | korrekt |

## 10. S3-Testplan

1. Bucket-Versioning/PAB/SSE per Terraform/Describe prüfen (AWS).
2. Upload-Ticket für synthetische PDF; PUT; `HeadObject`; `ready`.
3. Download nur Eigentümer; fremder Zugriff 404/403.
4. Nicht-`ready` → 409; Parent mit Kindern → 409 ohne S3-Änderung.
5. S3-Fehler → 502, Metadaten bleiben, Guard wird freigegeben, Retry.
6. Delete erzeugt Delete-Marker; `physicalPurge:false`.
7. Alte Versionen bleiben bestehen; R08-Erasure separat.
8. Cleanup muss **alle Versionen + Delete-Marker** löschen, nicht nur aktuelle
   Objekte.

## 11. Kosten- und Ressourcenbudget

Annahmen: ein Lauf ≤ 4 h, 2 synthetische User/Partner, ≤ 12 CVs, ≤ 4 CVSP,
≤ 12 ATS, ≤ 200 HTTP-Requests, wenige MB S3, keine NAT/VPC/EC2/RDS.

| Komponente | Annahme | Konservativ |
|---|---|---|
| API Gateway | 200 Requests | < 0,01 USD |
| Lambda | 200 Invocations, 128 MB, < 1 s | < 0,01 USD |
| DynamoDB | < 20k WRU/RRU, < 50 MB | < 0,05 USD |
| S3 | < 50 MB, < 2k Requests, Versionen | < 0,05 USD |
| CloudWatch Logs | < 100 MB | < 0,50 USD |
| CloudWatch Alarme/Dashboards | 20 Alarme, 2 Dashboards, 4 h | < 0,30 USD |
| CloudTrail | Multi-Region, wenige Events | < 0,10 USD |
| Cognito/SQS/EventBridge | Testumfang | < 0,05 USD |
| Orders-Stack (mitdeployt) | gleiche Größenordnung | < 0,30 USD |
| **Summe** | | **< 2 USD, harte Obergrenze < 5 USD** |

- Keine NAT-Gateways/VPC-Endpunkte/EC2/RDS in den Modulen gefunden.
- Health-Publisher läuft `rate(5 minutes)` → ca. 48 Invocations/4 h.
- Ein Budgetalarm ist **keine harte Grenze**; manueller Stop und
  Kostenprüfung sind Pflicht.
- Bei längerer Laufzeit oder Datenverkehr kann die Schätzung steigen; dann
  **BLOCKED** statt uncontrolled run.

## 12. Cleanup-Plan

1. `installer.ris destroy` mit demselben Projekt/Environment/Backend
   (`--yes`) für RIS + Orders; vorher `plan -destroy` reviewen.
2. Versionierte Buckets **vor** Destroy leeren:
   - `${p}-${e}-documents`
   - `${p}-${e}-data`
   - `${p}-${e}-health-public`
   - `${p}-${e}-health-state`
   - `${p}-cloudtrail-<account>`
   - jeweils `list-object-versions` + `delete-objects` für `Versions` **und**
     `DeleteMarkers`.
3. Nach Destroy: Backend-Bucket `${p}-tf-state-${e}` (alle Versionen) und
   Lock-Tabelle `${p}-tf-lock` löschen; State-Objekt
   `env:/<project>/<env>/terraform.tfstate` prüfen.
4. Cognito-Testbenutzer/Pool/Domain, API, Lambda, SQS, DynamoDB, IAM,
   Loggruppen, Alarme/Dashboards/Trail prüfen.
5. Unmanaged-Reste über Tag `Project=<project>` (Resource Groups Tagging API)
   und S3-/DynamoDB-/Cognito-/Lambda-/IAM-Listen verifizieren.
6. S3-Versionen/Delete-Marker sind ein separater Nachweis; ein erfolgreicher
   `terraform destroy` allein genügt nicht.
7. Keine Löschung in R07-B-G0.

## 13. Offene Findings

### F-5 PARTIAL
- Sicherer Legacy-Delete ist implementiert und lokal/local-DynamoDB getestet.
- **IAM `dynamodb:Scan` fehlt** in der Partner-Profile-Policy; der
  Legacy-Scan ist in AWS derzeit nicht ausführbar.
- Offline-Counter-Reconciliation/Backfill bleibt offen.
- Für frische R07-B-Ressourcen (Counter ab Erstellung) nicht blockierend;
  für historische Bestandsdaten und die F-5-Release-Aussage blockierend.

### P1-1 OPEN — CVDocument-Kompatibilitätsmatrix

| Feld | Jobsearch CVDocumentV1 | RIS | Kompatibel? |
|---|---|---|---|
| `cvId` | required | vorhanden | ja |
| `documentId` | required string | kann `null` sein (vor Ticket) | **nein** |
| `filename` | required 1..255 | `name` | **nein** |
| `contentType` | required | vorhanden | ja |
| `sizeBytes` | required integer ≥ 1 | `size` (initial 0) | **nein** |
| `processingStatus` | `pending/ready/failed/deleted` | `pending/upload_pending/ready/delete_failed/error` | **nein** (Mapping nötig) |
| `createdAt/updatedAt/version` | required | vorhanden | ja |

P1-1 verhindert einen vollständigen **Jobsearch-v1-CVDocument**-Vertrag. ATS
und CVSearchProfile sind davon nicht betroffen. Für den R07-B-Testscope kann
die RIS-eigene CV-Form getestet werden; eine Jobsearch-v1-CVDocument-
Konformitätsaussage ist **BLOCKED**.

### R08 OPEN
Physische Löschung aller S3-Versionen/Delete-Marker und Erasure bleiben
separat. `physicalPurge:false` bleibt korrekt.

## 14. Voraussetzungen für Cloud-Freigabe

1. **Entscheidung Mays-Orders-Kopplung:** isolierten Orders-Stack ausdrücklich
   freigeben **oder** RIS-only-Root/Flag bereitstellen. Ohne Entscheidung kein
   „Mays-Orders unverändert"-Nachweis.
2. **IAM:** `dynamodb:Scan` für die Partner-Profile-Tabelle ergänzen (nur für
   den begrenzten Legacy-Pfad) **oder** Legacy-Reconciliation offline
   verlagern und den Request-Pfad entfernen; danach IAM-Test.
3. **Account/Region:** `240571105849` / `eu-central-1` read-only per STS und
   Provider-Config bestätigen; dedizierten Testaccount prüfen.
4. **Globale Namen:** S3-Buckets, Cognito-Domain, CloudTrail-Trail vor Apply
   read-only auf Kollision prüfen.
5. **Testidentitäten:** synthetischer Cognito-User, API-Profile, Credential,
   Partner-Application/Registry, ggf. zweiter Tenant/Partner — erst nach
   separater AWS-Freigabe.
6. **Artefakte:** `terraform/modules/mays_orders` aus dem Pin bauen;
   `package --bundle all`; ZIP-Hash notieren.
7. **Kosten/Cleanup:** Zeitfenster, Budget, Stop-Bedingung und
   Version-Purge-Verantwortung freigeben.

## 15. Nächster R07-B-Ausführungsplan

1. Read-only Preflight (STS, Backend/Workspace, globale Namen, IAM-Simulation
   mit `iam simulate-principal-policy` für `Scan`).
2. Freigabe Projekt-ID/Environment/Region und Orders-Scope.
3. `package --bundle all`; ZIP-Inventar/Hash.
4. `plan` mit Provider-Refresh; Plan-Diff nur auf `<project>` prüfen.
5. Ressourcen-/Kostenliste freigeben.
6. `apply --yes`.
7. Testidentitäten/Registry/Credential synthetisch anlegen.
8. 40-Fälle-Matrix ausführen; Ergebnisse klassifizieren.
9. Inventar + Cleanup (inkl. S3-Versionen) + Nachweis.
10. R07-B-Abschlussbericht; keine Produktivfreigabe vor R08/P1-1/F-5-Klärung.

## 16. Cloud-Freigabegate

| Frage | Ergebnis |
|---|---|
| Testaccount eindeutig | **NEIN** – nur dokumentierter Dev-Account `240571105849`, nicht read-only verifiziert; kein dedizierter Testaccount |
| Region eindeutig | `eu-central-1` dokumentiert, unverifiziert |
| State isoliert | **JA (Design)** – eigener Workspace/Prefix/Backend |
| Namenskollisionen ausgeschlossen | **TEILWEISE** – konstruktiv, globale Prüfung AWS-REQUIRED |
| Testbenutzer/-partner vorgesehen | **JA, aber nicht vorhanden** – AWS-Freigabe nötig |
| Lambda-Paket vollständig | **JA lokal** – 64 Dateien, Import-Smoke, keine Secrets |
| Partner-Routen korrekt | **24 tatsächlich** (23 Profil/CV + 1 Agent); keine Wildcards |
| Kosten überschaubar | **JA geschätzt < 5 USD/4 h**, inkl. Orders-Stack; Budgetalarm keine harte Grenze |
| Cleanup vollständig geplant | **JA geplant**, inkl. S3-Versionen/Backend; nicht ausgeführt |
| P1-1/F-5 korrekt eingeordnet | F-5 PARTIAL + IAM-Scan-Blocker; P1-1 blockiert CVDocument-v1 |

**R07-B = BLOCKED.** G0 ist vorbereitet, aber die Cloud-Ausführung ist wegen
der Mays-Orders-Kopplung, der fehlenden `dynamodb:Scan`-Berechtigung und der
noch nicht verifizierten Testidentität/-Account-Grenze nicht freigabefähig.

## 17. Status

- **IMPLEMENTED:** G0-Analyse, Architekturmatrix, E2E-/S3-/Kosten-/Cleanup-Plan.
- **VERIFIED-LOCAL:** 608 lokale Tests (33 DynamoDB-Local), Packaging-Smoke,
  Terraform fmt/validate, OpenAPI.
- **SPECIFIED:** Testidentitäten, 40-Fälle-Matrix, Cleanup-Schritte.
- **OPEN:** F-5 Counter-Reconciliation + IAM `Scan`; P1-1; R08.
- **AWS-REQUIRED:** Account-/Region-/Kollisions-/Plan-/Apply-/E2E-/Cleanup-Schritte.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
