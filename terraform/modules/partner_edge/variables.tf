variable "project_name" {
  type = string
}

variable "environment" {
  type = string
}

variable "lambda_function_name" {
  description = "Bestehende RIS-Agent-Lambda, die auch die Kernel-API bedient."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Invoke-ARN derselben Lambda fuer die AWS_PROXY-Integration."
  type        = string
}

variable "cognito_issuer" {
  description = "Issuer des Partner-Pools (z. B. https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_XXXX)."
  type        = string
}

variable "cognito_client_id" {
  description = "App-Client des Partners (Audience des Access-Tokens)."
  type        = string
}

variable "cors_origins" {
  description = "Explizite Origins des Partner-Frontends; kein Wildcard."
  type        = list(string)
  default     = []
}
