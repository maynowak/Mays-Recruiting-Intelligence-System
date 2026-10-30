# P14-A — WRAPPER BUILD NACHWEIS

## Build-Ergebnis

**MO_SHA:** `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`
**WRAPPER_COMMAND:** `python -m installer.build_mays_orders_module --project-name ris-dev2`
**EXIT_CODE:** `0`
**MODULE_PATH:** `terraform/modules/mays_orders`

## Validierung

- 6 Inputs: `external_cognito`, `lambda_execution_boundary`, `log_retention_days`, `monitoring_enabled`, `project_name`, `tags`
- 20 Outputs: `api_gateway_authorizer_id`, `api_gateway_endpoint`, `api_gateway_id`, `api_gateway_stage_name`, `cognito_user_pool_arn`, `cognito_user_pool_client_id`, `cognito_user_pool_endpoint`, `cognito_user_pool_group_name`, `cognito_user_pool_id`, `dynamodb_table_arn`, `dynamodb_table_name`, `iam_handler_role_arn`, `iam_handler_role_name`, `lambda_function_arn`, `lambda_function_name`, `lambda_invoke_arn`, `sqs_queue_arn`, `sqs_queue_name`, `sqs_queue_url`, `sqs_worker_lambda_arn`
- `fmt -recursive`: OK
- `fmt -check`: OK
- `init -backend=false`: OK
- `validate`: OK
- `lambda.zip` SHA-256: `b1018a3bd03455ede329ffaa3c66ca8115c6077741c8aad5282ee5f5fbd00e2b` (Match gegen Manifest)
- F-01: `lambda_execution_boundary` mit `default = null` (MO-Vertrag korrigiert; Portabilität eines expliziten ARN bleibt separat zu prüfen)
- F-03: Keine ungeschützte SQS-Resource-Wildcard; Resource ist die konkrete Queue-ARN (MO-Vertrag korrigiert; keine automatische Produktionsfreigabe)

## Evidence-Pfade

- `build_output.txt` — Original-Terminal-Output des Wrapper-Builds
- `terraform/modules/mays_orders/` — Generiertes Modul
- `terraform/modules/mays_orders/module-builder.manifest.json` — Manifest mit SHA-256
- `terraform/modules/mays_orders/lambda/dist/lambda.zip` — Lambda-Artefakt

## Pin-Konfiguration

- `PINNED_COMMIT`: `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`
- `installer/mays-orders-builder.pinned.json`: `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`
- MO-Checkout-HEAD: `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`

## Git-Commit

- `d1b7594` — `feat: fix wrapper validation for 6 inputs and update builder pin`

## Status

**PASS** — Build erfolgreich, 6 Inputs, 20 Outputs, Terraform-Validierung bestanden; F-01/F-03 im MO-Vertrag korrigiert, Produktionsfreigabe separat.

Nach dem tatsächlichen Build und der Validierung: **STOPP**.
