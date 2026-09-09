# SQS Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "queue_config" {
  description = "Queue configuration"
  type = object({
    visibility_timeout_seconds = number
    message_retention_seconds  = number
    dlq_max_receive_count      = number
  })
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}