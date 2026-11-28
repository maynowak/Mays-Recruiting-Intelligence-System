# RIS-DEV2-ARTIFACT-SCOPE-RECONCILIATION-19G2

**Datum:** 2026-11-27\
**Branch:** `feature/ris-analysis-integration-07`\
**Abschluss-HEAD:** `be51f5eca69262fb3a793d3eb693faa812788d59`\
**Ergebnis:** **ARTIFACT_SCOPE=PASS — QA PASS — STOP AM 19G3-FREIGABEGATE**

## Entscheidung und Grenzen

Die 19G-Abweichung ist lokal korrigiert: Agent-Worker und Dispatch-Ingress
verwenden weiterhin ausschließlich das freigegebene Bundle
`507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
Analysis und Orders-Reader referenzieren über die separate Datei
`terraform/ris-dev2-19g2-artifact-overrides.tfvars.json` wieder exakt ihre
bisherigen Artefakte. Die kanonische plattformübergreifende Bundle-Erstellung
wurde nicht zurückgenommen.

`MODE=true`, Worker-Pin-Commit `febab54cfe6e0b4c6c67a4e94b7afb9083643576`
und Mays-Quelle `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` blieben unverändert.
Es gab keinen AWS-Zugriff, Plan, Apply, State-Eingriff, Live-Test, Install,
Order, Redrive, Recovery, Entitlement-Write oder Main-Merge. Der gespeicherte
19G-Plan blieb ausschließlich lokale Read-only-Evidenz und ist gesperrt.

## 19G-Plan: gelesene Evidenz, nicht wiederverwendbar

Der vorhandene Plan wurde lokal nur nach SHA-256 geprüft und mit
`terraform show -json` ausgelesen. SHA-256:
`7d8bfbb282795feb66b0e072250b8454f2cd111302aa920f7dc56d8268d65851`.
Er enthielt **0 Add / 4 Change / 0 Destroy**, 270 No-op-Ressourcen und keine
erkannte Resource-Drift. Jede der vier Lambda-Änderungen betraf
`source_code_hash` und das daraus berechnete `last_modified`:

| Lambda | Vorher deployed | 19G geplant | Lokale Referenz im korrigierten Scope |
|---|---|---|---|
| Agent-Worker | `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383` | `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d` | `terraform/lambda.zip`, `lambda/build_zip.py --bundle agent`; Shared Worker-Pin und `module.lambda.aws_lambda_function.agent` |
| Dispatch-Ingress | `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383` | `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d` | Dasselbe `terraform/lambda.zip`; `module.agent_transport[0].aws_lambda_function.dispatch_ingress` |
| Analysis | `276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10` | `370890d459488304481d99255cfa6a2891b5f19a8c5df2723556905195c7c621` | Bewahrtes ZIP unter `terraform/artifacts/`; expliziter DEV2-Override; `filebase64sha256(var.analysis_zip_path)` |
| Orders-Reader | `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b` | `bea4c3e59666bed8ad071ad4e405bcdfd57dafdac68096ce648667f0effb1b41` | Bewahrtes ZIP unter `terraform/artifacts/`; expliziter DEV2-Override; `filebase64sha256(var.filename)` |

Die zwei erwarteten Worker-/Ingress-Code-Updates waren im Soll. Analysis und
Reader verursachten die zwei zusätzlichen Änderungen. Der alte Plan ist nicht
auf die korrigierte Konfiguration übertragbar und **nicht anwendbar**.

## Root-Cause-Nachweis

### Analysis — `ANALYSIS_ARTIFACT_ROOT_CAUSE=VERIFIED`

Der exakte Read-only-Snapshot aus der lokalen 19B-Evidenz ist erhalten als
`terraform/artifacts/ris-dev2-analysis-276b4e4420272167dd32c590d6dbabed4008724a7091e4d86504d5444fe26b10.zip`.
Seine SHA-256 stimmt mit dem bisherigen Deployment-Hash überein.

Der Vergleich mit dem kanonischen Analysis-ZIP zeigt 113 Mitglieder mit
identischer Mitgliedschaft und Reihenfolge: 23 byte-identisch, 89 ausschließlich
CRLF/LF-Unterschiede und eine echte Runtime-Inhaltsänderung in
`agents/runtime/pipeline.py`. Das alte Archiv verwendete DEFLATE, das aktuelle
kanonische Archiv STORED. `create_system=0`, Zeitstempel 1980-01-01 und
Berechtigungen 0644 sind gleich. Damit ist die Abweichung **nicht nur
Packaging**; das bestehende Deployment-Artefakt muss erhalten bleiben.

### Orders-Reader — `READER_ARTIFACT_ROOT_CAUSE=VERIFIED`

Der Reader enthält vier Mitglieder mit gleicher Mitgliedschaft/Reihenfolge:
ein Member ist byte-identisch, drei unterscheiden sich nur durch CRLF/LF;
normalisiert sind alle vier Inhalte identisch zum aktuellen Quellstand. DEFLATE
gegen STORED ist die relevante Archivdifferenz; Zeitstempel, Berechtigungen und
`create_system=0` stimmen überein.

Das historische Verfahren, abgeleitet aus Quellrevision
`f08dfff36b8d4727ebdbbe92b641fb60a4da88fd`, reproduzierte den bisherigen ZIP-Hash
`610004f6…c81ae6b` zweimal mit Python 3.14.10/zlib-ng 1.3.1. Der reproduzierbare
Build ist separat in `scripts/build_preserved_ris_dev2_reader.py` dokumentiert;
der kanonische Builder blieb unverändert.

## Korrigierte Artefaktzuordnung und lokale Verifikation

| Gate | Ergebnis | Nachweis |
|---|---|---|
| `ARTIFACT_SCOPE` | **PASS** | DEV2-Overrides binden nur Analysis/Reader an die bewahrten Artefakte. |
| `WORKER_BUNDLE_REPRODUCIBILITY` | **PASS** | Agent-Bundle zweimal lokal gebaut; beide SHA-256 `507bc17…`. Ubuntu baut die kanonischen drei Bundle-Kandidaten jeweils zweimal identisch. |
| `ANALYSIS_ARTIFACT_PRESERVED` | **PASS** | Exaktes 19B-ZIP, SHA-256 `276b4e…`, als versioniertes Artefakt. |
| `READER_ARTIFACT_PRESERVED` | **PASS** | Historischer ZIP-Hash zweimal exakt reproduziert und versioniert. |
| Terraform-Verdrahtung | **PASS** | Vertrags-Test prüft Override-Datei, Artefakthashes, Root-Modul-Variablen und beide `filebase64sha256`-Referenzen. |
| Terraform lokale Validierung | **PASS** | Isoliertes `TF_DATA_DIR`; `terraform init -backend=false`, `validate`, `fmt -check -recursive`. Kein Plan. |
| Fokussierte Worker-/Artefakttests | **PASS** | 56 passed, 2 skipped; isolierte Order-/Result-E2E 8 passed; tfvars-Vertragstest 9 passed. |

## Unified Ubuntu QA

Etablierter Workflow, keine neue Testumgebung: Actions Run
[`46005456362`](https://github.com/maynowak/Mays-Recruiting-Intelligence-System/actions/runs/46005456362),
HEAD `be51f5eca69262fb3a793d3eb693faa812788d59`, Mays-Provenienz verifiziert
gegen exakt `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`. Python 3.14.10 auf
Ubuntu; AWS-Profile/Credentials waren im Workflow gesperrt.

| Profil | Ergebnis | Counts |
|---|---|---|
| `RIS_NATIVE` | **PASS** | 3.293 passed, 0 failed, 133 skipped, 450 Subtests, 0 Collection Errors |
| `MAYS_MODULE` | **PASS** | Original Mays Lambda 240; Builder 100 + 6 Subtests; Installer 81; Seed 28; Cognito Backup 2; alles ohne Fehler |
| `MODULE_BUILD` | **PASS** | Builder 100 + 6 Subtests; Installer 81; RIS Builder Contract 57; Generated Artifact 9 |
| `XREPO_CONTRACT` | **PASS** | 133 passed + 4 Subtests |
| `XREPO_E2E` | **PASS** | 39 passed |
| `FULL` | **PASS** | Sämtliche enthaltenen Gruppen PASS; RIS-Native 3.293 passed, 0 failed; Mays-Originalgruppen und XRepo PASS |

Der erste Lauf `46004384113` hatte genau einen RIS-Native-Testfehler: ein
historischer Test verbot pauschal jede eingecheckte tfvars-Datei. Die
DEV2-spezifische, ausdrücklich per `-var-file` gewählte Override-Datei wurde
daraufhin eng als Ausnahme erlaubt; automatisch geladene oder andere tfvars
bleiben verboten. Es wurde kein Test übersprungen oder fachlich abgeschwächt.
Der korrigierte Test bestand fokussiert (9/9), lokales RIS_NATIVE bestand
(3.284 passed, 0 failed), und der vollständige Ubuntu-Lauf oben ist grün.

Maschinenlesbare Resultate, Dependency-Liste und Bundle-Reproduzierbarkeit:
`docs/reports/evidence/19G2/ubuntu/`. Artifact-/Plan-Root-Cause-Matrix:
`docs/reports/evidence/19G2/artifact-reconciliation.json`.

## Gates und 19G3-Freigabevorlage

| Gate | Status |
|---|---|
| `ANALYSIS_ARTIFACT_ROOT_CAUSE` | VERIFIED |
| `READER_ARTIFACT_ROOT_CAUSE` | VERIFIED |
| `ARTIFACT_SCOPE` | PASS |
| `WORKER_BUNDLE_REPRODUCIBILITY` | PASS |
| `ANALYSIS_ARTIFACT_PRESERVED` | PASS |
| `READER_ARTIFACT_PRESERVED` | PASS |
| `RIS_NATIVE_QA` | PASS |
| `MAYS_ORIGINAL_QA` | PASS |
| `UNIFIED_FULL_QA` | PASS |
| `TERRAFORM_LOCAL_VALIDATE` | PASS |
| `REPLAN_READINESS` | **READY FOR SEPARATE PLAN APPROVAL ONLY** |
| `PREVIOUS_PLAN` | NOT_APPLICABLE — 19G-Plan gesperrt, nicht wiederverwendbar |
| `AWS_MUTATIONS / TERRAFORM_PLANS / TERRAFORM_APPLIES` | `0 / 0 / 0` in 19G2 |
| `RUNTIME_SOURCE_CHANGES` | 0 |

**Konkrete 19G3-Anfrage — noch nicht erteilt:**

> Ich genehmige ausschließlich die Erstellung von genau einem neuen,
> vollständigen, regulär refreshenden Terraform-Plan für RIS-DEV2 auf
> `feature/ris-analysis-integration-07` bei geprüftem aktuellem HEAD
> `be51f5eca69262fb3a793d3eb693faa812788d59`. Erwarteter Scope: **0 Add / 2
> Change / 0 Destroy**. Zulässig sind ausschließlich In-place-Code-Updates für
> Agent-Worker und Dispatch-Ingress auf Bundle SHA-256
> `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
> Analysis (`276b4e…`) und Orders-Reader (`610004…`) sowie alle übrigen
> Ressourcen/Attribute müssen unverändert bleiben. Jede Abweichung, Ersetzung,
> Zerstörung oder Drift stoppt die Ausführung. Diese Zustimmung erlaubt **keinen
> Apply**, keine State-Mutation, keinen Live-Test und keine Daten-/Entitlement-
> Operation. Der Plan ist vor jeder weiteren Freigabe separat zu reviewen.
>
> Approver: ____________________  Datum/Zeit: ____________________
>
> **19G3-Plan wurde nicht ausgeführt. Apply-Freigabe nicht erteilt. STOP.**
