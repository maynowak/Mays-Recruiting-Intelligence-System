# RIS-PARTNER-PROFILE-R07-FIX-03 — LEGACY CAPACITY COUNTER INTEGRITY & SAFE DELETE

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor Fix | `85aa139` (`fix(ris): classify transaction conflicts and bound safe retries`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| Scope | ausschließlich Mays-RIS |
| AWS-Mutation | keine |

## 2. Root Cause F-5

`delete` und `reserve_parent_delete` verlangten für jede Ressource einen
Capacity-Counter:

- Der eigene Counter wurde per `Update … ConditionExpression: #c > :zero`
  dekrementiert. Fehlte er, wurde die Transaktion abgebrochen und der Handler
  meldete **404** – obwohl die Ressource existierte.
- Der Kind-Counter wurde mit
  `attribute_not_exists(resourceId) OR #c = :zero` geprüft. Ein **fehlender**
  Kind-Counter galt damit als „0 Kinder“. Das war nicht nur ein
  Löschhindernis, sondern ein Orphan-Risiko, wenn Kinder ohne Counter
  existierten.
- Beim CV-Delete passierte das `reserve` vor dem S3-Delete; ein
  fehlschlagendes `finalize` (fehlender Counter) konnte S3 bereits gelöscht
  haben, während die Metadaten stehen blieben.

### Historische Datenlage (Evidence)

Die Git-Historie zeigt zwei Generationen:

| Commit | Bedeutung |
|---|---|
| `e43bf53` | erster Repository-Entwurf; Kapazität über GSI-Zählung, **keine** Counter-Items |
| `befbb59` | atomare Capacity-Counter (`capacity#…`) eingeführt |
| `2e2a72e` | Transaktionsstruktur der Counter korrigiert |

Es gibt **keinen** Backfill-/Migrationscommit und keinen Hinweis auf eine
nachträgliche Counter-Initialisierung. Ressourcen aus dem Zeitfenster
`e43bf53`–`befbb59` können daher ohne Counter existieren. Ob solche Daten
tatsächlich in einer Umgebung liegen, ist ohne AWS-Zugriff nicht feststellbar;
der Code muss beide Fälle sicher behandeln. Künstlich beschädigte moderne
Counter werden davon getrennt betrachtet (siehe §5).

## 3. Gewählte Strategie

### Moderne Ressourcen — unveränderter Fast Path

- Counter vorhanden, numerisch, ≥ 0 und vor der Ressource erzeugt:
  - Kind-Counter > 0 → 409 (Kinder vorhanden).
  - Kind-Counter = 0 → normaler Delete mit atomarem Counter-Dekrement und
    Kind-Counter-ConditionCheck.
- Beim Anlegen eines `CVDocument`/`CVSearchProfile` wird der jeweilige
  Kind-Counter jetzt **mit 0 angelegt**. Dadurch haben moderne Eltern mit
  null Kindern einen beweisbaren Counter und lösen keinen Scan aus.
- Keine Scans im normalen CRUD-Pfad.

### Legacy-Ressource — Guard + begrenzter Consistency-Scan

Nur wenn der eigene oder der Kind-Counter fehlt bzw. die Ressource zeitlich
**vor** dem Counter entstanden ist:

1. Parent autoritativ lesen, Ownership/Version prüfen.
2. **Guard transaktional auf `deleting` setzen** (Parent-ConditionCheck +
   Guard-Update). Damit können keine neuen Kinder mehr committen.
3. **Vollständiger, strongly-consistent Scan** der Basistabelle mit
   `FilterExpression parentId = :p AND resourceType = :rt`,
   `ConsistentRead=True`, alle Seiten über `LastEvaluatedKey`.
   - Kein Treffer → Kindfreiheit bewiesen.
   - Treffer → Guard zurück auf `active`, 409, keine Löschung.
   - Fehler/Abbruch/Seiten- oder Item-Limit → Guard zurück auf `active`,
     fail-closed.
4. Erst danach CV-S3-Delete bzw. `finalize`.
5. `finalize` überspringt bei einer verifizierten Legacy-Reservierung den
   fehlenden Counter und den Kind-Counter-Check; vorhandene, „nicht deckende“
   Counter werden **nicht** dekrementiert.

Warum der Scan sicher ist: Nach dem Guard kann kein neuer Kind-Create mehr
committen (alle aktuellen Pfade prüfen den Guard). Der Scan ist zwar kein
Snapshot, aber vorhandene Kinder können nur verschwinden, nicht hinzukommen.
Ein vollständiger Leer-Scan ist damit ein stabiler Kindfreiheitsnachweis.
Scan-Grenzen: `50` Seiten / `5.000` gescannte Items; danach fail-closed.

### Was ausdrücklich nicht geschieht

- Ein fehlender Counter wird **nie** als `count = 0` gelesen.
- Es wird **kein** Counter automatisch angelegt oder überschrieben.
- Keine Kaskadenlöschung.
- Keine leere/teilweise GSI-Abfrage als Löschfreigabe.
- Kein Counter-Update bei fehlendem/nicht deckendem Counter (kein
  Unterzählen; ein Überzählen ist möglich und damit kapazitätsseitig streng).
- Keine S3-Mutation vor erfolgreichem Guard/Scan.

## 4. Counter-/Guard-Transaktionen

- `reserve`: Guard-Update + Parent-ConditionCheck; optional Kind-Counter-Check
  nur wenn der Counter **vorhanden** ist (`attribute_exists AND #c = :zero`).
  Missing Counter → kein Check, sondern Scan nach dem Guard.
- `finalize`: Delete Parent + optional Counter-Dekrement + Guard-Delete +
  optional Kind-Counter-Check. Maximal eine Aktion pro Item.
- `delete` (CVSP/ATS): normaler Pfad wie bisher; Legacy-Pfad delegiert an
  `reserve` + `finalize`.
- Retry-/Transient-Semantik aus R07-FIX-02 bleibt unverändert.

## 5. Counter-Reconciliation — bewusst nicht automatisch

Eine sichere automatische Counter-Reparatur würde den tatsächlichen
Geschwister-/Kindbestand benötigen. Der Kindbestand ist über den Guard-Scan
beweisbar; der **eigene** Counter (z. B. `capacity#CV#<user>`) zählt aber
Geschwister, nicht Kinder. Ein automatisches Setzen auf 0/1 wäre Raten und
könnte die 10/2/5-Grenzen verletzen.

Deshalb:

- Fehlender/nicht deckender Counter → Dekrement wird übersprungen (kein
  Unterzählen; ein Überzählen ist möglich).
- Fehlender Kind-Counter → nach Scan wird **kein** 0-Counter angelegt.
- Inkonsistenter/nicht numerischer Counter, Counter 0 bei existierender
  Ressource, oder Counter > 0 mit vorhandenen Kindern → **409**,
  keine Mutation.
- Ein moderner Counter, der trotz vorhandener Kinder 0 sagt, ist ohne
  vollständigen Scan nicht als Widerspruch erkennbar; das ist ein
  Integritätsvorfall und bleibt dem Offline-Reconciliation-Verfahren
  vorbehalten (kein Scan auf jedem normalen Delete).

### Separates Migrationsverfahren (nicht in diesem Gate implementiert)

1. Wartungsfenster / keine parallelen Writes.
2. Parent per Guard auf `deleting` setzen.
3. Strongly-consistent, vollständig paginierten Scan über `parentId` und
   `resourceType` ausführen.
4. Nur bei beweisbarer Kindfreiheit den Parent löschen; andernfalls Kinder
   zuordnen/reparieren.
5. Eigene Capacity-Counter nur mit einer **expliziten, geprüften**
   Bestandsaufnahme (nicht pro Request) initialisieren.
6. Guard freigeben; keine öffentliche Admin-API ohne separate Freigabe.

## 6. CV / S3

- `_cv_delete` prüft Counter/Scan im `reserve` **vor** jedem S3-Zugriff.
- Kind vorhanden oder Kindbestand unklar → 409/5xx, `s3Touched=false`,
  S3 unverändert.
- S3-Fehler → `release_parent_delete` setzt Guard zurück auf `active`,
  Metadaten bleiben, Retry ist möglich.
- Erfolgreicher Pfad bleibt `reserve → S3 delete → finalize`.
- `physicalPurge=false` bleibt korrekt; ältere Objektversionen bleiben
  bestehen (R08).

## 7. Fehlervertrag

| Situation | Status |
|---|---|
| Kinder vorhanden | 409 |
| Legacy-Counter fehlt, Kindbestand nicht beweisbar | 409 `Profile integrity check failed` |
| Counter inkonsistent/nicht numerisch/0 bei existierender Ressource | 409 `Profile integrity check failed` |
| Fremde/nicht vorhandene Ressource | 404 |
| Scan-/DynamoDB-Lesefehler | 500 |
| Transienter Konflikt (R07-FIX-02) | intern Retry, sonst 503 |
| Unbekannter Commit-Ausgang | 503 |
| Stale Version | 409 |

Keine Counter-Keys, IDs, Tokens oder Payloads in Fehlerantworten.

## 8. Tests

Neu: `tests/test_partner_profile_legacy_counter.py` — **21 Tests PASS**:

- CV/CVSP ohne Counter, ohne Kinder → sicherer Delete
- CV/CVSP ohne Counter, mit Kind → 409, Guard freigegeben, Kind erhalten
- ATS ohne Counter → Delete ohne Counter-Erzeugung
- Counter 0 / >0 / nicht numerisch / Widerspruch
- Historischer Pfad, wiederholte Recovery, Scan-Fehler, Scan-Limit
- Mehrseitiger Scan
- Moderne Deletes ohne Scan
- Concurrent Legacy-Deletes: genau ein Gewinner
- Ownership-Isolation
- Transaktionsform (eine Aktion pro Item)
- CV/S3: kein S3 bei Kind/Scan-Fehler; S3-Fehler → 502, Metadaten bleiben,
  Retry erfolgreich

DynamoDB Local (`tests/integration/test_partner_profile_dynamodb_local.py`)
wurde um **6 echte Legacy-Counter-Tests** erweitert (CV/CVSP mit/ohne Kind,
ATS, nicht numerischer Counter). Die Suite umfasst jetzt **29 Tests**.

## 9. Regression

| Umgebung | Ergebnis |
|---|---|
| System-Python ohne boto3/Endpoint | **544 passed, 29 skipped, 256 subtests** |
| Venv + DynamoDB Local 3.3.2 (`127.0.0.1:18000`) | **573 passed, 0 skipped, 256 subtests** |
| DynamoDB-Local-Suite | **29/29 PASS** |
| Terraform / OpenAPI | nicht betroffen |
| `git diff --check` | PASS |

Der lokale Server wurde nach dem Lauf gestoppt; keine Testtabelle blieb
zurück. Es gab keine AWS-Verbindung.

## 10. F-5-Status

- **Sicherer Delete kinderfreier Legacy-Ressourcen:** IMPLEMENTED + VERIFIED.
- **Mit Kindern:** korrekt blockiert (409), keine Orphans, keine S3-Mutation.
- **Unklarer Kindbestand:** fail-closed (409/500), Guard wird freigegeben.
- **Automatische Counter-Reparatur/Backfill:** **nicht implementiert** und
  bewusst nicht geraten. Dafür ist das separate Migrationsverfahren nötig.
- **Modern-Counter-Widerspruch bei 0 mit Kindern:** per Request nicht
  erkennbar; Offline-Reconciliation.

**F-5 vollständig behoben: PARTIAL.** Der Löschpfad ist sicher und
funktionsfähig; die Counter-Reconciliation/Restbereinigung bleibt als
offline durchzuführende Migration offen.

## 11. Andere Findings

| ID | Status |
|---|---|
| F-6 Cursor-Integrität | OPEN, unverändert |
| P1-1 CVDocument-Naming/Status | OPEN, unverändert |
| R08 S3-Version-Purge | OPEN, unverändert |
| R07-B AWS E2E | NOT RUN |
| Residual | Re-Reservierung bei bereits `deleting` bleibt möglich (Recovery-Pfad); zwei parallele CV-Deletes können S3-Delete idempotent wiederholen, `finalize` gewinnt nur einmal. |

## 12. R07-FIX-04-Empfehlung

1. Offline-Reconciliation-Werkzeug (nicht öffentliche API) für Counter-
   Backfill und Widerspruchsprüfung spezifizieren.
2. R07-B AWS-E2E für reale Scan-Kosten, Guard-Races und S3-Lifecycle.
3. F-6 Cursor-Härtung (signiert/verschlüsselt, Scope-gebunden).
4. P1-1 CVDocument-Vertrag.

## 13. Status

- **IMPLEMENTED:** Guard+Scan-Legacy-Pfad, fail-closed Counterprüfung,
  Kind-Counter-Erzeugung bei modernen Eltern, 409-Integrity-Mapping.
- **VERIFIED:** 21 neue Unit-Tests, 6 neue Local-Tests, 573 Gesamttests.
- **PARTIAL:** F-5 (Counter-Reconciliation/Backfill offen).
- **OPEN:** F-6, P1-1, R08, Offline-Migration.
- **NOT RUN:** R07-B AWS E2E.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.
