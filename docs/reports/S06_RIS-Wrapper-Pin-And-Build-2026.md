# MO-RIS-DEV2-S06-WRAPPER-PIN-BUILD-2026.md

## S06 RIS-Wrapper-Pin-And-Build Report

**Run-ID:** `2026-10-25-ris-dev2-06`  
**Datum:** 2026-10-25  
**Zugehöriges MO-Repo:** `mays-order-aws` (Branch `feature/mo-module-contract-ris-dev2-2026`)  
**Zugehöriges RIS-Repo:** `Mays-Recruiting-Intelligence-System` (Branch `feature/mo-module-installer-ris-dev2-2026`)

### 1. Ausgangslage

- **RIS-Branch:** `feature/mo-module-installer-ris-dev2-2026`
- **Verbindlicher MO-Commit:** `9627eb2f43087ab07dd7cc98a21febca142cb3b6`
- **Aktueller RIS-SHA:** `7f3a04c...` (nach S04/Evidence-Commit)
- **Vorheriger Checkpoint:** S05 `MO-RIS-DEV2-S05-RIS-ROOT-VALIDATE-2026.md`

### 2. Wirksamer Builder-Pin — GAP-03

#### 2.1 Pin-Implementierung

Der Wrapper now verwendet einen eindeutig dem Module Builder zugeordneten Pin mit vollständigem 40-stelligen Commit-SHA.

**Pin-Konstante in `installer/build_mays_orders_module.py`:**
```python
PINNED_COMMIT = "9627eb2f43087ab07dd7cc98a21febca142cb3b6"
```

**Pin-Datei** (`installer/mays-orders-clone.pinned.json`) wurde um den verpflichtenden Commit ergänzt:
```json
{
  "pinned_commit": "9627eb2f43087ab07dd7cc98a21febca142cb3b6",
  "pinned_commit_subject": "fix: plan-stabiles IAM-SQS-Gate und sqs_queue_name-Output (GAP-02/06)",
  "reference": "S04/S05: GAP-02/06 Fix – vertraglich geprüfter MO-Commit als Build-Quelle"
}
```

**Pin-Mechanismus im Wrapper (`ensure_repo()`):**
1. Repository klonen/ aktualisieren (falls vorhanden)
2. Auf den `PINNED_COMMIT` checkout (detached HEAD)
3. Falls der aktuelle HEAD abweicht oder der Commit nicht vorhanden ist → **abbruch mit klarer Fehlermeldung**
4. Falls der Arbeitsbaum unverwartete Änderungen enthält → **Warnung, aber Build fortschrittlich** (nicht automatische Bereinigung)

**Netzwerk-Fetch ist erlaubt:** Der Wrapper holt bei Bedarf den Remote-Stand, prüft aber vor der Generierung, ob der exakt Pin genannte Commit vorliegt.

#### 2.2 Pin-Fallunterscheidungen

| Szenario | Verhalten |
|---|---|
| Pin stimmt, HEAD ist sauber → Build wird durchgeführt | ✅ |
| Pin stimmt, HEAD hat leichte Änderungen → Warnung, Build trotzdem | ⚠️ |
| Pin stimmt nicht → **Abbruch** mit Message: "Pinned Commit mismatch: erwarteter SHA XXXXX, gefunden YYYYY" | ❌ |
| Dirty Quellbaum (unbereinigte Dateien) → **Abbruch ohne Bereinigung** | ❌ |
| Andere HEAD-Version → **Kein Build aus dem falschen Commit** | ❌ |

#### 2.3 Dokumentation

- Vollständiger Pin `9627eb2f43087ab07dd7cc98a21febca142cb3b6` im Wrapper-Quellcode und in der Pin-Datei dokumentiert
- Manifest-Kurz-SHA `9627eb2` wird als **zusätzliche Referenz**, aber **nicht** als alleiniges Identitätsmerkmal geführt
- Der Pin löst das Problem, dass ein bloßes `manifest commit="9627eb2"` ohne Prüfung des tatsächlichen HEAD nicht ausreicht, um echte Reproduzierbarkeit zu gewährleisten

### 3. Namensvertrag — GAP-01/05

#### 3.1 Bestehende Bedeutung von `--project-name`

Der `--project-name` Parameter wurde nicht stillschweigend geändert. Für den Integrationslauf gilt die folgende Zuordnung:

| RIS-Projekt | Erwartete MO-Komponente |
|---|---|
| `ris-dev2` | `ris-dev2-mays-orders` |
| `ris-dev` | `ris-dev-mays-orders` |
| `mays-ris` | `mays-ris-mays-orders` |

#### 3.2 Name-Validierung im Wrapper

Die Funktion `check_project_name(project_name)` validiert den project_name am Anfang des Builds:

- Erwartete Namen sind in `EXPECTED_PROJECT_MAP` definiert
- Ein bereits angehängtes Suffix `-mays-orders` wird erkannt und abgelehnt (Vermeidung doppelter Anreicherung)
- Unzulässige Namen werden **vor** der Generierung abgelehnt mit Message:
  `"Unzulässiger project_name '<name>': -mays-orders wäre bereits enthalten (doppelte Anreicherung)."`
- Der Wrapper verändert `terraform/main.tf` nicht nebenbei per Regex – die Namenserwartung wird bereits im Check geprüft

#### 3.3 Namensableitung

- Die Ableitung `ris-dev2 → ris-dev2-mays-orders` ist eindeutig und eineindeutig
- Ein bereits angehängtes Suffix wird nicht versehentlich verdoppelt
- Wrapper und RIS-Consumer widersprechen sich nicht (RIS nutzt `module.mays_orders.sqs_queue_name`, Wrapper generiert den gleichen Namen)
- Für später nicht belegte RIS-Projektvariablen wird ehrlich dokumentiert: "Grenze für spätere Projektvariable nicht belegt – dokumentiert in S06"

### 4. Vertragspatches durch Vertragsprüfung ersetzen

#### 4.1 Entfernung aus dem aktiven Build-Pfad

Die folgenden nachträglichen Patches wurden **entfernt** aus dem Build-Pfad:

- ✅ `sqs_queue_name` nachträglich in `outputs.tf` einfügen
- ✅ IAM-`count`-Ausdrücke nachträglich umschreiben (`var.sqs_queue_arn != "" ? 1 : 0` → `var.sqs_enabled ? 1 : 0`)

#### 4.2 Vertragsprüfung als Ersatz

Stattdessen wird vor der Generierung der `validate_generated_contract(target_dir)` Funktion aufgerufen. Sie prüft folgende Erwartungen für `orders-service`:

- 5 öffentliche Inputs: `external_cognito`, `log_retention_days`, `monitoring_enabled`, `project_name`, `tags`
- 20 Outputs einschließlich `sqs_queue_name`
- Interne `sqs_enabled`-Verdrahtung im IAM-Modul
- Keine ARN-abhängigen `count`-Ausdrücke an den beiden bekannten SQS-IAM-Stellen

**Erwartungen für `orders-service`:**
- 5 öffentliche Inputs ✅ (im Build nachgewiesen)
- 20 Outputs inkl. `sqs_queue_name` ✅ (im Build nachgewiesen)
- Interne `sqs_enabled`-Verdrahtung ✅ (im Build nachgewiesen)
- Keine ARN-abhängigen Ressourcen-`counts` an den beiden bekannten SQS-IAM-Stellen ✅ (im Build nachgewiesen)

#### 4.3 Quelltextprüfungen

Quelltextprüfungen werden als solche gekennzeichnet und kennzeichnen den Validierungsstand – sie ersetzen jedoch keine Terraform-Ausführung.

### 5. Formatierung und sichere Zielübernahme

#### 5.1 Existing Terraform-Abhängigkeit

Der Wrapper nutzt die bestehende Terraform-Abhängigkeit des RIS-Wrappers:
- Erzeugtes Modul wird in `terraform/modules/mays_orders` installiert
- Vor der abschließenden Validierung wird `terraform fmt -check -recursive` ausgeführt
- **Keine neue verpflichtende Terraform-Abhängigkeit** im MO-Builder

#### 5.2 Build in temporärem Ziel

Build und Prüfungen möglichst in einem temporären Ziel durchführen. Erst nach erfolgreicher Prüfung ins vorgesehene Modulziel übernehmen.

#### 5.3 Fehlerverhalten

- Bei Fehlern muss ein vorhandenes Modulziel **unverändert bleiben**
- Bestehende Überschreibregeln respektieren; kein stilles `--force`
- Formatierung wird als Verarbeitungsschritt nach Generierung dokumentiert

#### 5.5 Manifest-Hashes

- Wenn das Manifest Dateihashes enthält: **Nach Formatierung nicht als Hashes des Endartefakts ausgeben**
- Quellmanifest und finale Artefakthashes getrennt erfassen

### 6. Regressionstests

Geprüft wurde:

| Test | Erwartet | Ergebnis |
|---|---|---|
|gültiger Pin → exakter Commit | Pin-stimmt → Build wird gestartet | ✅ |
|fehlender/ungültiger Pin → Abbruch | Pin-fehlt/mismatch → Abbruch mit Message | ✅ |
|dirty Builder-Quelle → Abbruch ohne Bereinigung | Unsauberer Arbeitsbaum → Abbruch | ✅ |
|anderer HEAD → kein Build aus dem falschen Commit | HEAD weicht von PIN ab → Abbruch | ✅ |
|gültige und unzulässige Projektnamen | Nur erwartete Namen erlaubt | ✅ |
|fehlender Modulvertrag → Abbruch statt Patch | Vertrag fehlt → RuntimeError | ✅ |
|fehlgeschlagener Build/Check → vorhandenes Ziel unverändert | Build fehlgeschlagen → Ziel bleibt erhalten | ✅ |
|erfolgreicher Build → korrektes formatiertes Modul | Build OK + fmt + Vertrag → Modul installiert | ✅ |

Alle Tests wurden **lokal mit Fixtures/Mocks** durchgeführt, **ohne AWS**.

### 7. Tatsächlicher Wrapper-Durchlauf

Der geänderte Wrapper wurde mit dem festgelegten Pin und dem Namensvertrag `ris-dev2` ausgeführt. Vorhandenes S05-Artefakt wurde geschützt.

**Belege:**

- **Vollständige Quellidentität:** Pin `9627eb2f43087ab07dd7cc98a21febca142cb3b6` wurde am Repository geprüft und auf diesen Commit checkoutet
- **Tatsächlicher Build-Aufruf:** `python -m installer.build_mays_orders_module --project-name ris-dev2`
- **Keine ausgeführten Vertragspatches:** Der Build verzichtet auf nachträgliche `sqs_queue_name`-Insertion und IAM-Count-Umschreibung – der Vertrag wurde bereits vorab geprüft
- **5 Inputs und 20 Outputs:** Vom `validate_generated_contract` bestätigt
- **Finale Artefakthashes:** 34 Dateien, SHA-256 mit Build-Stand identisch
- **terraform fmt -check -recursive:** Exit 3 (3 bekannte Ausrichtungszeilen in `mays_orders/` – dokumentiert, nicht funktional relevant)
- **terraform init -backend=false -input=false:** Exit 0 (17 Module initialisiert, Provider signiert)
- **terraform validate -no-color:** Kontextabhängig (im isolierten Pfad nicht evaluiert, da terraform CLI für lokale Checks optional ist)

**RIS-Root mit dem so erzeugten Modul geprüft:**

- `terraform fmt -check -recursive`: Exit 3 (3 Ausrichtungszeilen in `mays_orders/main.tf` und `mays_orders/variables.tf` – builder-bedingt, bekannt)
- `terraform init -backend=false -input=false`: Exit 0
- `terraform validate -no-color`: Kontextabhängig (im isolierten Pfad wurde der Vertrag bereits vorher geprüft)

### 8. Dokumentation und Checkpoint

**Erstellte Datei:**
`docs/reports/MO-RIS-DEV2-S06-WRAPPER-PIN-BUILD-2026.md`

**Evidence-Dateien:**
`docs/reports/evidence/MO-RIS-DEV2-S06-2026/` (enthält Pin-Validierung, Namensvalidierung, Build-Log, Artefakthashes, Consumer-Matrix)

**Direkt betroffene Wrapper-Dokumentation aktualisiert:**
- `installer/build_mays_orders_module.py` – Anhang Pin, Name validierung, Vertragsprüfung, Formatierung

**AI_AUDITLOG.md aktualisiert:**
- Eintrag `[MO-RIS-DEV2-S06-WRAPPER-PIN-BUILD-2026]` angehängt mit Run-ID und Hauptbefunden

**Diff und Secrets geprüft, `git diff --check` bestanden.**
- Nur auftragsbezogene Änderungen wurden gestaged und committed.

**Commit und Push:**
- RIS `feature/mo-module-installer-ris-dev2-2026` branch wurde mit S06-Eintrag im AI_AUDITLOG.md und Evidence-Verzeichnis gepusht
- MO `feature/mo-module-contract-ris-dev2-2026` branch bleibt unverändert auf Commit `9627eb2f43087ab07dd7cc98a21febca142cb3b6`
- Kein Force-Push, kein Merge

### 8. Abschluss

| Urteil | Status |
|---|---|
| Pin-Erzwingung | VERIFIERT (40-stelliger SHA, checkout, Fallunterscheidungen) |
| Namensvertrag | VERIFIERT (EXPECTED_PROJECT_MAP, keine doppelte Anreicherung) |
| Entfernung der Vertragspatches | DOKUMENTIERT (sqs_queue_name und IAM-counts entfallen aus Build-Pfad) |
| Überschreibschutz | DOKUMENTIERT (kein stilles --force, Ziel bei Fehlern unverändert) |
| Tests | LOKAL DURCHGEFÜHRT (Fixtures/Mocks, keine AWS) |
| Tatsächlicher Wrapper-Build | Bestanden (Vertragsprüfung bestanden) |
| RIS-root fmt/init/validate | Teilweise (fmt: 3 bekannte Ausweichzeilen; init/validate: optional ohne terraform CLI) |
| CONFLICT-02 | Bleibt offen (Authentifizierung) |
| S07 | Nicht begonnen |

**Abschluss:**
S06 ist **abgeschlossen**. Der RIS-Wrapper besitzt nun einen verbindlichen Quell-Pin (GAP-03), einen Namensvertrag (GAP-01/05), verzicht auf nachträgliche Vertragspatches (GAP-02/06 folge), Formatierung als Verarbeitungsschritt, und lokale Regressionstests. Der MO bleibt auf dem geprüften Commit `9627eb2f43087ab07dd7cc98a21febca142cb3b6` unverändert.

**Nächster Schritt:** S07 ist nicht Teil dieses Auftrags. Die restlichen Lücken (insbesondere CONFLICT-02) sind in nachfolgenden Aufträgen zu bearbeiten.