# TERRAFORM-ROOT-OUTPUTS-CONSOLIDATION-01

## Status

**YELLOW** — Root-Output-Vertrag konsolidiert (eine kanonische `outputs.tf`,
Inline-Duplikate entfernt, alle 26 Werte verifiziert existent, keine Consumer
gebrochen). `terraform validate` meldet keine Duplicate-Outputs mehr; es
verbleibt deterministisch der bekannte Parse-Fehler `variables.tf:18`
(R12, nächster Repair) sowie dahinter maskierte Modul-/Contract-Schichten.
IAM-Laufzeitfrage explizit NICHT entschieden (STOP-Punkt dokumentiert).

## Five previous variants

Die 5 Root-Duplikate (SoT: `outputs.tf` G0.1-Original vs. Inline-`main.tf`
G0.2-Kopien): `cognito_user_pool_id`, `api_endpoint`, `sqs_queues`,
`dynamodb_tables`, `lambda_functions`. Zusatzbefund: Inline-`dynamodb_tables`
enthielt nur `work_items` (stale/lagging), `outputs.tf` alle 5 Tabellen.

## Selected variant + why

`terraform/outputs.tf` (G0.1-Original, blame-belegt) als Basis: älteste
Schicht, vollständigste Werte, keine externen Consumer an Inline-Namen
gebunden (Repo-Grep leer). Inline-Blöcke `main.tf:187-209` entfernt.
Keine neue Architektur (keine Module/Inputs/Ressourcen angefasst).

## Mays-Orders-AWS reference pattern

`terraform/outputs.tf` @ `9c61237` (mays-order-aws, Remote-main, Git-only
gelesen): Root = öffentliche Export-Schicht mit Descriptions, flache explizite
Namen (`dynamodb_table_name`, `iam_handler_role_arn`, `lambda_function_name`,
`cognito_*`, `api_gateway_*`); Module intern; Monitoring bewusst NICHT
re-exportiert (keine Consumer). Übernommen: Struktur/Descriptions/flache Namen/
Monitoring-Verzicht. RIS-Abweichung begründet: Multi-Table-DynamoDB →
explizite Namen je Tabelle (`dynamodb_work_items_table_name` etc.) statt
singulärem `dynamodb_table_name`; bestehende RIS-Namen (`api_endpoint`,
`api_id`, `sqs_queues`) behalten statt umzubenennen (kein Churn ohne Consumer).

## Final canonical outputs (26, alle verifiziert existent)

DynamoDB 10 (name+arn × 5 Tabellen) · IAM 2 (`iam_role_name`/`iam_role_arn` ←
`module.iam.role_*`) · Lambda 3 (`lambda_function_name`/`function_arn`/
`invoke_arn`) · Cognito 5 (id/arn/endpoint/client_id/group_staff_name) ·
API 4 (`api_endpoint`/`api_id`/`api_stage_name`/`api_authorizer_id`) ·
SQS 1 (`sqs_queues`). Monitoring/CloudTrail: bewusst kein Export.

## Intentionally removed

- 5 Inline-Blöcke `main.tf:187-209` (stale Kopien).
- `dynamodb_tables`-Map (durch 10 explizite Outputs ersetzt, kein Alias übrig).
- `lambda_functions`-Map (durch `lambda_function_*` ersetzt).
- `lambda_role_arn = module.iam.lambda_role_arn` (Referenz auf nichtexistenten
  Output — entfernt statt umzubiegen, s. Ambiguity).

## Intentionally retained

Alle Werte mit existierendem Modul-Output (26/26 per Grep verifiziert);
`api_endpoint`/`api_id`/`sqs_queues`-Namen (bestehender Vertrag, keine Consumer-
Notwendigkeit zur Umbenennung); `function_arn`-Orphan als ACTIVE-Definition.

## Unresolved IAM ambiguity (STOP-Punkt, dokumentiert statt entschieden)

Kandidaten: `module.iam.lambda_role_arn` (existiert NICHT — entfiel) vs.
`module.lambda.lambda_role_arn` (existiert, `lambda_execution`, an Funktion
gebunden) vs. `module.iam.role_arn` (existiert, G0.1-Vertrag, exportiert).
Exportiert: `iam_role_arn ← module.iam.role_arn` (Existenz + G0.1-Vertrag +
Referenzmuster — explizit begründet, nicht stillschweigend). NICHT entschieden:
welche Rolle für das Lambda-Runtime maßgeblich ist (`main.tf:92` referenziert
weiter den nichtexistenten Output → IAM-Repair-Scope, R06/R07 NEU-Nummerierung).
Kein silent choice: die offene Laufzeitfrage bleibt UNKNOWN (SoT-konform).

## Validation results

1. `terraform fmt -check` (CWD-pwd-verifiziert, `terraform/`): meldet NUR noch
   `variables.tf:18` (R12, ausstehend) — kein Befund an geänderten Dateien.
2. `terraform validate` (dto.): EXIT 1 mit AUSSCHLIESSLICH `variables.tf:18`;
   die Duplicate-Output-Klasse ist eliminiert (vorher 5× + Parse-Fehler).
   Dahinter maskierte Schichten (Modul-Duplikate, Contracts) unverändert
   ausstehend — keine neue Schicht erzeugt.
3. Referenz-Check: 26/26 `module.*.*`-Werte in outputs.tf existieren als
   Modul-Outputs (Grep-Matrix; einziger MISS ist der Kommentar-Hinweis auf den
   entfernten Broken-Ref, kein Code).
4. `git diff --check`: PASS.
5. Bestehende Tests: keine Abhängigkeit (Python-Agent-Tests; Grep nach
   Output-Namen in tests/ leer; keine .tftest-Dateien).
6. Scope-Beleg: `git diff --stat` = nur `terraform/main.tf` (-24) +
   `terraform/outputs.tf` (+144/-45); keine Modul-/CI-/Backend-Änderung.

## Exact commit SHA

Folgt nach Commit (s. AI_AUDITLOG-Checkpoint).

---

*Konsolidierung: TERRAFORM-ROOT-OUTPUTS-CONSOLIDATION-01 · nur Root-Output-
Vertrag · keine IAM-/Lambda-/Cognito-/DynamoDB-/CI-/Backend-Änderung · kein
Apply · keine Architektur-Erfindung.*
