# Parallel-Test: RIS-A (Workspace ris-a) – Install + Online-Tests (2026-10-19)

**Workspace:** ris-a (TF_DATA_DIR=/tmp/tfS3)
**Profil:** AWS_PROFILE=mayaws, Account 240571105849, eu-central-1
**Backend:** S3 s3://mays-ris-tf-state-dev/terraform.tfstate, key env:/ris-a/terraform.tfstate, Lock mays-ris-tf-lock
**Code-Wiring:** Option A (monitoring_orders) vorhanden, Module-Arbeitsweise direkt im terraform/-Ordner

## 1. Plan
- terraform plan -out: 167 to add, 0 change, 0 destroy, Exit 0
- State-Key: env:/ris-a/terraform.tfstate

## 2. Apply
- terraform apply: Resources 167 added, 0 changed, 0 destroyed, Exit 0

## 3. Idempotenz
- terraform plan -detailed-exitcode: Exit 0 (clean, kein Drift)

## 4. Live-Checks
- Lambdas (mays-ris*): 6 (dev-agent, orders-reader, health-writer, health-publisher, handler, sqs-worker) – alle python3.14
- APIs: mays-ris-dev-api (jns196cdka), mays-ris-api (xm65gkb859)
- DynamoDB: 11 Tabellen (incl. mays-ris + 10 dev-*), mays-ris-tf-lock separat
- SQS: 6 Queues (dev-work/cv/ats/match/dlq + mays-ris-orders-queue)
- Dashboards: mays-ris-overview, mays-ris-orders-overview
- Alarme: 13 (7 Kern + 6 Orders, DLQ-gated)
- orders_reader Env: ORDERS_TABLE=mays-ris, ORDERS_SQS_QUEUE_URL=mays-ris-orders-queue
- ESM: mays-ris-orders-queue→mays-ris-sqs-worker Enabled, Batch 5

## 5. Auth-Smoke
- mays-ris-dev-api /health → 401 (JWT)
- mays-ris-api /orders → 401 (JWT) – konform API-STANDARD

## 6. Pytest (schnelle Tests)
- tests/test_p20_health_contract.py → 12/12 passed
- tests/test_p17_credential_lifecycle.py → 25/25 passed

## Ergebnis
**GRÜN – RIS-A läuft vollständig parallel, sauber getrennt über Workspace ris-a.**
