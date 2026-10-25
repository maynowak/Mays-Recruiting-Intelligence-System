# MO-RIS-DEV2-S00-BASELINE-2026 — Dokumentierter Ausgangsstand

**Datum (tatsächliche Ausführung):** 2026-10-25
**Run-ID:** `2026-10-25-ris-dev2-01`
**Status:** COMPLETE (Bestandsaufnahme) — Ausführung von S01 **BLOCKED** (siehe §9)
**Execution-Modus:** rein statisch/lesend, keine Implementierung, kein Deployment, keine AWS-Aufrufe

---

## 1. Auftrag und Abgrenzung

Ziel von S00 ist ausschließlich der dokumentierte Ausgangsstand für den schrittweisen
Integrationsnachweis des Mays-Orders-AWS Module Builders in Mays-RIS.

**In Scope**

- Git-Ausgangslage beider Repositories (Pfad, origin, Branch, SHA, Status)
- Toolchain-Ist-Stand gegen die Anforderungen des Codes
- Statische Zuordnung von Builder-, Modul-, Pin- und Consumer-Pfaden
- Einordnung vorhandener Evidence zu früher gemeldeten Ergebnissen
- Testkontext (Projekt, Workspace, Region, Backend-/State-Rahmen) als bekannt/offen

**Ausdrücklich nicht in Scope**

- Implementierung, Quellcodeänderung, Wrapper-Lauf
- `terraform init/plan/apply/destroy`, Backend-Bootstrap, State-Operationen
- AWS-Ressourcenzugriff, Release-Tags
- Der bisherige `Mays-Order-AWS-installer` und die Composite-`install`-Sequenz
  (nur als Abgrenzung referenziert, nicht bewertet)

**Vorgegebene Zielparameter (aus dem Auftrag, nicht aus dem Code abgeleitet)**

| Parameter | Wert |
|---|---|
| RIS-Branch | `feature/mo-module-installer-ris-dev2-2026` |
| RIS-Projekt / Terraform-Workspace | `ris-dev2` |
| Orders-Komponente | `ris-dev2-mays-orders` |
| Integrationsweg | `python -m module_builder build --preset orders-service` |
| RIS-Installations-/Integrationsweg | ALPHA |

---

## 2. Tatsächliches Datum und Run-ID

- Ausführungsdatum: **2026-10-25** (Systemdatum der Arbeitsumgebung, identisch mit dem
  Commit-Datum des RIS-HEAD `2026-10-25`; MO-HEAD datiert `2026-10-23`).
- Run-Zähler: **01**. Begründung: im Checkout existiert keine Datei, die zu einem früheren
  `ris-dev2`-Lauf gehört (`docs/reports/` enthält keinen `*DEV2*`-Report, siehe §5).
  Ein früherer Lauf ist damit nicht belegt; der Zähler startet bei 01.
- Run-ID: **`2026-10-25-ris-dev2-01`**.

---

## 3. Git-Matrix beider Repositories

### 3.1 RIS

| Feld | Wert |
|---|---|
| Absoluter Pfad | `C:\Users\DCI-Student\projekte\Mays-Recruiting-Intelligence-System` |
| origin | `https://github.com/maynowak/Mays-Recruiting-Intelligence-System.git` |
| Branch | `feature/mo-module-installer-ris-dev2-2026` (neu angelegt, nicht gepusht) |
| Ausgangs-SHA (Basis) | `e8a2ed8a5bcb5c795200defb18e1d1e10c1277df` |
| Commit-Betreff | `RIS-COGNITO-JOBSEARCH-CONFIRMATION-EMAIL-AUDIT-01: confirmation email audit` |
| `git status --short` | leer (0 Einträge) vor und nach Branch-Erstellung |
| Lokale Branches | `main`, `feature/mos-integrationstest` (Vorbereitung, gleicher SHA), `feature/mo-module-installer-ris-dev2-2026` |
| Remote-Branches | `origin/main`, `origin/feature/integration` |

Der vorgegebene Branch war **nicht vorhanden** und wurde gemäß Auftrag aus dem sauberen
Ausgangsstand (`e8a2ed8a…`, Working Tree clean) erstellt. Es wurden keine Änderungen
überschrieben, gestasht oder zurückgesetzt.

### 3.2 MO

| Feld | Wert |
|---|---|
| Absoluter Pfad | `C:\Users\DCI-Student\projekte\mays-order-aws` |
| origin | `https://github.com/maynowak/mays-order-aws.git` |
| Branch | `main` (kein detached HEAD) |
| HEAD | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` |
| Commit-Betreff | `docs: module builder invocation discoverability MAYS-ORDERS-MODULE-DOC-INTEGRATION-01` |
| `git status --short` | leer (0 Einträge); nur lesend verwendet |
| Remote-Branches | `main` + 9 Feature-Branches (`feature/cognito`, `feature/dynamodb-seed`, `feature/http-api`, `feature/lambda-python-314`, `feature/lambda-python-cleanup`, `feature/lambda-runtime-doc-cleanup`, `feature/presentation-qa`, `feature/t011-07-plan-review`, `feature/integration`) |

### 3.3 Abgleich mit den bisherigen Referenzen

| Referenz | Erwartet | Tatsächlich | Urteil |
|---|---|---|---|
| RIS-Quellbaseline | `e8a2ed8a5bcb5c795200defb18e1d1e10c1277df` | identisch | deckungsgleich |
| MO-Quellbaseline | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` | identisch | deckungsgleich |
| RIS-Doku-Commit `59f7f79` | vorhanden | `fatal: Not a valid object name` | **fehlt** |
| RIS-Doku-Commit `8280504` | vorhanden | `fatal: Not a valid object name` | **fehlt** |

Die beiden Doku-Commits sind im aktuellen Checkout nicht enthalten (auch nicht im
Reftog — dieser kennt nur `clone` und einen `checkout`). Sie wurden **nicht** rekonstruiert.

---

## 4. Toolchain-Matrix: Anforderung / Ist / Urteil

| Werkzeug | Anforderung (Quelle) | Ist (gemessen) | Urteil |
|---|---|---|---|
| Git | erforderlich für Clone/Fetch/Checkout des Builder-Checkouts (`installer/build_mays_orders_module.py:38-53`) | `git version 2.56.0.windows.3`, `C:\Program Files\Git\cmd\git.exe` | OK |
| Python | „Python 3.14 only" (`AGENTS.md`, Project identity); `requirements.txt` Kopf „Python 3.14 compatible" | `Python 3.15.0` (`C:\Python315\python.exe`); `py -0p` kennt **nur** 3.15 | **Abweichung** (kein 3.14 vorhanden) |
| Terraform | `required_version = ">= 1.6, < 2.0"` (`terraform/main.tf:2`); CI nennt abweichend `">= 1.16, < 2.0"` (`.github/workflows/ci-cd.yml:19`) | **nicht installiert** (kein `terraform` im PATH) | **BLOCKED** |
| AWS CLI | für STS-Preflight/Plan-Lesbarkeit ab S01 | `aws-cli/2.38.5` (`C:\Program Files\Amazon\AWSCLIV2\aws.exe`), Region konfiguriert `eu-central-1` | vorhanden; Identität **NOT VERIFIED** (S00 ohne AWS-Aufruf) |
| pytest | `pytest>=8.0.0` (`requirements.txt`) | nicht installiert (`No module named pytest`) | **BLOCKED** |
| moto | `moto[s3,dynamodb,sqs]>=5.0.0` (`requirements.txt`); RIS-Tests brauchen moto (`AGENTS.md`) | nicht installiert | **BLOCKED** |
| boto3 / botocore | `>=1.34.0` (`requirements.txt`) | nicht installiert | **BLOCKED** |
| pip | — | `pip 26.2.1` | OK |
| Build-Werkzeug MO | MO-Builder ist stdlib-only; `lambda/dist/lambda.zip` muss im MO-Checkout vorhanden sein (`module_builder/builder.py:836-845`) | `lambda/dist/lambda.zip` (11.815 B) und `lambda/dist/cognito_backup.zip` sind **getrackt** und im Checkout vorhanden | OK (statisch) |

Es wurden in S00 **keine** Installationen oder Upgrades vorgenommen und **keine**
Testsuite ausgeführt.

---

## 5. Zuordnung der Builder-, Modul-, Pin- und Consumer-Pfade

### 5.1 Builder-Checkout (Quelle des Moduls)

- Konstante: `MAYS_ORDERS_BUILDER_DIR = RIS_ROOT / "installer" / "projects" / "mays_order_builder"`
  (`installer/build_mays_orders_module.py:25`)
- Zustand im Checkout: **nicht vorhanden** (lazy angelegt); `installer/projects/` fehlt komplett.
- Ausschluss aus Git: `.gitignore:52` (`projects/`), `.gitignore:58` (`installer/projects/`)
- Quelle: `https://github.com/maynowak/mays-order-aws.git` (hart im Wrapper, Zeile 44)

### 5.2 Generierungsziel

- Konstante: `TARGET_MODULE_DIR = RIS_ROOT / "terraform" / "modules" / "mays_orders"`
  (`installer/build_mays_orders_module.py:26`)
- Zustand im Checkout: **nicht vorhanden**
- Ausschluss aus Git: `.gitignore:70` (`terraform/modules/mays_orders/`)
- Aufruf: `python -m module_builder build --preset orders-service --target <Ziel>
  --project-name <p> --validate [--force]`, `cwd = <Builder-Checkout>`
  (`build_module()`, Zeilen 55-112)

### 5.3 Quellversions-Bestimmung (entscheidend)

`ensure_repo()` (Zeilen 38-53) verhält sich wie folgt:

1. Fehlt der Builder-Checkout → `git clone <MO-URL>`
2. Vorhanden → `git fetch --quiet`
3. Danach **immer** `git checkout main`
4. Working-Tree-Prüfung: nur **Warnung** auf stderr, kein Abbruch, kein Reset

Damit gilt: **die Quellversion ist der jeweilige `main`-Stand von MO zum Build-Zeitpunkt.**
Es findet keine SHA-Prüfung, kein `reset --hard`, kein `clean` und keine Pin-Auswertung statt.
Der Build-Manifest-Eintrag `source.commit` (`module_builder/builder.py:989-995`) protokolliert
den *tatsächlich* verwendeten Commit nachträglich — er erzwingt ihn nicht.

### 5.4 Builder-Pin

| Frage | Befund |
|---|---|
| Existiert ein wirksamer Builder-Pin? | **Nein.** `installer/mays-orders-clone.pinned.json` wird vom Wrapper nicht gelesen. |
| Wo wird der Pin referenziert? | `PIN_FILE` ist in `installer/build_mays_orders_module.py:27` definiert, aber **nirgends verwendet** (tote Konstante). |
| Welche Pin-Datei gehört nur zum alten Orders-Installer? | `installer/mays-orders-clone.pinned.json` → `pinned_commit 5cf50a0a8e…` (v0.5.0-rc.2), `clone_path installer/projects/mays_orders`. Verwendet in `installer/ris.py:1185` (Composite-/Verify-Pfad), nicht im Module-Builder-Weg. |

**Doku-Drift:** Der Wrapper-Docstring (Zeilen 1-12) behauptet „Checks out mays-order-aws into
`installer/projects/mays_orders` (pinned commit)" — Code und `installer/README_MODULE_BUILDER.md`
sagen dagegen `mays_order_builder` auf `main`. Der Docstring ist insoweit überholt.

### 5.5 Generierte Dateien und Wrapper-Eingriffe

Der Wrapper verändert nach dem Build gezielt:

| Datei (im Zielmodul) | Eingriff | Quelle |
|---|---|---|
| `outputs.tf` | ergänzt `output "sqs_queue_name"` (vor `sqs_worker_lambda_arn`, sonst angehängt) | `build_module()`, Zeilen 75-96 |
| `modules/iam/main.tf` | `count = var.sqs_queue_arn != "" ? 1 : 0` → `count = var.sqs_enabled ? 1 : 0` (2 Varianten mit/ohne Doppel-Space) | `patch_iam_sqs_gate()`, Zeilen 114-140 |
| `modules/iam/variables.tf` | ergänzt `variable "sqs_enabled"` (bool, default `false`) | ebd., Zeilen 142-153 |
| `main.tf` (Modul-Root) | ergänzt `sqs_enabled = true` neben `sqs_queue_arn` | ebd., Zeilen 155-166 |

Zusätzlich patcht der Wrapper **RIS-Code**: in `terraform/main.tf` wird innerhalb des Blocks
`module "mays_orders"` die Zeile `project_name = var.project_name` durch
`project_name = "${var.project_name}-mays-orders"` ersetzt (Regex, `build_module()` Zeilen 99-112).

Fail-closed-Verhalten: Bleibt nach dem Patch eine `count`-Zeile mit `sqs_queue_arn` übrig,
bricht `patch_iam_sqs_gate()` mit `RuntimeError` ab.

Nachlauf (`post_run_checks()`, Zeilen 170-178): `terraform fmt -check -recursive`,
`terraform init -backend=false`, `terraform validate` — alle drei **erfordern Terraform**
(nicht installiert, siehe §4).

### 5.6 Consumer-Bindung in RIS

- `terraform/main.tf:172` → `module "mays_orders" { source = "./modules/mays_orders" … }`
- `terraform/main.tf:173` → `project_name = "${var.project_name}-mays-orders"`
- Weitergabe: `tags = var.tags`, `monitoring_enabled`, `log_retention_days` aus `lambda_config`
- Das Modulverzeichnis fehlt im Checkout → `terraform validate` ist **ohne vorherigen Build
  nicht lauffähig** (erwartbare, aber reihenfolgekritische Voraussetzung).

### 5.7 Übergabe RIS- und Orders-Projektname

| Ebene | Mechanik | Quelle |
|---|---|---|
| CLI → Terraform | `--project-name <p>` → `var.project_name` (Default `mays-ris`) | `terraform/variables.tf` |
| Workspace | `workspace = workspace_for_project(project_name)` — **verbatim**, nie `environment` | `installer/ris.py:1012-1014`, `AGENTS.md` |
| Orders-Komponente | `orders_project_name = f"{ris_project_name}-mays-orders"` (`ORDERS_COMPONENT_SUFFIX = "-mays-orders"`) | `installer/ris.py:128`, `:149` |
| Modul-Aufruf | `project_name = "${var.project_name}-mays-orders"` (identische Ableitung) | `terraform/main.tf:173` |
| Konkret für dev2 | `ris-dev2` → Workspace `ris-dev2`, Orders `ris-dev2-mays-orders` | abgeleitet, nicht AWS-verifiziert |

### 5.8 Erwartete Ausgabemenge des Presets (statisch)

Aus dem aktuellen MO-Quelltext deterministisch ableitbar
(`builder.py:854-1016`, `ORDERS_SERVICE_MODULES`, `MODULE_CATALOG`):

| Bestandteil | Anzahl |
|---|---|
| Moduldateien (`api` 3, `cognito` 3, `dynamodb` 3, `iam` 3, `lambda` 3, `sqs` 1, `sqs-worker` 3) | 19 |
| Root: `versions.tf`, `main.tf`, `variables.tf`, `outputs.tf` | 4 |
| `README.md` | 1 |
| `lambda/dist/lambda.zip`, `lambda/build_zip.py` | 2 |
| `lambda/src/*.py` | 7 |
| `module-builder.manifest.json` | 1 |
| **Summe** | **34** |

Die historisch berichtete Zahl **34 Dateien** ist damit aus dem heutigen Quelltext
strukturell reproduzierbar (ohne Build ausgeführt zu haben).

---

## 6. Evidence-Matrix

Klassifikation: **A** = durch vorhandene Evidence belegt, **B** = nur historisch berichtet,
**C** = im aktuellen Quelltext bestätigt, **D** = nicht überprüfbar.

| # | Behauptung | Herkunft | Klassifikation | Gültigkeitsgrenze |
|---|---|---|---|---|
| E1 | 87 Builder-Tests bestanden | Auftragskontext (kein Log im Checkout gefunden) | **B** (Lauf) + **C** (Anzahl) | `module_builder/tests/test_module_builder.py` enthält exakt 87 `def test_`-Methoden; ein Lauf-/Ergebnis-Log existiert in keinem der beiden Checkouts → „bestanden" **nicht** belegt |
| E2 | Generierung erzeugt 34 Dateien | `docs/reports/MAYS-ORDERS-MODULE-DOC-INTEGRATION-01.md:21,23` (MO-Repo) + statische Ableitung | **A** (für MO-Doku-Aussage) + **C** (Struktur) | Kein Build-Manifest im RIS-Checkout (`terraform/modules/mays_orders` fehlt); Aussage gilt für den Quellstand, nicht für einen Lauf am 2026-10-25 |
| E3 | `sqs_queue_name`-Output fehlt im Builder-Ergebnis | Auftragskontext; Quelltext | **C** | `module_builder/*.py` enthält **keinen** Treffer für `sqs_queue_name`; Vorkommen nur in MO-`terraform/main.tf:197` und `terraform/modules/sqs-worker/variables.tf:17`. Der Wrapper ergänzt den Output nachträglich (Zeilen 75-96) |
| E4 | Zwei ARN-abhängige `count`-Ausdrücke im IAM-Modul | Auftragskontext; Quelltext | **C** | `terraform/modules/iam/main.tf:83` und `:96` — beide `count = var.sqs_queue_arn != "" ? 1 : 0`; exakt die zwei Muster, die `patch_iam_sqs_gate()` ersetzt |
| E5 | Separates IAM-Patch-Experiment | `docs/reports/MAYS-RIS-OPTION-A-MONITORING-WIRING-2026-10-19.md:16-17` | **B** (historisch) — durch heutigen Code **überholt** | Der historische Ansatz gatete über `sqs_queue_name` (plan-bekannt); der heutige Wrapper gatet über den Bool `sqs_enabled`. Ein eigenständiges Experiment-Artefakt (Log/Manifest) ist im Checkout nicht vorhanden |
| E6 | Wrapper baut Modul und validiert Terraform (GREEN) | `docs/reports/02-01-WRAPPER-MAYS-ORDERS-MODULE-BUILDER-EXECUTION_LOG.md` | **B** | Report vom 2026-10-20, Branch `feature/integration`, HEAD `407b6ac`, Projekt `mays-ris-test`; bezieht sich auf einen anderen Branch/Projektnamen, nicht auf `ris-dev2` |
| E7 | `terraform init/validate` lief erfolgreich | ebd. | **D** für heute | In S00 kein Terraform vorhanden und kein Lauf durchgeführt |

**Abweichungen zum heutigen Quellstand (ausdrücklich):**

1. E5: historischer Patch (`sqs_queue_name`-Gate) ≠ aktueller Patch (`sqs_enabled`-Gate).
2. E6: historischer Lauf nutzte `installer/projects/mays_orders` / `mays-ris-test`;
   aktueller Wrapper nutzt `installer/projects/mays_order_builder` und erwartet einen
   RIS-Projektnamen (`ris-dev2`).
3. E1: 87 Tests existieren, aber es gibt **keine** Lauf-Evidenz im Checkout.

---

## 7. Bekannte und offene Kontextwerte

| Wert | Stand | Beleg |
|---|---|---|
| Projekt / Workspace | **bekannt (Auftrag):** `ris-dev2` | Auftrag; Workspace-Mechanik `installer/ris.py:1012-1014` |
| Orders-Projekt | **bekannt (abgeleitet):** `ris-dev2-mays-orders` | `installer/ris.py:128,149`; `terraform/main.tf:173` |
| Region | **bekannt:** `eu-central-1` | `terraform/variables.tf` (`aws_region` Default), `AGENTS.md` |
| Umgebung | **bekannt:** `dev` | `terraform/variables.tf` (`environment` Default) |
| Dev-Konto | **widersprüchlich/offen** | Repo dokumentiert Account `240571105849` (`AGENTS.md`); die lokal konfigurierte AWS-CLI-Identität dieser Umgebung zeigt ein **abweichendes** Konto `<ACCOUNT_ID>` mit IAM-User `<IAM-USER>` (Beobachtung außerhalb von S00, kein STS-Aufruf in S00) |
| AWS-Profil | **widersprüchlich/offen** | Dokumentiert: `AWS_PROFILE=mayaws` (`AGENTS.md`); lokal existiert nur Profil `[default]` in `~\.aws\config`, `AWS_PROFILE` ist nicht gesetzt |
| Backend-Bucket | **offen für `ris-dev2`** | Nur für `ris-dev` dokumentiert (`s3://mays-ris-tf-state-dev`, `AGENTS.md`); für `ris-dev2` kein Beleg. Wird **nicht** übernommen (Auftrag) |
| State-Key | **Schema bekannt, Wert offen** | Schema `env:/{project}/{environment}/terraform.tfstate` (`installer/ris.py:63-73`); für `ris-dev2` damit *ableitbar*, aber nicht belegt → offen |
| Lock-Mechanismus | **bekannt als Code-Default, Geltung offen** | Partial-Backend `dynamodb_table = "mays-ris-tf-lock"` (`terraform/main.tf:15-19`); Bucket/Region kommen per `-backend-config` (`installer/terraform_runner.py`) |
| `TF_DATA_DIR` | **offen** | In der Umgebung nicht gesetzt; Dokumentation nennt projektweise `/tmp/tfris-dev` bzw. `.ris-workdirs/...` — für `ris-dev2` nicht festgelegt |
| AWS-Identität | **NOT VERIFIED** | S00 ohne AWS-Aufrufe; STS-Preflight gehört zu einem späteren Schritt |

Es wurden keine Backendwerte erfunden und keine aus der permanenten `ris-dev`-Installation
übernommen. Es wurden keine Credentials, Tokens, State-Dateien oder Rohpläne gelesen oder
veröffentlicht.

---

## 8. Prüfmatrix

Format: `ID | Erwartung | Befehl/Quelle | tatsächliches Ergebnis | Evidence | Urteil`

### 8.1 Dokumente und Regelwerk

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| DOC-01 | RIS-`AGENTS.md` gelesen | `AGENTS.md` | vollständig gelesen (inkl. Orders-Integration, Pinning, Deployments) | Datei | PASS |
| DOC-02 | MO-`AGENTS.md` gelesen | `mays-order-aws/AGENTS.md` | vollständig gelesen | Datei | PASS |
| DOC-03 | `docs/installer/MO-RIS-DEV2-INTEGRATION-STEPPLAN-2026.md` | `Test-Path` | **fehlt** | Dateisystem | BLOCKED (fehlende Quelle) |
| DOC-04 | `docs/installer/MO-MODULE-INTEGRATION-ALPHA-2026.md` | `Test-Path` | **fehlt** | Dateisystem | BLOCKED (fehlende Quelle) |
| DOC-05 | `docs/reports/MO-MODULE-INSTALLER-RIS-DEV2-2026-EXECUTION_LOG.md` | `Test-Path` | **fehlt** | Dateisystem | BLOCKED (fehlende Quelle) |
| DOC-06 | `installer/README_MODULE_BUILDER.md` | `Test-Path` | vorhanden (3.221 B) | Datei | PASS |
| DOC-07 | `docs/AI_AUDITLOG.md` | `Test-Path` | vorhanden (401.627 B) | Datei | PASS |

### 8.2 Git

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| GIT-01 | RIS auf `feature/mo-module-installer-ris-dev2-2026` | `git branch --show-current` | `feature/mo-module-installer-ris-dev2-2026` | git | PASS |
| GIT-02 | RIS-Ausgangs-SHA dokumentiert | `git rev-parse HEAD` | `e8a2ed8a5bcb5c795200defb18e1d1e10c1277df` | git | PASS |
| GIT-03 | RIS Working Tree sauber | `git status --short` | 0 Einträge | git | PASS |
| GIT-04 | MO unverändert, nur gelesen | `git status --short`, `git branch --show-current` | `main`, 0 Einträge | git | PASS |
| GIT-05 | MO-SHA = Referenz | `git rev-parse HEAD` | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` | git | PASS |
| GIT-06 | Doku-Commits `59f7f79`, `8280504` vorhanden | `git cat-file -t` | beide `Not a valid object name` | git | BLOCKED (fehlende Quelle) |

### 8.3 Toolchain

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| TC-01 | Git verfügbar | `git --version` | `2.56.0.windows.3` | Shell | PASS |
| TC-02 | Python 3.14 | `python --version`, `py -0p` | `3.15.0` (einzige Version) | Shell | WARNUNG (Abweichung) |
| TC-03 | Terraform `>=1.6,<2.0` | `Get-Command terraform` | nicht installiert | Shell | **BLOCKED** |
| TC-04 | AWS CLI verfügbar | `aws --version` | `2.38.5` | Shell | PASS (Identität NOT VERIFIED) |
| TC-05 | pytest `>=8` | `python -m pytest --version` | nicht installiert | Shell | **BLOCKED** |
| TC-06 | moto/boto3 für RIS-Tests | `python -c "import moto"` u. a. | fehlen | Shell | **BLOCKED** |
| TC-07 | MO-Build-Voraussetzung `lambda/dist/lambda.zip` | `git ls-files lambda/dist/` | beide Zips getrackt, im Checkout vorhanden | git | PASS |

### 8.4 Pfadzuordnung (statisch)

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| PATH-01 | Builder-Checkout definiert | `build_mays_orders_module.py:25` | `installer/projects/mays_order_builder` | Code | PASS |
| PATH-02 | Builder-Checkout vorhanden | `Test-Path installer/projects` | fehlt (lazy, gitignored) | Dateisystem | PASS (erwartet) |
| PATH-03 | Zielmodul definiert | `:26` | `terraform/modules/mays_orders` | Code | PASS |
| PATH-04 | Zielmodul vorhanden | `Test-Path` | fehlt (generiert, `.gitignore:70`) | Dateisystem | PASS (erwartet) |
| PATH-05 | Quellversion bestimmt | `ensure_repo()` `:38-53` | `fetch` + `checkout main`, kein SHA-Check, dirty nur Warnung | Code | RISIKO |
| PATH-06 | Wirksamer Builder-Pin | `PIN_FILE` `:27` | definiert, **unbenutzt**; Pin-Datei gehört zum Composite-Pfad (`ris.py:1185`) | Code | FAIL (kein Pin) |
| PATH-07 | Consumer-Bindung | `terraform/main.tf:172-179` | `module "mays_orders"`, `project_name = "${var.project_name}-mays-orders"` | Code | PASS |
| PATH-08 | Projektnamen-Übergabe | `ris.py:128,149,1012-1014` | `ris-dev2` → Workspace `ris-dev2` → Orders `ris-dev2-mays-orders` | Code | PASS (abgeleitet) |
| PATH-09 | Erwartete Dateimenge 34 | statische Ableitung §5.8 | 34 | Code | PASS (statisch) |
| PATH-10 | Doku-Konsistenz Wrapper | Docstring `:1-12` vs. Code/README | Docstring nennt `installer/projects/mays_orders` + „pinned" | Code | WARNUNG (Drift) |

### 8.5 Evidence

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| EV-01 | 87 Tests existieren | `Select-String 'def test_'` | 87 | Code | PASS |
| EV-02 | 87 Tests bestanden | Logsuche in beiden Checkouts | kein Log gefunden | — | NICHT VERIFIZIERT |
| EV-03 | 34 Dateien | §5.8 | 34 (statisch) | Code + MO-Doku | PASS (statisch) |
| EV-04 | `sqs_queue_name` fehlt im Builder | `Select-String module_builder/*.py` | 0 Treffer | Code | PASS |
| EV-05 | Zwei ARN-`count` | `iam/main.tf` | 2 Treffer (Z. 83, 96) | Code | PASS |
| EV-06 | IAM-Patch-Experiment | `MAYS-RIS-OPTION-A-…-2026-10-19.md` | historisch dokumentiert, heute durch `sqs_enabled` ersetzt | Doku + Code | PASS (historisch eingeordnet) |

### 8.6 Kontext

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| CTX-01 | Projekt/Workspace `ris-dev2` | Auftrag | übernommen | Auftrag | PASS |
| CTX-02 | Orders-Projekt `ris-dev2-mays-orders` | Ableitung | deterministisch abgeleitet | Code | PASS |
| CTX-03 | Region `eu-central-1` | `terraform/variables.tf` | Default `eu-central-1` | Code | PASS |
| CTX-04 | Konto/Profil eindeutig | `~\.aws\config`, `AGENTS.md` | dokumentiert `240571105849`/`mayaws`; lokal nur `[default]` mit abweichendem Konto `<ACCOUNT_ID>` | Dateisystem | WIDERSPRUCH |
| CTX-05 | Backend-Bucket/Key/Lock für `ris-dev2` | Code + Doku | Schema bekannt, Werte offen | Code | OFFEN |
| CTX-06 | Kein AWS-Aufruf in S00 | — | keiner ausgeführt | Selbstauskunft | PASS |

---

## 9. Priorisierte Blocker

| # | Blocker | Auswirkung | Betroffener Schritt | Auflösung |
|---|---|---|---|---|
| B1 | **Terraform nicht installiert** | `terraform fmt/init/validate/plan` nicht möglich; Wrapper-Postrun und `--check` nicht lauffähig | S01 (Terraform-Checks), alle Plan-Schritte | Installation außerhalb S00 (separater Auftrag) |
| B2 | **pytest/moto/boto3 fehlen** | RIS-Testsuite (`python -m pytest tests/ -q`) nicht lauffähig | S01+ (Testnachweise) | `pip install -r requirements.txt` in isolierter Umgebung, separater Auftrag |
| B3 | **Python 3.14 fehlt (nur 3.15)** | Abweichung von „Python 3.14 only"; Lambda-Runtime-Nähe nicht gegeben | alle Python-Verifikationen | 3.14 bereitstellen oder Abweichung formal akzeptieren |
| B4 | **Kein wirksamer Builder-Pin** | Build ist nicht reproduzierbar; MO-`main` kann sich jederzeit ändern; Manifest-Commit ist nachträglich | S01-Vertragsmatrix und jeder Build | Pin-Entscheid (SHA oder bewusst „main") dokumentieren |
| B5 | **Vorgabedokumente fehlen** (Stepplan, ALPHA-Leitfaden, Execution-Log, 2 Doku-Commits) | Kein dokumentierter Soll-Verlauf; S01-Vertragsmatrix muss ohne Vorlage aufgesetzt werden | S01 | Dokumente bereitstellen oder S01-Vertrag neu schreiben |
| B6 | **Konto/Profil unklar** (dokumentiert `240571105849`/`mayaws`, lokal `[default]` mit `<ACCOUNT_ID>`) | Falscher-Ziel-Stack-Risiko bei späteren Plan/Apply | STS-Preflight (S01+) | Profil `mayaws` einrichten oder Zielliste bestätigen |
| B7 | **Backend-Werte für `ris-dev2` offen** (Bucket, Key, Lock, `TF_DATA_DIR`) | Kein `init` mit Backend möglich; State-Isolation unklar | S01+ | Explizite Werte festlegen (nicht aus `ris-dev` übernehmen) |
| B8 | `terraform/modules/mays_orders` fehlt | `terraform validate` schlägt ohne vorherigen Builder-Lauf fehl | jeder Terraform-Check | Reihenfolge erzwingen: Build → Validate |
| B9 | CI-Workflow inkonsistent (`on: plan:` kein gültiges Event; `terraform_version ">= 1.16, < 2.0"` vs. `required_version >= 1.6`) | CI liefert keine belastbare Validierung | nicht S00-relevant | separat bereinigen |

---

## 10. Gesamturteil und Abnahmegrenzen

**Gesamturteil: PASS für die Bestandsaufnahme — S01-Ausführung BLOCKED.**

Begründung:

- Beide Checkouts sind identisch zu den vorgegebenen Quell-Baselines und sauber.
- Der Auftrags-Branch existiert und ist aus dem dokumentierten Ausgangsstand erstellt.
- Builder-, Modul-, Pin- und Consumer-Pfade sind vollständig statisch zugeordnet;
  die erwartete Dateimenge (34) ist aus dem Code reproduzierbar.
- Die fünf gemeldeten Vorbefunde sind eingeordnet: drei im Quelltext bestätigt
  (E3, E4, Anzahl in E1/E2), zwei nur historisch berichtet (E1-Lauf, E5/E6).
- **Nicht** PASS-fähig für den nächsten Ausführungsschritt: Terraform und pytest/moto/boto3
  fehlen (B1, B2), Vorgabedokumente fehlen (B5), Konto/Profil und Backendwerte sind
  nicht eindeutig (B6, B7).

**Abnahmegrenzen (was dieses Dokument ausdrücklich NICHT belegt):**

1. Kein Builder-Lauf, kein Modulbuild, kein Terraform-Lauf, kein AWS-Aufruf.
2. Keine Aussage über die AWS-Identität, das Zielkonto oder die Existenz von `ris-dev2`.
3. Keine Aussage über die Lauffähigkeit der 87 Builder-Tests oder der RIS-Testsuite
   (Werkzeuge fehlen, Lauf nicht durchgeführt).
4. Keine Aussage über Plan-/Apply-Ergebnisse; alle Zahlen aus Vorgänger-Reports sind
   historisch und nicht auf `ris-dev2` übertragbar.
5. Kein Commit/Push der fehlenden Vorgabedokumente (nicht rekonstruiert).

---

## 11. Nächster Auftrag: S01-Vertragsmatrix

**S01-VERTRAGSMATRIX (statisch, ohne AWS):**

1. Soll-Vertrag des generierten Orders-Moduls vollständig erfassen:
   Inputs (`project_name`, `tags`, `monitoring_enabled`, `log_retention_days`,
   `external_cognito`) und alle Outputs inkl. `sqs_queue_name`-Patch und
   `sqs_worker_lambda_arn`.
2. Ist/Soll-Abgleich gegen die RIS-Consumer-Erwartungen in `terraform/main.tf:172-179`
   und `terraform/outputs.tf`.
3. IAM-Gate-Vertrag festhalten (`sqs_enabled` vs. `sqs_queue_arn`) inkl. Fail-closed-Regel
   aus `patch_iam_sqs_gate()`.
4. Namensvertrag dokumentieren: `ris-dev2` → Workspace `ris-dev2` → `ris-dev2-mays-orders`;
   Namenslängen gegen `docs/installer/AWS-NAME-LIMITS.md` prüfen.
5. Offene Kontextwerte (B6, B7) als Vorbedingungen für S02 listen; keine AWS-Calls in S01.
6. Ergebnis nach `docs/reports/MO-RIS-DEV2-S01-CONTRACT-MATRIX-2026.md` mit derselben
   Prüfmatrix-Struktur; AI_AUDITLOG ergänzen; nur eigene Doku committen.

**Voraussetzung für S01:** keine (rein statisch). **Voraussetzung für S02 (Build):**
B1 (Terraform), B3 (Python 3.14), B4 (Pin-Entscheid), B5 (Vorgabedokumente).

---

## 12. Checkpoint

| Prüfung | Ergebnis |
|---|---|
| `git diff --check` (vor Commit) | keine Whitespace-Fehler |
| Secret-Audit der Änderungen | nur Doku; keine Keys/Tokens/State; private Konto-/Profildetails durch `<ACCOUNT_ID>`/`<IAM-USER>` ersetzt |
| Geänderte Dateien | `docs/reports/MO-RIS-DEV2-S00-BASELINE-2026.md` (neu), `docs/AI_AUDITLOG.md` (ergänzt) |
| Commit | siehe `git log -1` auf `feature/mo-module-installer-ris-dev2-2026` |
| Push | Ergebnis siehe Chat-Abschluss (kein Force-Push) |
