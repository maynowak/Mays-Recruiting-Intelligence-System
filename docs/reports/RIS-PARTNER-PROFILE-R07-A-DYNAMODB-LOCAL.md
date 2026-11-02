# RIS-PARTNER-PROFILE-R07-A — REAL DYNAMODB LOCAL INTEGRATION

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor R07-A | `d7ada75` (`fix(ris): use consistent reads and fail closed on query errors`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| Scope | ausschließlich Mays-RIS |
| AWS-Verbindung / -Mutation | **keine** |

## 2. Lokale Umgebung

Alle Werkzeuge liegen außerhalb des Repositories unter
`%TEMP%\opencode\r07a`, damit weder Venv noch DynamoDB Local in Git
aufgenommen werden können.

| Werkzeug | Version / Herkunft | Prüfung |
|---|---|---|
| Python (Venv) | 3.15.0 (`C:\Python315`) | `python --version` |
| boto3 | 1.43.123 | Import + Client-Erzeugung |
| botocore | 1.43.123 | Import |
| pytest | 9.2.0 | `pytest --version` |
| PyYAML | 6.0.3 | für OpenAPI-Regression |
| Terraform | 1.17.0 | `fmt -check`, `validate` |
| Java | Temurin JRE **21.0.13+9 LTS** | `java -version` |
| DynamoDB Local | **3.3.2** (Jetty 12.1.14) | `-version`/Startlog |
| AWS CLI / Docker / WSL | nicht vorhanden | nicht benötigt |

### Bezug und Integrität

| Artefakt | SHA256 | Status |
|---|---|---|
| Temurin JRE 21.0.13+9 (`OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip`) | `2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628` | **OK** |
| Temurin JDK 21.0.13+9 (nur zum Kompilieren des Launchers) | `a4dbaa05fca4bd89d84584e58c459bd732efebb1722af80ab13c6516832004f9` | **OK** |
| DynamoDB Local `v2.x/dynamodb_local_latest.tar.gz` | `7a94eb65f81aee270738751a4e5e3e6a7ad02a5d25194f55b83e08ec2ba6342b` | **OK** (AWS-Published `.sha256`) |

Es wurde keine systemweite Installation und keine PATH-Änderung
vorgenommen.

## 3. Loopback-Härtung

DynamoDB Local 3.3.2 unterstützt **kein** `-bindAddress`; Jetty bindet mit
`new Server(port)` an die Wildcard-Adresse. Windows Firewall hatte für die
heruntergeladene `java.exe` automatische Inbound-Allow-Regeln (Profil Public,
Remote `Any`) angelegt. Ein reiner Start auf Port 18000 wäre damit im LAN
erreichbar gewesen.

Deshalb wird der offizielle `ServerRunner` verwendet, aber der Jetty-Connector
**vor** `start()` auf `127.0.0.1` gesetzt. Der Launcher nutzt die öffentliche
Factory `ServerRunner.createServerFromCommandLineArgs(args)` (sie startet den
Server nicht selbst) und reflektiert nur das private `server`-Feld:

```java
DynamoDBProxyServer proxy = ServerRunner.createServerFromCommandLineArgs(args);
Field f = DynamoDBProxyServer.class.getDeclaredField("server");
f.setAccessible(true);
Server server = (Server) f.get(proxy);
for (Connector c : server.getConnectors()) {
    ((AbstractNetworkConnector) c).setHost("127.0.0.1");
}
proxy.start();
proxy.join();
```

Verifikation:

- `Get-NetTCPConnection -LocalPort 18000` → `LocalAddress 127.0.0.1`
- Verbindung über die LAN-IP `192.168.178.31:18000` → `ConnectionRefused`
- keine AWS-Credentials, kein AWS-Endpoint, `-disableTelemetry`

Der Dienst wurde nach dem Testlauf gestoppt; Port 18000 ist geschlossen.

### Reproduzierbarer Start

```powershell
$base = "$env:TEMP\opencode\r07a"
$py   = "$base\venv\Scripts\python.exe"
$java = "$base\tools\jre21\jdk-21.0.13+9-jre\bin\java.exe"
$ddb  = "$base\tools\dynamodb-local"

# Einmalig:
python -m venv $base\venv
& $py -m pip install boto3 pytest pyyaml

# Launcher einmalig mit dem Temurin-JDK kompilieren:
& "$base\tools\jdk21\jdk-21.0.13+9\bin\javac.exe" `
  -cp "$ddb\DynamoDBLocal.jar" -d "$base\tools\launcher" R07Launcher.java

& $java "-Djava.library.path=$ddb\DynamoDBLocal_lib" `
  -cp "$base\tools\launcher;$ddb\DynamoDBLocal.jar" R07Launcher `
  -inMemory -sharedDb -port 18000 -disableTelemetry

$env:RIS_TEST_DYNAMODB_ENDPOINT = "http://127.0.0.1:18000"
& $py -m pytest tests/integration/test_partner_profile_dynamodb_local.py -q
```

Der Endpoint-Guard akzeptiert weiterhin ausschließlich Loopback und
`ris-r07g0-*`-Tabellen; die Testsuite löscht nur ihre eigene Tabelle.

## 4. Ergebnis der 23 Integrationstests

**23/23 PASS** gegen DynamoDB Local 3.3.2:

| Klasse | Fälle | Ergebnis |
|---|---|---|
| `TestPersistence` | 7 | PASS |
| `TestCapacity` | 8 | PASS |
| `TestIdempotency` | 5 | PASS |
| `TestGsiPagination` | 3 | PASS |

Damit sind real verifiziert:

- Create/Get/Update/Delete mit echtem `TransactWriteItems`
- Capacity 10 CVs / 2 CVSP / 5 ATS inkl. atomarem letztem Platz
- Delete gibt Kapazität frei; Delete-vs-Create ohne Orphan
- Idempotenz-Replay, Konflikt, parallele Retries, Ablauf-Wiederverwendung
- GSI-Pagination mit `LastEvaluatedKey`, Fremdidentität ohne Treffer
- Fresh Repository liest zuvor gespeicherte Daten
- Optimistisches Locking und 409 bei stale Version

## 5. Im Testlauf gefundene und behobene Integrationsfehler

Die In-Memory-Fakes hatten mehrere echte DynamoDB-Regeln nicht abgebildet.
Diese Fehler waren mit Fakes unsichtbar und sind jetzt behoben:

| ID | Befund | Fix |
|---|---|---|
| R07A-1 | `boto3.resource(...).meta.client` trägt die DynamoDB-Resource-Transformation und serialisiert die low-level `TransactWriteItems`-Items **doppelt** (`S` → `M`). | Repository erzeugt für Transaktionen einen **plain client** mit gleichem Endpoint/Credentials/Config. |
| R07A-2 | `count` und `state` sind reservierte DynamoDB-Wörter; Condition-/Update-Ausdrücke schlugen fehl. | `#c`/`#s`-Aliase mit `ExpressionAttributeNames` in allen Counter-/Guard-Ausdrücken. |
| R07A-3 | Platzhalter `:sys-idem`/`:sys-guard` sind syntaktisch ungültig. | `:sysidem`/`:sysguard`. |
| R07A-4 | Counter-Items hatten `parentId: ""`; ein leerer GSI-Key ist ungültig. | `parentId` bei Counter-Items weggelassen (sparse index). |
| R07A-5 | boto3 Resource-Reads liefern `Decimal`; der Contract erwartet `int` (z. B. `CVDocument.size`). | `_normalize_numbers` beim Read (Decimal → int/float), keine Validierungsabschwächung. |
| R07A-6 | `resourceType` ist Range-Key von `gsi-user` und darf nicht im `FilterExpression` stehen. | Typfilter in `KeyConditionExpression`; Systemitems über `attribute_exists(payload)` ausgeschlossen. |
| R07A-7 | Terraform definierte `tenantId` als Attribute, ohne es in einem Key zu verwenden; AWS lehnt das ab. | Unbenutzte `tenantId`-Attribute-Definition entfernt; statischer Test ergänzt. |

Zusätzlich korrigiert (nur Test-Harness):

- Dummy-Access-Key mit gültigem AWS-Format (`RISR07G0LOCALTEST0`), da
  DynamoDB Local die Key-Form prüft.
- `_ats()` gibt die vom Repository gelieferte (ggf. idempotent replayte) ID
  zurück.
- `_poll()` gibt den gefundenen Wert statt `True` zurück.
- Fakes akzeptieren native Query-Werte und `ExpressionAttributeNames`.

## 6. Regression

| Umgebung | Ergebnis |
|---|---|
| Venv + `RIS_TEST_DYNAMODB_ENDPOINT` (inkl. 23 Integrationstests) | **517 passed, 0 skipped, 256 subtests** |
| System-Python ohne boto3/Endpoint (Integrationstests übersprungen) | **494 passed, 23 skipped, 256 subtests** |
| Terraform `fmt -check` (relevante Dateien) | PASS |
| Terraform `validate` | PASS (vorbestehende Warnings) |
| `git diff --check` | PASS |

## 7. Verbleibende Befunde

| ID | Status |
|---|---|
| F-1 ConsistentRead / fail-closed | **CLOSED** (R07-FIX-01, real mitgetestet) |
| F-2 GSI eventual consistency | dokumentiert; Tests pollen, keine Geschäftsentscheidung auf GSI |
| F-3 TTL asynchron | Logik korrekt; echtes TTL-Löschen wurde nicht zeitlich erzwungen |
| F-4 `TransactionConflict` ohne Retry | OPEN; im lokalen Lauf nicht ausgelöst |
| F-5 Delete setzt Counter voraus (Legacy) | OPEN; kein Legacy-Item ohne Counter im Test |
| F-6 Cursor base64/reversibel | OPEN (Hardening) |
| P1-1 CVDocument-Naming/Status | OPEN, kein Blocker |

## 8. R07-B

R07-B (AWS E2E) bleibt **NOT RUN / NOT DEPLOYED**. Voraussetzungen unverändert:
isolierter Workspace, eu-central-1, synthetische Daten, Budget-/Cleanup-Plan,
keine Mutation von `ris-dev`.

## 9. Status

- **IMPLEMENTED:** sichere lokale DynamoDB-Local-Umgebung, Loopback-Launcher,
  echte Integrationstests, sieben Integrationsfixes.
- **VERIFIED:** 23/23 Integrationstests; 517/517 Gesamtsuite; Terraform.
- **OPEN:** F-4, F-5, F-6, P1-1.
- **NOT RUN:** AWS-E2E, reales S3, reales TTL-Verhalten.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.

**R07-A: GO.**
