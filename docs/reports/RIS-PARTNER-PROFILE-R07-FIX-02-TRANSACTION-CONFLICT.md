# RIS-PARTNER-PROFILE-R07-FIX-02 — TRANSACTION CONFLICT CLASSIFICATION & BOUNDED RETRY

## 1. Git-Baseline

| Prüfung | Ergebnis |
|---|---|
| Branch | `feature/ris-partner-profile-persistence-v1` |
| HEAD vor Fix | `8e8bb4c` (`fix(ris): make partner profile persistence DynamoDB-compatible`) |
| Tracked Working Tree | clean |
| Untracked Dateien | 39, unverändert |
| Scope | ausschließlich Mays-RIS |
| AWS-Mutation | keine |

## 2. Root Cause (vor der Änderung)

Alle Schreibtransaktionen (`create`, `delete`, `reserve_parent_delete`,
`finalize_parent_delete`) fingen ausschließlich
`self.client.exceptions.TransactionCanceledException` und werteten darin nur
`ConditionalCheckFailed` aus. Daraus folgte:

- Jeder andere `CancellationReason` – insbesondere `TransactionConflict` –
  wurde als generischer fachlicher `PartnerProfileConflictError` (409)
  behandelt.
- Ein top-level `TransactionConflictException` wurde nicht erkannt.
- `TransactionInProgressException` wurde nicht unterschieden.
- Es gab **keinen** Retry: ein kurzer, rein transienter Konflikt führte
  sofort zu 409.
- Netzwerk-/Timeout-Fehler nach dem Senden wurden als generischer 500
  weitergereicht; der Commit-Ausgang blieb unbestimmt.
- `None` in `CancellationReasons` wurde nicht sauber als „kein eigener Fehler
  dieser Aktion“ interpretiert.

## 3. Klassifikation

Zentrale, wiederverwendbare Funktion
`classify_transaction_error(exc) -> (kind, failed_indices)`.

| Eingabe | Ergebnis | Retry |
|---|---|---|
| `TransactionCanceledException` mit ausschließlich `TransactionConflict` und/oder `None` | `transient` | ja, begrenzt |
| `TransactionCanceledException` mit `ConditionalCheckFailed` | `business` | nein |
| `ConditionalCheckFailed` + `TransactionConflict` gemischt | `business` (Transaktion nicht committet) | nein |
| `None`/leere `CancellationReasons` | `indeterminate` | nein |
| unbekannter Reason-Code | `indeterminate` | nein |
| `ValidationError` / `ItemCollectionSizeLimitExceeded` | `fatal` | nein |
| top-level `TransactionConflictException` | `transient` | ja, begrenzt |
| `TransactionInProgressException` | `indeterminate` | nein |
| `EndpointConnectionError`, Timeout, Connection-Closed, HTTP-5xx | `indeterminate` | nein |
| ProvisionedThroughput/Throttling | `transient` | ja, begrenzt |
| sonstige Client-/Programmierfehler | `fatal` | nein |

Regeln:

- `None` bedeutet: diese Transaktionsaktion hat keinen eigenen Fehlergrund.
- Gemischte Gründe werden **nie** blind als transient behandelt. Ein
  `ConditionalCheckFailed` ist autoritativ (nichts committet) und wird auf den
  passenden fachlichen Fehler abgebildet; unbekannte Beimischungen führen zu
  `indeterminate`.
- Fehlende oder unbekannte Gründe werden fail-closed behandelt.
- Keine SDK-Rohfehler oder Ressourcen-IDs gelangen in API-Antworten.

## 4. Retry-Strategie

`PartnerProfileRepository._transact(...)` kapselt die Ausführung:

| Parameter | Wert | Begründung |
|---|---|---|
| Max. Versuche | **3** | Lambda-Timeout ist 30 s; drei kurze Versuche bleiben weit darunter |
| Gesamtbudget | **1,0 s** | harte Obergrenze inkl. Backoff |
| Backoff | Full Jitter, Basis 50 ms, Cap 300 ms | exponentiell mit Jitter, keine Synchronisation |
| Retry nur bei | `transient` | fachliche Bedingungen werden nie wiederholt |
| Unbekannter Ausgang | kein Retry | kein Blind-Commit |

Die **gleiche** `TransactItems`-Liste wird bei jedem Versuch verwendet. IDs,
Timestamps und Payloads werden vor dem ersten Versuch einmal erzeugt und nicht
verändert. Alle Bedingungen (`count < :max`, `attribute_not_exists`,
`version = :v`, Parent-/Guard-Checks) werden bei jedem Versuch erneut von
DynamoDB geprüft.

Bei erschöpften transienten Versuchen: `PartnerProfileTransientError` → **503**.
Kein fachlicher 409, keine Teilanlage, keine Counter-Buchung.

## 5. Unbekannter Commit-Ausgang

- **Create mit Idempotency-Key:** Nach `indeterminate` wird das
  Idempotenz-Item mit `ConsistentRead=True` gelesen. Existiert es mit
  passendem Payload-Hash, wird die ursprüngliche `targetResourceId`
  zurückgegeben (Erfolg wiederhergestellt). Existiert es mit anderem Hash →
  409. Existiert es nicht → 503; der Client kann mit demselben Key erneut
  versuchen, ohne eine zweite Ressource zu erzeugen.
- **Create ohne Idempotency-Key:** kein Retry, kein Recovery → 503.
- **Delete / Reserve / Finalize:** kein blinder Retry. Der Client kann mit
  derselben Version erneut versuchen; die Versions-/Statusbedingungen
  verhindern doppelte Effekte.
- **Update:** nutzt `PutItem` mit `version = :v`, keine Transaktion. Ein
  Netzwerkfehler bleibt ein kontrollierter 5xx; es wird nicht automatisch
  wiederholt.

## 6. ClientRequestToken — Entscheidung

**Nicht verwendet.**

- DynamoDB-Token sind nur **10 Minuten** idempotent; RIS braucht **24 Stunden**
  Anwendungsidempotenz.
- Ein `TransactionConflict` bedeutet laut AWS: Die Transaktion wurde
  abgebrochen, es wurde nichts committet. Ein Retry benötigt dafür keinen
  Token.
- Unbekannte Ausgänge werden nicht retryt, sondern über den 24-h-
  Idempotenznachweis (Create) oder gar nicht (Delete/Update) behandelt.
- Ein zusätzlicher Token würde eine zweite, kürzere Idempotenzsemantik
  einführen und die RIS-Semantik verwässern.

## 7. HTTP-Mapping

| Situation | Status |
|---|---|
| Capacity exceeded | 409 |
| Stale `version` | 409 |
| Parent fehlt / wird gelöscht | 409 bzw. 404 (bestehend) |
| Idempotency-Key mit anderem Payload | 409 |
| Transienter Konflikt, Retry erfolgreich | normaler Erfolg (200/201/204) |
| Transienter Konflikt, Budget erschöpft | **503** `Service unavailable` |
| Unbekannter Commit-Ausgang | **503** `Service unavailable` |
| Nicht klassifizierbarer DynamoDB-/Client-Fehler | 500 `Internal error` |
| Read-Fehler | 500 (R07-FIX-01) |

Die 503-Abbildung ist in den Partner-Handlern für Manual, CV, CVSearchProfile
und ATS sowie im zentralen `_partner_storage_guard` verankert. Es werden keine
Token, Credentials, Payloads oder internen IDs ausgegeben.

## 8. Tests

Neu: `tests/test_partner_profile_transaction_conflict.py` — **29 Tests PASS**.

| Bereich | Abdeckung |
|---|---|
| Klassifikation | reiner Conflict, Conditional, gemischt, fehlende/`None`/unbekannte Gründe, ValidationError, TransactionInProgress, Netzwerk, beliebiger Fehler |
| Retry | ein/zwei Konflikte, Limit, Versuchszahl, Backoff-Aufrufe, Capacity/Stale/Idempotency ohne Retry |
| Unbekannter Ausgang | Create ohne Key, Create mit Key + Recovery, Delete, TransactionInProgress |
| Invarianten | keine Doppelanlage, keine doppelte Counter-Buchung, Delete ohne Doppeleffekt, Parent-Guard wird beim Retry erneut geprüft |
| Konkurrenz | zwei Creates um den letzten Platz, Update-vs-Update mit gleicher Version |
| HTTP | 503 bei Erschöpfung/unklarem Ausgang; 409 bleibt für Capacity und Stale Version |

Zusätzlich werden die bestehenden R05-A-/R05-B-/R06-/R07-G0-/R07-FIX-01-Tests
unverändert ausgeführt.

## 9. DynamoDB-Local-Regression

Die R07-A-Toolchain war noch vorhanden:

- Temurin JRE 21.0.13+9, DynamoDB Local 3.3.2
- Loopback-Launcher, Bindung ausschließlich `127.0.0.1:18000`
- vorhandener Endpoint-Guard, Tabelle `ris-r07g0-*`

Ergebnis: **23/23 DynamoDB-Local-Tests PASS** (Persistence, Capacity,
Idempotency, GSI/Pagination). Der Server wurde danach gestoppt; keine Tabelle
blieb zurück.

DynamoDB Local belegt reale Transaktions-/GSI-Semantik, aber **nicht** die
vollständige AWS-API-Gateway-/Cognito-/IAM-Kette und nicht das reale
AWS-Konfliktverhalten unter Produktionslast.

## 10. Gesamtregression

| Umgebung | Ergebnis |
|---|---|
| System-Python ohne boto3/Endpoint | **523 passed, 23 skipped, 256 subtests** |
| Venv + DynamoDB-Local-Endpoint | **546 passed, 0 skipped, 256 subtests** |
| `git diff --check` | PASS |
| Terraform / OpenAPI | nicht betroffen (keine Änderung) |

## 11. Verbleibende Findings

| ID | Status |
|---|---|
| F-4 TransactionConflict / Retry | **CLOSED** (R07-FIX-02) |
| F-5 Legacy Capacity-Counter | OPEN, unverändert |
| F-6 Cursor-Integrität | OPEN, unverändert |
| P1-1 CVDocument-Naming/Status | OPEN, unverändert |
| R08 S3-Version-Purge | OPEN, unverändert |
| Residual | `finalize_parent_delete` nach bereits erfolgtem S3-Delete: bei 503 bleibt die Metadaten-Löschung mit Guard `deleting` stehen; kein automatischer Retry, kein doppelter S3-Effekt. R07-B/R08 muss den Wiederanlauf definieren. |
| Residual | `update` (PutItem) hat keinen Transaktions-Retry; Netzwerkfehler bleiben 500. Bewusst, da kein Transaktionskonflikt. |

## 12. R07-B-Relevanz

R07-B (AWS E2E) bleibt **NOT RUN / NOT DEPLOYED**. Die neuen Retry-Pfade
müssen dort unter realer API-Gateway-/Cognito-/IAM-Kette und realer
DynamoDB-Konkurrenz beobachtet werden. Keine AWS-Mutation in diesem Gate.

## 13. Status

- **IMPLEMENTED:** zentrale Klassifikation, begrenzter Jitter-Retry,
  Idempotenz-Recovery, 503-Mapping.
- **VERIFIED:** 29 neue Tests; 23 DynamoDB-Local-Tests; 546/523 Regression.
- **OPEN:** F-5, F-6, P1-1, R08, Residual finalize/update.
- **NOT RUN:** AWS-E2E.
- **NOT DEPLOYED:** keine AWS-Mutation, kein Push/PR/Merge.

**R07-FIX-02: GO.**
