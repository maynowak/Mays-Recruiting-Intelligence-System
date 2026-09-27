variable "project_name" {
  description = "Name des Projekts; wird als Tabellenname verwendet."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "table_config" {
  description = "DynamoDB table configuration"
  type = object({
    ttl_enabled   = bool
    ttl_attribute = string
  })
}

variable "tags" {
  description = "Zusaetzliche Tags, die der DynamoDB-Tabelle mitgegeben werden."
  type        = map(string)
  default     = {}
}