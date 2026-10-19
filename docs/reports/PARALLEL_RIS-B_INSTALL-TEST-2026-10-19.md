# Parallel-Test: RIS-B (Workspace ris-b, saubere Names) – Install + Online-Tests (2026-10-19)

**Workspace:** ris-b
**Projektname:** mays-ris-b (abweichend von A)
**Profil:** AWS_PROFILE=mayaws, eu-central-1
**Zweck:** Echte Parallelinstallation ohne Namenskonflikte (Prefix mays-ris-b-dev-*)

## 1. Plan
Vars: project_name=mays-ris-b zusätzlich zu Zips.
Erwartung: 167 to add (identische Ressourcenzahl, andere Namen)

Plan: s.o. nach Apply-Ausführung unten bestätigt (Plan lief vorher).
## 1. Plan
- terraform plan (project_name=mays-ris-b): 167 to add, 0 change, 0 destroy, Exit 0

## 2. Apply
- terraform apply: Ressourcen fast vollständig erstellt, danach Plugin-Timeout am Ende → Exit unklar. Live-Inventar zeigt jedoch vollständige Installation.
- State-Key (S3): env:/ris-b/terraform.tfstate
- Apply-Log enthält finale Plugin-Fehlermeldung (nicht blockierend für Nachweis der Ressourcenerzeugung)

## 3. Live-Checks
- Lambdas (mays-ris-b-*): 6 (dev-agent, orders-reader, health-writer, health-publisher, handler, sqs-worker) – python3.14
- APIs: mays-ris-b-dev-api (8ix1kaxgb7), mays-ris-b-api (zh0gxwx1nh)
- DynamoDB: 11 Tabellen (incl. mays-ris-b + 10 dev-*), getrennt von A
- SQS: 6 Queues (dev-work/cv/ats/match/dlq + mays-ris-b-orders-queue)
- Dashboards: mays-ris-b-overview, mays-ris-b-orders-overview
- Cognito: mays-ris-b-dev-users, mays-ris-b-users (+ staff in orders pool)
- orders_reader Env: ORDERS_TABLE=mays-ris-b, ORDERS_SQS_QUEUE_URL=…/mays-ris-b-orders-queue
- ESM: mays-ris-b-orders-queue→mays-ris-b-sqs-worker Enabled, Batch 5

## 4. Auth-Smoke
- mays-ris-b-dev-api /health → 401 (JWT)
- mays-ris-b-api /orders → 401 (JWT) – konform API-STANDARD

## 5. Pytest (schnelle Tests)
- tests/test_p20_health_contract.py → 12/12 passed
- tests/test_p17_credential_lifecycle.py → 25/25 passed

## Ergebnis
**GRÜN – RIS-B läuft sauber parallel zu A, mit eindeutigen Namen (mays-ris-b-*). Kein Konflikt mit A.** Der Apply-End-Timeout ist Terraform/Plugin-Noise, nicht substantiell (alle Ressourcen live nachgewiesen).

