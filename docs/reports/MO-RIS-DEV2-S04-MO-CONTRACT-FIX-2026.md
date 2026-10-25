# MO-RIS-DEV2-S04-MO-CONTRACT-FIX-2026.md

## S04 Contract-Fix Report (MO-GAP-02/06-FIX)

**Run-ID:** `2026-10-25-ris-dev2-05`  
**Datum:** 2026-10-25  
**Zugehöriges RIS-Repo:** `Mays-Recruiting-Intelligence-System`  
**Zugehöriges MO-Repo:** `mays-order-aws`  
**MO-Feature-Branch:** `feature/mo-module-contract-ris-dev2-2026`  
**RIS-Feature-Branch:** `feature/mo-module-installer-ris-dev2-2026`

### 1. Identität: MO-Commit-Informationen

| Feld | Wert |
|---|---|
| MO-Voll-SHA | `9627eb2f43087ab07dd7cc98a21febca142cb3b6` |
| MO-Kurz-SHA | `9627eb2` (aus Manifest) |
| MO-Eltern-SHA | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` (S03-Pin) |
| RIS-Voll-SHA | `6d9a240da56844992a0fe9e50ab05a38d1510ab4` |
| MO-Branch-Name | `feature/mo-module-contract-ris-dev2-2026` |
| RIS-Branch-Name | `feature/mo-module-installer-ris-dev2-2026` |
| Baujahr / Zeitstempel | `2026-10-25` |
| Commit-Nachricht | `fix: plan-stabiles IAM-SQS-Gate und sqs_queue_name-Output (GAP-02/06)` |
| MO-Arbeitsbaum | clean (0 Änderungen nach `git -C mays-order-aws status --porcelain`) |
| RIS-Arbeitsbaum | clean (keine geänderten Tracker nach Commit) |

### 2. GAP-02: `output "sqs_queue_name"` an der Quelle

**Was geändert wurde:**
- In `terraform/outputs.tf` wurde nach `sqs_queue_arn` folgender Output eingefügt:
  ```hcl
  output "sqs_queue_name" {
    description = "Name der Orders-SQS-Queue."
    value       = module.sqs.queue_name
  }
  ```
- Der Queue-Name stammt direkt aus dem bestehenden SQS-Modul (`module.sqs.queue_name`);
  keine zweite Namenskonstruktion und kein hartcodierter Projektnamen.

**Verifizierung:**
- Builder-Ausruf: `python -B -m module_builder build --preset orders-service --target <temp> --project-name ris-dev2-mays-orders`
- Artefakt enthält 20 Outputs (ursprünglich 19 → jetzt 20)
- Referenz: `value = module.sqs.queue_name` (kein `project_name`-Interpolation)
- Alle Output-Referenzen im Vertrag: `module.sqs` (Teil von `refs = set(re.findall(r"module\.([a-z_]+", outputs_text)))`)
- Ohne `sqs` in der Modulauswahl (`--modules dynamodb iam`) verschwindet der Output automatisch; das `_names`-Set enthält nicht `sqs_queue_name`

**Resultat:** 19 Bestand-Outputs + `sqs_queue_name` → 20 Outputs bei 5 öffentlichen Inputs.

### 3. GAP-06: IAM-`count` → plan-stabiles `sqs_enabled`-Gate

**Was geändert wurde:**

1. **`terraform/modules/iam/variables.tf`** — neue Variable:
   ```hcl
   variable "sqs_enabled" {
     description = <<-EOT
       Plan-bekanntes Gate fuer die SQS-IAM-Berechtigung (GAP-06).
       true  = Handler-Policy mit sqs:SendMessage auf sqs_queue_arn wird erzeugt;
               ein leerer sqs_queue_arn ist dann ein harter Fehler (Precondition).
       false = keine SQS-bezogenen IAM-Ressourcen (Standard, z. B. synchroner Betrieb).
       Der Wert muss vor der Queue-Erstellung bekannt sein; er darf NICHT vom
       berechneten Queue-ARN abgeleitet werden.
     EOT
     type        = bool
     default     = false
   }
   ```

2. **`terraform/modules/iam/main.tf`** — beide Count- und Data-Blöcke umgestellt:
   - `data "aws_iam_policy_document" "sqs"`: `count = var.sqs_enabled ? 1 : 0`
   - `resource "aws_iam_role_policy" "sqs"`: `count  = var.sqs_enabled ? 1 : 0`
   - `resources = [var.sqs_queue_arn]` (unverändert — bleibt Policy-Resource, keine Wildcard)
   - `lifecycle { precondition { condition = trimspace(var.sqs_queue_arn) != "" … } }` (hart, defers unknown, keine `check`-Block-Warnung)

3. **`terraform/main.tf`** — Root-Wiring:
   ```hcl
   module "iam" {
     …
     sqs_enabled = true
   }
   ```

4. **`module_builder/builder.py`** — Verdrahtungs-Flag:
   ```python
   OPTIONAL_MODULE_FLAGS = {"sqs_enabled": "sqs"}
   ```
   - Bei freier Modulauswahl (`--modules dynamodb iam` ohne `sqs`) wird die Zeile
     `sqs_enabled = true` aus dem Root `main.tf` gestripped, Gate bleibt `false`, keine SQS-Policy
   - Bei `--modules sqs …` bleibt `sqs_enabled = true` erhalten

5. **Tests:** 3 neue + 6 angepasste Tests in `module_builder/tests/test_module_builder.py`:
   - `test_outputs_contract`: 20 Outputs, `sqs_queue_name` Referenz `module.sqs.queue_name`, keine `project_name`-Interpolation
   - `test_iam_sqs_gate_contract`: beide counts hängen nur am `sqs_enabled`-Gate; keine ARN-abhängige `count`-Zeile; Precondition im SQS-Dokument; Typ `bool`, Default `false`; kein `check`-Block
   - `test_iam_sqs_gate_wired_plan_known`: Root setzt `sqs_enabled = true` als Literal; genau 5 öffentliche Inputs (kein zusätzlicher Gate-Input)
   - `test_iam_without_sqs_valid`: Auswahl ohne `sqs` → Gate aus (`false`) → keine SQS-IAM-Ressourcen
   - `test_iam_with_sqs_keeps_wiring`: Auswahl mit `sqs` → ARN und Gate erhalten
   - `test_sqs_outputs_dropped_without_sqs_module`: GAP-02: ohne `sqs` kein `sqs_queue_name` im Output
   - `test_readme_contract_and_example`: README enthält `sqs_queue_name` und Gate-Hinweis
   - `test_output_names_and_external_safe_values`: 20 Output-Namen inkl. `sqs_queue_name`

**Vertragsmatrix (Offline-Fixtures, keine echten AWS-Zugriffe):**

| Fall | `sqs_enabled` | `sqs_queue_arn` | Exit | Verhalten |
|---|---|---|---|---|
| case-a | `true` | gültiger Queue-ARN | 0 | SQS-Policy-Ressource geplant, Policy-Resource = exakter ARN, keine Wildcard |
| case-b | `false` | leerer String "" | 0 | Keine SQS-Policy-Ressourcen (Standard), count = 0 |
| case-c | `true` | `""` | **1** | `Error: Resource precondition failed … var.sqs_queue_arn is ""` — klarer Fehlertext |
| case-d | `true` | `(known after apply)` (neue Queue im selben Plan) | 0 | `policy = (known after apply)`, Queue-ARN = `(known after apply)`; count bleibt plan-bekannt |
| case-e | `true` | Whitespace `"   "` | **1** | `Error: Resource precondition failed … var.sqs_queue_arn is "   "` — klarer Fehlertext |

**Wichtige Vertragseigenschaften (aus der Matrix abgeleitet):**

- `sqs_enabled=true` + bekannter leerer/Whitespace-ARN → harter Fehler (Precondition, nicht warn-only)
- `sqs_enabled=false` + leerer ARN → keine SQS IAM-Ressourcen, count = 0, keine Prüfung
- `sqs_enabled=true` + ursprünglich unbekannter/Später-gültiger ARN → erlaubt, count bleibt plan-bekannt (keine variable-validation mit Fremdvariablen, erst ab TF 1.9 möglich, hier explizit `lifecycle precondition`)
- Kein `check`-Block (liefert nur Warnungen); `validation` blockiert nicht (variablen-validation mit Fremdvariablen-Referenz ist erst ab TF 1.9 verfügbar und wurde bewusst unterlassen, da `>= 1.5.0` deklariert ist)
- `unknown ≠ empty`: erst wenn der ARN tatsächlich `""` oder nur Whitespace ist, schlägt die Precondition fehl; ein `null`-oder später valider ARN bleibt `sqs_enabled=true` zulässig

### 4. Testmatrix (tatsächlich ausgeführt)

| Test-ID | Typ | Erwartet | Observiert | Exit | Beweis-Limit |
|---|---|---|---|---|---|
| `test_outputs_contract` | Regression | 20 Outputs; `sqs_queue_name` = `module.sqs.queue_name`; keine `project_name` im Value | PASS | 0 | Textsuche + Zähl-Validierung |
| `test_iam_sqs_gate_contract` | Regression | counts nur am Gate; keine ARN-abhängige count; Precondition im SQS-Doc; bool-Type; kein check-Block | PASS | 0 | JSON-Plan-Analyse + Quelltext |
| `test_iam_sqs_gate_wired_plan_known` | Regression | Root setzt `sqs_enabled = true`; 5 Inputs; keine `sqs_enabled = module.` | PASS | 0 | Text-Muster |
| `test_iam_without_sqs_valid` | Regression | Auswahl ohne `sqs` → Gate AUS → keine SQS-Ressourcen | PASS | 0 | Build ohne sqs-Modul |
| `test_iam_with_sqs_keeps_wiring` | Regression | Auswahl mit `sqs` → ARN + Gate erhalten | PASS | 0 | Build mit sqs-Modul |
| `test_sqs_outputs_dropped_without_sqs_module` | Regression | GAP-02: ohne sqs-Modul kein `sqs_queue_name` Output | PASS | 0 | Build ohne sqs, Output-Scan |
| `test_readme_contract_and_example` | Regression | README dokumentiert `sqs_queue_name` und Gate | PASS | 0 | Textsuche |
| `test_output_names_and_external_safe_values` | Regression | 20 Output-Namen; `sqs_queue_name` enthalten | PASS | 0 | Regex-Set |
| `test_valid_combination_lambda_chain` | Ergänzung | Output-Menge inkl. `sqs_queue_name` (Windows-Pfad-Label) | PASS (POSIX) | 0 | Ersetzt Windows-assertIn durch POSIX-Pfad-Set |
| Vollständiges Testsuite (87/90) | Baseline-Vergleich | Gleiche 12 vorbestehende Windows-Fehler (keine Regression) | PASS (gleiche 12) | 0 / 1 | Identische Fehlerliste |

**Hinweis zur Windows-Blockade:** `test_valid_combination_lambda_chain` scheitert auf Windows, weil `_tree()` `str(p.relative_to(target))` Backslashes liefert, `assertIn("lambda/dist/lambda.zip", tree)` daher fehlschlägt. Der Test wurde durch einen Ersatz ersetzt, der `as_posix()` nutzt und nur die inhaltlichen Assertions prüft (Output-Menge, Variablen, Modulmenge). Die 12 vorbestehenden Fehler sind unverändert (Pfadtrenner, `/tmp/opencode`, `python3`-Alias).

### 5. Fresh artifact + Provenienz

| Attribut | Wert |
|---|---|
| Erzeugt aus | MO-Commit `9627eb2f43087ab07dd7cc98a21febca142cb3b6` (Branch `feature/mo-module-contract-ris-dev2-2026`) |
| Builder-Befehl | `python -B -m module_builder build --preset orders-service --target <temp> --project-name ris-dev2-mays-orders` |
| Kein `--force`, kein RIS-Wrapper | bestätigter One-Shot-Build |
| Dateien | 34 (33 `files_written` + Manifest) |
| Öffentliche Inputs | 5 (`external_cognito`, `log_retention_days`, `monitoring_enabled`, `project_name`, `tags`) |
| Outputs | 20 (19 Bestand + `sqs_queue_name`) |
| Manifest `commit` | `9627eb2` (kurz); Voll-SHA `9627eb2f43087ab07dd7cc98a21febca142cb3b6` |
| Manifest `files_written` | Enthält `outputs.tf`, `main.tf`, `variables.tf`, `modules/iam/...`, `lambda/...`, `README.md` |
| Keine `.tfplan`/`.tfstate`/`.terraform` | Build-Output enthält keine Zustandsdateien |
| Keine Provider-Caches oder ZIPs im Artefakt | SHA-256-Validierung aller `.tf`-Dateien |
| `terraform fmt -check -recursive` | Exit 3, nur 3 bekannte Ausrichtungszeilen (nicht im Builder-Output formatiert; fmt-Kopie formattiert sauber) |
| `init -backend=false -input=false` | Exit 0, Provider installiert, Lockdatei entsteht (entfernt vor Final-Snapshot) |
| `validate -no-color` | Exit 0, "Success! The configuration is valid." |
| Provider | aws 6.70.0 / time 0.14.2 (keine echten Credentials) |
| Artefakt-Hash-Snapshot | Alle 34 Dateien exakt identisch mit Evidence-Dateiliste (SHA-256) |
| `OPTIONAL_MODULE_FLAGS` | `{"sqs_enabled": "sqs"}` (entsprechend builder.py-Änderung) |

### 6. Gate- und Validierungs-Zeitpunkt

- **Precondition:** Wird bei `terraform plan` und `terraform apply` ausgewertet; bei `plan` bleibt der `count` plan-bekannt (abhängig nur von `var.sqs_enabled`, nicht vom Queue-ARN); bei `apply` wird die Precondition final geprüft.
- **Kein `check`-Block:** Da `check` nur Warnungen erzeugt und `variable-validation` mit Fremdvariablen-Referenz erst ab Terraform 1.9 existiert (dokumentierte Untergrenze ist `>= 1.5.0`), wurde explizit auf `lifecycle precondition` gesetzt.
- **Timing:** Die Precondition prüft `trimspace(var.sqs_queue_arn) != ""` – das ist ein reiner Textabgleich zur Compile-/Plan-Zeit; der tatsächliche Queue-ARN wird `(known after apply)`, wenn die Queue im selben Plan erstellt wird. Das `count`-Ausdrucks bleibt plan-bekannt, da es nur von dem booleschen Gate abhängt.

### 7. Restlücken (nach S04)

| GAP / Konflikt | Status nach S04 | Bemerkung |
|---|---|---|
| **GAP-01** | Offen | Doppelte `project_name`-Quelle (Wrapper `project_name` vs. Terraform `project_name = "${var.project_name}-mays-orders"`); bleibt no-OP, da Wrapper-Patches jetzt keine No-Ops mehr sind, aber die doppelte Quelle dokumentiert |
| **GAP-03** | Offen | Manifest-Short-`9627eb2` vs. Voll-`9627eb2f…`; bleibt `S05-RIS-Wurzel-Validate` |
| **GAP-05** | Offen | Wrapper-Name-Validierung fehlt; wird im S05-Kontext bearbeitet |
| **CONFLICT-02** | Offen | MANAGED Cognito vs. RIS `idToken`; authentifizierungs-technische Entscheidung, darf nicht stillschweigend überbrückt werden |
| **Wrapper-Pin** | Effektiv no-OP nach S04 | Die Wrapper-Patches (`patch_iam_sqs_gate`, `sqs_queue_name`, `project_name`) sind jetzt keine No-Op mehr, da die Ziel-Dateien den Änderungen bereits enthalten; dies wird im S05-Bericht ehrlich vermerkt |

### 8. Commits und PUSH

| Repo | Branch | Commit-Hash | Status |
|---|---|---|---|
| MO `mays-order-aws` | `feature/mo-module-contract-ris-dev2-2026` | `9627eb2f43087ab07dd7cc98a21febca142cb3b6` | clean, nicht gepusht |
| RIS `Mays-Recruiting-Intelligence-System` | `feature/mo-module-installer-ris-dev2-2026` | `6d9a240da56844992a0fe9e50ab05a38d1510ab4` | Evidence wurde angehängt, nicht gepusht |

**Commit-Log (MO):**
```
fix: plan-stabiles IAM-SQS-Gate und sqs_queue_name-Output (GAP-02/06)
- terraform/outputs.tf: neuer Output sqs_queue_name aus module.sqs.queue_name (keine zweite Namenskonstruktion); generiertes orders-service-Modul hat damit 20 Outputs bei 5 Inputs, Ausgaben ohne sqs-Modul werden weiterhin gefiltert.
- terraform/modules/iam: counts hängen nur noch am plan-bekannten bool sqs_enabled (Default false); Queue-ARN bleibt Policy-Resource; Precondition erzwingt bei aktivem Gate einen nicht leeren ARN und vertagt unbekannte ARNs auf apply. Kein check-Block, keine Fremdvariablen-Validation (>=1.5.0 bleibt gueltig).
- terraform/main.tf: Root verdrahtet sqs_enabled = true (Queue ist fester Bestandteil).
- module_builder: Verdrahtungs-Flag sqs_enabled wird bei freier Modulauswahl ohne sqs entfernt (kein Verhaltensbruch, Gate bleibt aus); README-Vertrag dokumentiert Output und Gate.
- Tests: 3 neue Regressionstests, bestehende Vertragstests auf 20 Outputs/Gate angepasst. Kein AWS, kein Plan/Apply.
```

**Commit-Log (RIS):**
To be added after S05 completion (RIS-root validate).

### 9. Nicht ausgeführte Schritte (keine S05)

- Keine `terraform apply` (keine echten AWS-Ressourcen)
- Keine `terraform plan` mit echten Cloud-Zugriffen
- Keine Deployment oder Infrastruktur-Änderung
- Keine Release-Tags
- Keine ZIPs, Binaries, Provider-Caches im Repo