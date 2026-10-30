# Evidence — MO-RIS-DEV2-S04 (MO-GAP-02/06-FIX)

Run-ID: `2026-10-25-ris-dev2-05`
Datum: 2026-10-25
Zugehöriger Report: `docs/reports/MO-RIS-DEV2-S04-MO-CONTRACT-FIX-2026.md`

Alle Dateien sind Text-Evidence. Es wurden **keine** Binaries, ZIPs, Provider-Caches,
Terraform-Planfiles, State-Dateien oder Credentials abgelegt.

## Inhalt

| Datei | Inhalt | Aussagegrenze |
|---|---|---|
| `00-artifact-build.log` | Builder-Lauf (frisches, leeres Ziel, kein `--force`, kein RIS-Wrapper) inkl. Zielpfad und Exitcode | Exit 0 belegt nur die Generierung, nicht Planbarkeit |
| `01-mo-commit-meta.txt` | MO-Commit (voll/SHAs/Parent/Autor), Arbeitsbaum, `git show --stat` | — |
| `02-mo-commit-diff.patch` | Vollständiger Diff der 6 geänderten MO-Quelldateien | Text-Diff, keine Laufzeitwirkung |
| `03-tests-suite-comparison.txt` | Baseline `2d5cf2de` vs. S04 `9627eb2f`: Testzahlen + identische Fehlermenge | Nur Windows-Lauf; 12 Fehler sind plattformbedingt |
| `04-tests-targeted.log` | 9 gezielte Tests (neu/angepasst), Exit 0 | Testlogik, kein Plan/Apply |
| `05-tests-baseline-full.log` | Vollständiger Baseline-Lauf (87 Tests, 8 Failures + 4 Errors) | Nur Windows |
| `06-tests-s04-full.log` | Vollständiger S04-Lauf (90 Tests, gleiche 12 Fehler) | Nur Windows |
| `07-lambda-chain-output-check.log` | Ersatzprüfung für `test_valid_combination_lambda_chain` (Windows-Pfadlimit), Output-Menge inkl. `sqs_queue_name` | Ersetzt nur die plattformbedingt abbrechende Assertion |
| `08-artifact-inspection.txt` | 5 Inputs, 20 Outputs, Output-Block, IAM-Gate, Manifest, Dateiliste | Statische Inspektion des Textes |
| `09-artifact-filelist-sha256.txt` | 34 Dateien mit SHA-256 und Größe | Snapshot des Build-Stands |
| `10-terraform-fmt-check.log` | `fmt -check -recursive` auf dem Artefakt, Exit 3, unveränderte Hashes | Kein Auto-Format |
| `11-terraform-fmt-diff.txt` | Diff Builder-Output vs. formatierte **Kopie** (2 Dateien, 3 Zeilen) | Kopie, nicht das Artefakt |
| `12-terraform-init-validate.log` | `init -backend=false -input=false` + `validate -no-color` + `version -json` | Kein Backend, keine AWS-Aufrufe |
| `12b-terraform-lockfile-note.txt` | Hash der erzeugten Lockdatei; Lockdatei ist **kein** Builder-Output und wurde entfernt | Beweismittel, nicht versioniert |
| `13-iam-contract-matrix.json` | 5 Gate/ARN-Fälle mit Init-/Plan-Exitcode und Fehlertexten | Offline-Fixtures, keine echte Queue |
| `14-iam-contract-plans.log` | Vollständige Plan-Logs der 5 Fälle | Provider-Mock, kein AWS |
| `15-plan-json-analysis.json` | Maschinelle Auswertung der Plan-JSONs (Ressourcen, Policy-Inhalt, `after_unknown`) | Nur geplante Werte |
| `16-plan-fixtures.txt` | Fixture-`main.tf`/`.tfvars` der Offline-Plans | Dummy-Credentials, Skip-Flags |
| `17-consumer-validate.log` | Kindmodul-Einbindung + Referenz auf `module.orders.sqs_queue_name`, `validate` Exit 0 | Kein Plan |
| `18-consumer-fixture.tf.txt` | Konsumenten-Fixture (Textkopie) | — |
| `19-consumer-negative-control.log` | Negativkontrolle: nicht existierender Output → `Unsupported attribute`, Exit 1, „object with 20 attributes" | Belegt, dass der Positivtest nicht vakuum-grün ist |

## Reproduktion (Kurzform)

```text
python -B -m module_builder build --preset orders-service \
  --target <leeres Ziel> --project-name ris-dev2-mays-orders
terraform -chdir=<Ziel> fmt -check -recursive -no-color          # Exit 3 (3 Ausrichtungszeilen)
terraform -chdir=<Ziel> init -backend=false -input=false          # Exit 0
terraform -chdir=<Ziel> validate -no-color                        # Exit 0
```

Planfälle: `terraform -chdir=tools/... plan -var-file=case-x.tfvars` mit Dummy-Credentials und
`skip_credentials_validation`/`skip_requesting_account_id`/`skip_metadata_api_check`/
`skip_region_validation`; keine AWS-Datenquellen, keine Netzwerkaufrufe beabsichtigt.

## Nicht enthalten (bewusst)

- keine `*.tfplan`/`*.tfstate`/`.terraform`/Provider-Binaries,
- keine ZIPs (auch nicht `lambda.zip` aus dem Artefakt),
- keine echten Credentials, keine Account-ID-gebundenen Ressourcen,
- kein Apply-Ergebnis (Apply war nicht Teil des Auftrags).
