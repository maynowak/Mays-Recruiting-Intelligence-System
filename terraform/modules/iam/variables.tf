variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den IAM-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

variable "dynamodb_table_arn" {
  description = "ARN der DynamoDB-Tabelle fuer DynamoDB-Berechtigungen in der IAM-Policy."
  type        = string
}

variable "dynamodb_table_name" {
  description = "Name der DynamoDB-Tabelle fuer DynamoDB-Berechtigungen in der IAM-Policy."
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN des S3-Buckets fuer S3-Berechtigungen in der IAM-Policy."
  type        = string
}