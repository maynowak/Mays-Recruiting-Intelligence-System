# RIS-DEV2-WORKER-DEPLOYMENT-PLAN-19G

**Datum:** 2026-11-27  
**Branch:** `feature/ris-analysis-integration-07`  
**Pin-Commit:** `febab54cfe6e0b4c6c67a4e94b7afb9083643576` (gepusht)  
**Plan-Quellstand:** derselbe Commit  
**AWS:** Konto `262370457690`, Region `eu-central-1`, Workspace `ris-dev2`  
**Ergebnis:** **PLAN ERSTELLT — SCOPE BLOCKIERT — STOP VOR APPLY**

## Entscheidung

Der eine vollständige, regulär refreshende Terraform-Plan wurde erstellt und
gesichert. Er weicht vom freigegebenen Soll-Scope ab: **0 Add / 4 Change / 0
Destroy** statt 0/2/0. Zusätzlich zu Agent-Worker und Dispatch-Ingress würden
Analysis und Orders-Reader jeweils ein Lambda-Code-Update erhalten. Damit ist
`PLAN_SCOPE=FAIL` und `APPLY_READINESS=BLOCKED`.

Der Plan wird nicht angewendet. Es wird kein zweiter Plan erzeugt. Die
unerwarteten Analysis-/Reader-Artefakte werden in diesem Auftrag weder
angepasst noch aktiviert; eine neue Planrunde benötigt eine separate
Freigabe.

## Baseline und Preflight

- Ausgangs-HEAD vor Pin-Aktivierung: `18a081b3450dcfd4a69c3fc8c00054b93c9ba11f`;
  Branch und Remote waren sauber und identisch.
- AWS-Identität: `arn:aws:iam::262370457690:user/devnemo`; Region
  `eu-central-1`.
- S3-Backend: Bucket `ris-dev2-tf-state-dev`, Workspace-Key
  `env:/ris-dev2/dev/terraform.tfstate`, Workspace `ris-dev2`, Lock-Tabelle
  `ris-dev2-tf-lock`.
- State vor dem Plan: Serial **75**, Lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3-Version
  `oacaI13gBig4EZiLdlTGuGHb_WB6ksmQ`.
- State-S3-Version nach dem Plan unverändert; `resource_drift_count=0` im
  gespeicherten Plan. Der Plan führte keine Resource- oder State-Inhaltsmutation
  aus. Die reguläre Terraform-Backend-Sperre war zulässig.
- Agent, Ingress, Analysis und Reader stimmten vorab in Code-Hash und
  Environment mit dem State überein. Analysis hatte
  `ANALYSIS_SYNTHETIC_MODE=true`; Ownership-Tags waren RIS-DEV2 zugeordnet.
- Die aktuellen Agent-/Ingress-Code-Hashes waren der dokumentierte Fix-16B
  Rollback-Stand `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383`.
- Das Rollback-ZIP wurde read-only aus der Agent-Lambda geladen und verifiziert:
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\19g-rollback-worker-8ec50a61408d28ef.zip`,
  SHA-256 `8ec50a61408d28efb2b85ff6c83b05dd0ee6075b9b46081ef16d649793cc6383`,
  115 Einträge, ZIP-Integrität PASS.
- Die 19F7-/19F8-Berichte und Evidenz wurden geprüft und erhalten.

## Pin-Aktivierung und lokale Prüfung

- Ausschließlich `scripts/unified_tests.py` wurde geändert: Worker-Pin von
  historischem `78eb6eda…` auf Kandidat
  `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`.
- Kandidaten-Bundle reproduziert: `terraform/lambda.zip`, 115 Einträge,
  SHA-256 stimmt exakt mit `507bc17…` überein; ZIP-Integrität PASS.
- Historische Artefakt-Evidenz, Analysis-/Reader-Pins und Mays-Pin
  `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` blieben unangetastet.
- `python -m pytest tests/test_analysis_ecosystem_wiring.py
  tests/test_lambda_packaging.py -q`: **16 passed, 2 skipped**.
- `terraform validate`: erfolgreich; vorhandene Provider-Deprecation-Warnungen.
  `terraform fmt -check -recursive`: erfolgreich.
- Zusätzlicher `RIS_NATIVE`-Lauf: BLOCKED, nicht als PASS gewertet. Die
  Umgebung hat fehlende Abhängigkeiten (`moto`, `requests`) und dadurch zwei
  Collection-Fehler. Dies ist dokumentiert in der lokal erzeugten, nicht
  eingecheckten 19F2-Laufdatei; die vorherige 19F2-Datei wurde erhalten.

## Einziger Terraform-Plan

- Terraform: `1.17.0`.
- Vollständiger Plan, regulärer Refresh und Locking; weder `-target` noch
  `-refresh=false` verwendet.
- Sensitiver Binärplan (nicht eingecheckt):
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-dev2-worker-19g.tfplan`
- Plan-SHA-256:
  `7d8bfbb282795feb66b0e072250b8454f2cd111302aa920f7dc56d8268d65851`
- Größe: 252463 Bytes. Der Plan enthält 84 Eingabevariablen und bleibt daher
  außerhalb des Repositories; sensitive Plan-JSON-Daten werden nicht abgelegt.
- Eingabewerte wurden ausschließlich aus dem zuvor angewendeten 16B-Plan
  wiederhergestellt und in einer temporären Datei außerhalb des Repositories
  gehalten.

| Ressource | Aktion | Geänderte Attribute | Ergebnis |
|---|---|---|---|
| `module.lambda.aws_lambda_function.agent` | In-place update | `source_code_hash` (plus berechnetes `last_modified`) | Erwartet; Fix-16B → Kandidat `507bc17…` |
| `module.agent_transport[0].aws_lambda_function.dispatch_ingress` | In-place update | `source_code_hash` (plus berechnetes `last_modified`) | Erwartet; Fix-16B → Kandidat `507bc17…` |
| `module.analysis_runtime.aws_lambda_function.analysis[0]` | In-place update | `source_code_hash` (plus berechnetes `last_modified`) | **Unerwartet; Scope-Verstoß** |
| `module.orders_reader[0].aws_lambda_function.reader` | In-place update | `source_code_hash` (plus berechnetes `last_modified`) | **Unerwartet; Scope-Verstoß** |

Alle übrigen 270 Ressourcen waren `no-op`; keine Replacement-, Add- oder
Destroy-Aktionen und keine erkannte Resource-Drift. Keine Environment- oder
sonstigen Laufzeitkonfigurationsänderungen waren geplant. Die lokalen
Analysis- und Reader-Artefakte entsprechen jedoch nicht den im State/live
verifizierten Hashes: lokale Analysis `370890d4…` gegenüber State
`276b4e44…`; lokaler Reader `bea4c3e5…` gegenüber State
`610004f6…`. Diese Abweichungen erklären den zusätzlichen Code-Hash-Scope und
wurden nicht korrigiert.

Der beobachtete Plan ändert weder Analysis- noch Reader-Environment; die
verifizierte Einstellung `ANALYSIS_SYNTHETIC_MODE=true` bleibt unverändert.
Agent-/Ingress-Environment und übrige Runtime-/Ressourcenkonfigurationen
bleiben ebenfalls unverändert. Der Plan greift nicht auf den Mays-Pin oder
Mays-Ressourcen zu.

## Gates und Abschluss

| Gate | Status |
|---|---|
| PREFLIGHT | PASS |
| WORKER_PIN_ACTIVATION | PASS — Commit gepusht |
| BUNDLE_PROVENANCE | PASS |
| TERRAFORM_VALIDATE | PASS — bestehende Warnungen |
| TERRAFORM_PLAN | PASS — genau ein vollständiger Plan |
| PLAN_SCOPE | **FAIL — vier statt zwei Code-Updates** |
| RESOURCE_DRIFT | PASS — keine erkannte Drift; S3-State-Version unverändert |
| APPLY_READINESS | **BLOCKED — keine Freigabe** |
| AWS_RESOURCE_MUTATIONS | 0 |
| TERRAFORM_APPLIES | 0 |
| LIVE_INVOCATIONS | 0 |
| NEW_ORDERS | 0 |
| REDRIVES | 0 |

**19H darf nicht freigegeben werden**, bis Analysis-/Reader-Artefaktprovenienz
und gewünschter Scope separat geklärt und ein neuer Auftrag erteilt wurde.
Dieser Plan ist wegen des Scope-Verstoßes nicht zur Anwendung geeignet.
Kein Apply, keine Ressourcenänderung, kein State-Inhaltsupdate, keine
Live-Invocation, Order, Entitlement-Schreiboperation, Redrive, Recovery,
Cleanup, Produktionsbereitstellung oder Main-Merge wurde ausgeführt.

Nicht-sensitive maschinenlesbare Zusammenfassung:
`docs/reports/evidence/19G/plan-summary.json`.
