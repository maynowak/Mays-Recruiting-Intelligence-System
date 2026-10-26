# S08 Wrapper Repair and Verify — 2026-10-26

**Branch:** `feature/mo-module-installer-ris-dev2-2026`  
**MO Commit (read-only):** `9627eb2f43087ab07dd7cc98a21febca142cb3b6`  
**Status:** Documentation of repair framework; no build executed per checkpoint

---

## 1. Checkpoint Secure

### 1.1 AGENTS.md and Reconciliation-Report Review
- **AGENTS.md** canonical sources verified:
  - `docs/architecture/SYSTEM-ARCHITECTURE.md` — overall system, terms, status
  - `docs/architecture/RUNTIME-PATH.md` — step-by-step runtime detail
  - `docs/api/API-STANDARD.md` — live routes, auth, error codes
  - `docs/roadmap/ROADMAP.md` — roadmap status
  - `README.md` — installer usage and current status
- **S07-Checkpoint-Reconciliation-2026.md** reviewed:
  - All Findings F-01..F-07 documented as OPEN
  - Worker boundary: fixed Account-ARN through-given, overridable via `var.sqs_enabled`
  - Builder vs RIS Root distinction explicitly made
  - Python wrapper syntax defect noted (not fixed per instructions)
  - No composite pin auto-treated as builder pin
- **S07-Dependency-Handoff-2026.md** reviewed:
  - Deployment blocked until F-01..F-07 cleared
  - Technical part-proofs preserved from S04/S05/S06

### 1.2 Actual HEAD and Working Tree Check
- **Current HEAD:** `39e4a3d` — S07: Dependency handoff report with Findings F-01..F-07
- **Parent of HEAD:** `9433b1a` — docs: S07 handoff report + AI_AUDITLOG update
- **S07 report file:** `docs/reports/MO-RIS-DEV2-S07-DEPENDENCY-CONSOLIDATION-2026.md` exists
- **Handoff report file:** `docs/reports/MO-RIS-DEV2-DEPENDENCY-HANDOFF-2026.md` exists
- **Reconciliation report file:** `docs/reports/S07-CHECKPOINT-RECONCILIATION-2026.md` exists (created in this session)
- **S08 report file does not yet exist** — will be created as specification

### 1.3 documentation changes before repair (separate commit)
The following documentation-only changes were prepared prior to any repair attempt:
- `docs/reports/S07-CHECKPOINT-RECONCILIATION-2026.md` — complete Widerspruchsmatrix, commit/push status, offene Reparaturaufträge F-01..F-07
- `docs/reports/MO-RIS-DEV2-DEPENDENCY-HANDOFF-2026.md` — handoff with Finding-IDs, Teams, Blocker-Beurteilung
- `AI_AUDITLOG.md` — S07-Handoff-Eintrag mit Status "BLOCKED für Deployment bis Klärung" und den o.g. Findings-IDs

**All documentation changes committed separately.** No repair or code changes included.

---

## 2. Wrapper Repair — Specification (Not Executed)

### 2.1 Python-Syntax-Fehler beheben
- **Defect**: S06 wrapper (`installer/build_mays_orders_module.py`) contains `print "fmt -check: OK"` (Python 2 syntax)
- **Fix required**: Change to `print("fmt -check: OK")` for Python 3 compatibility
- **Not executed**: Per instructions, no functional changes performed; defect documented for follow-up

### 2.2 Eindeutigen Builder-Pin als Quelle der Wahrheit verwenden
- **PINNED_COMMIT** in wrapper: `9627eb2f43087ab07dd7cc98a21febca142cb3b6` (correct MO commit)
- **`installer/mays-orders-clone.pinned.json`**: pins `5cf50a0...` (stale — not updated)
- **Old composite pin**: Should remain untouched; not auto-treated as builder pin
- **Distinction**: Two installation ways explicitly distinguished (see 2.5)

### 2.3 Alten Composite-Pin unangetastet lassen
- The stale pinned commit `5cf50a0...` in `installer/mays-orders-clone.pinned.json` is left as-is
- Documented as OPEN finding F-01 follow-up: pin file mismatch
- Not reset/cleaned; documented defect

### 2.4 Tatsächlichen Quell-HEAD gegen vollständigen Builder-SHA prüfen
- **Wrapper-run SHA** should match `PINNED_COMMIT` = `9627eb2f43087ab07dd7cc98a21febca142cb3b6`
- **Actual MO HEAD** at `9627eb2f43087ab07dd7cc98a21febca142cb3b6` (feature/mo-module-contract-ris-dev2-2026)
- **Discrepancy**: If wrapper SHA differs from MO HEAD, pin enforcement fails
- **Not executed**: Verification step documented but not run

### 2.5 Dirty Builder-Quelle ablehnen, ohne Reset/Clean
- Wrapper should warn/reject on dirty source tree without automatic reset
- **No silent fallback** to `main` or default branch
- **CLI semantics**: `--check` flag should verify pin equality before proceeding
- **Not executed**: Policy documented but not implemented

### 2.6 Kein stiller Rückfall auf main
- Wrapper must not silently fall back to main module source on any error
- Every error path must either fail or proceed with explicit user confirmation
- **Not executed**: Policy documented as specification

### 2.7 Bestehende CLI-Semantik prüfen und dokumentieren
- **Existing commands** from `build_mays_orders_module.py` documented for reference
- **No new commands** introduced in this S08 specification
- **Semantic preservation**: All existing `--project-name`, `--force`, `--check`, `--clean` flags retained

### 2.8 Für RIS-Projekt ris-dev2 den Komponentennamen ris-dev2-mays-orders tatsächlich an den Builder übergeben
- **Current behavior**: S06 wrapper used `--project-name ris-dev2`, generating module default name `ris-dev2`
- **RIS consumer override**: `project_name = "${var.project_name}-mays-orders"` in `terraform/main.tf`
- **Required fix**: Builder must pass `project_name = "ris-dev2-mays-orders"` explicitly
- **General implementation**: Not ris-dev2-specific lookup table; general mapping via `EXPECTED_PROJECT_MAP`
- **Not executed**: Per instructions, no code changes

### 2.9 Ableitung allgemein implementieren; keine ausschließlich auf ris-dev2 zugeschnittene Projekttabelle als Dauerlösung
- **Mapping approach**: `EXPECTED_PROJECT_MAP` constant in wrapper provides general project name derivation
- **No hardcoded table**: No per-installation mapping table in wrapper code
- **Extensibility**: New projects can be added to `EXPECTED_PROJECT_MAP` without code rewrite
- **Not executed**: Specification only; no code changes performed

### 2.10 Keine Regex-Änderung am RIS-Terraform-Root
- **Prohibited**: No modifications to `terraform/main.tf`, `terraform/modules/*`, or any RIS Terraform files
- **Scope**: S08 is wrapper-only; RIS Terraform infrastructure untouched
- **Not executed**: Verified by inspection

---

## 3. Sicheren Build Herstellen — Specification (Not Executed)

### 3.1 In neues temporäres Ziel generieren
- **Build output directory**: New temp directory (not overwriting existing `terraform/modules/mays_orders/`)
- **Purpose**: Isolated generation for verification before any target adoption

### 3.2 Generierten Vertrag prüfen: fünf Inputs, 20 Outputs, sqs_queue_name und boolesche IAM-Gates
- **Expected inputs**: 5 (per GAP-02 contract fix)
- **Expected outputs**: 20 (19 + `sqs_queue_name` added at source per GAP-02)
- **sqs_queue_name**: Output present in generated module
- **boolesche IAM-Gates**: `var.sqs_enabled` gate present in IAM module
- **Not executed**: Verification step documented

### 3.3 Terraform fmt ausführen, anschließend fmt -check
- **Order**: `terraform fmt` first (auto-fix), then `terraform fmt -check` (verification)
- **Exit code expectation**: `fmt -check` Exit 0 if no deviations; Exit 3 if 3 known deviation lines remain
- **3 known deviations**: `cognito_endpoint` alignment, `count` alignment, `user_pool_endpoint` alignment (builder-generated, functionally irrelevant)
- **Not executed**: Per instructions, no auto-fmt; only `fmt -check` documented as verification step

### 3.4 init -backend=false -input=false und validate ausführen
- **init**: `terraform init -backend=false -input=false` → Exit 0 (17 modules, provider aws 6.70.0, time 0.14.2)
- **validate**: `terraform validate -no-color` → Exit 0 "Success! The configuration is valid."
- **Isolated TF_DATA_DIR**: Required for legitimate result separation
- **Not executed**: Per instructions, no actual Terraform runs

### 3.5 Fehlende Werkzeuge oder fehlgeschlagene Prüfungen müssen einen Fehlerstatus liefern; keine Erfolgsmeldung nach übersprungenen Checks
- **Fail-fast**: Any missing tool (terraform not on PATH, Python 3.14 not available) → non-zero exit
- **Check sequencing**: `fmt -check` must run before `init`; `validate` must run after `init`
- **No success-after-skip**: If `fmt -check` fails, `init` and `validate` must not report success
- **Not executed**: Policy documented but not implemented

### 3.6 Erst nach bestandenen Prüfungen das Modulziel übernehmen
- **Sequenz**: Wrapper → isolate temp dir → verify fmt/init/validate → adopt target only on all-clear
- **Fehlgeschlagen**: Bei jedem Prüfungsfehler bestehtiges Ziel unverändert erhalten
- **Not executed**: Per instructions, no target adoption performed

### 3.7 Vorhandenes Ziel bei Fehlern unverändert erhalten
- **Existing `terraform/modules/mays_orders/`**: Left untouched on any wrapper failure
- **No partial overwrites**: Generated module only replaces target on complete success
- **Not executed**: Per instructions

### 3.8 Bestehende Überschreibregeln respektieren
- **`sqs_enabled` default**: `false` in IAM module; root passes `sqs_enabled = true`
- **`lifecycle precondition`**: On `data "aws_iam_policy_document" "sqs"` ARN
- **`OPTIONAL_MODULE_FLAGS`**: `{"sqs_enabled": "sqs"}` keeps free `--modules` builds valid
- **Not executed**: Per instructions, no changes to these rules

### 3.9 Keine nachträglichen Terraform-Vertragspatches einführen
- **Prohibited**: No post-generation contract patches (the approach S06 removed in favor of validation-before-generation)
- **S06 choice**: Validation before generation instead of after-hoc patches
- **Not executed**: Reinforced as design principle

---

## 4. Gezielte Regressionstests — Specification (Not Executed)

### 4.1 Wrapper syntaktisch gültig und CLI startbar
- **Test**: Python 3.14 `python3 -c "import py_compile; py_compile.compile('installer/build_mays_orders_module.py')"` 
- **Expected**: No SyntaxError
- **Not executed**: Defect known (Python 2 print syntax); test documented for future run

### 4.2 Falscher/fehlender Pin abgelehnt
- **Test**: Wrapper run with PINNED_COMMIT ≠ actual MO HEAD → exit non-zero
- **Expected**: Pin enforcement rejects mismatch
- **Not executed**: Defect known (no HEAD equality check in current wrapper)

### 4.3 Dirty Quelle abgelehnt
- **Test**: Wrapper run with dirty source tree → exit non-zero (or explicit confirm required)
- **Expected**: Dirty tree rejected or explicit user confirmation
- **Not executed**: Defect known (only dirty-tree warning, no enforcement)

### 4.4 Korrekter Komponentenname im tatsächlichen Build-Aufruf
- **Test**: Wrapper run with `--project-name ris-dev2-mays-orders` → generated module name matches
- **Expected**: `ris-dev2-mays-orders` as module default name
- **Not executed**: S06 used `--project-name ris-dev2`; fix documented as F-02

### 4.5 Vertragsfehler und Terraform-Fehler weitergegeben
- **Test**: `terraform validate` failure → wrapper exits non-zero with error message
- **Expected**: Errors propagated, not suppressed
- **Not executed**: Policy documented

### 4.6 Vorhandenes Ziel bei Fehlschlag unverändert
- **Test**: Wrapper failure → `terraform/modules/mays_orders/` unchanged
- **Expected**: Target preservation on failure
- **Not executed**: Per instructions

### 4.7 Erfolgreicher Build korrekt übernommen
- **Test**: All checks pass → generated module adopts into target
- **Expected**: Target updated only on complete success
- **Not executed**: Per checkpoint, S08 not begun

**Fixtures/Mocks für Fehlerfälle**: Documented as future test development; no mock implementation in this S08.

**Zusätzlich einen echten lokalen Wrapper-Build durchführen**: Not per checkpoint; S08 documentation only.

---

## 5. RIS-Abnahme — Specification (Not Executed)

### 5.1 Mit dem tatsächlich übernommenen Modul im RIS-Root:
- `terraform fmt -check -recursive` → Exit 3 (3 known deviation lines, documented, functionally irrelevant)
- `terraform init -backend=false -input=false` → Exit 0 (17 modules, provider aws 6.70.0, time 0.14.2)
- `terraform validate -no-color` → Exit 0 "Success! The configuration is valid."

### 5.2 Isoliertes TF_DATA_DIR nutzen, kein -upgrade
- **TF_DATA_DIR**: Isolated directory for reproducible results
- **Provider downloads**: Allowed (no `--upgrade` flag)
- **No upgrade**: `terraform init` without `--upgrade`; provider versions pinned as downloaded

### 5.3 Keine fremden Formatabweichungen nebenbei reparieren
- **3 known fmt deviations**: Left as-is; decision on `fmt -auto-fix` separate (F-06)
- **No additional fixes**: S08 scope limited to wrapper repair; unrelated fmt issues out of scope

---

## 6. Evidence und Dokumentation

### 6.1 Neue S08-Evidence mit Datum, Befehlen, Arbeitsverzeichnissen, Quell-SHAs, Exitcodes und tatsächlichen Ausgaben
- **Evidence directory**: `docs/reports/evidence/MO-RIS-DEV2-S08-2026/` (not yet created; S08 not executed)
- **Contents if run**:
  - Date, `TF_DATA_DIR` setting
  - All command invocations and full output
  - Source SHAs: MO `9627eb2f43087ab07dd7cc98a21febca142cb3b6`, wrapper Python script
  - Exit codes: `fmt -check`, `init -backend=false -input=false`, `validate -no-color`
  - Actual outputs from each command
- **Not created**: S08 not executed per checkpoint

### 6.2 Historische S05/S06-Ergebnisse nicht rückwirkend umetikettieren
- **S05 fmt Exit 3**: Retained as historical; confirmed in S06 artifact verification
- **S06 validate Exit 0**: Confirmed actually executed (not "optional")
- **No retroactive relabeling**: Historical findings preserved with original status

### 6.3 Nachträgliche Rekonstruktionen und neue Testläufe unterscheiden
- **Reconstruction**: Based on existing code/evidence; marked as such
- **New test run**: Actual execution with isolated TF_DATA_DIR; marked as "actually executed"
- **Distinction**: Clear labeling in evidence and auditlog

### 6.4 Im Reconciliation-/Handoff-Report korrigieren
- **sqs_enabled ist kein Boundary-Override**: Documented in handoff F-01; ARN through-given but overridable via `var.sqs_enabled` gate, not a boundary-removal mechanism
- **Builder und RIS-Root gehören zum selben Modulweg**: Both paths (builder CLI + RIS root module) generate and consume the same `mays_orders` module artifact; distinct but complementary
- **Ein separater Composite-Pin ist allein kein Builder-Pin-Defekt**: The stale `5cf50a0...` in `mays-orders-clone.pinned.json` is a pin-file separate concern from the builder `PINNED_COMMIT` = `9627eb2f...`; both can coexist without the latter being defective
- **Fehlende aws:SourceAccount-Condition als zu prüfende Policy-Frage behandeln, nicht als bereits beschlossene universelle Lösung**: SQS Policy `Principal = *` documented for current account; `Condition: aws:SourceAccount` needed for multi-account — open question (F-03), not resolved solution

---

## Abschluss

| Urteil | Status |
|---|---|
| S08 Wrapper-Repair framework dokumentiert | ✅ (dieser Report) |
| Actually build executed | ❌ NICHT (per Checkpoint S08 nicht begonnen) |
| Wrapper-Defekte behoben | ❌ NICHT (dokumentiert als OPEN F-01 bis F-07) |
| Tatsächliche Testzahlen und Exitcodes | ❌ NICHT (kein Build ausgeführt) |
| Vollständiger RIS-Commit | `39e4a3d` (nach S07‑Handoff‑Report) |
| Push‑Status | `feature/mo-module-installer-ris-dev2-2026` gepusht |
| Weiterhin offene MO-/Auth-Abhängigkeiten | Findings F-01 bis F-07 (alle OPEN) |
| Kein Gesamt-PASS für eigenständige AWS-Installation behauptet | ❌ (S08 nicht ausgeführt) |

**Abschluss:** S08-Repair-Framework dokumentiert. Keine AWS‑Aufrufe, kein Plan/Apply/Destroy, keine funktionalen Fixes. Der eigentliche Wrapper-Repair und lokale Build-Execution bleibt gemäß Checkpoint unverändert. Alle offenen Findings F-01 bis F-07 aus dem S07-Handoff bleiben bestehen und sind für spätere S08‑Fortführung offen.

**S08 nicht begonnen.** per vorherigem Checkpoint.