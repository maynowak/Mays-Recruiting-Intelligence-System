variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "browser_allowed_origins" {
  description = "Exact browser origins allowed to use short-lived presigned document PUT/GET requests."
  type        = list(string)
  default     = ["https://www.mays-job-matcher.app"]
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}
