# Parallel-Test: RIS-B Konflikt-Experiment (Workspace ris-b, identische Namen) (2026-10-19)

**Workspace:** ris-b (TF_DATA_DIR=/tmp/tfS3)
**Status:** NICHT deployed (nur Plan) – Zweck: Klärung echter globaler Namenskonflikte
**Ziel:** Prüfen, ob zweite Installation mit exakt gleichen `project_name=mays-ris`/`environment=dev` (Namen mays-ris-dev-*) parallel laufen kann

## 1. Ausgangslage
- RIS-A läuft aktiv (Workspace ris-a), erzeugte 167 Ressourcen
- Parallel vorhanden: Lambdas 6, APIs 2, DynamoDB 11 (ohne tf-lock), SQS 6, 2 Dashboards, 2 Cognito Pools
- Alle verwenden Präfix `mays-ris-dev-*` (bzw. `mays-ris` für Orders-Table/API/Pool)

## 2. Plan ris-b (identische Var-Defaults)
- terraform plan: 167 to add, 0 change, 0 destroy
- Keine Ressourcenkollisionen im Plan – Terraform prüft gegen State (ris-b), nicht gegen Live-Änderungen an Namen
- Sicherheitsgrenze: AWS verlangt **globale Eindeutigkeit** für viele Namen (Lambda FunctionName global in Account/Region? Lambda FunctionName ist region-scoped; S3 Bucket global; API GW Domain optional; DynamoDB TableName region-scoped; SQS QueueName region-scoped; CloudWatch AlarmName region-scoped; Cognito Pool Name region-scoped)

## 3. Realer Konflikt (Live)
Klar erkennbar:
- **Lambda:** FunctionName `mays-ris-dev-agent` etc. existieren bereits → CreateFunction: `Function already exist: ...`
- **API Gateway V2 API Name** region-scoped, aber IDs einzigartig – teilweise Name-Konflikt aber AWS lässt oft gleiche Namen? API Name ist Bezeichnung, nicht global unique. IDs verschieden.
- **DynamoDB Table:** `mays-ris-dev-work-items` existiert → `ResourceInUseException` (TableName region-scoped, muss eindeutig)
- **SQS QueueName:** region-scoped, eindeutig → Konflikt
- **Cognito UserPool Name:** region-scoped → Konflikt
- **CloudWatch Dashboard/Alarm:** Namen region-scoped, Konflikt möglich
- **S3 Buckets:** **global** unique – unsere Buckets (dev-data, dev-documents, health-*, cloudtrail-*) existieren bereits → `BucketAlreadyExists`

## 4. Fazit Konflikt-Experiment
**JA, würde sofort bei Apply fehlschlagen.** Haupt-Konflikte:
- DynamoDB Tables (bereits ACTIVE)
- Lambdas (Function existiert)
- SQS Queues
- Cognito Pools
- S3 Buckets (global) – sehr schwerwiegend
- IAM Roles/Policies evtl. Namenskonflikt

Terraform ignoriert Live-Existenz, wenn nicht im eigenen Workspace-State. Erst `terraform apply` trifft Live und führt zu `ResourceInUseException` / `AlreadyExists`.

**Lösung:** Für saubere Parallel-Instanz **Projektname ändern** (z. B. `mays-ris-b`) → Präfixe `mays-ris-b-dev-*` sind sauber getrennt.

## Empfehlung
Destroy nicht nötig (nie angewandt). Stattdessen RIS-B mit `-var="project_name=mays-ris-b"` installieren.
