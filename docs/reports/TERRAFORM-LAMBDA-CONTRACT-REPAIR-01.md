# TERRAFORM-LAMBDA-CONTRACT-REPAIR-01

## STATUS: GREEN

Vier beweisbare Duplikate bereinigt, ein totes Variablen-Paar als Folge
entfernt. Keine Architektur-/Runtime-/IAM-Entscheidung. Alle Pfade gedeckt.

## Starting commit

9c8e095 (`docs: audit Terraform Lambda source of truth`).

## Exact files changed

- `terraform/modules/lambda/outputs.tf`: 4 G0.2-Kopie-Blöcke entfernt
  (Hinweis-Kommentar belassen); Inline-Originale in `main.tf` (G0.1) bleiben.
- `terraform/modules/lambda/main.tf`: `aws_lambda_permission.api_gateway`
  entfernt (source_arn `"${api_id}/*/*"` — bare ID, matcht nie; Pfad gedeckt
  durch api-Modul-Permission mit korrekter `execution_arn`); zugehöriges
  `depends_on` im sqs_mapping entfernt (Einzeleintrag).
- `terraform/main.tf`: Root-`aws_cloudwatch_log_group.lambda` entfernt
  (gleicher Name/Retention wie Modul-Gruppe, 0 Referenzen; Modul-Gruppe in
  Funktions-depends_on bleibt); `api_arn`-Root-Arg entfernt (Folge, 0 Leser).
- `terraform/modules/lambda/variables.tf`: `aws_region` + `api_arn`
  entfernt (je 0 Leser; Root übergab `aws_region` nie).

## Exact contracts repaired

Output-Duplikate (4, PROVEN identische Values) · funktionslose Permission
(PROVEN falsche source_arn + PROVEN Deckung) · Doppel-Log-Gruppe (PROVEN
gleicher Name + 0 Referenzen auf Root-Exemplar) · 2 tote Vars (PROVEN 0 Leser).

## Contracts intentionally retained

Inline-Outputs (ACTIVE-Originale) · api-Modul-Permission (korrekter Pfad) ·
Modul-Log-Gruppe (verdrahtet) · alle 16 genutzten Vars · Funktion/Runtime/Env/
Batch-5/SQS-Mapping/API-Integration/IAM-Anbindung (unverändert).

## Variables intentionally left unresolved

Keine — beide Kandidaten (`aws_region`, `api_arn`) hatten PROVEN 0 Leser und
wurden entfernt. Root-`aws_region` (Provider/Backend) und Monitoring-
`aws_region` unberührt (außerhalb Scope, aktiv genutzt).

## IAM runtime-role decision remains OPEN / R20

Explizit: keine Rollen-/Policy-Änderung, keine Auswahl. Anbindung
(`lambda_execution`) ist Code-Fakt; Deployment-Wirkung UNKNOWN.

## SQS/API wiring unchanged

Mapping (batch_size 5), `integration_uri`, Funktions-Rolle/Env/Depends
abzüglich entfernter Permission-Dependency (verwaister Eintrag) — per Grep
verifiziert. API-Semantik unverändert (korrekte Permission intakt).

## Validation results

- Post-Greps: entfernte Refs leer (außer fremde `aws_region`-Nutzer);
  api-Permission + Modul-Log-Gruppe + Wiring (Rollen/batch/integration)
  intakt — Direkt-Check nach leerem Pipe-Artefakt.
- `terraform fmt -check` (editierte Dateien, kein Write): meldet
  `main.tf` + `lambda/main.tf`-Alignment (teils pre-existing, teils
  Entfernungs-Folge) — dokumentiert, Phase H.
- `terraform validate` ohne init: nur `Module not installed` (erwartet,
  init verboten); keine neue Parse-Ebene.
- `git diff --check`: PASS. Scope: nur obige Dateien (+ Report/Log).

## AWS mutation

NONE (kein init/plan/apply/destroy/import, kein Backend/Provider-Setup).

---

*Repair: TERRAFORM-LAMBDA-CONTRACT-REPAIR-01 · nur Beweisbares · kein
Laufzeitentscheid · keine Folgereparatur hier.*
