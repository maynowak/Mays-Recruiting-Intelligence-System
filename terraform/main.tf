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
  maker  = "mays-ris"
  prefix = "${var.project_name}-${var.environment}"
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

  project_name    = var.project_name
  environment     = var.environment
  table_config    = var.table_config
  tags            = var.tags
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

  project_name                = var.project_name
  environment                 = var.environment
  cognito_user_pool_id        = module.cognito.user_pool_id
  cognito_user_pool_client_id = module.cognito.user_pool_client_id
  cognito_user_pool_endpoint  = module.cognito.user_pool_endpoint
  lambda_function_name        = "${local.prefix}-agent"
  lambda_invoke_arn           = module.lambda.invoke_arn
  tags                        = var.tags
}

module "lambda" {
  source = "./modules/lambda"

  project_name               = var.project_name
  environment                = var.environment
  lambda_config              = var.lambda_config
  dynamodb_table_name        = module.dynamodb.work_items_table_name
  dynamodb_table_arn         = module.dynamodb.work_items_table_arn
  jobsearch_table_name       = module.dynamodb.jobsearches_table_name
  jobsearch_table_arn        = module.dynamodb.jobsearches_table_arn
  user_profile_table_name    = module.dynamodb.user_profile_table_name
  agent_catalog_table_name   = module.dynamodb.agent_catalog_table_name
  entitlements_table_name    = module.dynamodb.entitlements_table_name
  user_profile_table_arn     = module.dynamodb.user_profile_table_arn
  agent_catalog_table_arn  = module.dynamodb.agent_catalog_table_arn
  entitlements_table_arn   = module.dynamodb.entitlements_table_arn
  s3_bucket_arn              = aws_s3_bucket.data.arn
  sqs_queue_arn              = module.sqs.work_queue_arn
  work_queue_url             = module.sqs.work_queue_url
  tags                       = var.tags
}

# Gate 4 — eigene Order-Fassade (orders_reader) auf unserer API.
# Liest/schreibt die Mays-Orders-Tabelle (gleiches Konto, eigene Rolle).
# Fremdes Projekt wird nicht veraendert.
module "orders_reader" {
  source = "./modules/orders_reader"

  project_name  = var.project_name
  environment   = var.environment
  api_id        = module.api.api_id
  authorizer_id = module.api.authorizer_id
  aws_region    = var.aws_region
  filename      = "${path.root}/../lambda/dist/orders-reader.zip"
  tags          = var.tags
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

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count               = var.monitoring_enabled ? 1 : 0
  alarm_name          = "${local.prefix}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = var.alarm_period_seconds
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold
  alarm_description   = "Lambda function error rate exceeded threshold"

  dimensions = {
    FunctionName = "${local.prefix}-agent"
  }

  alarm_actions = []
  tags          = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  count               = var.monitoring_enabled ? 1 : 0
  alarm_name          = "${local.prefix}-api-5xx"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = var.alarm_evaluation_periods
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = var.alarm_period_seconds
  statistic           = "Sum"
  threshold           = var.api_5xx_threshold
  alarm_description   = "API Gateway 5xx errors exceeded threshold"

  dimensions = {
    ApiId = module.api.api_id
  }

  alarm_actions = []
  tags          = merge({ "Project" = var.project_name }, var.tags)
}
