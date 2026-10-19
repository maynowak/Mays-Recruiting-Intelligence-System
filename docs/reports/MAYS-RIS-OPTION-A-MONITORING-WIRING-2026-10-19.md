# Schritt 1 – Option A: Orders ans RIS-Monitoring verkabeln (2026-10-19)

**Datum:** 2026-10-19
**Status:** COMPLETED (GREEN)
**Ausführungsumgebung:** direkt in `<RIS-Root>/terraform` (ohne Installer)
**Profil:** `AWS_PROFILE=mayaws` (nur für Plan-Lesbarkeit; Änderungen selbst sind rein lokal/konfigurativ)

## 1. Änderungen (Quellcode)

| Datei | Änderung |
|---|---|
| `terraform/main.tf` | neues `module "monitoring_orders"` (2. Monitoring-Instanz, Prefix `${var.project_name}-orders`), verdrahtet mit `module.mays_orders.*` |
| `terraform/modules/monitoring/main.tf` | DLQ-Widget + DLQ-Alarm **count-gated** auf `var.sqs_dlq_name != ""` (Widget via `concat`, Reihenfolge für Bestandsinstallationen erhalten) |
| `terraform/modules/monitoring/outputs.tf` | `alarm_dlq_messages_arn` ebenfalls auf `sqs_dlq_name != ""` gate't (sonst `Invalid index`) |
| `terraform/modules/mays_orders/outputs.tf` | neue Outputs `sqs_queue_name`, `sqs_worker_lambda_name` (CloudWatch-Dimensionen brauchen Namen, keine ARN) |
| `terraform/modules/mays_orders/main.tf` | übergibt `sqs_queue_name = module.sqs.queue_name` an das IAM-Modul |
| `terraform/modules/mays_orders/modules/iam/{variables,main}.tf` | SQS-Policy-Gate von `sqs_queue_arn` (unbekannt bis apply) auf **`sqs_queue_name` (plan-bekannt)** umgestellt – behebt `Invalid count argument` |

## 2. Fehler, die der Plan vor Apply noch zeigte (behoben)

1. `Invalid count argument` – `count` in `modules/iam` hing von der Queue-ARN ab,
   die erst nach apply bekannt ist. Gate jetzt über den Plan-bekannten Queue-Namen.
2. `Invalid index` – Output `alarm_dlq_messages_arn` indexierte `[0]`, obwohl der
   DLQ-Alarm ohne DLQ `count = 0` hat. Gate erweitert.

**Korrektur zu früheren Reports:** Die Plan-Läufe vor diesem Schritt endeten mit
Exit-Code 1 (diese zwei Fehler), obwohl die `Plan:`-Zeile gedruckt wurde. Die damals
angegebene Zahl 24 für `module.mays_orders` war dadurch um 1 zu niedrig.

## 3. Ergebnis

```
terraform fmt -check -recursive   → OK
terraform init -reconfigure       → OK
terraform validate                → Success (nur Deprecation-Warnings)
terraform plan -lock=false        → Plan: 167 to add, 0 to change, 0 to destroy  (Exit 0)
```

### Aufschlüsselung „to add" (167)
RIS-Kern 135 (unverändert, nur `mays_orders` +1: `aws_iam_role_policy.sqs`),
`module.mays_orders` **25** (24 + SQS-Policy), `module.monitoring_orders` **7**
(Dashboard + 6 Alarme, DLQ-Alarm korrekt abgeschaltet).

### Erwartung gegenüber vorher
159 (alt, mit Fehlern) → 167 = +7 Monitoring-Orders +1 Orders-IAM-SQS-Policy +0 sonst.

## 4. Variablen für Plan/Apply

```bash
-var="filename=$PWD/../lambda/dist/orders-reader.zip"
-var="health_writer_zip_path=$PWD/../lambda/dist/health-writer.zip"
-var="health_publisher_zip_path=$PWD/../lambda/dist/health-publisher.zip"
```

`project_name = mays-ris`, `environment = dev` (Defaults).
