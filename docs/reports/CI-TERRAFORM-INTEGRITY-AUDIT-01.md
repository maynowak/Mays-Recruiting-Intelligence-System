# CI-TERRAFORM-INTEGRITY-AUDIT-01

## Status

**RED** — `terraform validate` im Verzeichnis `terraform/` schlägt deterministisch
fehl (Exit 1): 5× Duplicate-Output auf Root-Ebene + 1× Syntaxfehler
(`variables.tf:18`). Dahinter liegen weitere statisch belegte
Contract-Brüche (Modul-Duplikate, stale `handler`-Referenzen, fehlende
Pflicht-Inputs, undeklarierte Variablen). Keine Reparatur in diesem Checkpoint.

## Objective

Technische Ursachen der drei Blocker aus CI-DEPLOY-PERMISSION-AUDIT-01 exakt
ermitteln (validate-FAIL, fmt-FAIL, IAM-Modul-Inkonsistenz). Ausschließlich
READ-ONLY. Keine Reparatur, kein IAM-Fix, kein Terraform-Fix.

## Audit Scope

- Git-Baseline (verifiziert, nicht übernommen)
- Terraform-Struktur: `terraform/` (Root + 8 Module), aktiv vs. historisch
- Vorgesehener CI-Validate-/Fmt-Befehl + Ausführung im korrekten Verzeichnis
- Alle Duplicate Outputs (Pfad, Name, Definition A/B)
- fmt-Befund ohne `terraform fmt`
- IAM-Modul, `lambda_role_arn`-Contract, stale Handler-Referenzen
- Modul-Schnittstellen (Inputs/Variablen/Ressourcen/Outputs/Consumer)
- CI-Workflow-Referenz (nur lesend)
- Strikte Problem-Separation A–G, Root-Cause-Map, Unknowns

## Repository Baseline

Verifiziert per Git (nicht blind übernommen):

| Feld | Wert |
|------|------|
| Repository | `/home/dci-student/projects/Mays-Recruiting-Intelligent-System` |
| Branch | `main` |
| HEAD | `346d6f4` ("docs: audit CI/CD deploy permission chain") — verifiziert vorhanden |
| Audit-Basis davor | `c236cd4` ("docs(cross-repo): document source of truth") — verifiziert vorhanden |
| Remote | `git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git` (fetch+push, SSH) |
| Modified | keine |
| Untracked (7, unberührt) | `API-DOC-01-PLATFORM-FRONTEND-STANDARD.md`, `GIT-MIGRATION-01-RECOVERY-PREPARATION-EXECUTION.md`, `INSTALLER-DEPENDENCY-INTEGRATION-REVIEW-01.md`, `MATCHING-AUDIT-01.md`, `SOURCE-CONNECTIVITY-GATE-02-INTEGRATION-GUIDE.md`, `WORKSPACE-CLEANUP-01-INVENTORY.md`, `WORKSPACE-RIS-CLEANUP-03-CONTENT-CHECK.md`, `WORKSPACE-RIS-CLEANUP-04-DECISION.md` (7 Dateien; WORKSPACE-RIS-02 fehlt/nicht vorhanden) |
| Terraform-Delta | keines (`git diff HEAD -- terraform/` leer; .tf-mtimes Sep 09/10) |

Methoden-Hinweis: Der `workdir`-Parameter der Ausführungsumgebung erwies sich
als unzuverlässig (CWD-Verwechslung Root vs. `terraform/`). Alle
Terraform-Befunde unten stammen aus Läufen mit per `pwd` verifiziertem CWD.
Läufe im falschen Verzeichnis (Repo-Root, keine `*.tf`) liefern ein leeres
`Success!` — derselbe Effekt erklärt, warum die CI-Gates blind sind (s. CI Workflow).

## Terraform Execution Path

Aktiver Deploy-/CI-Pfad (belegt):

```
.github/workflows/ci-cd.yml (validate/plan/deploy-Jobs)
  → Arbeitsverzeichnis laut Workflow: Repo-Root (kein working-directory, kein -chdir)
  → tatsächliche Konfiguration: terraform/ (Root: main.tf, outputs.tf, variables.tf)
  → Module (per module-Blöcke in terraform/main.tf aktiv): cognito, sqs, dynamodb, iam, api, lambda
  → Backend: S3 mays-ris-tf-state-${environment} + DynamoDB-Lock mays-ris-tf-lock (terraform/main.tf:11-17)
```

| Path | Purpose | Referenced by | Classification |
|------|---------|---------------|----------------|
| `terraform/main.tf` | Root: Provider, Backend, 6 Modulaufrufe, S3-Data-Bucket, CloudWatch, Inline-Outputs | CI (soll), Module-Consumer | ACTIVE |
| `terraform/outputs.tf` | Root-Outputs (duplizieren main.tf-Inline-Outputs) | — | ACTIVE (fehlerhaft) |
| `terraform/variables.tf` | Root-Variablen (u. a. `environment` mit Syntaxfehler Z.18) | Root + Modulaufrufe | ACTIVE (fehlerhaft) |
| `terraform/modules/iam/` | Lambda-Rolle + Policies | `module "iam"` (main.tf:66) | ACTIVE (fehlerhaft) |
| `terraform/modules/lambda/` | 2. Lambda-Rolle + 5 Inline-Policies + Outputs | `module "lambda"` (main.tf:87) | ACTIVE (fehlerhaft) |
| `terraform/modules/cognito/` | User-Pool etc. | `module "cognito"` (main.tf:40) | ACTIVE (teils fehlerhaft: Duplikat-Outputs, undeklarierte Call-Args) |
| `terraform/modules/dynamodb/` | Tabellen | `module "dynamodb"` (main.tf:57) | ACTIVE (teils fehlerhaft: Duplikat-Outputs, undeklarierte Vars/Args) |
| `terraform/modules/api/` | API-GW-Anbindung | `module "api"` (main.tf:74) | ACTIVE (Outputs eindeutig) |
| `terraform/modules/sqs/` | Queues (Outputs inline in main.tf, keine outputs.tf) | `module "sqs"` (main.tf:48) | ACTIVE (Outputs eindeutig) |
| `terraform/modules/cloudtrail/` | Trail + Bucket | nirgends (kein module-Block) | HISTORICAL/UNKNOWN (auf Platte, unverdrahtet) |
| `terraform/modules/monitoring/` | Dashboard + Alarme | nirgends (kein module-Block) | HISTORICAL/UNKNOWN (auf Platte, unverdrahtet) |
| `*.tfvars` / `*.tfvars.example` | — | — | NICHT VORHANDEN (find ohne Treffer) |

## Validate Result

Vorgesehene CI-Befehle (`ci-cd.yml:22-25`): `terraform init -backend=false`,
`terraform validate`. Ausführung im korrekten Verzeichnis `terraform/`
(CWD per `pwd` verifiziert), Terraform v1.16.1:

- `terraform validate -no-color` → **EXIT 1**
- 5× `Error: Duplicate output definition` (Root):
  `outputs.tf:1` vs `main.tf:187` (`cognito_user_pool_id`),
  `outputs.tf:9` vs `main.tf:191` (`api_endpoint`),
  `outputs.tf:17` vs `main.tf:195` (`sqs_queues`),
  `outputs.tf:21` vs `main.tf:199` (`dynamodb_tables`),
  `outputs.tf:31` vs `main.tf:205` (`lambda_functions`).
- 1× `Error: Missing newline after argument` (`variables.tf:18`,
  `var.environment in ["dev", "test", "prod"]`).
- Modul-interne Fehler (s. u.) erscheinen im Validate-Output NICHT —
  sie liegen hinter den Root-Fehlern (NOT VERIFIED via validate, aber
  statisch aus Dateiebene OBSERVED).

Kein `terraform init` mit Backend, kein Plan/Apply. `.terraform/`- und
Tracked-File-Zustand unverändert (`git status` vorher/nachher identisch
bis auf Audit-Doku).

## Duplicate Outputs

Vollinventar (statisch, `^output`-Scan aller Module):

| Output | Definition A | Definition B | Context | Assessment |
|--------|--------------|--------------|---------|------------|
| `cognito_user_pool_id` | `terraform/main.tf:187` | `terraform/outputs.tf:1` | Root, identischer Wert (`module.cognito.user_pool_id`) | DUPLIKAT, funktional identisch |
| `api_endpoint` | `terraform/main.tf:191` | `terraform/outputs.tf:9` | Root, identischer Wert | DUPLIKAT, funktional identisch |
| `sqs_queues` | `terraform/main.tf:195` | `terraform/outputs.tf:17` | Root, identischer Wert | DUPLIKAT, funktional identisch |
| `dynamodb_tables` | `terraform/main.tf:199` | `terraform/outputs.tf:21` | Root, identischer Wert | DUPLIKAT, funktional identisch |
| `lambda_functions` | `terraform/main.tf:205` | `terraform/outputs.tf:31` | Root, identischer Wert | DUPLIKAT, funktional identisch |
| `role_arn` | `modules/iam/main.tf:87` | `modules/iam/outputs.tf:7` | iam-Modul | DUPLIKAT (Werte widersprüchlich: `lambda_role` vs. nichtexistenter `handler`, s. Stale) |
| `role_name` | `modules/iam/main.tf:91` | `modules/iam/outputs.tf:2` | iam-Modul | DUPLIKAT (dto.) |
| `lambda_role_arn` | `modules/lambda/main.tf:231` | `modules/lambda/outputs.tf:18` | lambda-Modul, identischer Wert (`aws_iam_role.lambda_execution.arn`) | DUPLIKAT, funktional identisch |
| `function_name`/`function_arn`/`invoke_arn` | `modules/lambda/main.tf` | `modules/lambda/outputs.tf` | lambda-Modul | DUPLIKATE, funktional identisch |
| `user_pool_id`/`user_pool_endpoint`/`user_pool_client_id` | `modules/cognito/main.tf` | `modules/cognito/outputs.tf` | cognito-Modul | DUPLIKATE (je 2×) |
| `work_items_table_name`/`work_items_table_arn`/`agent_state_table_name` (+ …) | `modules/dynamodb/main.tf` | `modules/dynamodb/outputs.tf` | dynamodb-Modul | DUPLIKATE (je 2×) |
| api-/cloudtrail-/monitoring-/sqs-Outputs | — | — | — | EINDEUTIG, keine Duplikate |

Muster: `outputs.tf`-Dateien wurden parallel zu Inline-Outputs in `main.tf`
hinzugefügt statt sie zu ersetzen (parallele/historische Strukturen, keine
Lösch-/Zusammenführungsentscheidung in diesem Audit).

Referenzen auf Root-Outputs: keine externen Consumer im Repo belegt
(Outputs sind Kettenglieder für Plan/Show, kein Modul-Input).

## Format Check

CI-Befehl (`ci-cd.yml:28`): `terraform fmt -check`. Ausführung in `terraform/`
(CWD verifiziert): **EXIT 2**, einziger Befund `variables.tf` (Missing-newline,
Z.18 — derselbe Parse-Fehler wie in validate). Kein `terraform fmt` ausgeführt,
keine Formatänderung. Hinweis: `fmt -check` bricht hier auf Parse-Ebene ab;
weitergehende Formatabweichungen dahinter sind NOT VERIFIED.

| File | Format Finding | CI Relevant |
|------|---------------|-------------|
| `terraform/variables.tf:18` | Missing newline after argument (`in [...]`) | JA (`fmt -check` Gate) |

## IAM Module Audit

`lambda_role_arn`-Contract (Tabelle):

| Location | Expected From | Actual Provider | Status |
|----------|---------------|-----------------|--------|
| `terraform/main.tf:92` (`iam_role_arn = module.iam.lambda_role_arn`) | `module.iam`, Output `lambda_role_arn` | iam-Modul exportiert nur `role_arn`/`role_name`/`policy_name` (doppelt) — KEIN `lambda_role_arn` | BROKEN (statisch; würde nach Behebung der Parse-/Duplikatfehler als "Unsupported attribute" fehlschlagen) |
| `terraform/outputs.tf:37-38` (`value = module.iam.lambda_role_arn`) | dto. | dto. | BROKEN (dto.) |
| `modules/lambda/*` (`lambda_role_arn`-Output) | Eigenes Modul (Lambda-Rolle) | `aws_iam_role.lambda_execution.arn` (existent) | OBSERVED konsistent, aber doppelt definiert |

Antworten A–F: (A) Root erwartet `lambda_role_arn` an 2 Stellen. (B) Liefern
soll es das iam-Modul. (C) Nein — Output existiert dort nicht. (D) Tatsächlich
vorhanden: `role_arn` (= `aws_iam_role.lambda_role.arn`). (E) Ja — zwei
Lambda-Rollenstrukturen parallel (`iam.lambda_role` + `lambda.lambda_execution`;
unklar, welche effektiv trägt). (F) Ja — stale `handler`-Referenzen (s. u.).

Zusatz-Contractbruch im iam-Modul: Pflicht-Variablen `dynamodb_gsi1_arn` und
`permissions_boundary` (variables.tf, ohne Default) werden vom Root-Aufruf
NICHT übergeben (nur `project_name`, `dynamodb_table_arn`, `tags`) — fehlende
Pflicht-Inputs (würden als "No value for required variable" fehlschlagen).
`lambda_sqs`-Policy-Dokument ist definiert, aber nicht in `lambda_policy`
eingebunden (nur Logs/DynamoDB/S3).

## Stale Handler References

| Reference | File | Expected Resource | Exists? | Classification |
|-----------|------|-------------------|---------|----------------|
| `aws_iam_role.handler.name` | `modules/iam/outputs.tf:4` | `aws_iam_role.handler` | NEIN (nur `aws_iam_role.lambda_role` in main.tf) | STALE |
| `aws_iam_role.handler.arn` | `modules/iam/outputs.tf:9` | dto. | NEIN | STALE |
| `aws_iam_role_policy.handler.name` | `modules/iam/outputs.tf:14` | `aws_iam_role_policy.handler` | NEIN (nur `aws_iam_role_policy.lambda_policy`) | STALE |

Keine `handler`-Ressource sonstwo in `terraform/` (`grep` nur die 3 Treffer).
Kein Hinweis auf aktive Nutzung → STALE (historische Umbenennung
`handler` → `lambda_role`/`lambda_policy` ohne Nachziehen der Outputs;
keine Löschentscheidung in diesem Audit).

## Module Contract Findings

Input→Variable→Ressource→Output→Consumer (nur belegte Beziehungen):

- IAM→Lambda: BROKEN (s. o.: `module.iam.lambda_role_arn` nichtexistent;
  zusätzlich 2 ungefütterte Pflicht-Inputs `dynamodb_gsi1_arn`,
  `permissions_boundary`).
- Lambda→API: INTAKT auf Referenzebene (`module.lambda.invoke_arn` ←
  `invoke_arn`-Output existent; `api_arn = module.api.api_id` ← `api_id`
  existent). Durch Duplikat-Outputs derzeit nicht validierbar.
- IAM→SQS/DynamoDB/Cognito: keine direkten Modul-Outputs konsumiert;
  indirekt OK (`module.dynamodb.work_items_table_arn` ← Output existent).
- DynamoDB-Modul: Root übergibt `environment` + `table_config`, Modul
  deklariert nur `project_name`/`tags` → UNSUPPORTED ARGUMENTS (statisch);
  `main.tf:24-25` nutzt `var.table_config.*` (undeklariert) → UNDECLARED
  REFERENCE. Beides hinter den Parse-Fehlern (NOT VERIFIED via validate).
- Cognito-Modul: Root übergibt `environment` (undeklariert) →
  UNSUPPORTED ARGUMENT (statisch). `main.tf` nutzt keine undeklarierten Vars.
- SQS-/API-Module: Calls decken sich mit Deklarationen (INTAKT auf
  Referenzebene).
- CloudTrail/Monitoring: keine Consumer (HISTORICAL/UNKNOWN).

## CI Workflow

`.github/workflows/ci-cd.yml` (lesend, unverändert):

- Jobs: `validate` (Zeilen 10-28), `plan` (30-50, gated `ref != refs/heads/prod`),
  `deploy` (52-75, gated `ref == refs/heads/prod`, Secrets AWS_*).
- Validate-Job: `terraform init -backend=false`, `terraform validate`,
  `terraform fmt -check` — aber OHNE `working-directory`/`-chdir`
  (`grep` → NO_WORKING_DIRECTORY_SET). Die Konfiguration liegt in
  `terraform/`, der Job läuft in Repo-Root (dort keine `*.tf`).
- Belegt: `terraform validate` in Repo-Root → `Success!` (EXIT 0, vakuos,
  keine Dateien). Die Gates sind damit BLIND: sie prüfen nie die echte
  Konfiguration (OBSERVED, Kategorie E). So konnten sich die Duplikate
  ansammeln, obwohl das Gate "grün" zeigt.
- Nebenbefund (OBSERVED, Auswirkung NOT VERIFIED, GitHub-seitig):
  Trigger `on.plan.branches` (Zeilen 6-7) — `plan` ist kein GitHub-Event.
- Plan-Job: `terraform init` (mit Backend!), `plan -var environment=ref_name`,
  `show -json`. Deploy-Job: `init`, `apply -auto-approve` mit Secrets.
  Variablen/Module s. Execution Path. Keine Workflow-Änderung.

## Root-Cause Map

```
CI (GitHub Actions, Root-CWD, kein -chdir)
  ↓  VERIFIED (Workflow gelesen)
Blind-Gate: validate/fmt prüfen LEERE Root (vakuos grün)
  ↓  OBSERVED (Root-Validate Exit 0 ohne *.tf)
Echte Konfiguration terraform/ wird nie geprüft
  ↓  OBSERVED
terraform validate (in terraform/) → EXIT 1
  ↓  VERIFIED (Exit-Code, CWD per pwd belegt)
5× Duplicate Output (Root) + variables.tf:18 Syntax
  ↓  VERIFIED
PLAN NOT REACHED (parsen scheitert vor Modulauflösung)
  ↓  VERIFIED (kein Plan-Artefakt möglich)
Modul-Fehler dahinter (iam/lambda/cognito/dynamodb Duplikate,
stale handler, fehlende/undeklarierte Vars/Args)
  ↓  OBSERVED statisch / NOT VERIFIED via validate
Provider-Init / AWS-Identität / AWS-API
  ↓  NOT REACHED (keine Aussage über IAM-Runtime möglich)
```

Keine Behauptung über IAM-Funktionalität: der betreffende Schritt wurde
nicht erreicht (Separation F = NOT REACHED).

## Findings

1. (B, BLOCKIEREND, VERIFIED) 5 Root-Duplikate + variables.tf-Syntaxfehler →
   validate Exit 1. Jede `plan`/`apply`-Kette scheitert deterministisch davor.
2. (B, OBSERVED) Systematisches Duplikat-Muster in iam/lambda/cognito/dynamodb
   (outputs.tf parallel zu Inline-Outputs) — zweite Fehlerschicht nach Fix
   von (1).
3. (C, OBSERVED) `module.iam.lambda_role_arn` nichtexistent (2 Referenzen);
   iam-Pflicht-Inputs `dynamodb_gsi1_arn`/`permissions_boundary` ungefüttert;
   dynamodb/cognito erhalten undeklarierte Args (`environment`,
   `table_config`); dynamodb nutzt undeklariertes `var.table_config`.
4. (D, STALE) 3 `handler`-Referenzen ohne Ressource (Umbenennungsrest).
5. (E, OBSERVED) CI-Gates blind (falsches CWD) + `on.plan`-Anomalie —
   erklärt, wie (1)-(4) unbemerkt wachsen konnten.
6. (A, OBSERVED) fmt-Gate rot (derselbe Parse-Fehler; Dahinterliegendes
   NOT VERIFIED).
7. (F) IAM-Runtime: NOT REACHED — keine verifizierte Aussage (kein Vermischen).
8. Struktur-Hygiene: cloudtrail-/monitoring-Module unverdrahtet (UNKNOWN);
   keine tfvars-Dateien.

## Unknowns

- Exakte historische Reihenfolge (welche Output-Kopie ist "original") — keine
  Lösch-/Behalte-Empfehlung in diesem Audit (Ticket-Vorgabe).
- Validate-Befund nach Behebung der Root-Fehler (zweite Schicht NOT VERIFIED).
- Dahinterliegende fmt-Abweichungen (NOT VERIFIED, Parser bricht ab).
- CI-Gate-Verhalten nach CWD-Korrektur (GitHub-seitig NOT VERIFIED).
- `on.plan`-Auswirkung auf Job-Auslösung (NOT VERIFIED).
- Zweck/Status cloudtrail-/monitoring-Module (UNKNOWN).
- IAM-Runtime-Funktionalität (NOT REACHED).

## Evidence

| # | Command / Quelle (CWD-verifiziert) | Ergebnis |
|---|------------------------------------|----------|
| E1 | `git rev-parse --show-toplevel`, `git status --short --branch`, `git branch --show-current`, `git rev-parse HEAD`, `git log -1`, `git remote -v`, `git cat-file -t 346d6f4/c236cd4` | main, 346d6f4 (+c236cd4 existent), SSH-Remote, 0 modified / 7 untracked |
| E2 | `find terraform -name *.tf` (26 Dateien), `ls terraform/modules/`, `grep ^module terraform/main.tf` | Root + 8 Module, 6 aktiv verdrahtet, cloudtrail/monitoring ohne Block |
| E3 | `find . -name *.tfvars*` | keine Treffer |
| E4 | `terraform validate -no-color` in `terraform/` (pwd belegt), Terraform v1.16.1 | EXIT 1: 5× Duplicate (outputs.tf:1/9/17/21/31 vs main.tf:187/191/195/199/205) + variables.tf:18 Missing newline |
| E5 | `terraform validate -no-color` in Repo-Root | EXIT 0 `Success!` (keine `*.tf` — vakuos) |
| E6 | `terraform fmt -check` in `terraform/` | EXIT 2, Befund variables.tf:18 |
| E7 | `^output`-Scan aller Module | Duplikate: root 5, iam 2, lambda 4, cognito 3, dynamodb 3; api/cloudtrail/monitoring/sqs eindeutig |
| E8 | `grep handler` in `terraform/*.tf` | nur `modules/iam/outputs.tf:4/9/14` (STALE) |
| E9 | `grep lambda_role_arn` in `terraform/*.tf` | main.tf:92, outputs.tf:37-38 (Erwartung) vs. kein iam-Output; lambda-Modul doppelt |
| E10 | Variablen-vs-Call-Abgleich (iam/lambda/api/sqs/dynamodb/cognito) | iam: 2 Pflicht-Inputs ungefüttert; dynamodb/cognito: undeklarierte Args; dynamodb: undeklarierte Var-Nutzung Z.24-25 |
| E11 | `.github/workflows/ci-cd.yml` (Z.10-75), `grep working-directory/chdir` | kein CWD gesetzt; Befehle init -backend=false/validate/fmt-check/plan/show/apply; `on.plan`-Anomalie Z.6-7 |
| E12 | `git diff HEAD -- terraform/`, `git status` nach Checks | leer / unverändert → keine Mutation |

## Recommended NEXT STEP

Nächster technischer Arbeitsschritt (separater Repair-Checkpoint, nicht hier):
CWD der CI-Terraform-Schritte auf `terraform/` festlegen (`working-directory`),
danach schichtweise validierbar machen — zuerst Root-Duplikate + variables.tf:18
(bis `validate` die Modulebene erreicht), dann Modul-Duplikate, stale
`handler`-Outputs, `lambda_role_arn`-Contract und Variablen-Verträge je Schicht
mit `validate` gegenprüfen. Installer, Pipeline-System und historische
Parallelstrukturen dabei nicht löschen, nur entscheiden (eigener Schritt).

---

*Audit: CI-TERRAFORM-INTEGRITY-AUDIT-01 · Read-Only · keine Terraform-/IAM-/
AWS-Mutation · kein `terraform fmt`, kein init mit Backend, kein Plan/Apply ·
keine Secrets berührt · keine untracked Datei verändert.*
