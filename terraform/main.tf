terraform {
  required_version = ">= 1.5.0"

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
  maker       = "mays-ris"
  prefix      = "${var.project_name}-${var.environment}"
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

module "api" {
  source = "./modules/api"

  project_name              = var.project_name
  environment               = var.environment
  cognito_user_pool_id      = module.cognito.user_pool_id
  cognito_user_pool_client  = module.cognito.user_pool_client_id
  tags                      = var.tags
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

  project_name     = var.project_name
  dynamodb_table_arn = module.dynamodb.table_arn
  s3_bucket_arn    = aws_s3_bucket.data.arn
  tags             = var.tags
}

module "lambda" {
  source = "./modules/lambda"

  project_name        = var.project_name
  environment         = var.environment
  iam_role_arn        = module.iam.role_arn
  lambda_config       = var.lambda_config
  tags                = var.tags
}

module "monitoring" {
  source = "./modules/monitoring"

  project_name      = var.project_name
  environment       = var.environment
  lambda_function_name = module.lambda.function_name
  api_id            = module.api.api_id
  api_stage_name    = module.api.api_stage_name
  sqs_queues        = module.sqs.queue_urls
  tags              = var.tags
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