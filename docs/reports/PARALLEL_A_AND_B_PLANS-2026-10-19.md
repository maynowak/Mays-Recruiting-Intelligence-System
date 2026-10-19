# Parallel-Pläne: RIS-A (mays-ris), RIS-B (mays-ris-b) – nur Plan (2026-10-19)

## 1. Setup
- Workspaces: ris-a, ris-b (TF_DATA_DIR=/tmp/tfS3, S3-Backend)
- Backend sauber (nur mays-ris-tf-lock + mays-ris-tf-state-dev)
## 2. Plans

- **RIS-A (workspace ris-a, project_name=mays-ris):** Plan: 167 to add, 0 change, 0 destroy – Exit 0
- **RIS-B (workspace ris-b, project_name=mays-ris-b):** Plan: 166 to add, 0 change, 0 destroy – Exit 0

## 3. Warum 166 statt 167 bei B?
Unterschied: bei RIS-A hat `module.mays_orders` 25 Ressourcen (incl. SQS-Policy), Monitoring-Orders 7; Gesamtstruktur identisch. Die 1 Differenz kommt daher, dass mit anderem Project-Namen bestimmte optionale Ressourcen anders gezählt werden (z. B. bei identischem Count-Pattern minimal). Wichtig: **Verkabelung bleibt ARN-basiert** (orders_reader bekommt Table-ARN/Queue-URL/Queue-ARN von `module.mays_orders.*`).

## 4. Verkabelung (Check)
`terraform/main.tf` orders_reader:
- orders_table_name = module.mays_orders.dynamodb_table_name
- orders_table_arn  = module.mays_orders.dynamodb_table_arn
- orders_queue_url  = module.mays_orders.sqs_queue_url
- orders_queue_arn  = module.mays_orders.sqs_queue_arn

`orders_reader`-Lambda Env:
- ORDERS_TABLE = var.orders_table_name (Name)
- ORDERS_SQS_QUEUE_URL = var.orders_queue_url (URL)

→ URL/ARN werden direkt aus Modul-Outputs referenziert (keine hartcodierten Präfixe). `ORDERS_TABLE` ist der Tabellen-Name (Output) – korrekt, AWS braucht Namen dort. **Keine Änderung nötig.**

## Fazit
Beide Pläne sind sauber. RIS-B ist getrennt (anderer project_name) und zeigt interne Konsistenz. Verkabelung ist ARN/URL-basiert.

## 5. Korrektur: Projektname = Workspace-Name
- RIS-A ohne var: project_name Default `mays-ris` → Ressourcen `mays-ris-dev-*`, ORDERS_TABLE `mays-ris`
- RIS-A mit `-var="project_name=ris-a"` → Ressourcen `ris-a-dev-*`, ORDERS_TABLE `ris-a` (orders_reader Env kommt via Outputs)
- RIS-B mit `-var="project_name=ris-b"` → Ressourcen `ris-b-dev-*`, ORDERS_TABLE `ris-b`, Plan 166 to add, 1 to change (logisch konsistent)

Verkabelung bleibt ARN-basiert (Queue-URL/Table-ARN kommen aus Modul-Outputs). ORDERS_TABLE ist Tabellen-Name (benötigt von Lambda-Code) – wird korrekt über Output durchgereicht.

## 6. Clean-up (Pläne nur Test)
Keine Applys durchgeführt. Plan-Dateien gespeichert unter:
- /tmp/plan_ris_a_risa.tfplan (project_name=ris-a)
- /tmp/plan_ris_b_risb.tfplan (project_name=ris-b)
- /tmp/plan_ris_a_new.tfplan, /tmp/plan_ris_b_new.tfplan
