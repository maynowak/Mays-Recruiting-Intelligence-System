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

variable "writer_role_arn" {
  type = string
}

variable "writer_zip_path" {
  type = string
}

variable "publisher_role_arn" {
  type    = string
  default = null
}

variable "publisher_zip_path" {
  type = string
}

variable "public_bucket_name" {
  type = string
}

variable "public_bucket_arn" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "log_retention_days" {
  type        = number
  default     = 14
  description = "CloudWatch-Log-Retention der Health-Lambda-Log-Groups. Ohne verwaltete Gruppe erzeugt Lambda sie beim ersten Invoke selbst, und destroy entfernt sie nicht."
}
