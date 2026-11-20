variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "documents_bucket_arn" {
  description = "Existing RIS documents bucket (owner-scoped CV PDFs)."
  type        = string
}

variable "job_retention_days" {
  description = "S3 lifecycle backup; access is already refused after 4 hours."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  type    = number
  default = 14
}
