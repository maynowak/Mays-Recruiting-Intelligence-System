# Lambda Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "lambda_config" {
  description = "Lambda configuration"
  type = object({
    runtime            = string
    handler            = string
    timeout            = number
    memory_size        = number
    filename           = string
    log_retention_days = number
  })
}

variable "dynamodb_table_name" {
  description = "DynamoDB table name for work items"
  type        = string
}

variable "user_profile_table_name" {
  description = "DynamoDB table name for user profiles"
  type        = string
}

variable "agent_catalog_table_name" {
  description = "DynamoDB table name for agent catalog"
  type        = string
}

variable "entitlements_table_name" {
  description = "DynamoDB table name for entitlements"
  type        = string
}

variable "user_profile_table_arn" {
  description = "DynamoDB table ARN for user profiles"
  type        = string
}

variable "agent_catalog_table_arn" {
  description = "DynamoDB table ARN for agent catalog"
  type        = string
}

variable "entitlements_table_arn" {
  description = "DynamoDB table ARN for entitlements"
  type        = string
}

variable "work_queue_url" {
  description = "SQS work queue URL for agent execution"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN for data storage"
  type        = string
}

variable "sqs_queue_arn" {
  description = "SQS queue ARN for event source mapping"
  type        = string
}

variable "api_arn" {
  description = "API Gateway ARN for Lambda permission"
  type        = string
}

variable "log_level" {
  description = "Log level for Lambda"
  type        = string
  default     = "INFO"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}