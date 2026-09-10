terraform {
  required_version = ">= 1.6, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  backend "s3" {
    bucket         = "mays-ris-tf-state-${var.environment}"
    key            = "terraform.tfstate"
    region         = var.aws_region
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

  project_name = var.project_name
  environment  = var.environment
  tags         = var.tags
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

  project_name        = var.project_name
  environment         = var.environment
  iam_role_arn        = module.iam.lambda_role_arn
  lambda_config       = var.lambda_config
  dynamodb_table_name = module.dynamodb.work_items_table_name
  s3_bucket_arn       = aws_s3_bucket.data.arn
  sqs_queue_arn       = module.sqs.work_queue_arn
  api_arn             = module.api.api_id
  tags                = var.tags
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

resource "aws_cloudwatch_log_group" "lambda" {
  count             = var.monitoring_enabled ? 1 : 0
  name              = "/aws/lambda/${local.prefix}-agent"
  retention_in_days = var.lambda_config.log_retention_days

  tags = merge({ "Project" = var.project_name }, var.tags)
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

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "api_endpoint" {
  value = module.api.api_endpoint
}

output "sqs_queues" {
  value = module.sqs.queue_urls
}

output "dynamodb_tables" {
  value = {
    work_items = module.dynamodb.work_items_table_name
  }
}

output "lambda_functions" {
  value = {
    agent = module.lambda.function_name
  }
}