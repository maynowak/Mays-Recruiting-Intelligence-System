# TERRAFORM-IAM-CONTRACT-REPAIR-01

## STATUS

GREEN — alle vier Scope-Verträge statisch bewiesen und minimal repariert.
Laufzeit-Rollenentscheidung bleibt explizit OPEN (kein Raten, keine
Architekturänderung).

## Exact contracts inspected (live an HEAD 3b42fc0, per Grep belegt)

1. Dead input `variable "iam_role_arn"` (lambda/variables.tf:13): 0 Leser im
   Modul (`grep var.iam_role_arn` leer) — Funktion nutzt eigene
   `lambda_execution` direkt.
2. Stale expectation `iam_role_arn = module.iam.lambda_role_arn` (main.tf:92):
   Provider nichtexistent (`output "lambda_role_arn"` in modules/iam: kein
   Treffer).
3. Undeclared use: `var.dynamodb_table_name` (iam/main.tf:15),
   `var.s3_bucket_arn` (iam/main.tf:41) — beide in iam/variables.tf fehlend
   (Grep-Beleg).
4. Unfed declarations `dynamodb_gsi1_arn`, `permissions_boundary`: 0 Referenzen
   außerhalb der Deklaration (Grep-Beleg) — tot und ungefüttert.

## Exact changes made (5 Dateien, +12/-27)

- `terraform/main.tf`: Root-Arg `iam_role_arn = module.iam.lambda_role_arn`
  ENTFERNT (fütterte toten Input mit nichtexistenter Referenz — No-Op +
  Broken-Ref in einem); iam-Call um `dynamodb_table_name =
  module.dynamodb.work_items_table_name` (Output belegt: dynamodb/main.tf:157)
  und `s3_bucket_arn = aws_s3_bucket.data.arn` (Resource belegt: main.tf:109)
  ERWEITERT.
- `terraform/modules/lambda/variables.tf`: toter `iam_role_arn`-Block ENTFERNT
  (0 Leser — semantisch No-Op).
- `terraform/modules/iam/variables.tf`: `dynamodb_table_name` + `s3_bucket_arn`
  DEKLARIERT (Typ string, Stil der Datei); `dynamodb_gsi1_arn` +
  `permissions_boundary` ENTFERNT (0 Referenzen — semantisch No-Op).
- `terraform/modules/iam/outputs.tf`: 3 stale `handler`-Blöcke ENTFERNT
  (Ziele nie existent); Hinweis-Kommentar auf Inline-Outputs belassen.
- `terraform/outputs.tf`: nur NOTE-Kommentar aktualisiert (Wiring-Aussage war
  durch Repair überholt); keine Output-Definition angefasst.
- NICHT angefasst: beide Rollen-Ressourcen, alle Policies/Permissions,
  Lambda-Runtime, Cognito/DynamoDB/SQS/API/CloudTrail/Monitoring/CI/Backend.

## Contracts intentionally left unresolved

- Welche Rolle (`iam.lambda_role` vs `lambda.lambda_execution`) final die
  AWS-Laufzeitrolle ist — OPEN (braucht Plan/Live-Evidenz, R20).
- `iam.lambda_role`-Orphan-Schicksal; SQS-`" *"`-Scope + ungenutztes
  SQS-Dokument (S2-16-Notiz); `table_name`-ARN-Ausdruck-Semantik (Policy-
  Zeile, nicht angefasst); fmt-Alignment-Rest (Phase H).

## Runtime-role decision remains OPEN

Explizit: Diese Reparatur trifft KEINE Laufzeitentscheidung (kein Raten, kein
Redesign, keine Rollen-/Policy-Änderung). Die Funktions-Anbindung
(`lambda_execution`) ist Code-Fakt; die Deployment-Wirkung bleibt UNKNOWN.

## Validation results

- Post-Greps: `var.iam_role_arn` / `module.iam.lambda_role_arn` /
  `handler`-Refs / `gsi1_arn|permissions_boundary` in `terraform/*.tf` alle
  LEER (nur Doku-Kommentare außerhalb `terraform/`); Feed-Ziele belegt.
- `terraform fmt -check` (editierte Dateien, CWD-verifiziert, kein Write):
  meldet `main.tf`-Alignment (teils pre-existing dynamodb-Block, teils Folge
  der Zeilen-Entfernung im lambda-Block) — dokumentiert, nicht geschrieben
  (Phase H). Eigene Blöcke (iam-Call) fmt-konform.
- `terraform validate` (ohne init, verboten): R12-Fehler weg; meldet nur
  `Module not installed` (6×, erwartet ohne init). Maskierte Schichten
  (Lambda-/Cognito-/DynamoDB-Duplikate) unberührt, eigene Commits.
- `git diff --check`: PASS. Scope: nur die 5 Dateien oben (+ Report/Log).
- Bestehende Tests: keine Terraform-Abhängigkeit (Agent-Tests; unverändert).

## AWS mutation

NONE (kein init/plan/apply/destroy, kein Backend-Zugriff, keine Secrets).

---

*Repair: TERRAFORM-IAM-CONTRACT-REPAIR-01 · statisch bewiesen, minimal, kein
Laufzeitentscheid · keine Konsolidierung in andere Module.*
