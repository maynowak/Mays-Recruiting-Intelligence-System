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

variable "analysis_zip_path" {
  description = "Agent bundle containing analysis_runner.py at the root (absolute path in isolated workdirs)."
  type        = string
  default     = ""
}

variable "analysis_timeout_seconds" {
  description = "Dedicated analysis Lambda timeout; must cover parser (15 s) plus storage reads."
  type        = number
  default     = 60

  validation {
    condition     = var.analysis_timeout_seconds >= 15 && var.analysis_timeout_seconds <= 900
    error_message = "analysis_timeout_seconds must be between 15 and 900."
  }
}

variable "analysis_memory_size" {
  type    = number
  default = 512
}

variable "documents_bucket_name" {
  type = string
}

variable "work_items_table_name" {
  type = string
}

variable "work_items_table_arn" {
  type = string
}

variable "entitlements_table_name" {
  type = string
}

variable "entitlements_table_arn" {
  type = string
}

variable "partner_profiles_table_name" {
  type = string
}

variable "partner_profiles_table_arn" {
  type = string
}

# --- Synthetic analysis canary (default deny) -------------------------------
#
# All values default to "off". A canary plan must set them explicitly through a
# reviewed var-file. The Lambda still requires a persisted RUNNING WorkItem with
# an exact identity match; these values alone authorize nothing.

variable "analysis_synthetic_mode" {
  description = "Enable the fail-closed synthetic analysis identity. Off by default."
  type        = bool
  default     = false
}

variable "analysis_synthetic_installation" {
  description = "Installation binding for the synthetic profile. Must stay ris-dev2."
  type        = string
  default     = "ris-dev2"
}

variable "analysis_synthetic_tenant_id" {
  description = "Synthetic tenant id; must match the persisted WorkItem exactly."
  type        = string
  default     = ""
}

variable "analysis_synthetic_user_id" {
  description = "Synthetic user id; must match the persisted WorkItem exactly."
  type        = string
  default     = ""
}

variable "analysis_synthetic_partner_application_id" {
  description = "Synthetic partner application id; must match the persisted WorkItem exactly."
  type        = string
  default     = ""
}

variable "analysis_synthetic_issuer" {
  description = "Synthetic issuer URL; must match the persisted WorkItem exactly."
  type        = string
  default     = ""

  validation {
    condition     = var.analysis_synthetic_issuer == "" || can(regex("^https://", var.analysis_synthetic_issuer))
    error_message = "analysis_synthetic_issuer must be empty or an https:// URL."
  }
}

variable "analysis_synthetic_entitlements" {
  description = "Comma-separated synthetic capabilities granted only for the canary (e.g. parse.cv,parse.job,analyze.job,compare.tags)."
  type        = string
  default     = ""
}

variable "analysis_synthetic_expires_at" {
  description = "RFC3339 expiry for the synthetic profile; an expired value disables the profile (fail closed)."
  type        = string
  default     = ""
}
