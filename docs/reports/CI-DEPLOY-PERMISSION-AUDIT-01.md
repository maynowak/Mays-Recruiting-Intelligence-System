# CI-DEPLOY-PERMISSION-AUDIT-01

## Status

**RED** — die CI/CD Deploy-Kette ist bereits vor jeder IAM-Frage blockiert:
`terraform validate` schlägt deterministisch fehl (5× Duplicate-Output),
`terraform fmt -check` schlägt fehl. Kein Plan-/Deploy-Artefakt kann erzeugt
werden, unabhängig von Berechtigungen. Zusätzlich ist die effektive
Deploy-Identität (GitHub Secrets) NOT VERIFIED.

Kein Repair in diesem Report. Nur Ist-Zustand + belegte Gaps.

## Objective

Untersuche die aktuell bestehende CI/CD Deploy-Berechtigungskette im
Repository und dokumentiere sie vollständig. Konsolidierungsstand:
CodePipeline Source nutzt AWS CodeConnections, Source-Auth ist NICHT die
Baustelle — offen ist die Deploy-Berechtigungs-/Policy-Kette.
Keine neue Architektur, keine Änderungen am Installer/Pipeline-System.
Ausschließlich READ-ONLY AUDIT.

## Scope

- Repository-Identität (Git, Branch, HEAD, Remote, Working Tree)
- Bestehende Doku (AI_AUDITLOG, Reports, inkl. fehlender Konsolidierungsreport)
- Pipeline-Architektur aus Repository-Evidence (keine Annahmen)
- AWS-Identität (nur Read-Only APIs)
- Identity Chain, IAM-Rollen, Permission Boundaries, Trust/AssumeRole
- Deploy-Permission-Bedarf vs. vorhandene Berechtigungen
- Strikte Trennung: (A) Source/CodeConnections, (B) DOWNLOAD_SOURCE, (C) Deploy
- Keine Reparatur, keine Mutation

## Repository Identity

| Feld | Wert |
|------|------|
| Git root | `/home/dci-student/projects/Mays-Recruiting-Intelligent-System` |
| Branch | `main` |
| HEAD | `c236cd4` (`docs(cross-repo): document source of truth`) |
| Origin | `git@github.com:maynowak/Mays-Recruiting-Intelligence-System.git` (fetch+push, SSH) |
| Working Tree | DIRTY durch Vorarbeiten (M `docs/AI_AUDITLOG.md`, 8 untracked Reports) — von diesem Audit unverändert gelassen, nichts überschrieben |

## Current CI/CD Chain

Belegt im Repository (keine Annahmen):

```
GitHub Push auf main
  ↓  (.github/workflows/ci-cd.yml)
Job validate: checkout → setup-terraform → init -backend=false → validate → fmt -check
  ↓
Job plan (wenn ref != refs/heads/prod): init → plan → show -json
  ↓
Job deploy (NUR wenn ref == refs/heads/prod): init → apply -auto-approve
  mit Secrets: AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (nur Namen belegt)
  ↓
Terraform CLI mit Backend S3 (mays-ris-tf-state-${environment}) + DynamoDB-Lock (mays-ris-tf-lock)
  ↓
Module: cognito, sqs, dynamodb, iam, api, lambda (+ S3-Data-Bucket, CloudWatch)
  ↓
AWS APIs
```

OBSERVED:

- **Kein `aws_codepipeline` / kein `aws_codebuild` / keine Buildspec im Repo**
  (`grep` in `terraform/`: keine Treffer; kein `buildspec*.yml`,
  kein Workflow außer `ci-cd.yml`). CodePipeline/CodeBuild-Referenzen
  existieren nur in `agents/source_connectivity.py` (+ Tests) und in
  `SOURCE-CONNECTIVITY-GATE-01/02` — also im externen Mays-Orders-Kontext,
  nicht als deployende Pipeline dieses Repos.
- Die deployende Pipeline DIESES Repos ist GitHub Actions (`ci-cd.yml`).
- OBSERVED-Anomalie in `ci-cd.yml` (Zeile 6-7): Trigger `plan:` ist kein
  GitHub-Workflow-Event. Auswirkung auf Job-Auslösung: NOT VERIFIED
  (braucht GitHub-seitige Prüfung, kein Repo-Run möglich).
- Installer (`installer/orchestrator.py`, `installer/__main__.py`,
  `installer/projects/` = leer) ist lokaler Dev-Orchestrator
  (Projekt-Checkout, Git-Discovery, Koordination mit Mays-Orders-Installer),
  kein Deploy-Role-Inhaber. Keine IAM-/AssumeRole-Logik belegt.

Referenz (nicht dupliziert): `docs/reports/S2-16-IAM-DEPLOYMENT-GOVERNANCE.md`
(Runtime-vs-Deploy-Trennung, GREEN für Runtime-Seite),
`docs/reports/CROSS-REPO-SOURCE-01.md` (Repo-Grenzen RIS vs. Mays-Orders-AWS),
`docs/reports/SOURCE-CONNECTIVITY-GATE-01.md`,
`docs/reports/SOURCE-CONNECTIVITY-GATE-02-INTEGRATION-GUIDE.md`
(Source-Seite A+B, Framework, alle Live-Checks NOT_VERIFIED).

NICHT GEFUNDEN: `docs/reports/KONSOLIDIERUNG-CICD-SOURCE-AUTH-AUDIT.md`
existiert nicht (`ls docs/reports/KONSOLIDIERUNG*` → No such file).
Darauf kann nicht referenziert werden.

## Identity Chain

| Component | Identity / Role | Evidence | Next Hop |
|-----------|-----------------|----------|----------|
| Human / Trigger | GitHub Push-Akteur auf `main` | `ci-cd.yml:4-5` | GitHub Actions Runner |
| CI Runner Identity | `secrets.AWS_ACCESS_KEY_ID` (+ Secret Key, Region) | `ci-cd.yml:72-75` (nur Namen, keine Werte gelesen) | Terraform AWS Provider |
| Terraform Provider Identity | Inhalt der Secrets | NOT VERIFIED (Secrets nie gelesen/ausgegeben) | AWS Resource APIs + State-Backend |
| State Backend | S3 `mays-ris-tf-state-${environment}` + DynamoDB `mays-ris-tf-lock` | `terraform/main.tf:11-17` | Module-Ressourcen |
| Runtime Identity | `aws_iam_role.lambda_role` (iam-Modul) + `aws_iam_role.lambda_execution` (lambda-Modul), Trust nur `lambda.amazonaws.com` | `terraform/modules/iam/main.tf:46-63`, `terraform/modules/lambda/main.tf:8-24` | Lambda Runtime (kein Deploy) |

Kein CodePipeline-Role-Hop, kein CodeBuild-Service-Role-Hop, kein
AssumeRole-Hop im Repo belegt. Kette endet beim Terraform-Provider mit der
unbekannten Secrets-Identität.

Live-Prinzipal dieser Workstation (nur als Messpunkt, NICHT Deploy-Identität):
IAM-User `maymilly`, Account `992382612204`, Region `eu-central-1`
(`aws sts get-caller-identity`, `aws configure get region`).

## IAM Roles

OBSERVED (statisch, Dateiebene):

1. `terraform/modules/iam/main.tf`: `aws_iam_role.lambda_role`
   (`${project}-lambda-role`), Trust `lambda.amazonaws.com` / `sts:AssumeRole`,
   Inline-Policy: Logs (`arn:aws:logs:*:*:*`), DynamoDB-Dokument, S3-Dokument.
   SQS-Dokument (`sqs:ReceiveMessage/DeleteMessage/GetQueueAttributes` auf `"*"`)
   ist definiert, aber NICHT in die `lambda_policy` eingebunden (nur Logs,
   DynamoDB, S3) — POTENTIAL GAP / Inkonsistenz.
2. `terraform/modules/lambda/main.tf`: `aws_iam_role.lambda_execution`
   mit 5 Inline-Policies (dynamodb-platform RO, work CRUD, sqs-send, s3, logs).
   Zwei parallele Rollen für denselben Zweck (iam-Modul + lambda-Modul):
   POTENTIAL GAP (Doppelstruktur, unklare effektive Rolle).
3. Root ruft `module.iam` mit `lambda_role_arn`-Erwartung auf
   (`terraform/main.tf:92`, `terraform/outputs.tf:37-38`), das iam-Modul
   exportiert aber nur `role_arn`/`role_name` (+ doppelt) — POTENTIAL GAP,
   siehe Findings (validate-Fehler).

Kein Pipeline-Service-Role, kein CodeBuild-Service-Role, kein Deploy-Role,
kein Installer-Role im Repo.

## Permission Boundaries

- `terraform/modules/iam/variables.tf:22-25` deklariert
  `variable "permissions_boundary"` ("externally managed permissions boundary
  for the handler role") — aber: nirgends verwendet, nirgends übergeben
  (`grep permissions_boundary` → genau 1 Treffer, die Deklaration).
  Status: OBSERVED / POTENTIAL GAP (tote Variable; keine Boundary wirksam).
- `variable "dynamodb_gsi1_arn"` (ebenda:17-20): ebenfalls deklariert,
  nie verwendet/übergeben. OBSERVED (Nebenbefund).
- Kein `permissions_boundary`-Argument an irgendeiner `aws_iam_role`-Ressource.
- Live-Boundaries: NOT VERIFIED (keine List-/Get-Rechte, siehe unten).

## Trust / AssumeRole Chain

- Einzige belegte Trust-Beziehung: `lambda.amazonaws.com` → `sts:AssumeRole`
  (iam-Modul + lambda-Modul). Kein externer Principal, keine Conditions.
- Kein `AssumeRole`-Hop zwischen CI und Deploy im Repo (kein
  `sts:AssumeRole`-Aufruf in Installer/Workflows belegt).
- Folglich: keine Trust-Policy-Kette zu prüfen; Deploy nutzt langlebige
  Secrets-Key-Identität direkt. Bewertung der Secrets-Identität: NOT VERIFIED.

## Deploy Permission Requirements

Abgeleitet ausschließlich aus tatsächlich im Deployment enthaltenen
Ressourcen (`terraform/main.tf` + Module):

| Bereich | Benötigte Aktionen (Familien, keine erfundene Liste) |
|---------|------------------------------------------------------|
| Terraform State | S3 Get/Put/List auf State-Bucket, DynamoDB Get/Put/Delete auf Lock-Tabelle |
| S3 | s3:* (Bucket + Objekte) für Data-Bucket inkl. Versioning/Encryption/PublicAccessBlock |
| DynamoDB | Tabellen + Indizes + Tags für alle Tabellen |
| Lambda | iam:PassRole + lambda:* für Funktion, Layer, Event-Source-Mappings, Logs-Anbindung |
| IAM | iam:* für Rollen/Policies des iam- + lambda-Moduls |
| API Gateway | apigateway:* (Modul `api`) |
| SQS | sqs:* (Modul `sqs`) |
| Cognito | cognito-idp:* (Modul `cognito`) |
| CloudWatch | logs:*, cloudwatch:* (Log-Gruppen, Alarme) |
| Tags | Tagging-Aktionen aller obigen Services (default_tags) |

Abgleich mit vorhandenen Berechtigungen: Die Deploy-Identität (Secrets)
ist unbekannt → Abgleich NOT VERIFIED. Der einzige bekannte Prinzipal
(`maymilly`) ist nachweislich NICHT deployfähig (siehe Evidence:
`codepipeline:ListPipelines`, `codebuild:ListProjects`, `iam:ListRoles`,
`iam:ListAttachedUserPolicies`, `dynamodb:DescribeTable` alle
AccessDenied; State-Bucket `mays-ris-tf-state-dev` → NoSuchBucket).

## Observed Policy Coverage

- Runtime-Seite (S2-16, referenziert): Least-Privilege-Struktur belegt,
  kein IAM-/State-Zugriff der Runtime. Nicht erneut geprüft.
- Deploy-Seite: KEINE Identity-Policy im Repo (GitHub Secrets liegen außerhalb
  des Repos). Coverage daher NOT VERIFIED.
- Resource-Policies: keine im Repo (kein Bucket-/Queue-Policy-Dokument).
- SCP/Account-Boundary: NOT VERIFIED.

## Gaps / Unknowns

1. (BELEGT, BLOCKIEREND) `terraform validate` fails: 5× Duplicate-Output
   (Root `outputs.tf` vs. Inline-Outputs `main.tf:187-209`;
   `modules/lambda/outputs.tf` vs. `main.tf:231`;
   `modules/iam/outputs.tf` vs. `main.tf:87-93`).
   → CI-Job `validate` kann nicht grün werden → kein Plan/Deploy.
2. (BELEGT) `terraform fmt -check` fails:
   `variables.tf:18` Missing-newline (`in ["dev","test","prod"]`).
3. (BELEGT) `modules/iam/outputs.tf` referenziert `aws_iam_role.handler` /
   `aws_iam_role_policy.handler` — existiert nicht (nur `lambda_role`/
   `lambda_policy`). Würde nach Behebung der Duplikate als nächster Fehler
   erscheinen.
4. (BELEGT) Root erwartet `module.iam.lambda_role_arn` — Output existiert nicht.
5. (BELEGT) `permissions_boundary`-Variable tot (deklariert, nie verdrahtet).
6. (UNKNOWN) Effektive Deploy-Identität der GitHub Secrets (Policies, Boundary,
   Trust): NOT VERIFIED.
7. (UNKNOWN) Live-Pipeline/Rollen (CodePipeline-/CodeBuild-Rollen des
   Mays-Orders-Kontexts): NOT VERIFIED — aktueller Prinzipal hat keine
   List-Rechte (BLOCKED, kein Fehler der Kette).
8. (UNKNOWN) State-Backend-Existenz pro Environment: `dev`-Bucket → NoSuchBucket
   (OBSERVED nur für dev/eu-central-1); test/prod NOT VERIFIED.
9. (OBSERVED/UNKNOWN) Workflow-Trigger `plan:` ist kein GitHub-Event;
   Auswirkung auf Planauslösung NOT VERIFIED.

## Historical Findings

- DOWNLOAD_SOURCE-Kontext (SOURCE-CONNECTIVITY-GATE-01/02,
  `agents/source_connectivity.py`): historischer/designierter Befund der
  SOURCE-Seite (A: CodeConnections, B: CodeBuild-Download). Wird hier NICHT
  als Deploy-IAM-Befund gewertet. Keine neuen DOWNLOAD_SOURCE-Evidenzen in
  diesem Audit erhoben; keine Vermischung mit (C) Deploy Execution.
- S2.16 (IAM Deployment Governance): Runtime-Trennung GREEN, Policy-Gate als
  "documented only" offen. Konsistent mit Befund 1-2 (Gate läuft, schlägt an).

## Evidence

| # | Quelle | Befund |
|---|--------|--------|
| E1 | `git rev-parse --show-toplevel`, `git status --short --branch`, `git rev-parse HEAD`, `git remote -v`, `git log -1` | main, c236cd4, SSH-origin, dirty durch Vorarbeiten |
| E2 | `ls docs/reports/KONSOLIDIERUNG*` | Datei nicht vorhanden |
| E3 | `grep aws_codepipeline/aws_codebuild/buildspec` in `terraform/`; `glob buildspec*` | keine Treffer — keine Pipeline-Ressourcen im Repo |
| E4 | `.github/workflows/ci-cd.yml:1-75` | GitHub-Actions-Kette validate→plan→deploy; Secrets-Namen; `plan:`-Trigger; prod-gated apply |
| E5 | `terraform/main.tf:11-17,66-106` | S3/DynamoDB-Backend; Module; `module.iam.lambda_role_arn`-Referenz |
| E6 | `terraform/modules/iam/main.tf:1-93` | lambda_role, Trust, Policies; SQS-Dokument ungenutzt; Outputs role_arn/role_name |
| E7 | `terraform/modules/iam/outputs.tf:1-15` | handler-Referenzen (nichtexistent), Duplikate role_arn/role_name |
| E8 | `terraform/modules/iam/variables.tf:22-25` | permissions_boundary deklariert, ungenutzt |
| E9 | `terraform/modules/lambda/main.tf:8-24` + Outputs `:231` | zweite Lambda-Rolle; lambda_role_arn-Duplikat |
| E10 | `terraform init -backend=false -input=false` + `terraform validate` (read-only, keine Tracked-File-Änderung) | FAIL, 5× Duplicate output definition |
| E11 | `terraform fmt -check` (read-only) | FAIL, variables.tf:18 Missing newline |
| E12 | `aws sts get-caller-identity` | Account 992382612204, User maymilly (Identifikatoren, keine Secrets) |
| E13 | `aws codepipeline list-pipelines`, `aws codebuild list-projects`, `aws iam list-roles`, `aws iam list-attached-user-policies`, `aws dynamodb describe-table mays-ris-tf-lock` | AccessDenied (keine Identity-Based-Policy) → live Kette NOT VERIFIED |
| E14 | `aws s3 ls s3://mays-ris-tf-state-dev` | NoSuchBucket (dev, eu-central-1) |
| E15 | `installer/orchestrator.py`, `installer/projects/` (leer) | lokaler Orchestrator, keine Deploy-Rolle |
| E16 | `git status --short` nach allen Checks | unverändert (nur Vorarbeits-Delta) → Read-Only eingehalten |

Keine erfundenen AWS-Ergebnisse. Keine Secrets gelesen oder ausgegeben
(nur Secret-Namen aus dem Workflow + Identifier aus sts).

## Findings

1. **Deploy-Kette ist vor IAM blockiert (RED-treibend).** Duplicate-Outputs
   lassen `validate` deterministisch fehlschlagen; `fmt -check` ebenso.
   Der CI-Deploy-Pfad kann aktuell kein Artefakt produzieren — unabhängig
   davon, welche Rechte die Secrets-Identität hat.
2. **IAM-Modul inkonsistent.** Stale `handler`-Referenzen, fehlender
   `lambda_role_arn`-Output, tote `permissions_boundary`-Variable,
   Doppel-Rollenstruktur (iam- vs. lambda-Modul), ungenutztes SQS-Dokument.
3. **Deploy-Identität unbekannt.** Keine Aussage über effektive Permissions
   möglich (NOT VERIFIED). Bekannter Human-Prinzipal ist least-privilege
   und nachweislich nicht deployfähig — das ist korrektes Verhalten, kein Fehler.
4. **Source-Seite sauber getrennt.** Keine Vermischung von CodeConnections/
   DOWNLOAD_SOURCE mit Deploy. Konsolidierungsreport fehlt physisch.
5. **Keine Pipeline-Rollen im Repo.** CodePipeline/CodeBuild-Rollen liegen
   (falls existent) außerhalb dieses Repos (Mays-Orders-Kontext) und sind mit
   aktuellem Prinzipal nicht einsehbar.

## Conclusion

STATUS: **RED** — nicht wegen einer nachgewiesenen falschen IAM-Policy,
sondern weil die Deploy-Kette belegbar nicht ausführbar ist
(Validate-/Fmt-Gates rot) und die effektive Deploy-Berechtigungslage
unverifizierbar ist. Die Runtime-IAM-Seite bleibt per S2.16-Referenz GREEN;
dieser Befund betrifft ausschließlich den CI→Terraform-Deploy-Pfad.

## Next Step

Separater Repair-Schritt (NICHT Teil dieses Audits): Duplikat-Outputs
bereinigen, `handler`-Referenzen entfernen, `lambda_role_arn`-Export klären,
`fmt` fixen, danach `validate`/`fmt -check` grün stellen; anschließend
Deploy-Identität der GitHub Secrets (Policies, Boundary, Trust) in eigenem
Berechtigungs-Review mit geeignetem Prinzipal verifizieren. Installer und
Pipeline-System dabei unverändert lassen.

---

*Audit: CI-DEPLOY-PERMISSION-AUDIT-01 · Read-Only · keine Infrastruktur-Mutation
durchgeführt · keine IAM-/Pipeline-/Terraform-Änderung · keine Secrets ausgegeben.*
