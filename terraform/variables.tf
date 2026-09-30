variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "mays-ris"

  validation {
    condition     = length(var.project_name) >= 3 && can(regex("^[a-z0-9][a-z0-9-]*$", var.project_name))
    error_message = "project_name must be at least 3 characters and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be dev, test, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-central-1"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

variable "queue_config" {
  description = "SQS queue configuration"
  type = object({
    visibility_timeout_seconds = number
    message_retention_seconds  = number
    dlq_max_receive_count      = number
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
    ttl_enabled   = bool
    ttl_attribute = string
  })
  default = {
    ttl_enabled   = true
    ttl_attribute = "expiresAt"
  }
}

variable "lambda_config" {
  description = "Lambda function configuration"
  type = object({
    runtime            = string
    handler            = string
    timeout            = number
    memory_size        = number
    filename           = string
    log_retention_days = number
  })
  default = {
    runtime            = "python3.14"
    handler            = "handler.lambda_handler"
    timeout              = 30
    memory_size        = 128
    filename             = "lambda.zip"
    log_retention_days   = 14
  }
}

variable "monitoring_enabled" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "alarm_period_seconds" {
  description = "Auswertungsperiode der Alarme in Sekunden (300 = 5 Minuten)."
  type        = number
  default     = 300
}

variable "alarm_evaluation_periods" {
  description = "Anzahl aufeinanderfolgender Perioden, bis ein Alarm auslöst."
  type        = number
  default     = 1
}

variable "api_5xx_threshold" {
  description = "API 5xx error threshold"
  type        = number
  default     = 5
}

variable "lambda_error_threshold" {
  description = "Lambda error threshold"
  type        = number
  default     = 1
}

variable "lambda_duration_threshold_ms" {
  description = "Lambda duration threshold in milliseconds"
  type        = number
  default     = 30000
}

variable "lambda_throttle_threshold" {
  description = "Lambda throttle threshold"
  type        = number
  default     = 1
}

variable "dynamodb_throttled_threshold" {
  description = "DynamoDB throttled request threshold"
  type        = number
  default     = 1
}
