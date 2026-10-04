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

variable "dynamodb_table_arn" {
  description = "DynamoDB table ARN for work items (paired with dynamodb_table_name, MO pattern: explicit name + ARN wiring)"
  type        = string
}

variable "jobsearch_table_name" {
  description = "DynamoDB table name for job searches (Gate 9)"
  type        = string
}

variable "jobsearch_table_arn" {
  description = "DynamoDB table ARN for job searches (Gate 9)"
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

variable "api_profiles_table_name" {
  description = "DynamoDB table name for API profiles (P10 domain)"
  type        = string
}

variable "offers_table_name" {
  description = "DynamoDB table name for offers (P11 domain)"
  type        = string
}

variable "credentials_table_name" {
  description = "DynamoDB table name for credential metadata (P09 domain)"
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

variable "api_profiles_table_arn" {
  description = "DynamoDB table ARN for API profiles (P10 domain)"
  type        = string
}

variable "offers_table_arn" {
  description = "DynamoDB table ARN for offers (P11 domain)"
  type        = string
}

variable "credentials_table_arn" {
  description = "DynamoDB table ARN for credential metadata (P09 domain)"
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

variable "documents_bucket_name" {
  description = "Documents bucket name (Gate 14, private CV/document storage)"
  type        = string
}

variable "documents_bucket_arn" {
  description = "Documents bucket ARN (Gate 14, Least Privilege scope)"
  type        = string
}

variable "sqs_queue_arn" {
  description = "SQS queue ARN for event source mapping"
  type        = string
}

variable "log_level" {
  description = "Log level for Lambda"
  type        = string
  default     = "INFO"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}