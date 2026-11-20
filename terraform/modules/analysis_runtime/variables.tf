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

variable "enable_analysis_runtime" {
  description = "Create the dedicated Node parser Lambda and its invoke grant. Off by default so the shared plan baseline is unchanged."
  type        = bool
  default     = false
}

variable "parser_artifact_path" {
  description = "Path to the deterministic parser Lambda zip built from the pinned jobsearch commit."
  type        = string
  default     = ""
}

variable "parser_runtime" {
  type    = string
  default = "nodejs22.x"
}

variable "parser_timeout_seconds" {
  description = "Parser Lambda timeout; the API Gateway-style 29 s limit does not apply (internal invoke)."
  type        = number
  default     = 15

  validation {
    condition     = var.parser_timeout_seconds >= 1 && var.parser_timeout_seconds <= 60
    error_message = "parser_timeout_seconds must be between 1 and 60."
  }
}

variable "parser_memory_size" {
  type    = number
  default = 512

  validation {
    condition     = var.parser_memory_size >= 128 && var.parser_memory_size <= 3008
    error_message = "parser_memory_size must be between 128 and 3008 MB."
  }
}
