# AWS Name Limits — Orders Component

Der Orders-Ordner leitet fast jeden AWS-Ressourcennamen von `project_name` ab.
AWS lehnt Namen ab, die servicenspezifische Maximalängen überschreiten. Terraform
meldet diese Überschreitung **erst im Plan** — eine Ressource nach der anderen und
erst **nach** der Backend-Initialisierung.

Der RIS-Installer prüft die Grenzen deshalb **fail-closed vor jedem AWS-Aufruf**
(`installer/ris.py`).

## Woher die Werte kommen

Alle Overheads wurden aus dem **gepinnten** Mays-Orders-AWS-Repository gelesen
(Commit `5cf50a0`), nicht geschätzt:

| Muster | Quelle |
|---|---|
| `<project>-cloudtrail-<account>` | `terraform/modules/cloudtrail/main.tf:20` |
| `<project>` (DynamoDB-Tabelle) | `terraform/modules/dynamodb/main.tf:12` |
| `<project>-users` / `-client` | `terraform/modules/cognito/main.tf:9,33` |
| `<project>-handler` | `terraform/modules/lambda/main.tf:8` |
| `<project>-sqs-worker` | `terraform/modules/sqs-worker/main.tf:2` |
| `<project>-handler-role` / `-policy` | `terraform/modules/iam/main.tf:67,74` |
| `<project>-sqs-worker-role` / `-policy` | `terraform/modules/sqs-worker/iam.tf:51,59` |
| `<project>-orders-queue` | `terraform/modules/sqs/main.tf:186` |
| `<project>-api` / `-jwt-authorizer` | `terraform/modules/api/main.tf:8,30` |
| `<project>-overview`, `-dynamodb-throttled` | `terraform/modules/monitoring/main.tf:81,181` |
| `mays-orders-cognito-backup-Development-<project>` | `terraform/modules/cognito_backup/main.tf:3` |

Bei Änderungen an einer dieser Stellen im gepinnten Orders-Repo muss
`ORDERS_AWS_NAME_RULES` in `installer/ris.py` nachgezogen werden.

## Bindende Grenzen

### Immer aktive Module

| Ressource | Muster | AWS-Limit | Overhead | Max. `project_name` |
|---|---|---|---|---|
| CloudTrail-S3-Bucket | `<project>-cloudtrail-<12-stelliges Konto>` | 63 | 24 | **39** |
| IAM-Rolle Handler | `<project>-handler-role` | 64 | 13 | 51 |
| IAM-Rolle SQS-Worker | `<project>-sqs-worker-role` | 64 | 15 | 49 |
| Lambda Handler | `<project>-handler` | 64 | 8 | 56 |
| Lambda SQS-Worker | `<project>-sqs-worker` | 64 | 11 | 53 |
| IAM-Policy Handler | `<project>-handler-policy` | 128 | 15 | 113 |
| IAM-Policy SQS-Worker | `<project>-sqs-worker-policy` | 128 | 17 | 111 |
| SQS-Queue | `<project>-orders-queue` | 80 | 13 | 67 |
| DynamoDB-Tabelle | `<project>` | 255 | 0 | 255 |
| Cognito User Pool | `<project>-users` | 128 | 6 | 122 |
| Cognito Client | `<project>-client` | 128 | 8 | 120 |
| CloudTrail Trail | `<project>-trail` | 128 | 6 | 122 |
| API Gateway API | `<project>-api` | 128 | 4 | 124 |
| API Gateway Authorizer | `<project>-jwt-authorizer` | 128 | 16 | 112 |
| CloudWatch-Alarm | `<project>-dynamodb-throttled` | 255 | 20 | 235 |
| CloudWatch-Dashboard | `<project>-overview` | 255 | 9 | 246 |

**Bindend ist der CloudTrail-S3-Bucket mit 39 Zeichen.** Das ist der Wert von
`ORDERS_PROJECT_NAME_MAX_LENGTH`; er wird per `min()` aus der Regeltabelle
berechnet, nicht doppelt festgeschrieben.

### Optionales Cognito-Backup-Modul

Nur aktiv bei `enable_cognito_backup = true` (Default in Orders: `true`).

| Ressource | Muster | AWS-Limit | Overhead | Max. `project_name` |
|---|---|---|---|---|
| Cognito-Backup-S3-Bucket | `mays-orders-cognito-backup-Development-<project>` | 63 | 40 | **23** |
| Scheduler-Rolle | `<project>-cognito-backup-scheduler-role` | 64 | 34 | 30 |
| Backup-Rolle | `<project>-cognito-backup-role` | 64 | 26 | 38 |
| Backup-Lambda | `<project>-cognito-backup-lambda` | 64 | 24 | 40 |
| Backup-Schedule | `<project>-cognito-backup-schedule` | 64 | 25 | 39 |

**Mit aktivem Backup sinkt die Grenze von 39 auf 23.**

Der `Development`-Abschnitt ist in `terraform/main.tf:210` **hartkodiert**
(`environment = "Development"`) und lässt sich nicht über die Environment-Variable
verkürzen. Der Bucket-Namen selbst wird in `modules/cognito_backup/main.tf:3`
zusätzlich kleingeschrieben (`lower(...)`).

## Warum Composite-Projekte das Backup-Modul abschalten

`mays-ris-composite-a-mays-orders` ist 32 Zeichen — passt unter 39, aber nicht
unter 23. Mit aktivem Backup produziert der Plan:

```
Error: expected length of bucket to be in the range (0 - 63), got
mays-orders-cognito-backup-development-mays-ris-composite-a-mays-orders
```

Daher setzt der RIS-Installer für Composite-Installationen
`enable_cognito_backup=false` — über die in Orders **bereits vorhandene**
Variable, deren eigene Beschreibung lautet:

> `false deaktiviert das Backup-Modul (z. B. isolierte Testprojekte)`

Der Wert wird in `installer/ris.py` als Konstante `ORDERS_ENABLE_COGNITO_BACKUP`
geführt und **beim Plan mitgegeben** — nicht nur lokal gesetzt. Ein reiner
CLI-Pin überlebt den nächsten Lauf ohne Flag nicht (vgl.
`G3-COGNITO-CONFIG-PERSISTENCE-01` in `AI_AUDITLOG.md`).

An Mays-Orders-AWS-Quellcode wird dafür **nichts** geändert.

## Verhalten des Guards

Der Installer bricht **vor** jedem AWS-Aufruf ab und nennt **alle** Verletzungen,
nicht nur die erste:

```
$ python3 -m installer.ris --project-name <zu-lang> ... install
error: orders component project name 'too-long-name-mays-orders' (40 chars)
exceeds the AWS name limit of 23 chars for enable_cognito_backup=true:
  - cognito_backup_s3_bucket: mays-orders-cognito-backup-Development-too-long-name-mays-orders
    is 80 chars, AWS limit 63 (max project_name 23, got 40)
  - cognito_backup_scheduler_role: ... is 74 chars, AWS limit 64
    (max project_name 30, got 40)
```

Warum alle? Wer nur die erste Meldung repariert, läuft direkt in die nächste.

## init() führt keine Workspace-Operation aus — und braucht es nicht

Früher stand im `TerraformRunner.init()` eine Workspace-Auswahl **vor** der
Backend-Initialisierung. Das war **ein Vertragsbruch**: die Modul-Doku und zwei
Tests (`test_init_has_no_workspace_operations`,
`test_init_backend_config_has_no_workspace_operations`) pinnen ausdrücklich, dass
`init()` ausschließlich `terraform init` ausführt.

Die Änderung ist zurückgenommen. Grund: sie war nicht nötig.

`TERRAFORM_WORKSPACE` wird von `_terraform_env()` **für jeden Terraform-Kindprozess**
gesetzt. Das CLI wertet die Variable selbst aus und benutzt den Workspace ohne
explizites `workspace select`. Empirisch belegt:

| Variante | Workspace im Plan | Ergebnis |
|---|---|---|
| `TERRAFORM_WORKSPACE` gesetzt | `mays-ris-composite-a-mays-orders` | korrekt, kein Eingriff |
| Variable nicht gesetzt | `mays-orders` | **9 adoptierte Ressourcen zur Löschung vorgemerkt** |

Ohne die Environment-Variable landet Terraform im Default-Workspace und greift
fremde Ressourcen an. Deshalb ist `TERRAFORM_WORKSPACE` in `installer/ris.py`
verpflichtend gesetzt — nicht die Reihenfolge von `init()`.

## Zeichen-Konventionen

Zusätzlich zur Länge prüft `orders_component_project_name()`:

- Muster `^[a-z0-9][a-z0-9-]*[a-z0-9]$` — keine Großbuchstaben, kein führender
  oder abschließender Bindestrich
- mindestens 3 Zeichen (DynamoDB-Tabellennamen)
- kein `mays-orders`-Namespace (schützt die eigenständige Orders-Installation)

Unterstriche sind verboten, weil S3-Bucket-Namen sie nicht erlauben.

## RIS' eigene Namen

RIS bildet ebenfalls Namen aus `{project_name}-{environment}-…` ab. Die
Overheads in `RIS_AWS_NAME_RULES` rechnen mit dem **längsten** gültigen
Environment-Wert (`test`/`prod` = 4 Zeichen), damit der Guard für jedes
Environment gilt.

| Ressource | Muster | AWS-Limit | Overhead | Max. `project_name` |
|---|---|---|---|---|
| CloudTrail-S3-Bucket | `<project>-cloudtrail-<12-stelliges Konto>` | 63 | 24 | **39** |
| IAM-Rolle Health-Publisher | `<project>-<env>-health-publisher` | 64 | 22 | 42 |
| Lambda Health-Publisher | `<project>-<env>-health-publisher` | 64 | 22 | 42 |
| Lambda Health-Writer | `<project>-<env>-health-writer` | 64 | 19 | 45 |
| S3-Bucket Health-Public | `<project>-<env>-health-public` | 63 | 19 | 44 |
| S3-Bucket Health-State | `<project>-<env>-health-state` | 63 | 18 | 45 |
| S3-Bucket Documents | `<project>-<env>-documents` | 63 | 15 | 48 |
| IAM-Rolle Lambda | `<project>-lambda-role` | 64 | 12 | 52 |

**Auch RIS ist bei 39 Zeichen begrenzt** — wiederum der CloudTrail-S3-Bucket.
Die Grenze wird in `RisInstallContext.__post_init__()` geprüft, also an der
einzigen Stelle, an der die Identität entsteht.

Nicht bindend, aber zur Vollständigkeit: die längsten RIS-Namen sind
`aws_iam_role_policy` (Overhead 40) und
`aws_iam_role_policy`-Varianten wie
`<project>-<env>-lambda-dynamodb-entitlements-admin`. IAM-Policy-Namen erlauben
128 Zeichen, greifen also nie.

## Zusammenfassung

| Ebene | `enable_cognito_backup` | Max. Länge | Binding Ressource |
|---|---|---|---|
| RIS-Projekt | — | **39** | CloudTrail-S3-Bucket |
| Orders-Komponente | `false` (Composite) | **39** | CloudTrail-S3-Bucket |
| Orders-Komponente | `true` (Order-Default) | **23** | Cognito-Backup-S3-Bucket |

Da der Orders-Komponentenname das Suffix `-mays-orders` (12 Zeichen) trägt,
bleibt für den RIS-Namensanteil: **39 − 12 = 27 Zeichen**.

## Tests

`tests/test_orders_aws_name_limits.py` — 42 Tests, darunter:

- Grenzwert 23 akzeptiert, 24 abgewiesen
- Grenzwert 39 akzeptiert, 40 abgewiesen
- `ORDERS_PROJECT_NAME_MAX_LENGTH` und `RIS_PROJECT_NAME_MAX_LENGTH` sind aus
  den Tabellen **abgeleitet**, nicht doppelt festgeschrieben
- alle Verletzungen werden gemeldet, nicht nur die erste
- Regression auf den real beobachteten 71-Zeichen-Bucket
- Regression auf den `{env}`-Platzhalter, der `str.format()` zum Absturz brachte
- Der neue Guard verdeckt die bestehende Environment-Validierung nicht