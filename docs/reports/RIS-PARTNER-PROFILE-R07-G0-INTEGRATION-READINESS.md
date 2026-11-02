# RIS-PARTNER-PROFILE-R07-G0 — INTEGRATION READINESS & TEST HARNESS

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Repository | `C:\Users\DCI-Student\projekte\Mays-Recruiting-Intelligence-system` |
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor R07-G0 | `edeb5bb` (`feat(ris): add partner ATS search profile CRUD API`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| R01–R06-Berichte | vorhanden (`docs/reports/RIS-PARTNER-PROFILE-R0*`) |
| Jobsearch | read-only, Referenz `origin/main@0129559` |

Es wurden keine Bereinigungen, Resets, Stashes, Pushes oder Merges
durchgeführt. R07-G0 hat keine AWS-Ressource verändert.

## 2. Infrastruktur-Matrix

| Komponente | Quelle | Ist-Zustand | R07-Relevanz |
|---|---|---|---|
| Partner-Profile-Tabelle | `terraform/modules/dynamodb/main.tf` | `${project}-${env}-partner-profiles`, PAY_PER_REQUEST, PK `resourceId` | Persistenz aller vier Ressourcentypen + Systemitems |
| `gsi-user` | ebd. | HASH `userId`, RANGE `resourceType`, Projektion ALL | benutzerweite Listen, keine Scans |
| `gsi-parent` | ebd. | HASH `parentId`, Projektion ALL | Kindlisten (CV→CVSP, CVSP→ATS) |
| TTL | ebd. | `expiresAt`, enabled | nur Idempotency-Cleanup, nicht Korrektheit |
| IAM | `terraform/modules/lambda/main.tf` | PutItem, GetItem, Query, DeleteItem, UpdateItem, TransactWriteItems; Tabelle + `/index/*` | Repository braucht kein Scan/Describe |
| Repository | `jobsearch/partner_profile_repository.py` | TransactWriteItems, ConditionChecks, GSIs, Cursor | Kern von R07-A |
| API-Routen | `terraform/modules/api/main.tf` | 5 explizite ATS-Routen, JWT-Authorizer, kein Proxy | R07-B prüft Gateway-Auth live |
| Handler-Auth | `lambda/handler.py` `_partner_profile_context` | JWT (`tokenUse=access`), `X-Api-Credential`, Partner-Registry, Tenant-Claim, `iss` | Dual-Auth-Kette |
| OpenAPI | `docs/api/openapi-platform.yaml` | `ATSSearchProfileV1`, `ATSCriteriaV1`, `ATSProfileInput`, 5 Pfade | Vertragsdokumentation |
| Dokumente | `terraform/modules/documents/main.tf`, `lambda/documents.py` | Versioning, PAB, SSE AES256, kein Lifecycle | R08-Erasure |
| Test-Harness | `tests/test_partner_profile_integration_harness.py`, `tests/integration/` | neu in R07-G0 | siehe §9 |

## 3. DynamoDB-Schlüssel und Zugriffe

Tabelle: ein Item pro Ressource, `resourceId` als Partition Key (kein Sort Key).

| Repo-Operation | DynamoDB-API | Schlüssel / Index | Konsistenz | Testfall |
|---|---|---|---|---|
| `create` (CV) | TransactWriteItems: Counter-Update `capacity#CV#<user>`, Ressource-Put | PK | strong (Transaktion) | H-1, A-CAP-1 |
| `create` (CVSP) | + ConditionCheck Parent-CV, Guard `lifecycle#CVDocument#<cv>` | PK | strong | H-1, A-CAP-2 |
| `create` (ATS) | + ConditionCheck Parent-CVSP, Guard `lifecycle#CVSearchProfile#<sp>`, Counter `capacity#ATS#<sp>` | PK | strong | H-2, A-CAP-3 |
| `get` | GetItem | PK | **eventual** (`ConsistentRead` fehlt) | F-1, A-P-1 |
| `_get_raw` | GetItem | PK | **eventual** | F-1, A-IDEM-5 |
| `update` | GetItem + PutItem `version = :v` | PK | Read eventual, Write conditional | A-P-3 |
| `delete` | GetItem + TransactWriteItems (Delete + Counter-Update) | PK + Counter | strong | A-CAP-5, A-P-4 |
| `reserve_parent_delete` | TransactWriteItems (Guard-Update + Parent-Check + Child-Counter-Check) | PK + Guard + Counter | strong | H-5, A-RACE-1 |
| `finalize_parent_delete` | TransactWriteItems (Delete + Counter + Guard-Delete + Child-Check) | PK + Guard + Counter | strong | H-5 |
| `list_by_user` | Query `gsi-user` | `userId`/`resourceType` | **eventual (GSI)** | H-6, A-GSI-3 |
| `list_by_parent` | Query `gsi-parent` | `parentId` | **eventual (GSI)** | H-6, A-GSI-1/2 |
| `_ensure_counter` | GetItem + PutItem `attribute_not_exists` | Counter | Read eventual, Write conditional | F-8, A-CAP-* |

Es gibt **keinen** `.scan(`-Aufruf im Repository (statisch geprüft, H-7).

## 4. TransactWriteItems

Jede Create-Transaktion enthält höchstens eine Aktion pro Item. Der Harness
prüft das für alle vier Ressourcentypen sowie für Delete, Reservierung und
Finalisierung (H-1, H-5).

Beispiel ATS-Create:

1. `Put` Idempotency-Item (nur mit Key) – `attribute_not_exists OR expiresAt < :now`
2. `Update` Counter `capacity#ATS#<sp>` – `count < :max`, `count = count + 1`
3. `ConditionCheck` Parent-CVSP – `attribute_exists AND userId/tenantId`
4. `ConditionCheck` Guard – `attribute_not_exists OR state = active`
5. `Put` ATS-Ressource – `attribute_not_exists`

Eigenschaften:

- Kein Zwischenzustand: canceled transaction = keine Kapazitätsbuchung, kein Orphan.
- Parent-Existenz und Lifecycle-Guard sind echte ConditionChecks, keine GSI-Zähler.
- `TransactionCanceledException` wird über `CancellationReasons` klassifiziert:
  Idempotency → Replay/409, Capacity → 409, Parent/Guard → 409, Resource → 409.
- **F-4:** `TransactionConflict` (DynamoDB-interne Nebenläufigkeit) ist kein
  `ConditionalCheckFailed` und wird derzeit als generischer 409 gemappt; ein
  Retry/`5xx`-Pfad fehlt.

## 5. Idempotenz- und TTL-Vertrag

- Schlüssel: `idem#<resourceType>#SHA256(resourceType, userId, tenantId,
  partnerApplicationId, issuer, clientKey)`. Der Roh-Key wird nicht gespeichert.
- Payload-Hash: kanonisches JSON ohne eigene ID, `createdAt`, `updatedAt`,
  `schemaVersion`; ein servergenerierter Retry darf den Hash nicht ändern.
- `expiresAt = now_epoch + 86 400`; TTL-Attribut `expiresAt`.
- Bedingung: `attribute_not_exists(resourceId) OR expiresAt < :now`.
- Replay mit gleichem Hash → ursprüngliche `targetResourceId`.
- Gleicher Key, anderer Hash → 409.
- Abgelaufener Record blockiert **nicht**: die Bedingung ist autoritativ, nicht das
  asynchrone TTL-Löschen. Im Fake nachgewiesen (H-4); echtes TTL-Verhalten ist
  R07-A/AWS.
- **F-1:** Nach einem Timeout liest der Replay-Pfad das Idempotency-Item mit
  `_get_raw` ohne `ConsistentRead`; ein eventual-consistent Miss führt zu 409
  statt Replay.

## 6. Parent-/Lifecycle-Integrität

Kette: `ATS → CVSearchProfile → CVDocument → verifizierter Benutzer`.

- `_check_parent_exists` liest den Parent identitätsgebunden (User/Tenant/
  Partner/Issuer) und validiert `validate_ats_assignment`.
- Die Transaktion prüft Parent-Existenz und `state != deleting` erneut atomar.
- Zweiphasiger Parent-Delete: `reserve` setzt Guard `deleting` + prüft
  Kind-Zähler = 0; `release` rollt bei S3-Fehler zurück; `finalize` löscht
  Ressource, Zähler und Guard atomar.
- Parent-Delete mit ATS-Kindern → 409; keine Kaskade.
- Delete-vs-Create: beide erhöhen/prüfen denselben Kind-Zähler; genau eine
  Operation gewinnt. Im Fake H-5; real R07-A/A-RACE-1.
- **F-5:** `delete` enthält ein Counter-`Update` mit `count > 0`. Existiert für
  ein Legacy-Item kein Counter, schlägt die Transaktion fehl und Delete meldet
  404. Vor R07-A muss entschieden werden, ob Legacy-Items einen Counter
  nachgezogen bekommen.

## 7. GSI und Pagination

- `gsi-user` und `gsi-parent` sind eventual consistent; starke Konsistenz ist
  auf GSIs nicht verfügbar. Geschäftsentscheidungen (Kapazität, Parent,
  Idempotenz) hängen deshalb ausschließlich an autoritativen Items/Counters.
- `Limit` wirkt vor dem `FilterExpression`: Seiten können kürzer als `limit`
  sein; `LastEvaluatedKey` bleibt korrekt.
- Cursor = base64(JSON von `LastEvaluatedKey`). Er ist opak dargestellt, aber
  **nicht verschlüsselt oder signiert** und enthält interne Schlüssel
  (`resourceId`, ggf. `parentId`). **F-6** (Hardening, kein Datenleck: der
  Identitätsfilter bleibt aktiv).
- **F-7:** Schlägt die `gsi-parent`-Query fehl, fällt `list_by_parent` auf
  `list_by_user(limit=1000)` zurück und liefert **keinen** Cursor. Das kann
  still abschneiden und die Pagination-Semantik brechen. Der Fallback darf in
  R07-A nicht als Normalpfad gelten.
- Fremde Identitäten werden zusätzlich per FilterExpression
  (`userId`, `tenantId`, Partner, Issuer) ausgeschlossen; im Fake geprüft.

## 8. S3-Dokument-Lifecycle

- Bucket: Versioning `Enabled`, Public Access Block vollständig, SSE AES256,
  kein Lifecycle.
- Schlüssel: `tenant/{tenantId}/users/{userId}/documents/{docId}` (kein PII).
- Upload-Ticket → PUT → `HeadObject` → `ready`; Download nur nach Head-Check,
  Presigned URL kurzlebig; nicht-`ready` → 409.
- Delete erzeugt bei Versioning einen Delete-Marker; `delete_document_report`
  meldet `deleteMarker` und `physicalPurge: False`.
- `delete_all_for_user` löscht aktuelle Objekte, **nicht** alle Versionen;
  physische Erasure bleibt R08.
- Status der 12 Integrationsfälle: 1–11 sind mit dem S3-Fake unit-verifiziert
  (R04-Tests); echte Versionierung, Delete-Marker und Fehlerpfade sind
  AWS-REQUIRED. Fall 12 (alte Versionen vollständig klassifizieren) ist
  NOT RUN.

## 9. Test-Harness

### 9.1 Endpoint-Guard (`tests/integration/dynamodb_local_support.py`)

- Endpoint muss explizit gesetzt sein (`RIS_TEST_DYNAMODB_ENDPOINT`); kein
  Default, kein Fallback auf AWS.
- Nur Loopback (`127.0.0.1`, `localhost`, `::1`), expliziter Port, kein
  Userinfo/Path/Query. AWS-Hosts, private Netze und DNS-Aliase werden abgelehnt.
- boto3 wird mit statischen Dummy-Credentials und festem `endpoint_url`
  erzeugt; die normale Credential-Kette kann nicht greifen.
- Tabellenname muss `ris-r07g0-*` entsprechen und darf keine geschützten
  Marker (`ris-dev`, `mays-ris`, `partner-profiles`, `prod`, …) enthalten.
- Cleanup löscht ausschließlich die selbst erzeugte Tabelle, erneut nach dem
  Guard geprüft.

### 9.2 Statische/behaviorale Readiness-Tests

`tests/test_partner_profile_integration_harness.py` (36 Tests):

- Guard-Fälle (positiv/negativ), Tabellen-Isolation
- Terraform: PK, beide GSIs, TTL, IAM-Aktionen, kein `Scan`
- 5 explizite ATS-Routen, kein `{proxy+}`
- Repository: kein `.scan(`, beide GSI-Namen, 24-h-TTL-Bedingung,
  Lifecycle-/Child-Counter-Bedingungen, S3-Versioning/`physicalPurge`
- Transaktionsform (eine Aktion je Item) für Create/Delete/Reserve/Finalize
- Idempotenz: Replay, Konflikt, logische Wiederverwendung nach Ablauf
- GSI-Pagination mit Cursor, Fremdidentität ohne Treffer
- Cursor-Charakterisierung (F-6)

### 9.3 DynamoDB-Local-Suite

`tests/integration/test_partner_profile_dynamodb_local.py` (23 Tests):

- Persistenz/CRUD/Version/Fresh-Repository
- Kapazität 10 CVs, 2 CVSP, 5 ATS; paralleler letzter Platz; Delete-freigabe;
  getrennte Parent-Zähler
- Parent-Delete mit Kindern; Delete-vs-Create
- Idempotenz: Replay, Konflikt, Timeout-Retry, Ablauf, parallele Retries (F-1)
- GSI: Konvergenz-Polling, mehrseitige Cursors, kein Fremd-Leak
- Aufruf nur gegen Loopback; ohne Endpoint/boto3 sauberer Skip

## 10. Tatsächlich ausgeführt

| Prüfung | Ergebnis |
|---|---|
| `tests/test_partner_profile_integration_harness.py` | **36 passed** |
| `tests/integration/test_partner_profile_dynamodb_local.py` | **23 skipped** (kein Endpoint, kein boto3) |
| R01–R06-Regression + Harness | **473 passed, 23 skipped, 256 subtests passed** |
| Terraform `validate` | PASS (vorbestehende Deprecation-Warnings) |
| Terraform `fmt -check` (R07-relevante Dateien) | PASS |
| Terraform `fmt -check -recursive` | meldet nur das ignorierte lokale `terraform/ris-dev2.tfvars`; nicht tracked, nicht R07-G0 |
| `git diff --check` | PASS |

Nicht ausgeführt: echte DynamoDB-Transaktionen, echte GSIs, echtes TTL,
S3-Versionierung/Delete-Marker, API-Gateway-Auth, AWS-E2E.

## 11. Testumgebung

| Werkzeug | Gefunden | Konsequenz |
|---|---|---|
| Python | 3.15.0 | Tests laufen; Projektziel ist 3.14 |
| pytest | 9.2.0 | verfügbar |
| boto3 / botocore | **fehlt** | DynamoDB-Local blockiert |
| moto | **fehlt** | kein zusätzlicher AWS-Mock |
| Terraform | 1.17.0 | `validate`/`fmt` möglich |
| Java | **fehlt** | DynamoDB Local nicht startbar |
| Docker | **fehlt** | kein Container-Weg |
| AWS CLI | **fehlt** | kein Live-Smoke |
| DynamoDB Local | **fehlt** | R07-A nicht ausführbar |

`requirements.txt` listet `boto3`, `botocore` und `moto`, sie sind in dieser
Umgebung aber nicht installiert.

### Reproduzierbarer R07-A-Start (nicht ausgeführt)

```powershell
# Einmalig, nur nach Freigabe:
# DynamoDB Local (Java 17+) in ein lokales Werkzeugverzeichnis entpacken
java -Djava.library.path=./DynamoDBLocal_lib -jar DynamoDBLocal.jar `
     -inMemory -port 8000

python -m pip install boto3 botocore
$env:RIS_TEST_DYNAMODB_ENDPOINT = "http://127.0.0.1:8000"
python -m pytest tests/integration/test_partner_profile_dynamodb_local.py -q
```

Es wurde keine systemweite Installation und kein unkontrollierter Download
durchgeführt.

## 12. Befunde und Blocker

| ID | Befund | Schwere | Status |
|---|---|---|---|
| F-1 | `GetItem` ohne `ConsistentRead` in `get`/`_get_raw`: Create→Read kann die Version `null` liefern; Idempotenz-Replay kann 409 statt Replay ergeben | HIGH | OPEN — vor R07-A-Abnahme beheben |
| F-2 | GSIs sind eventual consistent; sofortige Sichtbarkeit ist keine Garantie | Constraint | DOCUMENTED — Tests pollen |
| F-3 | TTL ist asynchron; 24-h-Semantik hängt an `expiresAt < :now` | Design | VERIFIED (Logik) / echtes TTL NOT RUN |
| F-4 | `TransactionConflict` wird nicht unterschieden/retryt, sondern generisch 409 | MEDIUM | OPEN |
| F-5 | Delete setzt existierenden Capacity-Counter voraus; Legacy-Item ohne Counter ist nicht löschbar | MEDIUM | OPEN — R07-A-Fall |
| F-6 | Cursor ist base64, nicht verschlüsselt/signiert, enthält interne Keys | LOW–MED | OPEN — Hardening |
| F-7 | `list_by_parent`-Fallback auf `list_by_user(limit=1000)` ohne Cursor | MEDIUM | OPEN |
| F-8 | Counter-Bootstrap ist Get+Put, nicht atomar | LOW | ACCEPTED — Conditional Put |
| F-9 | `update` prüft die Parent-Kette nicht selbst; der Handler tut es | LOW | ACCEPTED |
| P1-1 | CVDocument `filename`/`name`, `sizeBytes`/`size`, Status-Set | — | OPEN (unverändert) |

**R07-A ist ohne Behebung oder ausdrückliche Waiver von F-1 und F-7 nicht
abnahmefähig.** F-4/F-5 sind vor Produktivbetrieb zu adressieren.

## 13. R07-A-Testplan (DynamoDB Local)

Reihenfolge:

1. F-1 beheben: `ConsistentRead=True` für Create-Response-Read und
   Idempotenz-Replay-Read; Create-Response-Version deterministisch setzen.
2. F-7 beheben oder den Fallback entfernen (Fehler statt stiller Teilmenge).
3. `boto3`/`botocore` installieren, DynamoDB Local starten, Suite ausführen.
4. 23 Tests grün; zusätzlich F-4/F-5 als neue Fälle aufnehmen.
5. Ergebnis als R07-A-Nachweis dokumentieren.

Klassifikation der vorhandenen Fälle: **DYNAMODB-LOCAL** (alle 23). Sie
beweisen reale Conditional Writes, TransactWriteItems, Counter, GSIs und
Concurrency – aber nicht API Gateway, Cognito, IAM oder S3.

## 14. R07-B-AWS-Testplan (nicht gestartet)

Voraussetzungen (vor jedem Start separat freigeben):

- **Konto/Region:** bestehendes Dev-Konto `240571105849`, `eu-central-1`;
  **kein** neues Konto, keine fremden Ressourcen.
- **Isolation:** eigener Workspace/`project_name` (z. B. `ris-r07`), eigene
  Tabelle/Bucket/Pool; niemals `ris-dev`-Bestand mutieren.
- **Daten:** nur synthetische Profile, keine echten CVs, keine Presigned-URLs
  oder Tokens in Logs/Reports.
- **Kostenrahmen:** < 5 USD für das Testfenster (DynamoDB on-demand wenige
  Tausend Operationen, API Gateway/Lambda im Cent-Bereich, S3 wenige Objekte).
  Budget-Alarm und Tag `R07Test=true` verpflichtend.
- **Cleanup:** `terraform destroy` ausschließlich des R07-Workspace; Nachweis,
  dass Tabelle, Bucket, Pool und API entfernt sind; keine fremden Ressourcen.
- **Nachweise:** JWT + `X-Api-Credential` live, Cross-Tenant/Partner/Issuer,
  reale Transaktionen/GSI-Konvergenz, TTL-Verhalten über die 24-h-Grenze
  (Zeitmanipulation nur über Testdaten, nicht über Systemzeit), S3-Versioning/
  Delete-Marker, 502 bei S3-Fehler, Retry.

R07-B bleibt ausdrücklich **NOT RUN / NOT DEPLOYED**.

## 15. P1-1 und R08

- **P1-1** bleibt offen: CVDocument nutzt `name`/`size` und das bestehende
  Status-Set; Jobsearch spricht von `filename`/`sizeBytes`. ATS und die
  Integrationstests hängen nur an `cv_id`, daher **kein Blocker**. Keine
  CVDocument-Migration in R07-G0.
- **R08 Erasure:** S3-Versioning erzeugt Delete-Marker; `delete_all_for_user`
  entfernt nur aktuelle Versionen. Eine vollständige Erasure muss alle
  Objektversionen und Delete-Marker sowie die persistenten Idempotency-,
  Counter- und Guard-Items abdecken. Physische Löschung ist nicht implementiert
  und wird hier nicht behauptet.

## 16. Status

| Status | Inhalt |
|---|---|
| **IMPLEMENTED** | Endpoint-/Tabellen-Guard, Readiness-Harness, DynamoDB-Local-Suite, dieser Bericht |
| **VERIFIED** | 36 Harness-Tests; 473 Regressionstests; Terraform `validate`/gezieltes `fmt`; Transaktionsform; TTL-Logik; S3-Statik |
| **PLANNED** | 23 DynamoDB-Local-Tests (geschrieben, übersprungen) |
| **BLOCKED** | Ausführung von R07-A: kein boto3/botocore, Java, DynamoDB Local, Docker |
| **NOT RUN** | echte DynamoDB-Transaktionen/GSIs/TTL, S3-E2E, API-Gateway-Auth, R07-B |
| **NOT DEPLOYED** | keine AWS-Mutation, kein Apply/Destroy, kein Push/PR/Merge |

## 17. Git-Abschluss

Commit: `test(ris): prepare partner profile integration harness`

Geänderte/neue Dateien:

- `tests/test_partner_profile_integration_harness.py`
- `tests/integration/__init__.py`
- `tests/integration/dynamodb_local_support.py`
- `tests/integration/test_partner_profile_dynamodb_local.py`
- `docs/reports/RIS-PARTNER-PROFILE-R07-G0-INTEGRATION-READINESS.md`
- `docs/AI_AUDITLOG.md`

Die 39 untracked Dateien bleiben unverändert.
