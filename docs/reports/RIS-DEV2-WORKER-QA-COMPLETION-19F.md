# RIS-DEV2-WORKER-QA-COMPLETION-19F

**Datum:** 2026-11-27
**Branch / geprüfter Start-HEAD:** `feature/ris-analysis-integration-07` / `259caa7be426df0fe0a2936a5aefebce530673c2`
**Ausführung:** lokale QA und Dokumentation. Keine Live-AWS-Abfragen oder -Mutationen.

## Final gates

| Gate | Ergebnis | Evidenz / Einschränkung |
|---|---|---|
| `QA_ENVIRONMENT` | `VERIFIED` | Isolierte Python-3.14.10-venv, festgehaltene Paketversionen, `pip check` sauber; externe Netzwerkverbindungen im Testprozess blockiert. |
| `FULL_COLLECTION` | `PASS` | Vollständige RIS-Collection: 3.416 Tests, 0 Collection Errors; keine Suite ausgeschlossen. |
| `WORKER_REGRESSION` | `PASS` | Fokussierte Claim-/Lifecycle-/Security-/Transport-Gruppen: 279 passed, 6 Subtests. |
| `FULL_REGRESSION` | `PASS_WITH_DOCUMENTED_EXCEPTIONS` | RIS: 3.269 passed, 5 klassifizierte Fehler, 142 skipped, 446 Subtests; keine bestätigte Fix-Regression. Mays-Modul-Gruppen siehe unten. |
| `LOCAL_E2E` | `PASS` | Lokale RIS↔Mays-Orders-Gruppen: 53 passed, 4 Subtests; Mays Lambda-Suite: 240 passed. Nur lokale Fixtures/Testdoubles. |
| `BUNDLE_REPRODUCIBILITY` | `PASS` | Zweimal gebaut; beide Hashes entsprechen dem 19C/19D-Pin. |
| `DEPLOYMENT_SCOPE` | `VERIFIED` | Shared Agent-Bundle verdrahtet Agent-Worker und Dispatch-Ingress; separate Analysis-Lambda bleibt unberührt. Kein Plan/Upload. |
| `DEPLOYMENT_READINESS` | `READY_FOR_PLAN` | Nur Empfehlung für einen separat autorisierten, read-only 19G-Plan; nicht `READY_FOR_APPLY`. |
| `HISTORICAL_RECOVERY` | `NOT_EXECUTED` | Kein Zugriff/Write/Redrive. |
| `ALTERNATIVE_CANARY` | `NOT_AUTHORIZED` | Keine Order angelegt oder ausgeführt. |
| `MAYS_ORDERS_UPGRADE` | `NOT_AUTHORIZED` | Mays-Orders-Worktree nur gelesen; keine Änderungen. |
| `AWS_MUTATIONS` / `LIVE_INVOCATIONS` / `REDRIVES` | `0 / 0 / 0` | Keine AWS-Credentials oder Live-Endpunkte verwendet. |
| `SOURCE_CODE_CHANGES` | `0` | Nur dieser QA-Bericht und `docs/AI_AUDITLOG.md` werden geändert. |

## Environment und Reproduzierbarkeit

- RIS `requirements.txt` verlangt Python 3.14-kompatible Testabhängigkeiten, enthält aber Mindestversionen (`>=`) und kein Lockfile. Die CI-Datei deckt statische Terraform-Prüfungen ab, nicht die Python-Tests.
- Verwendet wurde eine neue isolierte Umgebung: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-19f-venv314`, Python **3.14.10**, ohne System-Site-Packages. Paketversionen wurden exakt aus bereits vorhandenen lokalen 3.14-QA-Snapshots festgehalten und installiert; Installationsquelle war der konfigurierte pip-Index/Cache. `pip check` war erfolgreich.
- Direkte Testabhängigkeiten: `pytest 9.2.0`, `pytest-cov 7.1.0`, `pytest-subtests 0.15.0`, `moto 5.2.5` (S3/DynamoDB/SQS extras), `requests 2.34.2`, `boto3 1.44.9`, `botocore 1.44.9`. Vollständiger installierter Freeze und temporärer Lock lagen außerhalb des RIS-Worktrees; keine Manifest-/Lockfile-Änderung.
- Keine AWS-Profile, Access Keys oder Session Tokens; leere temporäre AWS-Konfigurationsdateien und deaktivierte EC2-Metadaten. Ein nur für die QA-Prozesse geladener Socket-/DNS-Guard blockierte Nicht-Loopback-Verbindungen und ließ Loopback für lokale HTTP-Tests zu.
- RIS-Compileall und Mays Lambda-Source-/Tests-Compileall erfolgreich. Bundle-Tests: **15 passed, 2 skipped** (beide erfordern das nicht bereitgestellte `mayaws`-Profil). Eine bestehende `datetime.utcnow()`-Deprecation-Warnung bleibt.

### Dauerhafte RIS↔Mays-Orders-`PYTHONPATH`-Regel

Bei künftigen RIS-QA-Läufen dürfen der gesamte Temp-Root und `MO_ORDERS_SRC` **nicht gemeinsam** als breitflächiger `PYTHONPATH` für eine komplette RIS-Prozesssuite eingesetzt werden. Der RIS-QA-/Plugin-Root enthält Top-Level-Dateien wie `agent_order.py` und `validation.py`; diese können Mays-Orders-Module gleichen Namens überschreiben. Beobachtete Folgen waren zirkuläre/falsche Imports in Mays-Tests sowie zwei zusätzliche RIS Order-Ownership/Bridge-Fehler im gemeinsamen Vollsuite-Prozess. Diese zusätzlichen Fehler verschwanden bei Prozessisolation; dieselben Cross-Repo-Gruppen bestanden separat.

Verbindlicher Ablauf, ohne Suite-/Manifeständerung:

1. RIS-Vollsuite **ohne** `MO_ORDERS_SRC` ausführen.
2. Mays-Orders-Suites in separaten Prozessen mit `PYTHONPATH` ausschließlich auf das jeweilige Mays-Quellverzeichnis begrenzen (für Lambda: `...\lambda\src`). Runner-/Plugin-Hilfen gezielt laden, nicht den allgemeinen Temp-Root in den Mays-Modul-Suchpfad stellen.
3. RIS↔Mays-Contract-/Bridge-Gruppen ebenfalls separat ausführen; `MO_ORDERS_SRC` nur im jeweiligen RIS-Testprozess auf das lokale `lambda/src` setzen.
4. Nie einen globalen `MO_ORDERS_SRC`-Wert für die komplette RIS-Testausführung exportieren.

Der lokale Mays-Teststand war Clone-Commit `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`, detached und sauber. Das ist **nicht** der RIS-Pin (`5cf50a0...`) und nicht automatisch der freizugebende Upgrade-Zielstand.

## Collection, Suite-Ergebnisse und Skips

### RIS

| Lauf | Ergebnis |
|---|---|
| `pytest tests/ --collect-only -q` | **3.416 collected, 0 errors** |
| Vollsuite ohne Mays-Source-Env | **3.269 passed, 5 failed, 142 skipped, 446 subtests passed** |
| Worker-/Lifecycle-/Transport-/Security-Fokus | **279 passed, 6 subtests passed** |
| RIS-Paketierung + Ecosystem-Wiring | **15 passed, 2 skipped** |
| RIS↔Mays Dispatch-Handoff, Cross-Repo-Contract, Partner E2E und Bridge-Gruppen, isolierte Prozesse | **53 passed, 4 subtests passed** |

Keine Tests oder Module wurden ausgeschlossen. In den Tests verwendete Marker sind pytest-Standardmarker (`parametrize`, `skipif`); keine benutzerdefinierten Marker wurden zur Collection-Filterung verwendet.

Die 142 RIS-Skips sind begründet und nicht als PASS gewertet: nicht konfigurierter lokaler DynamoDB-Endpunkt; fehlende Parser-CLI/Node-Konfiguration; kein `MO_ORDERS_SRC` bzw. kein `MO_ORDERS_MODULE` im bewusst isolierten Vollsuite-Lauf; nicht bereitgestellte mayaws-Credentials für Live-/STS-Vertragsprüfungen; kein aufgezeichneter Plan; geplante/nicht implementierte Privacy-Funktionen; bekannte Windows-Grenzen für POSIX-Modus-/Symlinkprüfungen; dokumentierter CloudFront-OAC-Security-Befund. Die vollständigen Einzelfallgründe stehen im pytest-Protokoll `ris-19f-full-skip-reasons.out` außerhalb des Worktrees. Cross-Repo-Skips wurden durch die nachfolgend separat bestandenen Mays-/RIS↔Mays-Läufe ergänzt, nicht aus dem Testvertrag entfernt.

### Mays-Orders-Modul (lokal, read-only)

Die dauerhaft in RIS-QA zu berücksichtigenden Mays-Testgruppen wurden separat in eigenen Prozessen ausgeführt:

| Gruppe | Ergebnis | Klassifikation |
|---|---:|---|
| `lambda/tests` gemäß Mays `AGENTS.md` | **240 passed** | PASS |
| `module_builder/tests` | **86 passed, 14 failed, 6 Subtests** | 14 Windows-Pfad-/Plattform-Erwartungsfehler, siehe unten |
| Installer `installer.tests.test_installer` | **81 Tests, 11 Errors, 1 Skip** | Fehler durch fest codierte Linux-Pfade und `python3`, siehe unten |
| Seed-Tools `scripts/tests` | **28 passed** | PASS |

Die 14 Module-Builder-Fehler vergleichen Pfade mit POSIX-`/` (einschließlich generierter README-/Tree-Erwartungen) auf einem Windows-Runner, dessen tatsächliche Pfade `\\` enthalten; die betreffenden Artefakte/Dateien sind vorhanden. Als `ENVIRONMENT_FAILURE` klassifiziert, nicht behoben oder umgangen.

Alle 11 Installer-Errors endeten reproduzierbar in `FileNotFoundError [WinError 2]`: betroffene Tests starten `python3` und/oder verwenden den fest codierten Arbeitsordner `/home/dci-student/projects/Mays-Orders-AWS`. Diese Linux-Annahmen existieren auf dem Windows-Runner nicht. Als `ENVIRONMENT_FAILURE` klassifiziert. Keine Tests wurden gepatcht oder mit Ersatzpfaden wiederholt.

Mays-Gruppen wurden vollständig in der für 19F erreichbaren Teststruktur identifiziert: Lambda, Module Builder, Installer, Seed-Tools. Zusätzliche Backup-/E2E-Testbereiche, die laut Mays-Anweisungen Live-/bereitgestellte Infrastruktur voraussetzen, wurden nicht live ausgeführt; es gab keine AWS-Credentials und der externe Netzwerkzugriff war gesperrt.

## Klassifikation der fünf RIS-Vollsuite-Fehler

Seit Referenz `4e19726bf733e6d4f2f75fae0e083c8e0bd906b5` gibt es keine Änderungen an RIS-Source, Tests, Terraform oder Installer-Code; der Branch-Zuwachs bis zum geprüften HEAD enthält die dokumentierten 19E-Berichte/Audit-Einträge. Die Fehler sind mit dem aktuellen, unveränderten Code-/Teststand reproduziert und keine Änderung des Worker-Fixes:

| Fehler | Klasse | Deployment-Risiko / Entscheidung |
|---|---|---|
| `test_analysis_fresh_plan_16c1::test_bundles_match_local_artifacts_when_present` – lokales Worker-ZIP ist `78eb6e…`, historisches 16C1-Manifest erwartet `85775f…` | `BASELINE_FAILURE` – veralteter historischer Artefakt-Pin | Erwartete Folge des später korrigierten Worker-Bundles; 19C/19D pinnt `78eb6e…`. Keine Änderung an Analysis-Lambda oder Worker-Fix belegt. Historisches Manifest nicht aktualisiert. Separater Plan muss aktuellen Kandidatenhash prüfen. |
| `test_composite_lifecycle::TestStateCommandBackend::test_discover_subprocess_env_keeps_path` – Test fordert `mayaws`, Profil fehlt absichtlich | `ENVIRONMENT_FAILURE` | Test versucht STS-Identitätsvalidierung; in 19F wurden keine Credentials/externen Endpunkte bereitgestellt. Kein WorkItem-/Worker-Runtime-Pfad. Kein Live-STS zur Behebung. |
| Drei `test_platform_openapi_contract`-Assertions – Terraform-/Dispatcher-Route `POST /v1/apiprofiles/{apiProfileId}/binding` fehlt im kanonischen OpenAPI-Dokument | `CONTRACT_FAILURE` | API-Dokumentations-/Contract-Abweichung, unabhängig vom Worker-Claim-/Dispatch-Envelope-Fix. Muss als eigener API-Contract-Befund verfolgt werden; 19F ändert weder Route noch Spec. |

Der Lauf mit globalem `MO_ORDERS_SRC` hatte zwei zusätzliche Order-Ownership-/Bridge-Fehler (3.320 passed, 7 failed, 89 skipped, 450 Subtests). Die betroffenen RIS↔Mays-Testgruppen bestanden in isolierten Prozessen. Daher als `ENVIRONMENT_FAILURE` durch Python-Modulüberschattung/Prozesskontamination klassifiziert; dieser Lauf ist nicht der maßgebliche RIS-Vollsuite-Wert.

## Worker-Regression, Cross-Repo und Bundle

- Fokussierte Regression **279 passed / 6 Subtests**; enthält den erfolgreichen QUEUED-Initialclaim bis zur Agent-Ausführung, FAILED-only Retry-Claim, verlorene Conditional Writes, Duplicate Suppression, konkurrierende Claims, Agent Resolution/Execution, Fehlerbehandlung, Result Publication/Consumer, Tenant-/Owner-Isolation und MODE-Verhalten. Bestehende RUNNING-Items bleiben gegen unautorisierte Wiederholung geschützt.
- Separater RIS↔Mays-Testnachweis: `test_lambda_bridge_e2e.py`, `test_agent_order_dispatch_e2e.py`, `test_mo_contract_compat.py` **22 passed**; zusätzlich `test_mo_dispatch_handoff.py` **10 passed**, `test_cross_repo_mo_contract.py` **5 passed + 4 Subtests**, `test_partner_e2e_real.py` **16 passed**. Diese Befunde sind lokale synthetische Tests, keine Live-Order.
- Mays Lambda-Tests bestanden **240/240** mit dem gezielten Source-Pfad. Ursache eines ersten fehlgeschlagenen Runnerstarts war der allgemeine `Temp\opencode`-Pfad im `PYTHONPATH`, der Mays-Top-Level-Module überschattete; nach Isolation bestand die Suite. Dieser Fall ist oben als dauerhafte RIS-QA-Regel festgehalten.
- Agent-Bundle zweimal mit `python lambda/build_zip.py --bundle agent` erzeugt. Beide Builds und vorhandenes ignoriertes lokales Artefakt: SHA-256 **`78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7`**, **115 Dateien**. Enthält Handler, Pipeline und Dispatch-Ingress; keine Testdateien oder `.pyc`; separate `analysis_runner.py`-Lambda nicht enthalten. Kein Upload.
- Terraform-Wiring aus lokalem Source bestätigt gemeinsamen Artefaktkonsum durch Agent-Worker und Dispatch-Ingress; separate Analysis-Lambda verwendet ihr eigenes Artefakt. Keine Runtime-Konfiguration, insbesondere `MODE=true`, geändert.

## Separate Mays-Orders-Upgrade-Gates (weiter offen)

19F ersetzt keinen vollständigen XRepo-Audit oder Upgrade-QA. Weiter separat zu klären: exakter freizugebender Generated-Module-Pin und Provenienz gegenüber lokalem `db4f9e7`-/RIS-Metadatenstand; RC4 `agentOrder` Create-Validator-Kompatibilität; Transport-V1-HMAC-Vertrag gegenüber dem dokumentierten RC4-`APP_MANAGED`-HMAC; Installer-/Builder-QA auf unterstützter Linux-Umgebung. Kein Mays-Modul, Pin, Manifest oder Testvertrag wurde geändert.

## Empfehlung 19G und Grenzen

**Nächster konkreter Auftrag:** `RIS-DEV2-WORKER-DEPLOYMENT-PLAN-19G`, ausschließlich read-only und nach eigener expliziter Freigabe. Vor Planbeginn lokalen Kandidatenhash `78eb6e…`, Branch/Worktree, AWS-Identität, Workspace/State-Lineage und die aktuelle Freigabe erneut verifizieren. Einen Terraform-Plan nur nach Planauftrag mit Backend-/State-Zugriff gemäß dessen Grenzen erstellen; erwarteter Scope ist exakt ein In-place-Update des gemeinsamen Worker-Artefakts bei **Agent-Worker + Dispatch-Ingress**, keine separate Analysis-Lambda und keine zusätzlichen Ressourcenänderungen/-ersetzungen. Plan bei Hash-, Identity-, Drift- oder Scope-Abweichung stoppen. Kein Apply, Upload, Recovery, Redrive, Canary, Order, Upgrade oder Deployment wird durch 19F autorisiert.

`READY_FOR_PLAN` ist eine lokale QA-Empfehlung, keine AWS-Aktionsfreigabe. Historische Recovery bleibt nicht ausgeführt; alternative Canary und Mays-Orders-Upgrade bleiben nicht autorisiert.

## Abschlussnachweis

- Start-HEAD und Remote-HEAD vor Änderungen: `259caa7be426df0fe0a2936a5aefebce530673c2`.
- Commit-SHA, Remote-HEAD und abschließender Worktree-Status werden nach dem Dokumentationscommit in diesem Abschnitt ergänzt.
- AWS-Mutationen 0; Live-Invocations 0; Redrives 0; Source-Code-Änderungen 0; Mays-Orders-Änderungen 0.
