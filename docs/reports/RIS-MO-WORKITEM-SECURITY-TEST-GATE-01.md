# RIS-MO-WORKITEM-SECURITY-TEST-GATE-01

**Datum:** 2026-11-25
**RIS-Branch:** `feature/ris-analysis-integration-07`
**RIS-Baseline:** `f2c0fdd7f9b4fb38c7dbdb66ab31589ae1c991c7`
**MO-Pin (verifiziert):** `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`
**Plan-Kandidat (unverändert):** `279a530fa957a0547a355cb94822e42d4639128d315712eac6faa2fbceea1184`
**Modus:** Tests + Dokumentation; **kein Apply, kein AWS-Write, kein State-Write, kein Main-Merge**

## Ergebnis

**READY FOR LIMITED HUMAN RISK ACCEPTANCE** — begrenzt auf synthetische
DEV2-Daten, ohne echte Personendaten.

Belege: gepinnte MO-Lambda-Suite **240 Tests OK**; die vier geforderten
MO-Sicherheitsdateien **101 Tests OK**; RIS-Cross-Repo-Set **60 passed, 0
skipped**; erweitertes Order-/Auth-Set **160 passed, 7 subtests, 0 skipped**.
Die WorkItem-Matrix ist vollständig fail-closed; die IAM-Policy enthält nur
`dynamodb:GetItem` auf zwei Tabellen. Die verbleibende Risikofläche ist die
IAM-weite Tabellenlesbarkeit (kein itemgenauer IAM-Ausdruck möglich), die nur
durch Anwendungscode begrenzt wird.

## 1. Grundlagen

Gelesen: `AGENTS.md` (RIS), `docs/AI_AUDITLOG.md` (RIS),
`AGENTS.md` (Mays-Orders), `docs/AI_AUDITLOG.md` (Mays-Orders),
`docs/AGENTS.md` (MO-Verweis) sowie die MO-Teststrategie.

Pin-Verifikation:

| Prüfung | Wert |
| --- | --- |
| MO-Checkout | `installer/projects/mays_order_builder` |
| `git rev-parse HEAD` | `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` |
| Builder-Pin | `installer/mays-orders-builder.pinned.json` = `db4f9e7…` |
| Arbeitsbaum | unverändert; kein MO-Code angefasst |

**Isolierte Prozesse:** MO-Suite, RIS-Cross-Repo-Set und erweitertes RIS-Set
liefen in getrennten Python-Prozessen. Die bekannte Harness-Interferenz
(Cross-Repo + Bridge im selben Prozess) wurde damit umgangen und nicht als
Produktfehler gewertet. Es gab **keine Skips** in den geforderten
Cross-Repo-Läufen.

## 2. Mays-Orders-Suite (gepinnt)

Befehl (Windows-äquivalent): `cd lambda; PYTHONPATH=src python -m unittest discover -s tests -v`

| Lauf | Ergebnis |
| --- | --- |
| Vollständige MO-Lambda-Suite | **Ran 240 tests — OK**, 0 failures, 0 errors, 0 skipped |
| `test_dispatch.py`, `test_result_handoff.py`, `test_result_consumer_lambda.py`, `test_ownership.py` | **Ran 101 tests — OK** |

Abgedeckte Transportnachweise (unverändert übernommen, nicht dupliziert):

- Dispatch-Envelope und Idempotenz,
- Result-Handoff und Consumer-Verarbeitung,
- Signaturprüfung über die Envelope-`messageId` (nicht die SQS-Record-ID),
- falsche Work-ID/Korrelation wird verworfen,
- Owner-Isolation bei Lese-/Statuspfaden,
- partielle Batch-Fehler und DLQ-Verhalten.

## 3. RIS-Tests gegen denselben Pin

`MO_ORDERS_SRC` = obiger `lambda/src`-Pfad; Cross-Repo-Tests **nicht**
übersprungen.

| Lauf | Ergebnis |
| --- | --- |
| `test_mo_dispatch_handoff.py`, `test_agent_order_dispatch_e2e.py`, `test_work_queue.py`, `test_analysis_synthetic_profile.py`, `test_analysis_runtime_terraform.py` | **60 passed**, 0 skipped |
| `test_orders_reader.py`, `test_orders_reader_agent_gate.py`, `test_agent_order_order_description.py`, `test_order_transport_contract.py`, `test_dispatch_ingress_lambda.py`, `test_analysis_order_boundary.py`, `test_analysis_runner_pipeline.py` | **160 passed, 7 subtests**, 0 skipped |

Enthalten: Order-GET mit JWT, fremder Owner → 404, ORDER_RESULT-E2E gegen MO
`db4f9e7`, Dispatch→Work-Queue, WorkItem-Idempotenz, Analysis-Boundary.

## 4. WorkItem-Sicherheitsmatrix

Verifikation: `lambda/analysis_runner.py::_build_synthetic_verifier` liest die
persistierte Zeile per `GetItem(ConsistentRead=True)` und akzeptiert nur
`status=RUNNING` **und** exakte Übereinstimmung von `tenantId`, `userId`,
`partnerApplicationId`, `issuer`. Jede Abweichung oder ein Lesefehler führt zu
„keine synthetische Identität“ und damit zur normalen, consent-/entitlement-
abhängigen Ablehnung.

| Fall | Test | Ergebnis |
| --- | --- | --- |
| Positiv: persistiertes `RUNNING`, korrekte WorkId + alle Identitätsfelder | `test_persisted_verifier_maps_camelcase_fields`, `test_real_verifier_drives_the_analysis_agent`, `test_exact_identity_gets_a_synthetic_identity` | PASS (akzeptiert) |
| Unbekannte WorkId (Key nicht vorhanden) | **neu** `test_unknown_or_empty_work_id_is_denied` | PASS (fail-closed) |
| Leere/fehlende WorkId | **neu** dito (`""`, `None`) | PASS (fail-closed) |
| Nicht persistiertes WorkItem | `test_persisted_verifier_maps_camelcase_fields` (leere Tabelle), `test_direct_invoke_without_trusted_binding_is_denied` | PASS |
| Ungültiger Status (`QUEUED`/`COMPLETED`/`FAILED`/`CANCELLED`) | `test_persisted_verifier_maps_camelcase_fields` | PASS |
| Fremder Tenant | Identitäts-Loop + `test_every_mismatch_is_denied` | PASS |
| Fremder User | dito | PASS |
| Fremde PartnerApplicationId | dito | PASS |
| Falscher Issuer | dito | PASS |
| Manipuliertes Event (nested/outer Konflikt) | `test_manipulated_nested_workitem_is_denied`, `test_outer_real_nested_synthetic_is_denied_without_parser` | PASS (kein Parser-Aufruf) |
| Replay eines abgeschlossenen WorkItems | **neu** `test_replay_of_completed_workitem_is_denied_without_result` | PASS, **kein `data`-Feld** |
| DynamoDB-Lesefehler | bestehender Verifier-Test + **neu** `test_workitem_read_error_is_denied_without_result` | PASS, **kein `data`-Feld** |

Die drei neuen Tests ergänzen ausschließlich bislang ungeprüfte Grenzen
(Key-Bindung, Replay ohne Ergebnisfreigabe, Lesefehler ohne Ergebnisfreigabe);
bereits belegte Fälle wurden nicht dupliziert.

**Beobachtung (kein Defekt):** Die WorkId-Bindung stützt sich auf die
DynamoDB-Key-Semantik von `GetItem`; der Verifier vergleicht `item["workId"]`
nicht zusätzlich mit der Anfrage. Das ist bei echtem DynamoDB korrekt, wäre aber
eine sinnvolle Defense-in-Depth-Härtung. Sie wurde **nicht** umgesetzt, weil
dieses Gate keine RIS-Laufzeitänderung erlaubt.

## 5. IAM-Grenze

Geprüft am Plan-Kandidaten (`terraform show -json`) und am Modul:

| Prüfung | Ergebnis |
| --- | --- |
| Aktionen der Analysis-Daten-Policy | ausschließlich `dynamodb:GetItem` |
| Ressourcen | `…:table/ris-dev2-dev-partner-profiles`, `…:table/ris-dev2-dev-work-items` |
| `dynamodb:Query` / `Scan` | nicht vorhanden |
| Schreibrechte (`PutItem`, `UpdateItem`, `DeleteItem`, Batch-Write) | nicht vorhanden |
| Orders-DynamoDB | **keine** Ressource, kein ARN |
| Statements | 2 (PartnerProfiles, WorkItems) |

Zusätzlich pinnt `tests/test_analysis_runtime_terraform.py` die Aktionsmenge
per Regex auf genau `{dynamodb:GetItem}` und verbietet `mays-orders`/
`ORDERS_TABLE` in Modul und Analysis-Quellen.

### Verbleibende Risikofläche (ausdrücklich)

- **Anwendungstests beseitigen den IAM-weiten Tabellenzugriff nicht.**
  `GetItem` gilt für jeden Schlüssel der jeweiligen Tabelle. Eine itemgenaue
  IAM-Grenze ist für `GetItem` nicht ausdrückbar (`LeadingKeys` gilt nur für
  `Query`/`Scan`).
- Die Begrenzung erfolgt ausschließlich im Code:
  - PartnerProfiles: `_identity_ok` prüft gespeicherte `userId`/`tenantId`
    (und optional Partner/Issuer) nach dem Read;
  - WorkItems: exakter Identitätsvergleich gegen die persistierte Zeile.
- Jeder künftige Codepfad dieser Lambda mit derselben Rolle könnte beide
  Tabellen tabellenweit lesen. Mitigation: kleiner Bundle-/Handlerumfang,
  keine Order-Tabelle, deny-by-default-Konfiguration, keine Schreibrechte.
- Der synthetische Pfad ist derzeit **inaktiv** (`ANALYSIS_SYNTHETIC_MODE=false`);
  die WorkItems-Berechtigung ist damit ruhend.

## 6. Entscheidung

**READY FOR LIMITED HUMAN RISK ACCEPTANCE.**

Bedingungen der begrenzten Akzeptanz:

1. Nur `ris-dev2` mit synthetischen Testdaten; keine echten Personendaten.
2. Akzeptiert wird die tabellenweite `GetItem`-Lesbarkeit beider Tabellen,
   begrenzt durch Anwendungscode — nicht durch IAM.
3. Der synthetische Modus bleibt aus, bis eine gesonderte Aktivierung
   freigegeben ist.
4. Eine interne, autorisierte WorkItem-Verifikationsschnittstelle bleibt offen
   (siehe `RIS-DEV2-ORDER-API-READ-01`, §4); bis dahin bleibt der direkte
   `GetItem`-Pfad fail-closed.

## 7. Nicht ausgeführt

Kein `terraform apply`, keine AWS-Mutation, kein State-Write, kein Main-Merge,
keine Änderung an MO-Produktionscode, RIS-Laufzeit, Terraform oder am Plan.
Der Plan `279a530f…` bleibt unverändert und unangetastet; der alte Plan
`2bbf8142…` bleibt gesperrt.
