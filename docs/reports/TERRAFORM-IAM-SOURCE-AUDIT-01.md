# TERRAFORM-IAM-SOURCE-AUDIT-01

## Status

**YELLOW** — IAM-Quellenlage vollständig identifiziert (kein Fix, keine Konsolidierung).
Authoritative Implementierung aus Evidence bestimmt; eine Laufzeitfrage bleibt
explizit UNKNOWN (kein Raten). IAM ist KONTRAKT-bereit für Konsolidierung
(alle Adressen/Consumer bekannt), aber NICHT laufzeit-verifiziert.

## A. Scope

Ausschließlich IAM-Varianten im canonical RIS-Repo (read-only): main.tf-Wiring,
alle IAM-Pfade, Lambda-IAM-Definitionen, Contract-Graph, role_arn-vs-
lambda_role_arn-Konflikt, externe Consumer, Historie, Mays-Orders-Referenzmuster,
Auswirkungsprüfung (lesend). Kein init/plan/apply, keine AWS-Mutation, keine
Änderung an Lambda/Cognito/DynamoDB/CI/CloudTrail/Monitoring.

## B. Canonical repository/HEAD

toplevel `/home/dci-student/projects/Mays-Recruiting-Intelligent-System`,
Remote `git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git`,
Branch `main`, HEAD `6d57f3a` (R12-Fix; c34e1e9-Vorgänger unangetastet),
0 modified, 7 untracked (unberührt). Genau 1 Audit-Log.

## C. Existing IAM variants

Genau EIN IAM-Verzeichnis (`terraform/modules/iam`, `find`-belegt — keine
Paralleldirs). "2 Varianten" = zwei Rollenverträge + tote Handler-Namen:

1. `aws_iam_role.lambda_role` (`${project}-lambda-role`, Trust nur
   `lambda.amazonaws.com`, eigene Inline-Policy Logs/DynamoDB/S3) — seit G0.1.
2. `aws_iam_role.lambda_execution` (`${project}-${environment}-agent`,
   5 Policies, an `aws_lambda_function.agent` gebunden: lambda/main.tf:165,
   depends_on-Policies) — ebenfalls seit G0.1 (G0.1-Datei belegt).
3. `aws_iam_role.handler` / `aws_iam_role_policy.handler` — nur in
   `modules/iam/outputs.tf:4/9/14` referenziert, Ressource nie existent
   (Total-Historie leer, geboren c83e3a2, Order-Domäne/T011-Tag).
4. `variable "iam_role_arn"` (lambda-Modul, Input) — deklariert G0.2, wird
   Nirgends gelesen (Funktion nutzt eigene Rolle direkt). Toter Input.

## D. Active Terraform wiring

- `module "iam"` (main.tf:66): Inputs project_name, dynamodb_table_arn, tags.
  NICHT übergeben (Pflicht): `dynamodb_gsi1_arn`, `permissions_boundary`.
  Modul-intern UNDEKLARIERT genutzt: `var.dynamodb_table_name` (iam/main.tf:15),
  `var.s3_bucket_arn` (iam/main.tf:41, lambda_s3-Dokument).
- `module "lambda"` (main.tf:87): `iam_role_arn = module.iam.lambda_role_arn`
  (Z.92, BROKEN — Output nichtexistent). Input `iam_role_arn` wird im Modul
  ignoriert; `aws_lambda_function.agent.role` = eigene `lambda_execution`.
- Implizite Dependency: api-Modul ← `module.lambda.invoke_arn`;
  lambda ← api (`api_arn`), sqs, dynamodb, S3-Bucket. Keine `depends_on`
  zwischen iam/lambda-Root-Calls (Modul-Referenzen tragen Ordnung — der
  gebrochene Ref würde ohnehin zuerst scheitern).

## E. Role contract graph

```
ROOT
 ├─ module.iam ── aws_iam_role.lambda_role ── role_arn/role_name ──▶ root outputs (NEU, c34e1e9)
 │       ├─ aws_iam_role_policy.lambda_policy (Logs/DynamoDB/S3; SQS-Dok. ungenutzt)
 │       └─ ✗ KEIN lambda_role_arn-Output ──✗──▶ main.tf:92 (broken)
 └─ module.lambda ── var.iam_role_arn (DEAD INPUT, 0 Leser)
         └─ aws_iam_role.lambda_execution ── 5 Policies ──▶ aws_lambda_function.agent.role
                 └─ lambda_role_arn-Output ──▶ NIEMAND
```

ARN-Quellen: `lambda_role.arn` (orphan, existent) vs. `lambda_execution.arn`
(angebunden). Policy-Anbindung: je Rolle eigene Inline-Policies (kein Sharing).
Permissions (lesend): iam-Rolle Logs/DynamoDB-CRUD/S3-Objekte; execution-Rolle
Plattform-RO + Work-CRUD + SQS-Send + S3 + Logs (Details s. Dateien, nicht
erweitert/bewertet). Modulgrenzen-Überschreitung: nur gebrochene Ref Z.92.

## F. Competing role/output analysis

`role_arn` vs. `lambda_role_arn` ist KEIN bloßes Naming-Duplikat und KEINE zwei
aktiven Execution-Rollen im Rennen — es ist ein gebrochener Vertrag plus tote
Struktur: (a) `module.iam.lambda_role_arn` hat nie einen Provider gehabt
(G0.2-Einzeiler ohne Output-Seite); (b) der einzige existierende
`lambda_role_arn`-Output (lambda-Modul) ist consumerlos; (c) der Lambda-Input
dafür wird ignoriert. Historie: G0.1 = `role_arn`-Vertrag + Doppel-Rolle von
Beginn; G0.2 = Umbenennung ohne Output; c83e3a2 = handler-Namen (fremd, tot).

| Variant | Path | Role Resource | Consumer | Contract | Evidence | Classification |
|---------|------|---------------|----------|----------|----------|----------------|
| iam.lambda_role | modules/iam/main.tf:46 | existent, orphan | root outputs (c34e1e9) | role_arn/role_name | G0.1-Präsenz, Trust, Policy | ACTIVE |
| lambda.lambda_execution | modules/lambda/main.tf:8 | existent, angebunden (Funktion Z.165) | Funktion + 5 Policies | lambda_*-Outputs | G0.1-Datei, depends_on | ACTIVE |
| iam.lambda_role_arn (erwartet) | main.tf:92, ex-outputs.tf:37 | KEIN Provider | main.tf:92 (broken) | BROKEN | G0.2-Diff, Grep 1 Treffer | UNREFERENCED (als Quelle; Code-Stelle aktiv-broken) |
| handler-Familie | modules/iam/outputs.tf | nie existent | niemand | STALE | Total-Historie leer | UNREFERENCED |
| var.iam_role_arn (Input) | modules/lambda/variables.tf:13 | — (Input) | 0 Leser im Modul | DEAD | Nutzungs-Grep leer | UNREFERENCED |
| lambda.lambda_role_arn (Output) | modules/lambda/*.tf | lambda_execution (existent) | niemand | orphan, korrekt | Duplikat-Audit, Consumer-Grep leer | ACTIVE (Definition, ungenutzt) |

## G. External consumers

Code-Referenzen (keine Doku-/Historien-Texte): `module.iam.role_arn`/
`role_name` ← root `outputs.tf` (c34e1e9, öffentlich); `module.iam.
lambda_role_arn` ← nur main.tf:92 (broken); `module.lambda.lambda_role_arn`
← niemand; `var.iam_role_arn` ← niemand. API/SQS/Skripte/Tests/CI: NULL
Treffer (py/sh/yml-Greps leer). Doku-Referenzen (S2-16, Audit-Reports):
beschreibend, keine Consumer.

## H. Historical evidence

G0.1: Doppel-Rolle + `role_arn`-Vertrag + lambda-eigene-Execution (Datei-
belegt). G0.2: `role_arn`→`lambda_role_arn`-Einzeiler (Diff), `iam_role_arn`-
Input-Deklaration, Lambda-`outputs.tf`-Neuanlage. c83e3a2: handler-Outputs +
Boundary-Vars (Order-Domäne, nie aktiv). G0.3.1/G0.4: Lambda-Ausbau
(`lambda_execution`-Treffer). Danach nur Doku. Mays-Orders-Referenz (Git-only,
9c61237): EIN-Rollen-Modell — `role = var.iam_role_arn`, Root `module.iam.
role_arn`, outputs `iam_handler_role_*`. RIS weicht ab (Selbst-Rolle + toter
Input), behält eigene Architektur (nicht kopiert).

## I. Source-of-truth decision (identifizierend, kein Redesign)

Authoritative Implementierung: ZWEI reale Rollen-Ressourcen (beide ACTIVE als
Ressourcen) mit geteilten Verträgen — `iam.lambda_role` (Export-Vertrag
`role_arn`, G0.1) und `lambda.lambda_execution` (Laufzeit-Anbindung, einzige
Funktions-Rolle). `lambda_role_arn`-Erwartung an iam: STALE/broken.
handler: STALE. Input: tot. Effektive Laufzeit-Rolle: ANGEBUNDEN ist
`lambda_execution` (Funktions-Code Z.165) — als Deployment-Wirkung dennoch
UNKNOWN markiert (kein Plan/Live-Beleg; kein Raten über AWS-Seite hinaus).

## J. Open questions

Effektive Rolle zur Laufzeit (Plan/Live-Beleg ausstehend); `iam.lambda_role`-
Orphan-Schicksal (Owner); `table_name`/`s3_bucket_arn`-Lücken im iam-Modul
(belegt, Repair-Scope); SQS-`" *"`-Scope + ungenutztes SQS-Dokument (S2-16-
Notiz, nicht erneut bewertet).

## K. Recommended next repair boundary

STOP-Linie: `main.tf:92` REWIRE (auf belegten `role_arn`) + toter Input +
stale outputs.tf-Blöcke = eigener IAM-Contract-Checkpoint (R06–R08);
Rollen-Zusammenlegung/Boundary-Entscheidung erst nach Plan/Live-Evidenz (R20).
NICHT in diesem Task: Lambda/Cognito/DynamoDB/CI/CloudTrail/Monitoring.

---

*Audit: TERRAFORM-IAM-SOURCE-AUDIT-01 · read-only · kein init/plan/apply ·
keine AWS-Mutation · keine Implementierungsänderung.*
