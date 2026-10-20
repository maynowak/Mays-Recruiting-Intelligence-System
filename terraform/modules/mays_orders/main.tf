locals {
  maker       = "Maymilly Nowak"
  environment = "Development"

  # Tag-Parität zum Stamm-Deploy (WP3): Maker/Environment bleiben
  # auch ohne Provider-default_tags an jeder Orders-Ressource.
  default_tags = merge({ "Maker" = local.maker, "Environment" = local.environment }, var.tags)

  # Cognito-Bereitstellungsart (EXTERNAL-COGNITO-INTEGRATION-01):
  # MANAGED (external_cognito = null): eigener Pool (module.cognito count=1).
  # EXTERNAL (external_cognito gesetzt): vorhandener Pool; das Modul
  # erzeugt KEINE Cognito-Ressourcen (count=0, splat bleibt leer).
  # one() macht beide Zweige auswertungssicher (kein Index-Fehler).
  cognito_endpoint  = var.external_cognito == null ? one(module.cognito[*].user_pool_endpoint) : var.external_cognito.user_pool_endpoint
  cognito_client_id = var.external_cognito == null ? one(module.cognito[*].user_pool_client_id) : var.external_cognito.user_pool_client_id
}

# T011-02 — DynamoDB-Tabelle + GSI1
# Fachquelle: database/dynamodb-design.md, database/access-patterns.md, ADR-002, ADR-007
module "dynamodb" {
  source       = "./modules/dynamodb"
  project_name = var.project_name
  tags         = local.default_tags
}

# T011-03 — IAM: Lambda Execution Role (Least Privilege)
# Fachquelle: security/iam-design.md §2.1 (mit Code synchronisiert, MODULARIZATION-01-PHASE2)
# Bewusst NICHT erlaubt: dynamodb:Scan/BatchWriteItem/CreateTable, s3:*, iam:*.
# DeleteItem: Erasure-Funktion. SQS:SendMessage: OPTIONAL, count-gated nur mit Queue.
module "iam" {
  source             = "./modules/iam"
  project_name       = var.project_name
  tags               = local.default_tags
  dynamodb_table_arn = module.dynamodb.table_arn
  dynamodb_gsi1_arn  = module.dynamodb.gsi1_arn
  dynamodb_gsi2_arn  = module.dynamodb.gsi2_arn
  sqs_queue_arn      = module.sqs.queue_arn
}

# T011-04 — Lambda: Order Handler (Zip-Build, Python 3.14)
# Fachquelle: ADR-001 (Serverless), api/endpoints.md, database/access-patterns.md (AP1..AP4)
# Execution Role: module.iam.role_arn. Zip-Build reproduzierbar via lambda/ (python3 build_zip.py).
# Migration: nodejs22.x → python3.14 (feature/lambda-python-314). Handler "index.handler" gilt für Python (index.py am ZIP-Root).
# API-GW→Lambda Invoke-Permission folgt in T011-06 (HTTP API + Routen + Authorizer).
module "lambda" {
  source              = "./modules/lambda"
  project_name        = var.project_name
  tags                = local.default_tags
  iam_role_arn        = module.iam.role_arn
  dynamodb_table_name = module.dynamodb.table_name
  queue_url           = module.sqs.queue_url
  monitoring_enabled  = var.monitoring_enabled
  log_retention_days  = var.log_retention_days
  filename            = "${path.module}/lambda/dist/lambda.zip"
  runtime             = "python3.14"
}

# T011-05 — Cognito: User Pool + App Client + Gruppe `staff`
# Fachquelle: security/authentication-decision.md (ADR-003), F002, security/iam-design.md
# Scope T011-05: nur Pool, Client, Gruppe. API Gateway / JWT-Authorizer / Lambda
# Invoke-Permission folgen in T011-06 (HTTP API + Routen + Authorizer).
# Kein user_pool_domain: Login via USER_PASSWORD_AUTH (kein Hosted-UI/OAuth-Redirect nötig,
# siehe terraform/README.md — Domain nur "falls nötig").
module "cognito" {
  count        = var.external_cognito == null ? 1 : 0
  source       = "./modules/cognito"
  project_name = var.project_name
  tags         = local.default_tags
}

# T011-06 — API Gateway HTTP API + Routen + JWT Authorizer
# Fachquelle: ADR-004 (HTTP API V2), api/endpoints.md, api/api-documentation.md,
# security/authentication-decision.md (JWT-Flow §3), security/iam-design.md §3.
# Scope: HTTP API + Stage, Lambda-Integration (Payload v2), vier dokumentierte
# Routen, JWT-Authorizer (Cognito), Lambda-Invoke-Permission.
module "api" {
  source                      = "./modules/api"
  project_name                = var.project_name
  tags                        = local.default_tags
  lambda_invoke_arn           = module.lambda.invoke_arn
  lambda_function_name        = module.lambda.function_name
  cognito_user_pool_endpoint  = local.cognito_endpoint
  cognito_user_pool_client_id = local.cognito_client_id
}

# SQS Queue for async order processing
# This module will be imported to manage existing AWS resources
module "sqs" {
  source       = "./modules/sqs"
  project_name = var.project_name
  tags         = local.default_tags
  queue_name   = "${var.project_name}-orders-queue"
}

# SQS Worker Lambda - processes messages from SQS queue
# This module will be imported to manage existing AWS resources
module "sqs_worker" {
  source              = "./modules/sqs-worker"
  project_name        = var.project_name
  tags                = local.default_tags
  sqs_queue_arn       = module.sqs.queue_arn
  sqs_queue_name      = module.sqs.queue_name
  dynamodb_table_name = module.dynamodb.table_name
  dynamodb_table_arn  = module.dynamodb.table_arn
  filename            = "${path.module}/lambda/dist/lambda.zip"
  monitoring_enabled  = var.monitoring_enabled
  log_retention_days  = var.log_retention_days
}
