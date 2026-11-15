# MO-RIS-AWS-TERRAFORM-WIRING-01 — L07 Lambda Deployables & ESMs

**Datum:** 2026-11-13
**Typ:** Terraform-Code + statische Tests. **Kein Apply, kein Plan, kein Deployment.**
**Ergebnis:** Beide Lambda-Entrypoints sind vollständig verdrahtet — default-off.

## 1. Baseline

| Repo | Branch | HEAD vor |
|---|---|---|
| Orders | `feature/mo-agent-order-body-01` | `b919344` |
| RIS | `feature/ris-mo-addition-agent-e2e-01` | `8037db7` |

## 2. W00 — Bestandsaufnahme

| Element | Vorher | Verwendung |
|---|---|---|
| RIS `agent_transport` | Queue + DLQ + Policy | erweitert |
| Orders `agent_transport` | Queue + DLQ + Policy + Secret | erweitert |
| RIS Lambda-Modul | ein Agent-Handler | **nicht** angefasst |
| Orders Lambda-Modul | HTTP-Handler | **nicht** angefasst |
| Tabellen | `work_items`, `api_profiles`, `entitlements` (RIS), `orders` (Orders) | per Output referenziert, keine Duplikate |
| KMS | keiner | nicht eingeführt |

Es wurde **keine** bestehende Ressource dupliziert.

## 3. W01 — RIS Dispatch-Ingress

| Punkt | Umsetzung |
|---|---|
| Handler | `dispatch_ingress.handler` |
| Runtime | `python3.14` (Variable, Default) |
| ZIP | `${path.root}/lambda.zip` (Agent-Bundle, enthält `dispatch_ingress.py`) |
| Rolle | eigene Rolle `…-agent-dispatch-ingress` (nicht die Agent-Rolle) |
| Rechte | Logs (eigene Log-Group), `dynamodb:GetItem` auf Profiles, RW auf WorkItems, Read auf Entitlements, `Receive/Delete/GetQueueAttributes` auf der Dispatch-Queue |
| ESM | `batch_size 5`, `ReportBatchItemFailures`, DLQ über die Queue-Redrive-Policy |
| Env | `WORK_ITEMS_TABLE`, `API_PROFILES_TABLE`, `ENTITLEMENTS_TABLE`, `DISPATCH_QUEUE_ARN` |
| Keine neue Runtime | nutzt `process_record` im bestehenden Bundle |

## 4. W02 — Orders Result-Consumer

| Punkt | Umsetzung |
|---|---|
| Handler | `result_consumer.handler` |
| ZIP | `${path.root}/../lambda/dist/lambda.zip` (dasselbe Bundle) |
| Rolle | eigene Rolle `…-agent-result-consumer` |
| Tabelle | `dynamodb:GetItem` + `UpdateItem` auf der bestehenden Orders-Tabelle — **kein** PutItem/Delete |
| Secret | `secretsmanager:GetSecretValue` **nur** auf `aws_secretsmanager_secret.result_hmac.arn` |
| KMS | nur wenn `result_secret_kms_key_arn` gesetzt ist (`count = 0` sonst) |
| ESM | `batch_size 10`, `ReportBatchItemFailures` |
| Env | `ORDERS_TABLE`, `ORDER_RESULT_SECRET_ARN` |
| Öffentliche Route | **keine** (kein `aws_apigatewayv2_route` im Modul) |

## 5. W03 — Ressourceninventar (aus dem Code, nicht aus Annahmen)

**RIS-Modul — 8 Ressourcen:**
`aws_sqs_queue.dispatch`, `aws_sqs_queue.dispatch_dlq`,
`aws_sqs_queue_policy.dispatch`, `aws_cloudwatch_log_group.dispatch_ingress`,
`aws_iam_role.dispatch_ingress`, `aws_iam_role_policy.dispatch_ingress`,
`aws_lambda_function.dispatch_ingress`, `aws_lambda_event_source_mapping.dispatch`.

**Orders-Modul — 11 definiert, 10 aktiv:**
`aws_sqs_queue.results`, `aws_sqs_queue.results_dlq`,
`aws_sqs_queue_policy.results`, `aws_secretsmanager_secret.result_hmac`,
`aws_secretsmanager_secret_policy.result_hmac`,
`aws_cloudwatch_log_group.result_consumer`, `aws_iam_role.result_consumer`,
`aws_iam_role_policy.result_consumer`, `aws_lambda_function.result_consumer`,
`aws_lambda_event_source_mapping.results`,
`aws_iam_role_policy.result_consumer_kms` (count = 0 ohne KMS-Key).

**Mit `enable_agent_transport = true`: 18 Creates, 0 Updates, 0 Deletes.**
**Mit `false` (Default): 0 Änderungen.**

## 6. W04 — Validierung

| Prüfung | Ergebnis |
|---|---|
| `terraform fmt -check` RIS | 0 |
| `terraform validate` RIS | Success (nur Deprecation-Warnungen bestehender Module) |
| `terraform fmt -check` Orders | 0 |
| `terraform validate` Orders | Success |
| Statische Wiring-Tests RIS | **11 passed** |
| Statische Wiring-Tests Orders | **12 passed** |
| Orders Gesamtsuite | **217 OK** |
| Lambda-/Packaging-Tests (vorherige Runde) | Ingress 15, Bridge 5, Consumer 12 |

Kategorien sauber getrennt: **statisch validiert** und **mit lokalen Fakes
getestet**. Es wurde **kein** AWS-Plan erstellt und **nichts** live verifiziert.

## 7. W05 — Sicherheit

- Kein Secretwert in Code, State-Input, Log oder Test (nur ARN-Referenz).
- Queue-Policies nennen ausschließlich die übergebenen Rollen-ARNs; leere Liste
  ⇒ kein Producer.
- Keine `Resource: "*"` für DynamoDB/SQS (Test prüft es).
- Keine Cross-Account-Policy; Same-Account ist die Datei-Evidenz-Annahme.
- Keine RIS-Rechte auf Orders-DynamoDB und umgekehrt.
- Keine neue öffentliche Route.
- SSE-SQS, Retention 4 d, DLQ 14 d.

## 8. Risiken und offene Fragen

| # | Risiko | Wirkung |
|---|---|---|
| 1 | **Account `240571105849` live unbestätigt** | Wenn RIS/Orders getrennt liegen, sind Principal-Arns und ESM ungültig |
| 2 | Secret-Wert nicht gesetzt | Consumer fail-closed, keine Ergebnisse |
| 3 | Lambda-Concurrency ungesetzt | Standard-Konto-Limit; bei Burst Throttling |
| 4 | Rotationsfenster `{current, previous}` | erfordert koordiniertes Rollout |
| 5 | ZIP muss vor dem Plan gebaut sein | `filebase64sha256` schlägt sonst fehl (bestehender Contract) |
| 6 | Log-Retention 14 d fix | bewusst konservativ, kein Kostenrisiko |

## 9. STOP

Kein `terraform plan`, kein Apply, kein Deployment. Für den nächsten Schritt
braucht es ein freigegebenes Profil für `240571105849`, ein gebautes ZIP und den
Secret-Wert.

## 10. Commits

Siehe Abschlussmeldung (SHA je Repo).
