# Testabdeckungs-Analyse: Warum 13 Checks zu wenig waren (2026-10-19)

**Anlass:** Der Parallel-Test lief anfangs mit nur 12–13 Prüfungen je Durchlauf.
Vorhalt: „das klingt immer noch nach zuwenig, scanne die Reports diesbezüglich."
**Methode:** Durchsicht der kanonischen Test-Reports auf dokumentierte, reproduzierbare
Prüfungen; Abgleich, ob der Test-Runner sie abbildet.

## 1. Scan-Ergebnis: wo stehen die „echten" Checks?

`docs/reports/` enthält **379 Dateien**. Die referenzfähigen Live-Testbatterien sind:

| Report | Umfang | Was dort geprüft wird |
|---|---|---|
| `MAYS-RIS-APPLY-OPTION-A-VOLLTEST-2026-10-19.md` | **34/34 Live-Prüfungen** | Idempotenz, Vollinventar, Verkabelung, Auth-Smoke, Monitoring, Backend/State |
| `MAYS-RIS-TRUE-Paralleltest-ISOmatte-01.md` | **13 Isolations-Gates + Regression** | WORKDIR/TF_DATA_DIR/BACKEND/WORKSPACE/STATE_OWNERSHIP/PLAN_SAFETY/DESTROY_SAFETY, 36/36 Installer-Tests, 1399 Regression, fmt, validate |
| `G2-AWS-DEPLOY-VERIFY-01.md` | 8/8 AWS-Live-Tests | Cognito-Guards, No-Forbidden-Resources, Observability |
| `MAYS-RIS-BEFUND-FIX-UND-DESTROY-2026-10-19.md` | 7 Befund-Fixes + 7 Destroy-Checks | Destroy-Vollständigkeit je Dienst |
| `AUDIT-MONITORING-01-CLOUDTRAIL-CLOUDWATCH.md` | Alarm-Naming, Thresholds, Kosten | Alarm↔Metrik-Konsistenz |
| `2026-10-19-CLEANUP-VERIFICATION.md` | 7 Aufräum-Prüfungen | Reste/Kostenstellen |

**Befund:** Der 13-Check-Runner bildete davon nur einen Bruchteil ab — genau die
Ownership-Zugehörigkeit, aber **nicht** das Vollinventar, die Vertrags-/Routen-Checks,
die Verkabelungs-Angaben aus Schritt 3, die Monitoring-Details (Retentions, Trail,
Gruppe `staff`) und **keiner** der Isolations-Gates.

## 2. Abdeckungsmatrix: dokumentierte Prüfung → Runner-ID

| Dokumentierte Prüfung (Quelle) | Vorher | Jetzt (Runner-ID) |
|---|---|---|
| Idempotenz `plan -detailed-exitcode` = 0 (VOLLTEST §1) | ✅ | S1.5 |
| — | ❌ | **S1.1** Workspace-Wahl gegen Ziel halten (neu, nach T-3-Fund) |
| — | ❌ | **S1.3** STATE_OWNERSHIP: kein Fremd-Präfix im State (neu) |
| — | ❌ | **S1.4** PLAN_SAFETY_GATE: Plan ohne Fremd-Namen (neu) |
| — | ❌ | **S1.6** Output == Live-Name, **S1.7** S3-State-Objekt (neu) |
| Tabellen 10 + Orders-Tabelle `== project_name`, ACTIVE (VOLLTEST §2) | ⚠️ nur „≥11" | **S2.2** (10 Kern + Tabelle präzise + Lock) |
| Lock-Tabelle vorhanden (VOLLTEST §2) | ✅ | S2.2 + S5.3 |
| Lambdas 6 (VOLLTEST §2) | ✅ | S2.1 |
| Runtimes python3.14 (VOLLTEST §2) | ✅ | S2.1 |
| HTTP-APIs 2 (VOLLTEST §2) | ✅ | S2.3 |
| SQS 6 Queues (VOLLTEST §2) | ✅ | S2.4 |
| — | ❌ | **S2.4** DLQ-Redrive-Policy vorhanden (neu) |
| S3 Buckets 5 (VOLLTEST §2) | ✅ | S2.5 |
| — | ❌ | **S2.5** Public-Access-Block gesetzt (neu) |
| Cognito 2 Pools (VOLLTEST §2) | ✅ | S2.6 |
| — | ❌ | **S2.6** Gruppe `staff` + AutoVerifiedAttributes=email (neu) |
| Dashboards 2, Alarme 13, alle OK, Orders-Präfix (VOLLTEST §5) | ⚠️ grob | **S2.7** präzise (13 = 7+6, ALARM-Zustand 0) |
| CloudTrail 1, multi-region (VOLLTEST §2) | ⚠️ grob | **S2.8** + HomeRegion=eu-central-1 (neu) |
| Log-Groups 8, Retention 14d/7d (VOLLTEST §2) | ⚠️ nur „≥6" | **S2.9** präzise: 6 verwaltete, Retention reader=7, agent=14, 0 ohne Retention |
| Orders-Routen Kern-API + eigene API, alle JWT (VOLLTEST §2/§4) | ❌ | **S3.1/S3.2** (neu) |
| 2 Authorizer jwt-human + jwt-m2m (VOLLTEST §4) | ⚠️ | **S3.3** |
| — | ❌ | **S3.3** keine Route mit AuthorizationType NONE (neu) |
| 401-Smoke health/platform/orders (VOLLTEST §4) | ✅ | S3.4 (erweitert um `/me`, Facade, eigene API) |
| Verkabelung Env/ESM/IAM-Least-Privilege (VOLLTEST §3) | ✅ | S4.1–S4.3 (IAM um `dynamodb:Query` erweitert) |
| — | ❌ | **S5.1** keine Alt-Präfix-Ressourcen (neu) |
| — | ❌ | **S5.2/S5.3** Parallel-Trennung + Schonung Fremder (neu) |
| Installer 36/36, Regression 1399, fmt, validate (TRUE-Parallel) | ❌ | **R1.1–R1.5** in `static`; FULL=1 für Gesamt-Suite |
| WORKDIR/TF_DATA_DIR/BACKEND/WORKSPACE-Isolation (TRUE-Parallel) | ❌ | teilweise **S1.1/S1.3/S1.4/S5.2**; die Installer-seitigen Gates sind Unit-Tests (R1.3) |

## 3. Neuer Umfang

| Suite | Prüfungen je Lauf |
|---|---|
| `ris-a` / `ris-b` (Vollserie je Installation) | **≈ 60** |
| `both` (Parallel-/Trennungsserie) | **≈ 20** |
| `destroy-check <p>` (vollständiger Abbau-Nachweis) | **16** |
| `static` (fmt/validate/Unit-Tests/Bundles) | **10** |
| Kompletter Zyklus A→B→Destroy→A→Destroy | **≈ 230** |

Jede Prüfung benennt weiterhin: **Ziel-Installation, Präfix, Erwartungswert, Ist-Wert**
(`PASS [S2.2] Kern-Tabellen ris-a-dev-* → 10`), plus fehlgeschlagene IDs im Ergebnis.

## 4. Fund des erweiterten Tests (erster Lauf, 2026-10-19)

Schon beim ersten Durchlauf des ausgebauten Runners, noch am **leeren** Konto:

**GELB — zwei Log-Groups überleben jeden `destroy` (beide Installationen):**

```
/aws/lambda/ris-a-dev-health-writer       /aws/lambda/ris-a-dev-health-publisher
/aws/lambda/ris-b-dev-health-writer       /aws/lambda/ris-b-dev-health-publisher
/aws/lambda/mays-ris-b-dev-health-writer  (Rest der falsch etikettierten Ausführung)
```

**Ursache:** `modules/health_plane/main.tf` deklariert `aws_lambda_function.health_writer`
und `.health_publisher` **ohne** `aws_cloudwatch_log_group`. Die Lambda-Dienste erzeugen
die Gruppe beim ersten Invoke automatisch; Terraform kennt sie nicht → `destroy` kann sie
nicht entfernen. Alle anderen Log-Groups (core-Modul, orders_reader, mays_orders) sind
verwaltet und werden sauber gelöscht.

**Bewertung:** Kein Sicherheits- oder Kostenrisiko (dauerhaft 0 Byte, keine Logs), aber
ein **Vollständigkeitsdefekt im Destroy-Pfad** — und der exakte Typ von Fund, den der
13-Check-Runner strukturell übersehen hat (er prüfte nur `Log-Groups ≥ 6`, nie `== 0`
nach dem Destroy).

**Optionaler Fix (Vorschlag, nicht ausgeführt):** In `modules/health_plane` je Lambda ein
`aws_cloudwatch_log_group` mit `retention_in_days` ergänzen. Effekt: +2 Ressourcen
(167 → 169), Destroy vollständig, Retention-kostenbewusst. Betrifft auch die
Bestandsinstallation `mays-ris` — daher Freigabe erforderlich.

## 5. Bekannter Baseline-Defekt (nicht durch diese Arbeit entstanden)

`tests/test_ris_installer.py`: **2 failed, 35 passed**
(`test_install_dry_run_performs_no_mutation`, `test_validate_skips_workspace_without_backend`).
Das sind Teile der in `AGENTS.md` dokumentierten 5 Baseline-Defekte. Der Runner meldet
sie jetzt **ehrlich** statt „36/36" zu behaupten wie ältere Reports.

## 6. Reproduktion

```bash
./scripts/parallel_tests.sh static                 # Regression, kein AWS-Zugriff
./scripts/parallel_tests.sh destroy-check ris-a    # Abbau-Nachweis (16 Checks)
./scripts/parallel_tests.sh ris-a                  # Vollserie, benötigt laufende Installation A
./scripts/parallel_tests.sh both                   # Parallel-Serie, benötigt A+B
FULL=1 ./scripts/parallel_tests.sh ris-a           # zusaetzlich komplette pytest-Suite
```

## 7. Live-Lauf der Vollserie (nach Fix, 2026-10-19)

**RIS-A neu installiert:** `169 added` (167 + 2 verwaltete Log-Groups), Exit 0.
**Vollserie `ris-a`: 63 bestanden, 0 fehlgeschlagen, 1 Warnung (Baseline).**

Der erste Lauf der Vollserie lieferte 6 Fehlschläge — davon **4 Assertion-Fehler im
Runner** und **2 echte Signale**, die genau den Zweck der Ausweitung belegen:

| ID | Symptom | Ursache | Bewertung |
|---|---|---|---|
| S1.2 | State = 185 statt 167 | `terraform state list` listet Data-Sources als `module.x.data.y`, Filter `^data\.` griff nicht | Runner-Fehler, korrigiert (169 erwartet) |
| S1.5 | Plan Exit 2 („3 to change") | `filename`-Pfad im Test (`…/lambda/dist/x.zip`) ≠ Apply-Pfad (`…/terraform/../lambda/dist/x.zip`) → Terraform sieht Pfadänderung | **echtes Signal**: identische Pfade nötig, sonst falscher Drift |
| S2.6 | `AutoVerifiedAttributes=None` | Prüfung am Orders-Pool (`ris-a-users`), `email` steht am RIS-Pool (`ris-a-dev-users`) | Runner-Fehler, korrigiert |
| S3.3 | Ist = `0\n0` | `length(...)` wird **pro Paginierungs-Seite** ausgegeben | Runner-Fehler, Zählung über Route-Keys |
| S4.3 | Pattern enthielt `"` | Maskierungsfehler | Runner-Fehler, korrigiert |
| S6.1 | Installer 2 failed | dokumentierte Baseline-Defekte (AGENTS.md Z.39) | **kein Regress** → WARN statt FAIL |

**Lehre:** Die Pfad-Schreibweise im `filename` erzeugt „Drift", obwohl keine Ressource
abweicht. Der Runner verwendet jetzt exakt die Apply-Pfade (`$TERRA/../lambda/dist/...`).
