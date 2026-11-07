terraform {
  required_version = ">= 1.6, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Partial S3 backend: static values only. Dynamic values (bucket, region)
  # MUST be supplied via `terraform init -backend-config=...` (see
  # installer/terraform_runner.py: BackendConfig). Input variables are NOT
  # allowed in backend configuration.
  backend "s3" {
    key            = "terraform.tfstate"
    encrypt        = true
    dynamodb_table = "mays-ris-tf-lock"
  }
}

locals {
  maker            = "mays-ris"
  prefix           = "${var.project_name}-${var.environment}"
  identity_managed = var.identity_mode == "managed"
  orders_managed   = var.orders_lifecycle == "managed"
  orders_enabled   = var.orders_lifecycle != "disabled"
  identity_issuer  = local.identity_managed ? "https://${module.cognito[0].user_pool_endpoint}" : var.external_cognito_issuer
  m2m_issuer       = local.identity_managed && !var.identity_m2m_enabled ? var.identity_m2m_fallback_issuer : local.identity_issuer
  m2m_client_id    = local.identity_managed && !var.identity_m2m_enabled ? var.identity_m2m_fallback_client_id : (local.identity_managed ? module.cognito[0].user_pool_m2m_client_id : var.external_cognito_m2m_client_id)
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        "Project"     = var.project_name
        "Maker"       = local.maker
        "Environment" = var.environment
      },
      var.tags
    )
  }
}

module "cognito" {
  count  = local.identity_managed ? 1 : 0
  source = "./modules/cognito"

  project_name               = var.project_name
  environment                = var.environment
  tags                       = var.tags
  email_verification_enabled = var.identity_email_verification_enabled
  email_subject              = var.identity_email_subject
  email_message              = var.identity_email_message
  sender_mode                = var.identity_sender_mode
  google_client_id           = var.identity_google_client_id
  google_client_secret       = var.identity_google_client_secret
  google_callback_urls       = var.identity_google_callback_urls
  google_logout_urls         = var.identity_google_logout_urls

  oauth_enabled                 = var.identity_oauth_enabled
  oauth_scopes                  = var.identity_oauth_scopes
  oauth_callback_urls           = var.identity_oauth_callback_urls
  oauth_logout_urls             = var.identity_oauth_logout_urls
  custom_domain_enabled         = var.identity_custom_domain_enabled
  custom_domain                 = var.identity_custom_domain
  custom_domain_certificate_arn = var.identity_custom_domain_certificate_arn
  m2m_enabled                   = var.identity_m2m_enabled
}

module "sqs" {
  source = "./modules/sqs"

  project_name = var.project_name
  environment  = var.environment
  queue_config = var.queue_config
  tags         = var.tags
}

module "dynamodb" {
  source = "./modules/dynamodb"

  project_name     = var.project_name
  environment      = var.environment
  table_config     = var.table_config
  r08_pitr_enabled = var.r08_pitr_enabled
  tags             = var.tags

  # B5: opt-in. Empty by default -> no foundation entitlement is provisioned.
  # Passed through so the dev workspace can supply the synthetic owner sub.
  foundation_entitlements = var.foundation_entitlements
}

module "iam" {
  source = "./modules/iam"

  project_name        = var.project_name
  dynamodb_table_arn  = module.dynamodb.work_items_table_arn
  dynamodb_table_name = module.dynamodb.work_items_table_name
  s3_bucket_arn       = aws_s3_bucket.data.arn
  tags                = var.tags
}

module "api" {
  source = "./modules/api"

  project_name                    = var.project_name
  environment                     = var.environment
  cognito_user_pool_id            = local.identity_managed ? module.cognito[0].user_pool_id : var.external_cognito_user_pool_id
  cognito_user_pool_client_id     = local.identity_managed ? module.cognito[0].user_pool_client_id : var.external_cognito_human_client_id
  cognito_user_pool_m2m_client_id = local.m2m_client_id
  cognito_user_pool_endpoint      = local.identity_managed ? module.cognito[0].user_pool_endpoint : replace(var.external_cognito_issuer, "https://", "")
  cognito_issuer                  = local.identity_issuer
  cognito_m2m_issuer              = local.m2m_issuer
  lambda_function_name            = "${local.prefix}-agent"
  lambda_invoke_arn               = module.lambda.invoke_arn
  cors_origins                    = var.api_cors_origins
  tags                            = var.tags
}

module "lambda" {
  source = "./modules/lambda"

  project_name         = var.project_name
  environment          = var.environment
  lambda_config        = var.lambda_config
  dynamodb_table_name  = module.dynamodb.work_items_table_name
  dynamodb_table_arn   = module.dynamodb.work_items_table_arn
  jobsearch_table_name = module.dynamodb.jobsearches_table_name
  jobsearch_table_arn  = module.dynamodb.jobsearches_table_arn
  # Partner profile persistence (R02/R03): manual search profile CRUD.
  partner_profiles_table_name     = module.dynamodb.partner_profiles_table_name
  partner_profiles_table_arn      = module.dynamodb.partner_profiles_table_arn
  privacy_receipts_table_name     = module.dynamodb.privacy_receipts_table_name
  privacy_receipts_table_arn      = module.dynamodb.privacy_receipts_table_arn
  erasure_operations_table_name   = module.dynamodb.erasure_operations_table_name
  erasure_operations_table_arn    = module.dynamodb.erasure_operations_table_arn
  s3_erasure_phases_table_name    = module.dynamodb.s3_erasure_phases_table_name
  s3_erasure_phases_table_arn     = module.dynamodb.s3_erasure_phases_table_arn
  upload_ticket_ledger_table_name = module.dynamodb.upload_ticket_ledger_table_name
  upload_ticket_ledger_table_arn  = module.dynamodb.upload_ticket_ledger_table_arn
  upload_cutover_table_name       = module.dynamodb.upload_cutover_table_name
  upload_cutover_table_arn        = module.dynamodb.upload_cutover_table_arn
  deletion_ledger_table_name      = module.dynamodb.deletion_ledger_table_name
  deletion_ledger_table_arn       = module.dynamodb.deletion_ledger_table_arn
  user_profile_table_name         = module.dynamodb.user_profile_table_name
  agent_catalog_table_name        = module.dynamodb.agent_catalog_table_name
  entitlements_table_name         = module.dynamodb.entitlements_table_name
  api_profiles_table_name         = module.dynamodb.api_profiles_table_name
  offers_table_name               = module.dynamodb.offers_table_name
  credentials_table_name          = module.dynamodb.credentials_table_name
  # Partner Application Registry: resolved on every authorized partner and
  # M2M execution. Without this env var the registry lookup returns None and
  # both routes fail closed with 403.
  partner_applications_table_name     = module.dynamodb.partner_applications_table_name
  applications_table_name             = module.dynamodb.applications_table_name
  user_profile_table_arn              = module.dynamodb.user_profile_table_arn
  agent_catalog_table_arn             = module.dynamodb.agent_catalog_table_arn
  entitlements_table_arn              = module.dynamodb.entitlements_table_arn
  api_profiles_table_arn              = module.dynamodb.api_profiles_table_arn
  offers_table_arn                    = module.dynamodb.offers_table_arn
  credentials_table_arn               = module.dynamodb.credentials_table_arn
  partner_applications_table_arn      = module.dynamodb.partner_applications_table_arn
  partner_applications_gsi_client_arn = module.dynamodb.partner_applications_gsi_client_arn
  applications_table_arn              = module.dynamodb.applications_table_arn
  consents_table_name                 = module.dynamodb.consents_table_name
  consents_table_arn                  = module.dynamodb.consents_table_arn
  applications_cursor_secret_arn      = var.applications_cursor_secret_arn
  partner_surface_enabled             = var.partner_surface_enabled
  application_consent_enforced        = var.application_consent_enforced
  consent_notice_state_enforced       = var.consent_notice_state_enforced
  consent_pilot_allowlist             = var.consent_pilot_allowlist
  applications_gsi_owner_arn          = module.dynamodb.applications_gsi_owner_arn
  s3_bucket_arn                       = aws_s3_bucket.data.arn
  documents_bucket_name               = module.documents.bucket_name
  documents_bucket_arn                = module.documents.bucket_arn
  sqs_queue_arn                       = module.sqs.work_queue_arn
  work_queue_url                      = module.sqs.work_queue_url
  tags                                = var.tags
}

# Gate 4 — eigene Order-Fassade (orders_reader) auf unserer API.
# Liest/schreibt die Mays-Orders-Tabelle (gleiches Konto, eigene Rolle).
# Fremdes Projekt wird nicht veraendert.
# GLUE-01: Composite-Installationen zeigen auf die projekt-eigene
# Orders-Instanz (var.orders_*), Standalone behaelt die Defaults.
module "orders_reader" {
  count  = local.orders_enabled ? 1 : 0
  source = "./modules/orders_reader"

  project_name      = var.project_name
  environment       = var.environment
  api_id            = module.api.api_id
  authorizer_id     = module.api.authorizer_id
  aws_region        = var.aws_region
  filename          = var.filename
  tags              = var.tags
  orders_table_name = local.orders_managed ? module.mays_orders[0].dynamodb_table_name : var.external_orders_table_name
  orders_table_arn  = local.orders_managed ? module.mays_orders[0].dynamodb_table_arn : var.external_orders_table_arn
  orders_queue_url  = local.orders_managed ? module.mays_orders[0].sqs_queue_url : var.external_orders_queue_url
  orders_queue_arn  = local.orders_managed ? module.mays_orders[0].sqs_queue_arn : var.external_orders_queue_arn
}


# Mays-Orders as Terraform-Module (Orders-Service)
module "mays_orders" {
  count              = local.orders_managed ? 1 : 0
  source             = "./modules/mays_orders"
  project_name       = "${var.project_name}-mays-orders"
  tags               = var.tags
  monitoring_enabled = var.monitoring_enabled
  log_retention_days = var.lambda_config.log_retention_days
  # external_cognito = null  # MANAGED (Default) oder EXTERNAL
}
# Observability-Foundation: CloudWatch (Runtime) + CloudTrail (Audit),
# strikt getrennt (s. Modul-Kommentare). Ersetzt die frueheren Inline-Alarme.
module "monitoring" {
  source = "./modules/monitoring"

  project_name                 = var.project_name
  tags                         = var.tags
  monitoring_enabled           = var.monitoring_enabled
  dashboard_enabled            = var.dashboard_enabled
  aws_region                   = var.aws_region
  alarm_period_seconds         = var.alarm_period_seconds
  alarm_evaluation_periods     = var.alarm_evaluation_periods
  api_5xx_threshold            = var.api_5xx_threshold
  api_4xx_threshold            = var.api_4xx_threshold
  lambda_error_threshold       = var.lambda_error_threshold
  lambda_duration_threshold_ms = var.lambda_duration_threshold_ms
  lambda_throttle_threshold    = var.lambda_throttle_threshold
  dynamodb_throttled_threshold = var.dynamodb_throttled_threshold
  api_id                       = module.api.api_id
  api_stage_name               = module.api.api_stage_name
  lambda_function_name         = module.lambda.function_name
  dynamodb_table_name          = module.dynamodb.work_items_table_name
  sqs_queue_name               = module.sqs.work_queue_name
  sqs_dlq_name                 = module.sqs.dlq_name
}

# Option A (MODULE-WIRING / Ressourcen-Count-Abgleich 2026-10-19): zweite
# Monitoring-Instanz fuer den Orders-Service. Die Foundation-Instanz oben
# bleibt am RIS-Kern; hier werden die Orders-Ressourcen (API, Handler-Lambda,
# Orders-Tabelle, Orders-Queue) ueberwacht. Eigener Dashboard-/Alarmprefix
# "${var.project_name}-mays-orders" (identisch zum Komponentennamen in
# module.mays_orders), damit keine Namenskollision entsteht.
# Orders hat keine DLQ -> sqs_dlq_name = "" (Modul gate't Alarm/Widget).
module "monitoring_orders" {
  source = "./modules/monitoring"

  project_name                 = "${var.project_name}-mays-orders"
  tags                         = var.tags
  monitoring_enabled           = var.monitoring_enabled
  dashboard_enabled            = var.dashboard_enabled
  aws_region                   = var.aws_region
  alarm_period_seconds         = var.alarm_period_seconds
  alarm_evaluation_periods     = var.alarm_evaluation_periods
  api_5xx_threshold            = var.api_5xx_threshold
  api_4xx_threshold            = var.api_4xx_threshold
  lambda_error_threshold       = var.lambda_error_threshold
  lambda_duration_threshold_ms = var.lambda_duration_threshold_ms
  lambda_throttle_threshold    = var.lambda_throttle_threshold
  dynamodb_throttled_threshold = var.dynamodb_throttled_threshold
  count                        = local.orders_managed ? 1 : 0
  api_id                       = local.orders_managed ? module.mays_orders[0].api_gateway_id : ""
  api_stage_name               = local.orders_managed ? module.mays_orders[0].api_gateway_stage_name : ""
  lambda_function_name         = local.orders_managed ? module.mays_orders[0].lambda_function_name : ""
  dynamodb_table_name          = local.orders_managed ? module.mays_orders[0].dynamodb_table_name : ""
  sqs_queue_name               = local.orders_managed ? module.mays_orders[0].sqs_queue_name : ""
  sqs_dlq_name                 = ""
}

module "cloudtrail" {
  source = "./modules/cloudtrail"

  project_name = var.project_name
  tags         = var.tags
}

# Gate 14 — privater Dokumenten-Storage (eigener Bucket, kein Eingriff in Data-Bucket).
module "documents" {
  source = "./modules/documents"

  project_name = var.project_name
  environment  = var.environment
  tags         = var.tags
}

resource "aws_s3_bucket" "data" {
  bucket = "${local.prefix}-data"

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# HINWEIS: Die frueheren Inline-Alarme (lambda_errors/api_5xx, *-dev-Namen)
# sind in module.monitoring aufgegangen (bessere Config + project_name-Namen
# wie Referenz). Alte -dev-Namen werden ersetzt, nicht dupliziert.

module "health_public" {
  source = "./modules/health_public"

  project_name = var.project_name
  environment  = var.environment
  tags         = var.tags
}

module "health_plane" {
  source = "./modules/health_plane"

  project_name       = var.project_name
  environment        = var.environment
  tags               = var.tags
  writer_role_arn    = module.iam.role_arn
  writer_zip_path    = var.health_writer_zip_path
  public_bucket_name = module.health_public.bucket_name
  public_bucket_arn  = module.health_public.bucket_arn
  publisher_zip_path = var.health_publisher_zip_path
  aws_region         = var.aws_region
  log_retention_days = var.lambda_config.log_retention_days
}

# ---------------------------------------------------------------------------
# Isolierter Partner-Gateway (Variante B): eigener Issuer, gleiche Lambda.
# Nur aktiv, wenn Issuer und Client explizit konfiguriert sind.
# ---------------------------------------------------------------------------
module "jobsearch_edge" {
  source = "./modules/partner_edge"
  count  = var.jobsearch_cognito_issuer != "" && var.jobsearch_cognito_client_id != "" ? 1 : 0

  project_name         = var.project_name
  environment          = var.environment
  lambda_function_name = module.lambda.function_name
  lambda_invoke_arn    = module.lambda.invoke_arn
  cognito_issuer       = var.jobsearch_cognito_issuer
  cognito_client_id    = var.jobsearch_cognito_client_id
  cors_origins         = var.jobsearch_edge_cors_origins
}

# ---------------------------------------------------------------------------
# Module address reconciliation (RIS-DEV-UPGRADE-S04-A).
#
# The ris-dev state predates the count gates on these four module calls, so the
# resources are stored under unindexed addresses while the configuration now
# instantiates them as index [0]. Without these declarations Terraform plans a
# destroy+create of the whole module (Cognito pool, orders stack, reader,
# monitoring) instead of continuing to manage the same AWS resources.
#
# These blocks change addresses only. They add no resource, no attribute and no
# permission; the target instance must exist in the applied state (count = 1).
# ---------------------------------------------------------------------------
moved {
  from = module.cognito
  to   = module.cognito[0]
}

moved {
  from = module.mays_orders
  to   = module.mays_orders[0]
}

moved {
  from = module.orders_reader
  to   = module.orders_reader[0]
}

moved {
  from = module.monitoring_orders
  to   = module.monitoring_orders[0]
}
