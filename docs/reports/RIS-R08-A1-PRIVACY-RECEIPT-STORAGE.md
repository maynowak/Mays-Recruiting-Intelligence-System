# RIS-R08-A1 — PRIVACY RECEIPT JOURNAL: DURABLE STORAGE FOUNDATION

Status: **IMPLEMENTED (repository + infrastructure), production writes
DISABLED**. No CRUD integration, no public API, no AWS mutation.

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor Gate | `a38c510` |
| Tracked Working Tree vor Gate | clean |
| Untracked Dateien vor Gate | 39, unverändert |
| AWS-Zugriffe/-Mutation | keine |
| Deploy / Apply / Destroy | keines |
| Neue öffentliche API | nein |
| Neue Receipt-Definition | nein (Wiederverwendung `PrivacyReceiptV1`) |

Geprüfte Grundlagen: R08-G0-Report, `PrivacyReceiptV1`-Contract mit
30 Contract-Tests, `PartnerProfileRepository`, bestehende DynamoDB-/Terraform-
Strukturen sowie die G5-Privacy-/Erasure-Implementierung.

## 2. Persistenzentscheidung

**Gewählt: eigene DynamoDB-Tabelle `${project}-${environment}-privacy-receipts`.**

Alternativen:

| Option | Bewertung |
|---|---|
| Eigene Tabelle (gewählt) | getrennte IAM-Rechte, eigene Retention-/Löschdomäne, kein Kontakt mit 10/2/5-Zählern, keine Vermischung mit Cursor-/Idempotenz-Items, unabhängige spätere TTL-/Erasure-Policy |
| Namespace in `partner-profiles` | gleiche IAM-Rolle für Profil- und Nachweisdaten, gemeinsame Lösch-/Retention-Grenze, Kollisionsrisiko mit Cursor-/Idempotenz-/Counter-Keys, kein sauberer Nachweis der Isolation |

Ausschlaggebend waren Identitätsisolation, getrennte IAM-Berechtigungen,
eigene Retention und die spätere atomare Kopplung. Die Tabelle ist
`PAY_PER_REQUEST`; bei receipt-großen Items sind die Kosten vernachlässigbar.
Es wurde keine zusätzliche Infrastruktur (Stream, Queue, eigener Service)
eingeführt.

## 3. DynamoDB-Schema

| Eigenschaft | Wert |
|---|---|
| Tabelle | `${project_name}-${environment}-privacy-receipts` |
| Billing | `PAY_PER_REQUEST` |
| Partition Key | `receiptId` (S) |
| GSI | `gsi-subject`: HASH `scopeKey`, RANGE `scopeSort`, Projektion `ALL` |
| TTL | **keine** — Retention ist REVIEW REQUIRED |
| Kapazität/Guards | keine; nicht Teil der 10/2/5-Zähler |

Item-Felder:

```text
receiptId, scopeKey, scopeSort, subjectRef, tenantRef,
partnerApplicationRef, issuerRef, eventType, recordedAt,
schemaVersion, contentHash, payload, createdAt, updatedAt
```

- `scopeKey = SHA256(tenantRef \x1f partnerApplicationRef \x1f issuerRef \x1f subjectRef)`.
  Die Rohidentität steht nicht im Key.
- `scopeSort = recordedAt + "#" + receiptId`; neueste zuerst über
  `ScanIndexForward=false`.
- `payload` ist der validierte `PrivacyReceiptV1`; keine CV-Texte, Prompts,
  Tokens, presigned URLs oder S3-Keys.
- Kein `parentId`, kein Capacity-Counter, kein Lifecycle-Guard, keine
  Receipt-Hierarchie.

## 4. Identitätsbindung

- Die Identität stammt ausschließlich aus dem **verifizierten** `PrivacyContextV1`
  (JWT + Partner-Registry + Tenant/Issuer). Es gibt keinen clientseitig
  wählbaren `subjectRef`.
- `append_receipt` prüft `receipt_matches_context` vor jedem Schreibvorgang.
- `get_receipt` liest per PK mit `ConsistentRead=True` und vergleicht
  `subjectRef`, `tenantRef`, `partnerApplicationRef`, `issuerRef` exakt gegen
  den Kontext. Abweichung → `PrivacyReceiptNotFound` (kein Leak, ob der Beleg
  existiert).
- `list_receipts` filtert über den GSI-Partitionsschlüssel `scopeKey`, also
  exakt eine Identitätsdomäne. Ein Cursor einer anderen Identität wird
  abgelehnt.
- Cross-User-, Cross-Tenant-, Cross-Partner- und Cross-Issuer-Isolation sind
  durch Unit- und DynamoDB-Local-Tests abgedeckt.

## 5. Append-/Idempotenzvertrag

- Nur validierte `PrivacyReceiptV1`-Instanzen werden akzeptiert; ungültige
  Eventtypen/Status/Evidence-Werte scheitern im Contract-Validator.
- `recordedAt` wird **serverseitig** gesetzt; ein mitgelieferter Zeitstempel
  wird nicht vertraut.
- Insert ist bedingt: `PutItem` mit
  `ConditionExpression="attribute_not_exists(receiptId)"`.
- `contentHash` = SHA-256 des kanonischen Receipts **ohne** `recordedAt`.
  Dadurch gilt eine identische Wiederholung (neuer Server-Zeitstempel) als
  dieselbe Operation.
- Gleiche `receiptId` + gleicher `contentHash` → der gespeicherte Beleg wird
  zurückgegeben; kein Duplikat, keine Mutation.
- Gleiche `receiptId` + anderer `contentHash` → `PrivacyReceiptConflict`.
- Parallele identische Inserts: genau ein bedingter Write gewinnt; der
  Verlierer liest konsistent und gibt bei Gleichheit den gespeicherten Beleg
  zurück, sonst Konflikt.
- Das Repository bietet **keine** Update-/Delete-Methode. Eine absolute
  Unveränderlichkeit wird nicht behauptet: IAM erlaubt derzeit kein
  `UpdateItem`/`DeleteItem`, aber eine spätere autorisierte Retention-/Erasure-
  Policy kann dies ändern.

## 6. Zugriffskontrolle

IAM-Policy `lambda_privacy_receipts` erlaubt ausschließlich:

- `dynamodb:PutItem`
- `dynamodb:GetItem`
- `dynamodb:Query`

auf Tabelle und Index. Kein `Scan`, `UpdateItem`, `DeleteItem` in R08-A1.
Normale Lesepfade nutzen PK-`GetItem` und GSI-`Query`; ein vollständiger
Table-Scan ist im Benutzerpfad nicht vorhanden und wird durch einen
Quelltext-Test abgesichert.

Fehlerbehandlung:

- deaktiviert/nicht konfiguriert → `PrivacyReceiptJournalDisabled`
- Schreib-/Lesefehler → `PrivacyReceiptStorageError` (nie stiller Erfolg)
- fehlender/fremder Beleg → `PrivacyReceiptNotFound`
- ungültiger/fremder Cursor → `PrivacyReceiptInvalidCursor`
- Hash-/Payload-Abweichung → `PrivacyReceiptIntegrityError`

Fehlermeldungen enthalten keine Receipt-Inhalte, Secrets oder Rohdaten.

## 7. Datensparsamkeit

Der Beleg enthält nur stabile Referenzen und Metadaten. Ausgeschlossen sind
insbesondere: vollständige CV-Texte, PDF-Inhalte, Dateinamen, frei eingegebene
Profilnamen, E-Mail-Adressen, Modellprompts, presigned URLs, JWTs,
API-Credentials, S3-Objektschlüssel und vollständige DynamoDB-Rohdatensätze.
Personenbezogene Stammdaten bleiben in ihren vorgesehenen RIS-Speichern.
Pseudonyme Referenzen bleiben bei Zuordenbarkeit personenbezogene Daten.

Ein Test prüft, dass gespeicherte Items weder verbotene Inhaltsfelder noch
Counter-/Lifecycle-/Idempotenz-Hierarchien enthalten. Die 8-KiB-Grenze bleibt
im Contract erzwungen.

## 8. Retention-Entscheidungsbedarf

- Es wurde **keine** willkürliche Speicherfrist und **keine** TTL gesetzt.
- Unbefristete Speicherung wird nicht als rechtlich genehmigt ausgegeben.
- DynamoDB-TTL ist kein sofortiger physischer Löschungsnachweis.
- Produktive Journal-Schreibfunktion ist fail-closed:
  `PRIVACY_RECEIPT_JOURNAL_ENABLED=false` (Default und Terraform-Env).
  Ohne explizite Freigabe schlagen alle Operationen kontrolliert fehl.
- Testdaten existieren nur in der isolierten lokalen DynamoDB-Local-Tabelle
  und werden mit dieser gelöscht.

Offene Entscheidung: fachlich begründete Aufbewahrungsfrist bzw. Löschregel
für PrivacyReceipts, einschließlich des Verhältnisses zu Backups/PITR und zur
späteren Erasure-Evidenz.

## 9. Atomare R08-A2-Integrationsstrategie

### DynamoDB-only-Profiländerungen

Profilmutation, Capacity-Counter, Idempotenzrecord, Lifecycle-Guard und
Receipt können in einem `TransactWriteItems` liegen, sofern jedes Item genau
eine Aktion erhält.

- Receipt-Aktion: `Put` mit `attribute_not_exists(receiptId)`.
- Bricht die Transaktion wegen eines bereits vorhandenen Receipts ab:
  konsistent lesen und `contentHash` vergleichen.
  - gleicher Inhalt/Operation → Replay-Erfolg, Profilmutation nicht erneut
    anwenden;
  - anderer Inhalt → Konflikt.
- Unbekannter Commit-Ausgang: über den bestehenden Idempotenz-/Operations-
  zustand auflösen; niemals Erfolg ohne konsistente Bestätigung melden.
- Höchstens eine Receipt-Aktion pro Item; kein Receipt-Update in derselben
  Transaktion.

### S3/CV

S3 und DynamoDB können nicht atomar abgeschlossen werden; siehe Abschnitt 10.

## 10. S3-Teilfehlerszenarien

- `CV_STORAGE_CONFIRMED` wird erst geschrieben, nachdem `HeadObject` das
  Objekt verifiziert **und** der CV-Statusübergang erfolgreich war.
- Schlägt der Receipt-Write nach erfolgreicher CV-Bestätigung fehl, muss ein
  dauerhaft gespeicherter Outbox-/Reconciliation-Zustand den Nachweis
  nachholen. Kein Receipt vor verifizierter Speicherung.
- Ein fehlendes Receipt darf nicht als fehlende Speicherung interpretiert
  werden; der Outbox-Zustand ist maßgeblich.
- Für Erasure wird ein Abschluss-Receipt erst geschrieben, nachdem alle
  Objektversionen und Delete-Marker nachweislich entfernt sind; sonst
  `ERASURE_PARTIALLY_COMPLETED`.
- Ein Receipt ersetzt keine S3-Bereinigung und ist kein physischer
  Löschungsnachweis.

R08-A1 spezifiziert und ermöglicht diesen Mechanismus, baut aber keine
CRUD-Pfade um.

## 11. Browser-Auth-Boundary

`X-Api-Credential` ist ein opakes `ris_...`-Bearer-Secret (32 Zufallsbytes,
nur SHA-256-Lookup-Digest gespeichert). Es ist ein vertrauliches
Partner-Credential und darf **niemals**:

- im Browser-Code oder in `localStorage` liegen,
- als `VITE_*`-Variable oder öffentliche Frontend-Konfiguration ausgeliefert
  werden,
- geloggt oder in API-Antworten zurückgegeben werden.

Die bestehende Dual-Auth (Human-JWT + `X-Api-Credential`) bleibt unverändert
und wird nicht abgeschwächt. Der spätere Browser-Pfad benötigt eine von zwei
Varianten:

1. **BFF/Delegation:** Jobsearch-Backend hält das Partner-Credential und
   reicht das verifizierte Benutzer-JWT an RIS weiter; der Browser sieht nur
   das Benutzer-JWT.
2. **Separates End-User-Auth-Gate:** eine eigene, geprüfte RIS-
   Benutzerauthentifizierung/Delegation.

R08-A1 implementiert keine neue Browser-Auth. Das Repository ist serverseitig
identitätsgebunden und vertraut keinen Client-Identitätsfeldern.

## 12. Neue Tests

| Datei | Inhalt | Anzahl |
|---|---|---|
| `tests/test_privacy_receipt_journal.py` | Append/Get-Roundtrip, Idempotenz, Konflikt, Validierung, Kontextbindung, Cross-Identity-Isolation, Pagination, ungültiger/fremder Cursor, Limit-Begrenzung, Fail-closed, Read/Write/Query-Fehler, Integritätserkennung, keine Scan-Nutzung, parallele Inserts, Datensparsamkeit, Terraform-Contract | 26 |
| `tests/integration/test_partner_profile_dynamodb_local.py` | 6 neue Journal-Tests gegen echtes DynamoDB Local: Insert/Read, Idempotenz + Konflikt, GSI-Pagination, Cross-Identity + falscher Cursor, parallele Inserts, keine TTL | 6 |
| `tests/test_privacy_receipt_contract.py` | neue v1-Events und Notice-Acknowledgement-Regeln | 32 gesamt |

Neue Contract-Events mit Begründung:

- `USER_PROFILE_UPDATED` — eigener UserProfile-Schreibpfad, der nicht unter
  die Partner-Profil-Events fällt.
- `PRIVACY_NOTICE_ACKNOWLEDGED` — belegbare Bestätigung; verlangt
  Notice-Version und -Digest.
- `PROFILE_DELETED` — Löschung eines Profils ist ein eigener Nachweis und
  nicht mit `PROFILE_UPDATED` gleichzusetzen.

`CONSENT_GRANTED`/`CONSENT_WITHDRAWN` waren bereits erlaubt und bleiben an
eine ausdrückliche Einwilligungsgrundlage gebunden. Nicht jede
Profilspeicherung erzeugt eine Einwilligung. Ein Receipt belegt eine
technische Operation bzw. dokumentierte Benutzerentscheidung, nicht die
Rechtmäßigkeit der gesamten Verarbeitung.

Die sechs geplanten R08-A/B/C-Tests bleiben **skipped**: R08-A1 liefert nur
das interne Repository, nicht das öffentliche `privacy.receipts`-Read-Model
oder R08-B/C-Funktionen.

## 13. Regression

Ausgeführt mit venv + DynamoDB Local (`RIS_TEST_DYNAMODB_ENDPOINT` auf
Loopback, nur synthetische Daten):

```text
718 passed, 6 skipped, 256 subtests passed
```

Enthalten: 32 Receipt-Contract-Tests, G5-Privacy-/Erasure-Tests, R01–R07-
Partnerprofil-Tests, 39 DynamoDB-Local-Tests (davon 6 neu) und 26 neue
Journal-Tests. Die 6 Skips sind ausschließlich die geplanten R08-A/B/C-Tests.

Zusätzlich:

- `terraform fmt -check` für die geänderten Dateien: PASS
- `terraform validate` (backend-frei): PASS, nur vorbestehende
  Validierungswarnungen
- `git diff --check`: PASS

DynamoDB Local wurde nach dem Lauf beendet; Port 18000 geschlossen; keine
Testtabellen zurückgelassen.

## 14. Offene rechtliche Entscheidungen

1. Aufbewahrungsfrist/Löschregel für PrivacyReceipts.
2. Verhältnis von Receipt-Aufbewahrung zu Erasure-Nachweisen (darf ein
   Löschbeleg den Löschvorgang überleben?).
3. Zulässigkeit und Wortlaut von Privacy-Notice/Consent-Referenzen.
4. Behandlung von Backups/PITR und Restore-Reconciliation.
5. Endgültige Evidence-Anforderungen für Provider-/Drittanbieter-Ereignisse.
6. Browser-/BFF-Delegationsmodell und dessen datenschutzrechtliche Zuordnung.

`REVIEW_REQUIRED` bleibt als expliziter Platzhalter offen und ist keine
rechtliche Feststellung.

## 15. R08-A2-Readiness

| Voraussetzung | Status |
|---|---|
| Stabiles, identitätsgebundenes Journal-Repository | GO |
| Dedizierte Tabelle + minimale IAM-Rechte | GO |
| Fail-closed-Konfiguration | GO |
| Atomare DynamoDB-Strategie spezifiziert | GO |
| S3-Outbox-/Reconciliation-Strategie spezifiziert | GO |
| Retention-/Legal-Policy freigegeben | **BLOCKED** |
| CRUD-Integration implementiert | **nicht in A1** |
| Öffentliches Receipt-Read-Model | **nicht in A1 (R08-B)** |

**R08-A2: BLOCKED** bis Retention-/Legal-Policy und Integrationsreview
freigegeben sind. R08-B/C/D und R07-B bleiben unverändert nicht gestartet.

## 16. Abschlussbericht

| Prüfung | Ergebnis |
|---|---|
| RIS Branch / HEAD | `feature/ris-partner-profile-persistence-v1` / `a38c510` (vor Gate) |
| PrivacyReceiptV1-Contract | wiederverwendet; 32 Contract-Tests PASS |
| Journal-Datenmodell | `PrivacyReceiptV1` + `scopeKey`/`scopeSort`/`contentHash` |
| Persistenz | eigene DynamoDB-Tabelle `privacy-receipts`, PAY_PER_REQUEST |
| Identitätsbindung | verifizierter Kontext, exakte User/Tenant/Partner/Issuer-Isolation |
| Append-Only-Semantik | bedingtes Insert, keine Update/Delete-API, kein Scan |
| Idempotenz | gleicher Inhalt → Replay; anderer Inhalt → Konflikt; parallel getestet |
| Pagination | GSI + sicherer Cursor, Limit ≤ 50, fremder Cursor abgelehnt |
| Keine sensiblen Daten | Contract + Speichertest + Logging-Grenze |
| Retention-Grenze | keine TTL, `REVIEW REQUIRED`, Writes fail-closed |
| DynamoDB Local | 39 Tests PASS (6 neu) |
| Neue Tests | 26 Unit/Contract + 6 Local |
| Gesamtregression | **718 passed, 6 skipped** |
| Browser-Auth-Boundary | `X-Api-Credential` nie im Browser; BFF/Delegation dokumentiert |
| R08-A2 bereit? | **BLOCKED** (Retention/Legal + Integration) |
| Git-Commit | `feat(ris): add durable privacy receipt journal repository` |
| 39 untracked erhalten | ja (unverändert, keine fremden Dateien gestaged) |
