variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "mays-ris"
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
  default     = "dev"
  
  validation {
    condition     = var.environment in ["dev", "test", "prod"]
    error_message = "Environment must be dev, test, or prod."
  }
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

variable "queue_config" {
  description = "Queue configuration"
  type = object({
    visibility_timeout_seconds = number
    message_retention_seconds  = number
    dlq_max_receive_count        = number
  })
  default = {
    visibility_timeout_seconds = 300
    message_retention_seconds  = 1209600
    dlq_max_receive_count      = 3
  }
}

variable "table_config" {
  description = "DynamoDB table configuration"
  type = object({
    ttl_enabled    = bool
    ttl_attribute  = string
  })
  default = {
    ttl_enabled   = true
    ttl_attribute = "expiresAt"
  }
}

variable "lambda_config" {
  description = "Lambda configuration"
  type = object({
    runtime          = string
    timeout          = number
    memory_size      = number
    log_retention_days = number
  })
  default = {
    runtime            = "python3.14"
    timeout              = 30
    memory_size          = 128
    log_retention_days   = 14
  }
}