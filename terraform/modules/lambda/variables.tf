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

variable "partner_profiles_table_name" {
  description = "DynamoDB table name for partner profile persistence (R02). Absent means profile CRUD fails closed."
  type        = string
}

variable "partner_profiles_table_arn" {
  description = "DynamoDB table ARN for partner profile persistence (R02). Grants the runtime role read/write access to profile resources and capacity counters."
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

variable "partner_applications_table_name" {
  description = "DynamoDB table name for the Partner Application Registry. Read on every authorized partner/M2M execution; absent means the registry lookup returns None and both partner routes fail closed with 403."
  type        = string
}

variable "partner_applications_table_arn" {
  description = "DynamoDB table ARN for the Partner Application Registry. Grants the runtime role read-only GetItem for the authoritative base-table re-read that makes partner deactivation take effect immediately."
  type        = string
}

variable "partner_applications_gsi_client_arn" {
  description = "DynamoDB GSI ARN for gsi-client on the Partner Application Registry. DynamoDB does not accept a table ARN for index access, so the Query grant uses this ARN."
  type        = string
}

variable "applications_table_name" {
  description = "DynamoDB table for authenticated ApplicationV1 persistence."
  type        = string
}

variable "applications_table_arn" {
  description = "DynamoDB table ARN for ApplicationV1 persistence."
  type        = string
}

variable "applications_gsi_owner_arn" {
  description = "Owner-scoped GSI ARN for ApplicationV1 list operations."
  type        = string
}

variable "partner_surface_enabled" {
  description = "Aktiviert die Partner-/Personen-Oberflaeche (/v1/partner/me/*). Default AUS; Aktivierung ist eine Betreiberentscheidung, keine Deployment-Nebenwirkung."
  type        = bool
  default     = false
}

variable "applications_cursor_secret_arn" {
  description = "ARN of the Secrets Manager secret that holds the pagination HMAC key. ARN only; the value must never enter Terraform state, environment variables or logs. Empty = pagination stays fail-closed."
  type        = string
  default     = ""
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

variable "privacy_receipts_table_name" {
  description = "DynamoDB table name for the privacy receipt journal (R08-A1)"
  type        = string
}

variable "privacy_receipts_table_arn" {
  description = "DynamoDB table ARN for the privacy receipt journal (R08-A1)"
  type        = string
}

variable "erasure_operations_table_name" {
  description = "DynamoDB table name for durable erasure operation state (R08-C0B)"
  type        = string
}

variable "erasure_operations_table_arn" {
  description = "DynamoDB table ARN for durable erasure operation state (R08-C0B)"
  type        = string
}

variable "s3_erasure_phases_table_name" {
  description = "DynamoDB table name for fenced S3 erasure phases (R08-C0F)"
  type        = string
}

variable "s3_erasure_phases_table_arn" {
  description = "DynamoDB table ARN for fenced S3 erasure phases (R08-C0F)"
  type        = string
}

variable "upload_ticket_ledger_table_name" {
  description = "DynamoDB table name for the CV upload-ticket ledger (R08-C0F-2C)"
  type        = string
}

variable "upload_ticket_ledger_table_arn" {
  description = "DynamoDB table ARN for the CV upload-ticket ledger (R08-C0F-2C)"
  type        = string
}

variable "upload_cutover_table_name" {
  description = "DynamoDB table name for legacy upload cutover evidence (R08-C0F-2D)"
  type        = string
}

variable "upload_cutover_table_arn" {
  description = "DynamoDB table ARN for legacy upload cutover evidence (R08-C0F-2D)"
  type        = string
}

variable "deletion_ledger_table_name" {
  description = "DynamoDB table name for durable R08 deletion evidence; runtime remains disabled by default."
  type        = string
}

variable "deletion_ledger_table_arn" {
  description = "DynamoDB table ARN for durable R08 deletion evidence."
  type        = string
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
