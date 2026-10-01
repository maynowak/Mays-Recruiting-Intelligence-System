# Orders-Reader Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

variable "api_id" {
  description = "ID unserer API (mays-ris-dev-api) fuer Integration und Routen"
  type        = string
}

variable "authorizer_id" {
  description = "JWT-Authorizer unserer API"
  type        = string
}

variable "orders_table_name" {
  description = "Name der Mays-Orders-Tabelle (lesend/schreibend, gleiches Konto)"
  type        = string
  default     = "mays-orders"
}

variable "orders_table_arn" {
  description = "ARN der Mays-Orders-Tabelle"
  type        = string
  default     = "arn:aws:dynamodb:eu-central-1:240571105849:table/mays-orders"
}

variable "orders_queue_url" {
  description = "URL der Mays-Orders-Queue fuer Worker-Anstoss (nur SendMessage)"
  type        = string
  default     = "https://sqs.eu-central-1.amazonaws.com/240571105849/mays-orders-orders-queue"
}

variable "orders_queue_arn" {
  description = "ARN der Mays-Orders-Queue (nur SendMessage-Recht)"
  type        = string
  default     = "arn:aws:sqs:eu-central-1:240571105849:mays-orders-orders-queue"
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.14"
}

variable "timeout" {
  description = "Lambda timeout in Sekunden"
  type        = number
  default     = 10
}

variable "memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 128
}

variable "filename" {
  description = "Deployment-Zip mit orders_reader.py am Root"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch-Log-Retention in Tagen"
  type        = number
  default     = 7
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}
