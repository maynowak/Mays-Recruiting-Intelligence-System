# Erklärung: Namenskonflikte vs. Referenzen (ARN/Outputs)

**Frage:** „the connects that y made with names wont be working withouth arn directly because the elements not know now what is the right one. y remember? the ressourcen knodes"

## 1. Was wir getestet haben
- Workspace-Trennung (State getrennt) → kein State-Mix
- Identische Namen (project_name=mays-ris): Plan sieht nur eigenen State, kennt Live-Ressourcen nicht → Plan sagt „167 to add“ (falsch in Gegenwart von Live-Ressourcen)
- Bei Apply: AWS prüft Eindeutigkeit → CreateFunction/CreateTable/CreateQueue etc. schlagen mit `AlreadyExists/ResourceInUse` fehl (keine Cross-Terraform-Verkabelung, sondern reine Namenskollision auf AWS-Seite)

## 2. Verkabelung in unserem Code
Die meisten Referenzen sind **via Terraform Resource References** (ARNs/IDs), nicht über String-Literale:
- orders_reader Env: `ORDERS_TABLE = module.mays_orders.dynamodb_table_name` (Output) → zur Plan-Zeit bekannt (abhängig von Modul), beim Apply wird richtiger Name eingesetzt
- Queue URL: `ORDERS_SQS_QUEUE_URL = module.mays_orders.sqs_queue_url` (Output enthält ARN/URL, nicht hartcodierter Name)
- Lambda-Integrationen: API Gateway Integration nutzt `aws_lambda_function.*.arn` (Resource-Referenz)
- ESM: verweist auf `aws_sqs_queue.*.arn` (Resource-Reference)
- IAM Policies: `Resource = aws_dynamodb_table.*.arn`, `Resource = aws_sqs_queue.*.arn`

→ **String-Namen werden nur dort verwendet, wo AWS Namen erwartet (Naming)**; die logische Verkabelung läuft über ARNs/IDs/Outputs (Terraform managed).

## 3. Problem bei paralleler Installation mit identischen Namen
Problem nicht „Verkabelung geht kaputt“, sondern **Erstellungsversuch** scheitert:
1. Terraform will Resource X mit Name N anlegen (z. B. Lambda mays-ris-dev-agent)
2. AWS existiert bereits Resource X mit Name N (von Workspace A)
3. Create* → `ResourceConflictException/AlreadyExists`
4. Apply bricht, keine „falsche Verkabelung“ (es wird nichts falsch verdrahtet), sondern **keine zweite Ressource erstellt**

## 4. Workspace + gleicher Name = State-isoliert, aber AWS-Namespace geteilt
- State (S3): `env:/ris-a/*`, `env:/ris-b/*` – komplett getrennt (Terraform weiß nichts vom jeweils anderen)
- AWS Namespace (region/global): Namen müssen eindeutig sein → Kollision
- **Fazit:** Für echte Parallel-Installation brauchst du entweder unterschiedliche Namen (project_name) ODER anderen Account/Region.

## 5. Erkenntnis aus Experiment
Mit `project_name=mays-ris-b` (andere Namen) funktioniert parallele Installation sauber: beide Sets existieren parallel, keine Kollision, Verkabelung jeweils intern korrekt (ARN-based). Mit identischen Namen funktioniert Plan, Apply **nicht**.

**Kurz:** Die Verkabelung („connects“) ist ARN-basiert (richtig). Der Knackpunkt ist der **AWS-Namensraum (Naming)** – nicht die Referenzen.
