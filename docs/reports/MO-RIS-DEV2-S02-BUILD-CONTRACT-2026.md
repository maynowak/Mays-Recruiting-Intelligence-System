# MO-RIS-DEV2-S02-BUILD-CONTRACT-2026 — Reproduzierbarer Build-Vertrag und erste isolierte Modulgenerierung

**Datum (tatsächliche Ausführung):** 2026-10-25
**Run-ID:** `2026-10-25-ris-dev2-03`
**Status:** COMPLETE — Generierung lokal ausgeführt (Exit 0), keine Terraform-Ausführung, kein AWS-Aufruf
**Eingang:** `docs/reports/MO-RIS-DEV2-S01-CONTRACT-MATRIX-2026.md` (Commit `6afdfb2f48419799137600e2fe12b61e84188923`)

---

## 1. Ausgangslage

### 1.1 Repository-Stände (tatsächlich geprüft)

| Repo | Absoluter Pfad | Branch | Voller HEAD | Status |
|---|---|---|---|---|
| RIS | `C:\Users\DCI-Student\projekte\Mays-Recruiting-Intelligence-System` | `feature/mo-module-installer-ris-dev2-2026` | `6afdfb2f48419799137600e2fe12b61e84188923` | clean (0) |
| MO (nur lesend) | `C:\Users\DCI-Student\projekte\mays-order-aws` | `main` | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` | clean (0) |

- MO `origin` = `https://github.com/maynowak/mays-order-aws.git`
- Der geforderte MO-Testquellen-SHA stimmt **exakt** mit dem tatsächlichen HEAD überein.
- `git rev-parse --short HEAD` = `2d5cf2d`; `git rev-parse --disambiguate=2d5cf2d` liefert **genau ein**
  Objekt (`2d5cf2de…`) — der kurze SHA im Manifest ist damit eindeutig, ersetzt aber keine Pin-Prüfung.

### 1.2 Abweichungen gegenüber S01

| Punkt | S01 | S02 | Bewertung |
|---|---|---|---|
| RIS-HEAD | `b194b80…` | `6afdfb2…` | erwartet (S01-Doku-Commit) |
| MO-HEAD | `2d5cf2de…` | `2d5cf2de…` | unverändert (kein Update, kein Checkout, kein Fetch) |
| Builder-Ausführung | nicht ausgeführt | ausgeführt (lokal, isoliertes Ziel) | freigegeben durch diesen Auftrag |
| Terraform | nicht verfügbar | weiterhin nicht verfügbar | **kein** Generator-Blocker (§3.3) |

### 1.3 Toolchain (Ist)

| Werkzeug | Version / Ergebnis | Verwendung in S02 |
|---|---|---|
| Python | `3.15.0` (`C:\Python315\python.exe`, einzige Installation) | Generator ausgeführt |
| Git | `2.56.0.windows.3` | Quellprüfung, SHA-Verifikation |
| Module Builder | `0.1.0` (`python -m module_builder --version`) | Generator |
| Terraform | **nicht installiert** | nicht ausgeführt (bewusst) |
| AWS CLI | vorhanden, **nicht verwendet** | kein AWS-Aufruf |

---

## 2. Verbindlicher Build-Vertrag

| Feld | Wert |
|---|---|
| RIS-Projekt | `ris-dev2` |
| Orders-Komponentenprojekt | `ris-dev2-mays-orders` |
| Preset | `orders-service` |
| Quelle | MO `2d5cf2de08a05109452e88964a8b1a4d6940afcf` (voller SHA = maßgebliche Quellidentität) |
| Quelle ist RC? | **nein** — bekannte Vertragslücken (§8, §9), nicht freigegebener Stand |
| Wrapper | `installer/build_mays_orders_module.py` **nicht geändert, nicht ausgeführt** |
| Ziel | neues, leeres, absolutes Verzeichnis außerhalb aller Deployment-Workdirs |
| `--force` | **nicht verwendet** |
| `--validate` | **nicht verwendet** (Terraform gehört in einen späteren Schritt) |

**GAP-01 dokumentarisch aufgelöst (nur für diesen Nachweis):**
Beim direkten Builder-Aufruf erhält `--project-name` den **effektiven Orders-Komponentennamen**
`ris-dev2-mays-orders`. Die spätere RIS-Modulübergabe liefert denselben Namen
(`terraform/main.tf:174` → `"${var.project_name}-mays-orders"` mit `var.project_name = ris-dev2`).
Die doppelte Namensquelle (Wrapper-CLI vs. Terraform-Wert) bleibt als GAP-01 **bestehen**; sie ist
hier nur durch eine Vorgabe im Aufruf überbrückt, nicht behoben.

---

## 3. Quellenschutz und Prüfung vor der Generierung

### 3.1 Prüfungen (alle vor dem Build)

| ID | Erwartung | Befehl/Quelle | Tatsächliches Ergebnis | Evidence | Urteil |
|---|---|---|---|---|---|
| Q-01 | MO-HEAD == festgelegter SHA | `git rev-parse HEAD` | `2d5cf2de08a05109452e88964a8b1a4d6940afcf` | §1.1 | MATCH |
| Q-02 | MO-Arbeitsbaum sauber | `git status --short` | 0 Einträge | §1.1 | MATCH |
| Q-03 | MO-Branch `main`, kein detached HEAD | `git branch --show-current` | `main` | §1.1 | MATCH |
| Q-04 | Kein stiller Quell-Update | kein `fetch`/`pull`/`checkout`/`reset`/`clean` ausgeführt | nur lesende Befehle | §3.3 | MATCH |
| Q-05 | Builder unverändert nutzbar | `python -m module_builder --version` | `0.1.0` | §1.3 | MATCH |
| Q-06 | Keine Schreibspur im Quell-Repo | `PYTHONDONTWRITEBYTECODE=1`, `python -B` | `module_builder/**/__pycache__` nicht vorhanden, `git status` leer | §3.3 | MATCH |

### 3.2 Pflichtbestandteile der Quelle

| Bestandteil | Zustand |
|---|---|
| `terraform/{main,variables,outputs}.tf` | vorhanden |
| 7 Modulverzeichnisse (`api`, `cognito`, `dynamodb`, `iam`, `lambda`, `sqs`, `sqs-worker`) | vorhanden, 19 `.tf`-Dateien |
| `lambda/dist/lambda.zip` | vorhanden (11 815 Bytes) — **gitignored**, also kein Commit-Bestandteil |
| `lambda/build_zip.py` | vorhanden |
| `lambda/src/*.py` | 7 Dateien |

### 3.3 Python-Kompatibilität (getrennt beurteilt)

| Frage | Ergebnis | Beleg |
|---|---|---|
| Läuft der **Generator** unter Python 3.15? | **ja** | `python -B -m module_builder --version` / `presets` / `build` alle Exit 0 |
| Ist der Generator-Quelltext syntaktisch gültig? | **ja**, 8 Dateien, 0 Fehler | In-Memory-`compile()` über `module_builder/**/*.py`, ohne Schreibzugriff |
| Ist Python 3.14 für den **Generator** erforderlich? | nein — reine stdlib-Nutzung (`argparse`, `pathlib`, `json`, `shutil`, `re`, `datetime`, `subprocess`) | Code-Sicht |
| Ist Python 3.14 für die **Lambda-Zielruntime** erforderlich? | ja, als Zielruntime deklariert: `runtime = "python3.14"` | `terraform/main.tf:89` |

Damit ist fehlendes Python 3.14 **kein** Generator-Blocker; die Lambda-Zielruntime bleibt eine
separate Deployment-Voraussetzung (§10, NOT VERIFIED).

---

## 4. Isoliertes Build-Ziel

| Feld | Wert |
|---|---|
| Zielpfad (absolut) | `C:\Users\DCI-Student\AppData\Local\Temp\opencode\mo-ris-dev2-s02-2026-10-25\orders-module` |
| Zustand vor Build | Verzeichnis **existierte nicht**; kein Altbestand, keine Wiederverwendung |
| Lag außerhalb von RIS/MO? | ja (System-Temp, nicht versioniert) |
| Bestehendes `terraform/modules/mays_orders` verwendet? | **nein** |
| Deployment-/State-Verzeichnis verwendet? | **nein** |

Der Zielordner ist bewusst flüchtig; die prüfbaren Artefakte sind als Evidence versioniert
(`docs/reports/evidence/MO-RIS-DEV2-S02-2026/`), nicht der Modulbaum selbst.

---

## 5. Soll-Aufstellung (vor der Generierung aus dem Code abgeleitet)

Ableitung aus `module_builder/builder.py:846-1016` (Phase A/B) und `spec.py:84-103`:

| Gruppe | Soll | Herleitung |
|---|---|---|
| Modulumfang | 7 Komponenten | `ORDERS_SERVICE_MODULES` |
| Modul-`.tf` | 19 Dateien | je Modul `*.tf`: api 3, cognito 3, dynamodb 3, iam 3, lambda 3, sqs 1, sqs-worker 3 |
| Root | `main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `README.md` = 5 | `builder.py:920-971` |
| Lambda | `lambda/dist/lambda.zip`, `lambda/build_zip.py`, 7 × `lambda/src/*.py` = 9 | `builder.py:975-986` |
| Manifest | `module-builder.manifest.json` = 1 | `builder.py:1014-1016` (**nicht** in `files_written`) |
| **Soll gesamt auf Platte** | **34** | 19 + 5 + 9 + 1 |
| **Soll `files_written`** | **33** | Manifest zählt sich selbst nicht mit |

Damit ist der S01-Prüfwert „34 Dateien" **bestätigt und aufgeschlüsselt**; er war kein Ersatz für
diese Gegenüberstellung.

---

## 6. Generierung und Ist-Prüfung

### 6.1 Ausführung

| Feld | Wert |
|---|---|
| Arbeitsverzeichnis | `C:\Users\DCI-Student\projekte\mays-order-aws` |
| Befehl | `python -m module_builder build --preset orders-service --project-name ris-dev2-mays-orders --target "<Ziel>"` |
| Zusatzumgebung | `PYTHONDONTWRITEBYTECODE=1`, Interpreter `-B` |
| Exitcode | **0** |
| stdout (bereinigt) | `Build OK: <Ziel>` + Preset/Vertrag/Projekt + Nutzungshinweis |
| Dauer/Zeitstempel | `generated_at = 2026-10-25T17:17:51+00:00` (Manifest) |

Evidence: `evidence/MO-RIS-DEV2-S02-2026/build-command.txt`, `build-stdout.txt`.

### 6.2 Ist-Dateiliste (34 Dateien, 11 Verzeichnisse)

| Gruppe | Ist | Soll | Urteil |
|---|---|---|---|
| `modules/*/*.tf` | 19 | 19 | MATCH |
| Root-`.tf` + README | 5 (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `README.md`) | 5 | MATCH |
| Lambda-Artefakte/Quellen | 9 | 9 | MATCH |
| Manifest | 1 | 1 | MATCH |
| **Gesamt** | **34** | **34** | **MATCH** |

Es gibt **keine unerwarteten Dateien**; das Ziel war vor dem Build nicht vorhanden, ein Altbestand
ist damit ausgeschlossen. Keine `.terraform*`, keine `*.tfstate*`, kein `*.tfplan`, kein Backend.

### 6.3 Manifest (Provenienz)

| Feld | Wert |
|---|---|
| `builder_version` | `0.1.0` |
| `preset` | `orders-service` |
| `modules` | `api, cognito, dynamodb, iam, lambda, sqs, sqs_worker` |
| `project_name` | `ris-dev2-mays-orders` (entspricht dem Vertrag) |
| `source.repo` | `maynowak/mays-order-aws` |
| `source.commit` | `2d5cf2d` — **kurzer** SHA (7 Zeichen) |
| `files_written` | 33 Einträge (Windows-Separatoren `\`) |
| `artifacts_sha256["lambda/dist/lambda.zip"]` | `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` |
| Manifest-Datei SHA-256 | `70bb4137c110e59284c664f59e44c00f54555cf3ab46f9402a7d9f36d909bcbc` |

**Grenze des Manifest-Pins:** Das Manifest enthält nur den kurzen SHA und **keine** Verifikation
gegen einen erwarteten Wert. Die Verknüpfung zum vollständigen SHA erfolgt ausschließlich extern:
`git rev-parse --short HEAD` → `2d5cf2d` bei HEAD `2d5cf2de08a05109452e88964a8b1a4d6940afcf`
(eindeutig). Eine **vollständige Manifest-Pinprüfung wird hier nicht behauptet**; GAP-03 bleibt offen.

### 6.4 ZIP-Provenienz

| Prüfung | Ergebnis |
|---|---|
| SHA-256 des kopierten `lambda.zip` | `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` |
| ZIP-Mitglieder | 7, Inhalt jeweils **bytegleich** zu `HEAD:lambda/src/<name>` |
| Quell-ZIP getrackt? | nein (`lambda/dist/` ist gitignored) → Container ist lokales Artefakt |
| Byte-Reproduzierbarkeit des Containers | **NOT VERIFIED** (Zip-Eintragszeitstempel variieren je Datei; kein Rebuild durchgeführt) |
| Zeilenenden | ZIP-Mitglieder LF (= committeter Blob), `lambda/src` im Arbeitsbaum CRLF (`core.autocrlf=true`); Inhalt nach Normalisierung identisch |

Damit ist die **Inhalts**-Provenienz des ZIP zum Quell-SHA belegt, die **Container**-Reproduzierbarkeit nicht.

### 6.5 Vertragsprüfung am generierten Modul (statisch)

| ID | Erwartung | Quelle | Tatsächliches Ergebnis | Urteil |
|---|---|---|---|---|
| C-01 | Genau 5 Variablen | S01 §2.2 | `project_name`, `tags`, `monitoring_enabled`, `log_retention_days`, `external_cognito` | MATCH |
| C-02 | `project_name`-Default = Consumer-Name | `substitute_project_name` | `default = "ris-dev2-mays-orders"` | MATCH |
| C-03 | `external_cognito` fail-closed (`null` = MANAGED) | `EXTERNAL_COGNITO_VARIABLE` | `default = null` + Regex/`client_id != ""`-Validierung vorhanden | MATCH |
| C-04 | Genau 19 offizielle Outputs | S01 §3.1 | 19 Outputs, identische Namen | MATCH |
| C-05 | `sqs_queue_name` **nicht** als Output | GAP-02 | als Root-Output **nicht vorhanden** | MATCH (Lücke bleibt) |
| C-06 | Kein eigener Provider, kein Backend | Modulvertrag | nur `versions.tf` mit `terraform{}`/`required_providers` (aws `>= 6.0`, time `~> 0.11`); kein `provider "aws"`, kein `backend` | MATCH |
| C-07 | IAM-Gate weiter ARN-abhängig | GAP aus S01 §4.2 | `modules/iam/main.tf:83` und `:96` unverändert `var.sqs_queue_arn != "" ? 1 : 0`; **kein** `sqs_enabled` | MATCH (Lücke bleibt) |
| C-08 | `path.module`-Artefakte statt `path.root` | Builder-Transform | `main.tf:54`, `:105` → `${path.module}/lambda/dist/lambda.zip` | MATCH |
| C-09 | Tag-Parität über `local.default_tags` | Builder-Transform | alle 7 Modulblöcke nutzen `local.default_tags` | MATCH |
| C-10 | Cognito-`count` + API über `local.cognito_*` | EXTERNAL-Sicherheit | `main.tf:65` count; `:82-83` locals statt `module.cognito.*` | MATCH |
| C-11 | Root-Referenzen selbstkonsistent | statische Prüfung | benutzte `var.*` = deklarierte `var.*` (5); keine `module.<x>`-Referenz ohne Block; alle benutzten `local.*` definiert | MATCH |
| C-12 | Interne Queue-Namensableitung vorhanden | `main.tf:92,102` | `"${var.project_name}-orders-queue"` intern, an `sqs_worker` durchgereicht — als **Input**, nicht als Output | MATCH mit GAP-02 |

**Bekannte Lücken bleiben sichtbar (nicht gepatcht, nicht nach RIS installiert):**
`sqs_queue_name` fehlt als Output; beide ARN-abhängigen `count`-Ausdrücke bestehen weiter.

### 6.6 Nicht ausgeführt

- **kein** `terraform fmt` — der Builder führt es nur aus, wenn `terraform` im PATH liegt
  (`builder.py:1021-1025`). Die generierten Dateien sind daher im Transform-Zustand, nicht
  fmt-normalisiert. Formatkonformität: **NOT VERIFIED**.
- **kein** `terraform init/validate/plan`, **kein** AWS-Aufruf, **kein** Wrapper-Lauf,
  **keine** Installation des Moduls in RIS.

---

## 7. Negativprobe (Überschreibschutz)

| Feld | Wert |
|---|---|
| Befehl | identisch zum Build, **ohne** `--force`, gleiches Ziel |
| Exitcode | **1** |
| Meldung | `module-builder: FEHLER: Zielordner ist nicht leer: <Ziel>` / `Bestehende Inhalte werden ohne --force nicht überschrieben.` |
| Ablehnungsstelle | `builder.py:846-850` (Phase A, **vor** jedem Schreiben) |
| Dateianzahl vor/nach | 34 / 34 |
| SHA-256-Vergleich (34 Zeilen) | **identisch, 0 Unterschiede** |
| Quell-Repo danach | `git status --short` leer |

Evidence: `evidence/MO-RIS-DEV2-S02-2026/negative-probe.txt`.
Damit ist belegt: der Builder **verweigert** das Überschreiben belegter Ziele und verändert vorhandene
Inhalte im Fehlerfall nicht.

---

## 8. Bewertung (getrennte Urteile)

| Dimension | Urteil | Begründung |
|---|---|---|
| **Quellidentität** | **PASS** | MO-HEAD exakt `2d5cf2de…`, Branch `main`, Arbeitsbaum sauber, kein Update/Checkout; Quelle unverändert |
| **Generatorausführung** | **PASS** | Exit 0 unter Python 3.15.0, Builder 0.1.0, ohne Schreibspur im Quell-Repo |
| **Artefaktvollständigkeit** | **PASS** | 34/34 Dateien, 19 Modul-`.tf`, 5 Root, 9 Lambda, 1 Manifest — exakt die Soll-Liste |
| **Manifest-/ZIP-Provenienz** | **PASS mit Grenze** | Manifest nennt nur `2d5cf2d` (extern eindeutig zum vollen SHA aufgelöst, keine Pin-Prüfung); ZIP-Inhalte bytegleich zu den HEAD-Blobs, Container-Byte-Reproduzierbarkeit **NOT VERIFIED** |
| **Schutz vor unbeabsichtigtem Überschreiben** | **PASS** | Exit 1, klare Meldung, 34 Dateien und alle Hashes unverändert |
| **RIS-Vertragskompatibilität** | **FAIL** | GAP-02 (`sqs_queue_name` fehlt als Output), unveränderte ARN-`count`s (Patch nicht Teil des Builds), GAP-01 (Namensdoppelquelle), CONFLICT-02 (Token/Cognito) |

**NOT VERIFIED (unverändert offen):** Terraform-Planbarkeit/Validierbarkeit des generierten Moduls,
AWS-Identität/Zielkonto, JWT-Kompatibilität, RIS-E2E.

**Die S01-Authentifizierungsfrage bleibt ausdrücklich offen:** MANAGED-Cognito (Modul-Pool) und
RIS-`idToken` (RIS-Pool) werden **nicht** als kompatibel behandelt. Es wurde **kein** Token
eingetragen, keine Credential überbrückt und keine Cognito-Variante migriert.

---

## 9. Verbleibende Vertragslücken (Stand nach diesem Build)

| ID | Lücke | Beleg im generierten Stand | Zuständigkeit |
|---|---|---|---|
| GAP-02 | `sqs_queue_name` fehlt als Modul-Output (Wert intern vorhanden) | `outputs.tf` (19 Outputs, ohne `sqs_queue_name`); Wert existiert in `main.tf:102` | MO primär, RIS als Übergangspatch |
| GAP-06 | IAM-Gate am ARN, nicht plan-stabil; kein `sqs_enabled`; leerer ARN bei aktivem Gate ungeprüft | `modules/iam/main.tf:83,96` | MO (Semantik) / RIS (Patch) |
| GAP-01 | Projektname doppelt gesetzt (Wrapper-CLI vs. Terraform) | Aufruf-Vorgabe in §2; Wrapper unverändert | RIS |
| GAP-03 | Kein wirksamer Pin; Manifest nur kurzer SHA ohne Prüfung | Manifest `source.commit = 2d5cf2d` | RIS |
| GAP-05 | Keine Namensprüfung im Wrapper | Wrapper nicht ausgeführt/geändert | RIS |
| CONFLICT-02 | MANAGED-Cognito vs. RIS-`idToken` | `modules/api/main.tf:34-35` (Audience/Issuer = Modul-Pool) | RIS (Entscheidung), MO (EXTERNAL existiert) |
| — | Formatierung nicht fmt-normalisiert (kein Terraform lokal) | §6.6 | S03 |

---

## 10. Konkrete nächste Änderungsaufträge

### 10.1 Hersteller (MO) — kleinste Änderungen

| Prio | Auftrag | Bezug | Kleinste Änderung |
|---|---|---|---|
| 1 | Root-Output `sqs_queue_name` ergänzen | GAP-02 | `output "sqs_queue_name" { value = module.sqs.queue_name }` in `terraform/outputs.tf` + Builder-Test |
| 2 | IAM-Gate plan-stabil machen (bool-Gate, ARN als Scope) + Validierung „Gate an ⇒ ARN nicht leer" | GAP-06 | Gate-Ausdruck ersetzen, `validation` ergänzen |
| 3 | Optionaler Output Worker-`function_name` | S01 §3.3 | ein Output |
| 4 | Manifest: vollständigen SHA statt `--short` aufnehmen | GAP-03 (MO-Anteil) | `git rev-parse HEAD` statt `--short HEAD` |

### 10.2 Consumer (RIS)

| Prio | Auftrag | Bezug |
|---|---|---|
| 1 | Namensableitung zentralisieren (`ris-dev2` → `ris-dev2-mays-orders`) + bestehende Namensprüfung im Wrapper aufrufen | GAP-01, GAP-05 |
| 2 | Pin erzwingen (`checkout <sha>` + Manifest-Prüfung) — **„main + Manifest-Gate" ist für diesen Nachweis kein Ersatz** | GAP-03 |
| 3 | `ORDERS_BASE_URL` aus `api_gateway_endpoint` verdrahten | GAP-04 |
| 4 | Token-/Cognito-Entscheidung treffen (EXTERNAL vs. M2M vs. Pfad B als E2E-Ziel) | CONFLICT-02 |
| 5 | `var.orders_*`-Altvertrag bereinigen | GAP-07 |

### 10.3 Nächster Schritt S03

**S03-MODULE-VALIDATE (offline, ohne AWS):** `terraform fmt -check`, `terraform init -backend=false`,
`terraform validate` gegen den **hier erzeugten** Modulstand; Soll-Ist der Formatierung nachziehen.

Voraussetzung: Terraform `>= 1.6,<2.0` muss installiert werden (separater Auftrag; in S02 **nicht**
installiert). Ohne Terraform bleibt S03 auf eine statische Prüfung beschränkt.

---

## 11. Grenzen dieses Nachweises

1. Die Generierung lief lokal gegen Python 3.15; **keine** Aussage über die Lambda-Zielruntime 3.14.
2. `terraform fmt` wurde vom Builder übersprungen (kein Terraform) — Formatierung ungeprüft.
3. Keine Terraform-Validierung, kein Plan, kein Apply, kein State, kein AWS-Aufruf.
4. Der Modulbaum selbst wurde **nicht** versioniert (nur Manifest, Logs, Hashes als Evidence).
5. Die ZIP-Container-Byte-Reproduzierbarkeit wurde nicht gemessen (kein Rebuild im Quell-Repo, um
   den Quellstand nicht zu verändern).
6. Der Wrapper (`installer/build_mays_orders_module.py`) wurde nicht ausgeführt; seine Patches
   (`sqs_queue_name`, IAM-Gate) sind **nicht** Teil dieses Builds.

---

## 12. Checkpoint

| Prüfung | Ergebnis |
|---|---|
| Quell-SHAs dokumentiert | RIS `6afdfb2…`, MO `2d5cf2de…` (§1.1) |
| `git diff --check` | ohne Befund |
| Secret-Audit | keine Keys/Tokens/State; keine Kontonummern; keine ZIPs versioniert |
| Geänderte Dateien | Report + `docs/AI_AUDITLOG.md` + `docs/reports/evidence/MO-RIS-DEV2-S02-2026/*` (5 Dateien) |
| MO | unverändert (`git status` leer, HEAD unverändert) |
| Commit/Push | siehe Chat-Abschluss (kein Force-Push) |
