# RIS-DEV2 – wiederverwendbares Partner-/Gateway-/ApplicationV1-E2E-Testhandbuch

**Dokumenttyp:** Operatives Test-Runbook und Regressionstest-Spezifikation  
**Stand:** 2026-11-05 · Erkenntnisse aus RIS-R08-Phasen 15–27  
**Repository-Pfad:** `docs/testing/RIS-DEV2-PARTNER-GATEWAY-E2E-PLAYBOOK.md`  
**Gültigkeit:** ausschließlich `ris-dev2`, synthetische Testdaten. **Nicht** als Produktionsfreigabe verwenden.  
**Status:** Wiederverwendbare Vorlage; konkrete Befehle, Tabellen-/API-Namen und Berechtigungen stets gegen den aktuellen Checkout und die echte DEV2-Umgebung verifizieren.  
**Faktencheck 2026-11-05:** gegen den lokalen RIS-Code und die Phase-27-Evidence geprüft; Code-Referenzen in §16. Hashes und Zähler sind Referenzstand, kein Live-Versprechen für spätere Läufe.

## 0. Zweck und Erfolgskriterium

Dieses Dokument verhindert, dass bei jedem neuen RIS- oder Jobsearch-Release erneut die gesamte Auth-/Partner-/JWT-/DynamoDB-E2E-Testarchitektur untersucht werden muss. Ein neuer Durchlauf soll mit derselben geprüften Testmatrix beginnen und nur Änderungen sowie Abweichungen neu untersuchen.

**Abnahmekriterium des Kernpfads:** Synthetischer Partner und kurzlebiges Credential werden über den vorhandenen RIS-Admin-Lifecycle provisioniert; ein gültiger Access-JWT aus dem bestehenden DEV2-Cognito-Pool authentifiziert einen synthetischen Benutzer; die RIS-API verarbeitet Metrics + ApplicationV1 Create/List/Detail/Patch/Export/Delete und negative Zugriffsfälle korrekt; alle temporären Berechtigungen werden widerrufen und Testobjekte bereinigt. Verbleibende historische INACTIVE-Records werden dokumentiert, nicht ungeprüft gelöscht.

**Getrennte Gates:** (a) DEPLOY VERIFIED, (b) LAMBDA-BOUNDARY E2E, (c) REAL GATEWAY/JWT E2E, (d) CLEANUP VERIFIED, (e) JOBSEARCH-BFF INTEGRATION, (f) PRIVACY/GATE B, (g) PRODUCTION. Ein PASS in (a)–(d) ist weder (e) noch (f)/(g).

## 1. Festgelegte Schutzgrenzen

- **Nur `ris-dev2`:** AWS-Profil `default`, Konto `262370457690`, Region `eu-central-1`, Terraform-Workspace `ris-dev2`. Vor jedem Lauf per STS und Workspace verifizieren; nie auf Profilnamen allein vertrauen.
- **`ris-dev` ist TABU.** Keine State-, Datenbank-, Infrastruktur- oder Authentifizierungsänderung dort.
- Keine Änderung an bestehenden Cognito-Pools, -Clients, Hosted UI, Domains, CloudFront, DNS, ACM, SQS, Event-Source-Mappings, Mays-Orders oder Jobsearch. Eine **kurzlebige synthetische Testidentität** in einem bestehenden DEV2-Pool ist nur im ausdrücklich genehmigten Testumfang zulässig; anschließend löschen.
- Keine Verwendung echter Personen, Bewerbungen, Lebensläufe, Gehälter, E-Mail-Adressen oder Zugangsdaten.
- Kein `terraform apply`, manuelles DynamoDB-Delete, Registry-Write, Credential-Issue, Provisionierung, Cognito-User-Create oder Deployment ohne passende, konkrete Betreiberfreigabe. Eine Testfreigabe ersetzt **nicht** den vom RIS-Code verlangten Admin-Trust-Anchor.
- `RIS_ADMIN_AUTHORIZATION_FILE` ist eine lokale, autorisierte, owner-only JSON-Zuordnung **außerhalb des Repositories**. In keinem Fall selbst eine nicht genehmigte Rolle, Principal-Zuordnung, Tenant-ID oder Genehmigung fingieren. Das JSON allein kodiert laut geprüftem früherem Resolver-Code nicht zwingend Ablauf/Umgebungs-Scope; diese getrennt in Freigabe/Run-Kontext absichern.
- **Windows-Hinweis aus dem geprüften Lauf:** Der bestehende Guard prüft die `os.stat()`-Schreibbits. Auf Windows kann zusätzlich das Read-only-Attribut der Datei erforderlich sein, damit der Modus nicht als group/other-writable gilt. ACL und Dateiinhalt bleiben dabei unverändert; das ist keine Umgehung und keine Abschwächung des Trust Anchors.
- Geheimnisse niemals in Git, Chat, CLI-Argument-Historie, CI-Logs, Terraform-Ausgaben, Screenshots oder Reports veröffentlichen. `RIS_API_KEY` ist ausschließlich serverseitig; Headername `X-Api-Credential`. Der API-Key ist keine Benutzeridentität.
- Alle Agenten/Unteragenten lesen `docs/AI_AUDITLOG.md` vor Beginn; Read-only-Agenten liefern Audit-Evidence an den Commander. Jeden abgeschlossenen logischen Arbeitsschritt mit Tests/Report/Audit sauber committen. Kein Push/Merge ohne Auftrag.

## 2. Architektur des Testpfades

```text
Synthetischer Benutzer / existierender Cognito DEV2 User Pool
      │ gültiger Access JWT (token_use=access, erwarteter client_id/issuer)
      ▼
API Gateway JWT Authorizer
      │ JWT-Claims
      ▼
RIS Agent Lambda ─────── X-Api-Credential (opaker ris_...-Key)
      │                         │
      │                         ▼
      │                Credential Digest Registry
      │                         │
      │                    ACTIVE APIProfile
      │                         │
      └────────► Partner Registry / Client Reservation
                                     │
                       ACTIVE + Tenant + Client + Issuer
                                     ▼
                           ApplicationV1 / Metrics
                                     ▼
                               DynamoDB
```

- Partner-Credential: identifiziert **Partneranwendung**; nie im Browser. Entsteht im vorhandenen RIS-Lifecycle (`ris-admin credential issue`), 32 Zufallsbytes, serverseitiger SHA-256-Digest; Geheimnis nur einmal in owner-only Datei ausgegeben.
- Benutzer-JWT: identifiziert **Benutzer** aus dem **eigenen Pool des Partners**. `iss + sub` ist Eigentumsgrundlage, keine E-Mail-Fallbacks. Partner-/Tenant-/Client-Bindung muss zusätzlich stimmen.
- Partner-Resolver: Reservation `CLIENT#<clientId>` autoritativ; Owner strongly consistent lesen; nur ACTIVE, Client und Tenant müssen übereinstimmen. Ohne Reservation genau **ein** ACTIVE-Datensatz. INACTIVE-Historie ignorieren, nicht willkürlich löschen. Null oder mehrere ACTIVE: fail-closed.

## 3. Einmalige Run-Eingaben / präzise Variablen

Pro Lauf einen eindeutigen, nicht personenbezogenen `RUN_ID` verwenden, z. B. `ris-dev2-e2e-YYYYMMDD-<suffix>`. Kennungen nicht blind wiederverwenden.

| Eingabe | Herkunft | Regel |
|---|---|---|
| AWS-Profil/Konto/Region | Betreiber-Vorgabe + STS | `default` / `262370457690` / `eu-central-1` zwingend verifizieren |
| Terraform-Workspace und State | lokaler Checkout | `ris-dev2`; Lineage und Serial erfassen |
| API Base URL / Routen | aktuelle Terraform-Outputs + deployed OpenAPI/Route-Liste | Keine URL/Route erraten; exakte Pfade aus aktueller Evidence |
| JWT Issuer/Audience/Client | **bestehende** Cognito-/Authorizer-Konfiguration | Korrektes `token_use`, `client_id`, Issuer, Audience kontraktgemäß prüfen |
| Synthetischer Tenant | ausdrücklich genehmigte Betreiber-Zuordnung | Nicht frei aus einem CLI-Argument übernehmen |
| Admin-Principal | STS GetCallerIdentity | Erwartet zuletzt: `arn:aws:iam::262370457690:user/devnemo`; vor jedem Lauf verifizieren |
| `RIS_ADMIN_AUTHORIZATION_FILE` | geschützter lokaler Pfad | Vorhanden, vom eigenen Benutzer kontrolliert, korrekt autorisiert; nie ins Repo |
| `API_PROFILES_TABLE`, `CREDENTIALS_TABLE`, Registry-Tabelle | laufende DEV2-Konfiguration | Keine Tabelle aus Namen ableiten; exakte Identität prüfen |
| Test-Secret-Ausgabepfad | geschützter lokaler Ordner | Absolut, nicht vorhanden, kein Symlink, owner-only; nach Widerruf sicher entfernen |
| Lösch- und Cleanup-Berechtigungen | genehmigter Testscope | Nur RUN_ID-eigene Objekte; niemals globale Scans mit destruktivem Ergebnis |

**Windows/PowerShell-Hinweis:** `RIS_ADMIN_AUTHORIZATION_FILE` als Prozess-Umgebungsvariable im tatsächlich verwendeten Ausführungskontext setzen; `Test-Path` und `aws sts get-caller-identity` sind nur Vorprüfungen und ersetzen die RIS-interne Autorisierungsprüfung nicht. ACL darf nicht durch fremde Benutzer veränderbar sein; die tatsächlichen Plattformprüfungen des Codes beachten.

## 4. Schnellstart – Checkliste vor jedem E2E

### 4.1 Read-only Preflight (keine Änderungen)

- [ ] Exakten Repo-/Branch-/Commit-/Working-Tree-Stand notieren.
- [ ] `docs/AI_AUDITLOG.md` und letzten E2E-Report lesen; offene Befunde übernehmen.
- [ ] STS Account + ARN + Region prüfen; nur `default` verwenden.
- [ ] Terraform-Workspace `ris-dev2`, Lineage, State Serial, `No Changes` bzw. autorisierten Plan prüfen.
- [ ] Deployed Lambda `CodeSha256`, Version/Status, Health 200 und Logging-Fenster verifizieren.
- [ ] API Gateway Authorizer und exakte Test-Endpoints verifizieren.
- [ ] Admin-Trust-Anchor gültig und Tenant passend; kein Rechte-Bypass.
- [ ] Synthetischer Benutzer: Erstellung/Löschung separat autorisiert; bestehende Pool-Konfiguration unberührt.
- [ ] Bestehende Registry-Records, Reservations und aktive Credentials read-only aufnehmen. **INACTIVE-Historie nicht als Fehler an sich behandeln.**
- [ ] Eindeutigen Run-ID, Testdatensatz, Cleanup-Matrix und Stop-Bedingungen vorbereiten.

Beispiel für read-only AWS-Identität (Ausgabe darf keine Credentials enthalten):

```powershell
$env:AWS_PROFILE = 'default'
aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json
aws configure get region --profile default
```

### 4.2 STOP vor jeder Mutation, falls

- Konto/Workspace/Principal nicht stimmen; `ris-dev` betroffen sein könnte.
- Genehmigte Test-Tenant-Zuordnung oder Trust-Anchor fehlt/ungültig ist.
- Test-Credential nur mit ungesichertem Output-Pfad ausgegeben werden könnte.
- Neue oder widersprüchliche ACTIVE-Partner/Reservations die Isolation gefährden.
- Geplanter Apply mehr als die ausdrücklich freigegebenen Ressourcen berührt; PITR/IAM/CloudFront/Cognito-/Health-Lambda-Drift nicht geklärt ist.
- Testdaten nicht sicher eigener RUN_ID zugeordnet oder nicht sauber bereinigbar sind.
- Erwartete JWT-Eigenschaften nicht bestätigt werden können.

## 5. Deployment-Regression: nur wenn tatsächlich Code geändert wird

**Ohne Codeänderung diesen Abschnitt überspringen.** Keine Terraform-Schleife nur für E2E.

1. Geänderten Commit und zielgenauen Diff verifizieren; Tests vor Build.
2. Reproduzierbares Agent-Lambda-Bundle bauen; Anzahl Dateien, Hash (base64) und Artefaktpfad protokollieren.
3. `terraform init/validate` und frischen Plan mit normalem State-Locking; vollständigen JSON-/Text-Diff kontrollieren.
4. Bei Lambda-only-Fix soll Plan `0 add / 1 change / 0 destroy` und **allein** `module.lambda.aws_lambda_function.agent` zeigen. **Hash und gespeicherte Plan-Datei sind build-spezifisch**, nie ungeprüft von einem alten Lauf wiederverwenden.
5. Frühere 6 unbeabsichtigte PITR-Änderungen sind ein bekanntes Risiko. Ungewollten Plan verwerfen, Code-/State-Ursache beheben, neuen überprüften Plan erzeugen.
6. Erst nach separater Freigabe genau den geprüften gespeicherten Plan applyen.
7. Nach Apply: Lambda-CodeSha256 == geprüfter Bundle-Hash; State Serial/Lineage dokumentieren; `No Changes` / Health 200.
8. Keine Mutation an `ris-dev`, Cognito-, CloudFront-, DNS-, ACM-, SQS-, PITR-, anderen Ressourcen.

**Letzter belegter Live-Stand aus Phase 27 (nur Referenz):** Terraform-State Serial 30; Agent-Lambda-CodeSha256 `uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=`; `No Changes` und Health 200. Bei einem neuen Lauf niemals ohne Live-Check voraussetzen.

## 6. Sichere Testpartner-Provisionierung (genehmigter Lifecycle)

Es ist **kein** Jobsearch-Key erforderlich. Für RIS-DEV2 wird ein **separater temporärer synthetischer Test-Key** erstellt. Die reale Vercel-Umgebungsvariable `RIS_API_KEY` bleibt unverändert.

1. Bereits autorisierte lokale `RIS_ADMIN_AUTHORIZATION_FILE` und exakt zugehörigen STS-Principal prüfen.
2. Synthetischen APIProfile-Entwurf mit zugelassenem Tenant und minimalen Rechten über vorhandene RIS-CLI erstellen; nur ACTIVE und tenantgleich ist zulässig.
3. Über abgesicherten `partner create`-Lifecycle genau einen Partner für den existierenden DEV2-Cognito-Client registrieren. Kein `--tenantId`-Override; Tenant kommt aus autorisierter Principal-Zuordnung.
4. Reservation `CLIENT#<clientId>` und eindeutigen ACTIVE-Owner (Client-/Tenant-Gleichheit) kontrollieren. Historische INACTIVE-Records dürfen existieren.
5. `ris-admin credential issue` mit kurzer Gültigkeit, sicherem absolutem Ausgabepfad, eigenem Run-Label/Reason ausführen. Der Key wird **einmalig** gespeichert; nur ID und Status in Report.
6. Vor erfolgreichem Auth-Positivtest: APIProfile ACTIVE, Credential ACTIVE, Partner ACTIVE, Reservation eindeutig.
7. Niemals ein frei erfundenes `ris_...` als gültig annehmen: Digest muss serverseitig registriert sein.

**CLI-Befehlssyntax aus aktuellem `--help` oder Repo entnehmen; keine hypothetischen Flags aus diesem Runbook als Ausführungsanweisung lesen.**

## 7. Testidentität und Gateway-/JWT-Positivtest

1. In dem **bereits bestehenden DEV2-Testpool** genau einen synthetischen User nach freigegebenem Verfahren anlegen, falls nicht schon genehmigt bereitgestellt.
2. Authentischen Access-JWT über den vorgesehenen Cognito-Flow beziehen; Token nicht anzeigen oder persistieren. Erforderliche Claims wie `token_use=access`, Client-ID, Issuer verifizieren, ohne JWT selbst ins Report zu schreiben.
3. Server-/Test-Runner sendet `Authorization: Bearer <TOKEN>` und `X-Api-Credential: <SECRET>` an die **aktuelle** RIS-API-Route. Kein Browser mit Partner-Secret.
4. **Nur HTTP über den echten API Gateway zählt als `GATEWAY PASS`.** Direktaufrufe der deployed Lambda mit Authorizer-äquivalenten Claims sind `LAMBDA-BOUNDARY PASS`, nicht Gateway/JWT PASS.
5. Metrics erwarteter Erfolg: 200; User- und Partnerkontext in bereinigter Evidence nachweisen.

## 8. Vollständige ApplicationV1-E2E-Matrix

Nur nach erfolgreicher Gateway-Dual-Auth und mit RUN_ID-markierten synthetischen Datensätzen:

| ID | Test | Erwartung / Nachweis |
|---|---|---|
| A01 | Metrics vor Create | `200`, erwartete initiale Zählung protokollieren |
| A02 | Create mit `salary.amount=50000.5` | `201`, neue Server-ID, `schemaVersion`/`version` als JSON-Zahlen |
| A03 | DynamoDB-Rohwert nach Create | `Decimal("50000.5")` exakt, ohne Float-Artefakte |
| A04 | List/Pagination | `200`, eigene Application enthalten, Cursor korrekt, keine Fremddaten |
| A05 | Detail | `200`, richtige Eigentümerbindung und Nutzdaten |
| A06 | Patch `salary.amount=60000.75` und Notiz | `200`, `version` 1 → 2, keine irreführende 422/409 |
| A07 | DynamoDB-Rohwert nach Patch | `Decimal("60000.75")` exakt, Version 2 |
| A08 | Detail nach Patch | `200`, geänderte Daten und Version 2 |
| A09 | Export | `200`, eigene Daten, richtige Serialisierung/Content-Type |
| A10 | Metrics nach Create | `200`, `total` steigt exakt um 1 |
| A11 | Stale-Version-Patch | korrekter Konfliktstatus gemäß aktuellem Vertrag, keine zweite Mutation |
| A12 | Delete | `204`; nur eigene synthetische Application löschen |
| A13 | List/Metrics nach Delete | `200`, RUN_ID-bezogener Application-Zähler wieder 0; keine Restobjekte |

Falls API-Response und DynamoDB-Zustand auseinanderfallen: **Status nicht allein aus HTTP-Code ableiten.** Bei mutierenden Requests mit Antwortfehler nie blind wiederholen: zuvor anhand ID und Version read-only prüfen, ob Commit bereits erfolgt ist.

### Decimal-/Fehler-Regression

- Request-Decimal: keine direkten Python-`float`-Werte an boto3-DynamoDB senden; die im RIS-Handler implementierte verlustbewusste Decimal-Konvertierung muss aktiv sein.
- Response-Decimal: DynamoDB-`Decimal` sauber in vertragskonforme JSON-Zahlen konvertieren; Präzision bei Gehältern beachten.
- `50000.5` Create und `60000.75` Patch sind verbindliche Regressionen aus Phase 25/27.
- Ungültige Datentypen, `NaN`/Infinity, unzulässige Präzision, negative/unerlaubte Beträge nach aktuellem Vertrag: korrekte Validierungsfehler; kein irreführendes `409` für boto3-Typfehler.
- Exakte Persistenz immer am DynamoDB-Rohwert nachweisen, nicht nur anhand der gerundeten JSON-Ausgabe.

## 9. Auth-, Tenant- und Partner-Negativmatrix

| ID | Eingabe | Erwartung |
|---|---|---|
| N01 | Gateway ohne Bearer/JWT | `401` |
| N02 | Ungültiger Bearer | `401` |
| N03 | Gültiger JWT ohne Partner-Credential | Verweigert; konkreten Status dokumentieren |
| N04 | Malformed/ungültiges `X-Api-Credential` | `401` im zuletzt beobachteten Pfad |
| N05 | Widerrufenes Credential | `403` im zuletzt beobachteten Gateway-Pfad |
| N06 | Fremder Tenant | `403` im zuletzt geprüften Lambda-Isolationspfad; Gateway-Nachweis separat |
| N07 | Unbekannter Client | `403` im zuletzt geprüften Lambda-Isolationspfad; Gateway-Nachweis separat |
| N08 | Andere Issuer-/Client-/Partnerkombination | fail-closed; keine Fremddaten |
| N09 | Historische INACTIVE + ein ACTIVE | Autoritativer ACTIVE-Owner wird deterministisch aufgelöst |
| N10 | Reservation verweist auf INACTIVE/mismatch | fail-closed |
| N11 | Keine Reservation + genau ein ACTIVE | Genau dieser ACTIVE-Partner wird aufgelöst |
| N12 | Keine Reservation + null oder >1 ACTIVE | fail-closed |
| N13 | GSI-Lag und unterschiedliche Trefferreihenfolge | keine zufällige Owner-Auswahl |

**Nicht behaupten, ein am Lambda getesteter Negativfall sei auch über Gateway getestet worden.** Testebene und HTTP-Status einzeln notieren.

## 10. Release / Reuse / Revocation / Cleanup

**Reihenfolge bewusst abstimmen**, damit nach Credential-Revocation kein irrtümlicher positiver Call mehr verlangt wird.

1. Vor Revocation sämtliche Positivtests abschließen.
2. Test-Credential über autorisierte RIS-CLI widerrufen, `REVOKED` in Metadaten verifizieren.
3. **Noch vor dem Löschen der nur einmal ausgegebenen Secret-Datei**: falls vorgesehen, Negativtest mit jetzt widerrufenem Key über Gateway ausführen (erwartet zuletzt `403`). Danach Secret-Datei geschützt entfernen.
4. APIProfile über vorgesehenen Lifecycle widerrufen/deaktivieren.
5. Partner über gesicherten Lifecycle deaktivieren; Reservation freigeben; exakte ACTIVE-/INACTIVE- und Reservation-Metadaten prüfen.
6. Wenn ein Wiederverwendungs-Test vorgesehen ist: denselben echten DEV2-Cognito-Client mit einem **neuen synthetischen ACTIVE-Partner** registrieren und korrekte Resolution testen; anschließend auch diesen Partner/Profile/Credential widerrufen/deaktivieren/freigeben.
7. Test-Application und verknüpfte synthetische Objekte löschen; read-only Abwesenheit verifizieren.
8. Temporären Cognito-Benutzer löschen und Benutzeranzahl verifizieren (Phase 27: wieder 0; nur erwarten, wenn Startzustand ebenfalls 0 war).
9. Temporäre Secret-Dateien, Skripte und Token-Caches kontrolliert entfernen; keine fremden oder gemeinsam verwendeten Dateien löschen.
10. Globalen Residualzustand **read-only** erfassen: Anzahl `ACTIVE` Credentials/Profile/Partner, offene Reservations, Applications, synthetische Cognito-User. Historische `INACTIVE`-Partner und `REVOKED`-Metadaten sind kein Cleanup-Fehler, solange keine aktive Berechtigung verbleibt und der Lifecycle sie vorsieht.

**Keine manuelle DynamoDB-Löschung historischer Partner:** Die deterministische Resolver-Korrektur aus Phase 26/27 soll ältere INACTIVE-Records sicher ignorieren. Für unerwartete Residual-Reservations nur bestehenden geprüften Lifecycle nutzen oder separat präzise Genehmigung einholen.

## 11. Bekannte Fehlerbilder und schnelle Diagnose

| Symptom | Wahrscheinlicher Fokus | Nächste gezielte Prüfung |
|---|---|---|
| `401` bei Metrics, JWT bei Gateway gültig | fehlendes/ungültiges `X-Api-Credential`, Credential-Bindung | Quelle 401 (Gateway vs RIS), Credential/Profile/Partner-Status, Header |
| Partner-/Profile-/Credential-Tabellen leer | DEV2 nicht provisioniert | legitimer Admin-Trust-Anchor, regulärer CLI-Lifecycle |
| `RIS_ADMIN_AUTHORIZATION_FILE` fehlt | RIS-interne Admin-Zuordnung fehlt, **nicht** AWS-Profil-Defekt | autorisierten Betreiberprozess, Datei-Eigentümer/ACL/Principal/Tenant; keine Freigabe fingieren |
| `403` trotz ACTIVE-Nachfolger | historische GSI-Client-Kollision / Reservation | deployed Resolver-Hash und ACTIVE/Reservation-Owner prüfen; nicht blind historische Records löschen |
| List/Detail/Patch/Export `422` mit echten Items | DynamoDB `Decimal` ohne Response-Encoder | aktueller Lambda-Code-Hash, Response-Serialisierung; nach Commit Zustand prüfen |
| Create von `50000.5` → `409` | Python Float beim DynamoDB-Write, falsches Error Mapping | Request-Decimal-Normalisierung und aktuelle Lambda-Version prüfen |
| Patch ändert DB trotz 422 | Response-Serialisierung nach erfolgreichem Commit | Read nach Patch, Version/Idempotenz, keinen blinden Retry |
| Release erfolgreich, Reuse scheitert | inaktiver historischer Partner verdeckt neuen ACTIVE | deterministischen Resolver + Reservation-Owner prüfen |
| `403` CloudFront Health | Origin/OAC/Distribution-Pfad gesondert | CloudFront-Health ist nicht gleich API-Gateway-Health; keine Konfigurationsänderung ohne Scope |
| `OPTIONS`/Browser-CORS schlägt fehl | Gateway-CORS oder BFF-Konfiguration | realen Browser-Preflight prüfen; fehlende API-Gateway-CORS-Metadaten allein reichen als Beweis nicht |
| Terraform-Plan enthält zusätzliche PITR-Änderungen | Drift/Provider/State-Konfiguration | Plan verwerfen; nicht zusätzliche Updates applyen |

## 12. Testebenen und tatsächlicher Stand als Referenz

**Phase 27, 2026-11-05 – durch den lokalen Phase-27-Report belegte Ergebnisse:**

- DEV2 Apply `0 add / 1 change / 0 destroy`; Lambda-Hash `uGQX0tnPcIW0y1q6GtSaEPVEBjIDLqYrJzm2OX5wMEU=`; State 29 → 30; No Changes; Health 200.
- Real Gateway + JWT + Partner-Key: Metrics 200; Application Create 201 mit `50000.5`; List/Detail 200; Patch 200 mit `60000.75` und Version 1→2; Export 200; Delete 204; List/Metrics nach Delete 0.
- DynamoDB persisted `Decimal("50000.5")` und `Decimal("60000.75")` exakt.
- Drei historische INACTIVE-Partner blockierten ACTIVE nicht. Release + echter Client-Reuse PASS. Ungültiger Key 401, revoked Key 403 (Gateway); fremder Tenant und unbekannter Client 403 (deployte Lambda).
- Cleanup: 0 Users, 0 Reservations, 0 Applications, 0 Secret-Dateien; 6 Partner INACTIVE, 8 APIProfiles REVOKED, 6 Credentials REVOKED. Historie blieb erhalten.
- **Gate B NO-GO / Production BLOCKED.** Der echte Jobsearch-Vercel-Key und BFF sind durch diesen synthetischen RIS-Test **nicht** geprüft.

**Primäre interne Evidence für spätere Vergleiche:**

- `docs/reports/RIS-R08-DEV2-SYNTHETIC-PARTNER-E2E-20.md`
- `docs/reports/RIS-APPLICATION-DEV2-APPLY-E2E-25.md`
- `docs/reports/RIS-R08-PARTNER-RESOLVER-FIX-26.md`
- `docs/reports/RIS-R08-RESOLVER-DEV2-GATEWAY-E2E-27.md`
- `docs/reports/RIS-R08-DEV2-PARTNER-COLLISION-23.md`
- `docs/reports/RIS-R08-DEV2-ADMIN-BOOTSTRAP-19.md`
- `docs/reports/RIS-DEV2-OPERATOR-AUTHORIZATION-20.md`
- `docs/reports/RIS-R08-DEV2-JOBSEARCH-INTEGRATION-HANDOFF.md`

Existenz und Pfade im lokalen Checkout prüfen; ältere oder nur lokale Reports nicht als bereits gepusht ausgeben.

## 13. Reportvorlage für jeden neuen Testlauf

Berichtsziel: `docs/reports/RIS-DEV2-E2E-<RUN_ID>.md` (Dateiname an Repo-Konvention anpassen).

```markdown
# RIS DEV2 E2E – <RUN_ID>

## Baseline
Date, AWS account/region/profile, STS ARN, repo branch/commit, Terraform workspace/state serial/lineage, deployed Lambda hash, geprüfter API-Vertrag.

## Testfreigabe / Scope
Genehmigter synthetischer Tenant und Testzweck, erlaubte Operationen, Admin-Trust-Anchor VALIDATED (ohne Inhalte), KEINE reale Identität.

## Provisioning
APIProfile-/Partner-/Credential-IDs und Status, gebundener Client/Issuer, Reservation Owner; niemals Secret/Token.

## Deployment (falls zutreffend)
Plan SHA-256, Full Diff, Bundle-Hash, Apply, State danach, No Changes, Health.

## Testmatrix
ID | Ebene (GATEWAY/LAMBDA/LOCAL) | HTTP | fachlicher Befund | Evidence/Korrelation | PASS/FAIL/BLOCKED

## Security
Credential/Tenant/Issuer/Client-Isolation, Revocation, version_conflict, no-store/PII-Leaks; nur tatsächlich ausgeführte Tests als PASS.

## Cleanup
Created IDs, widerrufen/deaktiviert/gelöscht, Reservations verbleibend, Applications verbleibend, User vor/nach, Secret-Dateien; Residual-Historie und Abweichungen.

## Findings
Severity | Symptom | reproduzierbarer Test | Root Cause | Owner-Team | Follow-up.

## Gates
DEPLOY | LAMBDA | REAL_GATEWAY | CLEANUP | JOBSEARCH_BFF | PRIVACY_GATE_B | PRODUCTION

## Git/Audit
AI_AUDITLOG aktualisiert; Commits; Push/Merge (i.d.R. NONE).
```

## 14. Auftrag an das Jobsearch-Team – **separater** Integrationsgate

Das bestandene RIS-DEV2-E2E legitimiert **nicht** automatisch die Nutzung echter Benutzer-/Bewerberdaten oder der produktiven Jobsearch-Seite.

- RIS-Backend stellt verifizierten Vertrag, tatsächlich vorhandene Routen/Fehlerstatus, Pagination, Versionierung, Decimal- und Tenant-Isolation bereit.
- Jobsearch verwendet den vorhandenen **serverseitigen** `RIS_API_KEY` ausschließlich in Vercel-BFF-/Serverfunktionen, niemals in `src/`, `VITE_*` oder Browser-Requests.
- Bestehenden Jobsearch-Cognito-Pool verwenden, kein Pool-/Client-Umbau. Benutzer-Ownership aus `iss + sub`; kein E-Mail- oder clientseitiger ownerId-Fallback.
- Jobsearch-`ApplicationPersistencePort` gegen den tatsächlichen RIS-Vertrag implementieren; lokale Session-Drafts bleiben bis zur bestätigten serverseitigen Speicherung erhalten, keine automatische Migration.
- Browser-/BFF-Tests, CORS, Session-Wechsel, Logout, 401/403/409/429/503, Fehlermeldungen, sichere Retry-/Idempotenzbehandlung **separat** prüfen.
- Für PROD/Privacy ausdrücklich eigene Abnahme einschließlich Gate B, Erasure/Inspect/Export, Lifecycle und Berechtigungen durchführen.

## 15. Wartung / Änderungsregeln dieses Handbuchs

1. Nach jedem erfolgreich absolvierten DEV2-E2E nur die **neuen Fakten/Abweichungen** und Evidence ergänzen, statt Architektur neu zu ermitteln.
2. Echte Routen, CLI-Flags, Tabellen, Versionen und Hashes dürfen sich ändern; sie werden **laufzeitnah** aus dem Repository / AWS verifiziert.
3. Wenn ein Regressionstest einen neuen Defekt aufdeckt, minimalen Fix + lokale Tests + separaten zielgenauen Deploy-Plan; niemals ungeprüften globalen Apply.
4. Nach jeder Handbuchänderung `docs/AI_AUDITLOG.md` ergänzen und sauber committen.
5. Dieses Handbuch ist ein Hilfsmittel für den autorisierten Test; es ersetzt **keine** Sicherheitsfreigabe, keinen Admin-Trust-Anchor und keine Produktionsabnahme.

## 16. Verifizierte Code-Referenzen (Faktencheck 2026-11-05)

Die folgenden Aussagen wurden gegen den lokalen Checkout geprüft. Sie sind
Referenz, keine Garantie für einen späteren Commit.

| Aussage | Verifiziert in |
|---|---|
| Credential-Präfix `ris_`, 32 Zufallsbytes, SHA-256-Digest mit Domain `ris-cred-v1:` | `agents/ecosystem/credentials.py` (`SECRET_PREFIX`, `SECRET_RANDOM_BYTES`, `generate_secret`, `digest_secret`) |
| Once-only-Ausgabe, sichere Zielprüfung, Revocation | `tools/ris_admin/credentials.py` (`precheck_output_destination`, `open_secret_file`, `issue`, `revoke`) |
| Admin-Trust-Anchor: exakter STS-Principal, Rolle, Tenant, owner-only Datei | `tools/ris_admin/credentials.py:resolve_admin_authorization` |
| Partner-Reservation `CLIENT#<clientId>` mit `tenantId`, `reservedForApplicationId`, Status `RESERVED` | `agents/ecosystem/partner_registry.py:create_partner_application` |
| Deterministischer Resolver: Reservation autoritativ, Owner ACTIVE, Client/Tenant-Abgleich, sonst fail-closed | `agents/ecosystem/partner_registry.py:resolve_partner_application` |
| Release nur mit Dependency-Check und exakter Ownership | `agents/ecosystem/partner_registry.py:deactivate_partner_application` |
| CLI-Flag `partner deactivate --release-reservation` | `tools/ris_admin/cli.py` |
| Salary-Input: `Decimal(str(value))`, max. 38 signifikante Stellen, NaN/Infinity/negative Werte abgelehnt | `jobsearch/application_contract.py:_salary_amount` |
| Response-Serialisierung: DynamoDB-`Decimal` → JSON-Zahl | `lambda/handler.py:_application_json_default`, `_application_response` |
| Serialisierungsfehler werden nicht als 409 maskiert | `jobsearch/application_repository.py` (Create/Patch `except TypeError: raise`) |
| Belegter Phase-27-Stand: State 30, Lambda `uGQX…`, echte Gateway-Matrix, 0 Users/Reservations/Applications | `docs/reports/RIS-R08-RESOLVER-DEV2-GATEWAY-E2E-27.md` |

Die früheren Phasenberichte bleiben die primäre Evidence. Insbesondere sind
die Zähler (6 INACTIVE-Partner, 8 REVOKED-APIProfiles, 6 REVOKED-Credentials)
ein Momentaufnahmewert aus Phase 27 und vor einem neuen Lauf read-only neu zu
erheben.
