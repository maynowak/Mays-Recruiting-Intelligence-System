# RIS-ANALYSIS-MAIN-CI-PREFLIGHT-FIX-01

**Datum:** 2026-11-22  
**Repository:** `maynowak/Mays-Recruiting-Intelligence-System`  
**Branch:** `feature/ris-analysis-integration-07`  
**Baseline:** `75d62c1df6e313a49dfbb95f6f096d1fb5e9302b`  
**CI-Fix-Commit:** `4d3c43964b370d496312d4ea42aa934f59acb54c`  
**Status:** `MAIN CI READY`

## Ergebnis

Der bisherige Workflow war nicht nur falsch konfiguriert, sondern **invalid**:
GitHub erzeugte bei jedem Push einen Zero-Job-Failure-Run für
`.github/workflows/ci-cd.yml` (z. B. Run `45037624423` bei HEAD `75d62c1`).
Der Workflow wurde durch eine rein lesende statische Pipeline ersetzt.
Main-Push und Pull Requests gegen `main` führen nur noch
`terraform fmt -check -recursive` sowie `terraform init -backend=false` und
`terraform validate` pro committetem Modul aus. Es gibt keinen Terraform-Plan,
keinen Apply, keine AWS-Credentials und kein `environment`-Mapping mehr.
Deployment bleibt beim freigegebenen Installer-Saved-Plan-Verfahren.

## Befunde vor dem Fix

| # | Befund | Evidenz | Wirkung |
|---|---|---|---|
| 1 | `on: plan:` ist kein GitHub-Actions-Event | alte `ci-cd.yml` Z. 6-7 | Workflow invalid; jeder Push erzeugt Zero-Job-Failure (45037624423, 45037364297, ...) |
| 2 | Kein `working-directory`/`-chdir` | alte Z. 22-28; Terraform-Root ist `terraform/` | `init`/`validate`/`fmt` liefen im Repo-Root ohne `*.tf`; Validate war vakuos |
| 3 | Plan mit `environment=main` | alte Z. 47; `terraform/variables.tf` erlaubt nur `dev|test|prod` | Main-Plan würde deterministisch scheitern |
| 4 | `terraform init` mit partiellem S3-Backend ohne `-backend-config`; keine AWS-Credentials im Plan-Job | alte Z. 43-48 | Plan-Job nicht ausführbar |
| 5 | `deploy` unerreichbar und `apply -auto-approve` ohne Saved Plan | alte Z. 52-75; `prod` wird nicht getriggert, `plan` ist auf `prod` übersprungen, `deploy needs plan` | Kein nutzbares Deployment; Auto-Apply widerspricht AGENTS.md |
| 6 | Generiertes `terraform/modules/mays_orders/` ist gitignored (nur `variables.tf` getrackt) | `git ls-tree` | Root-Validate scheitert im Clean-Checkout ohne Builder-Modul |

## Fix (Commit `4d3c439`)

- Trigger: `push` auf `main` und `pull_request` gegen `main`; kein `plan:`-Key.
- `permissions: contents: read`; keine `secrets.*`, keine AWS-Env.
- `working-directory: terraform`; `terraform fmt -check -recursive`.
- Pro Modul: `terraform -chdir=modules/<name> init -backend=false -input=false`
  und `validate`; `modules/mays_orders` wird explizit übersprungen.
- Root-Validate nur, wenn ein Builder-Checkout `modules/mays_orders/main.tf`
  bereitstellt; sonst explizite Notice (kein fabriziertes Modul).
- `terraform_version` auf `>= 1.6, < 2.0` an `required_version` angeglichen.
- Kein `plan`, `show`, `apply`, `-auto-approve`, kein `environment: production`.
- Deployment-Kommentar verweist auf den freigegebenen Installer-Saved-Plan-Pfad.

## Tatsächlich ausgeführte Validierung

| Prüfung | Kontext | Ergebnis |
|---|---|---|
| Workflow-Lint | `actionlint v1.7.12` auf `ci-cd.yml` | PASS (Exit 0) |
| YAML-Struktur | PyYAML `compose` | Top-Level `name/on/permissions/env/jobs`; `on` = `push` + `pull_request`; genau ein Job |
| Verbotene Muster | `terraform plan/apply`, `auto-approve`, `secrets.`, `AWS_ACCESS_KEY`, `environment=` | keine Treffer |
| Clean-Checkout-Simulation | detached Worktree @ `75d62c1`, Git Bash, exakte Workflow-Schritte | `fmt` PASS; 15/15 Module `init`+`validate` PASS; Root übersprungen wie vorgesehen |
| Root-Validate mit Modul | dieselbe Simulation + temporäre Kopie des generierten Moduls | `init -backend=false` + `validate` PASS (nur Deprecation-Warnungen) |
| Fokussierte Regression | 7 Analysis-/Builder-/Plan-/Apply-Testdateien, Python 3.14.10 | **94 passed** |
| `git diff --check` | Workflow + Docs | PASS |
| Secret-Audit | Diff-Scan | keine Treffer |
| GitHub-Parse-Evidenz | `gh run list` nach Push `4d3c439` | kein neuer Zero-Job-Failure-Run; alte Invalid-Workflow-Runs enden bei `75d62c1` |
| Hosted Green Run | noch nicht möglich ohne PR/Main-Push | offen, kein Blocker für den Fix |

Die vollständigen QA2-Suites (3.193/3.259) wurden nicht erneut ausgeführt; sie
bleiben historische Regression bei `550090e` (Python 3.14.10/3.15).

## Merge-Readiness

- Feature vs. `origin/main` (`e95fe48`): **112 ahead / 0 behind**, **303 changed paths** nach dem Dokumentations-Commit.
- `git merge-tree --write-tree origin/main HEAD`: sauber, keine Konflikte.
- CI-Wirkung eines Main-Pushs: nur statische Checks; kein AWS-Plan, kein Apply,
  keine Credentials, kein `environment=main`.
- Keine Änderung an Analysis-Agent, Parsern, Contracts, Entitlements, Consent,
  Terraform-Ressourcen, Pins oder generiertem Mays-Target.
- Kein Terraform-Apply, AWS-Deployment, RC4-Upgrade, Target-Rebuild oder Main-Merge.

## Offene Gates

- Gate B: synthetische Analysis-Aktivierung — offen.
- Gate C: Mays `apiProfileRef`-Owner-Bindung — offen.
- Analysis-Live-E2E — nicht freigegeben.
- DLQ-Exhaustion → terminal `ORDER_FAILED` — nicht implementiert.
- Automatischer Parent-Agent-Resume — nicht implementiert.
- Technischer Cognito-Service-Principal — offen.

## Verdict

`MAIN CI READY` — der Main-Push führt ausschließlich sichere statische
Terraform-Prüfungen aus. Der erste GitHub-gehostete Green Run entsteht
erwartungsgemäß erst durch einen PR gegen `main` oder den Main-Push selbst;
die Pre-Merge-Evidenz ist actionlint + Clean-Checkout-Simulation + das
Ausbleiben des bisherigen Invalid-Workflow-Failure-Runs.
