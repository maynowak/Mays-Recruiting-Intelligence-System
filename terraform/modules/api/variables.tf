# API Module Variables

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  type        = string
}

variable "cognito_user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  type        = string
}

variable "cognito_user_pool_m2m_client_id" {
  description = "Cognito User Pool M2M Client ID for client credentials flow"
  type        = string
  default     = ""
}

variable "cognito_user_pool_endpoint" {
  description = "Cognito User Pool endpoint (URL)"
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda function name"
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Lambda invoke ARN for API Gateway integration"
  type        = string
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

# CORS fuer die Browser-Frontends (Jobsearch-UI). Explizite Origins, KEIN
# Wildcard. Leere Liste = kein cors_configuration-Block (Bestandsverhalten,
# kein Diff). Methoden/Header sind fest und minimal (Auth-Header + Content-Type).
variable "cors_origins" {
  description = "Erlaubte CORS-Origins (explizit, kein Wildcard). Leer = CORS aus."
  type        = list(string)
  default     = []

  validation {
    condition     = length([for o in var.cors_origins : o if can(regex("\\*", o))]) == 0
    error_message = "Wildcard-Origins sind nicht erlaubt; Origins muessen explizit sein."
  }
}