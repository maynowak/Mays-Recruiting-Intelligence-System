variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
  default     = "test-arn"

  # Naming-Safety (T013): ein vorhersagbarer, kompatibel nutzbarer Installationsname.
  # Kleinschreibung + Bindestrich ist über alle verwendeten Ressourcen hinweg gültig
  # (DynamoDB-Tabelle == project_name → min. 3 Zeichen; S3-Bucket ist kleinschreibungs-
  # pflichtig). Kein leading/trailing Bindestrich. Siehe terraform/README.md §9.
  validation {
    condition     = length(var.project_name) >= 3 && can(regex("^[a-z0-9][a-z0-9-]*$", var.project_name))
    error_message = "project_name muss mind. 3 Zeichen lang sein und darf nur Kleinbuchstaben, Ziffern und Bindestriche enthalten (kein fuehrender/trailender Bindestrich)."
  }
}

variable "tags" {
  description = "Zusaetzliche Tags, die allen Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

# T011-11 — CloudWatch Monitoring (Dashboard, Alarme, Logs)
# Fachquelle: monitoring/monitoring-design.md, cost/cost-analysis.md §2 CloudWatch.
# monitoring_enabled=false erzeugt KEINE Monitoring-Ressourcen (kostenbewusst);
# Standard ist aktiv, aber ohne unnötige Zusatzressourcen (kein SNS-Topic, keine
# Custom Metrics — siehe docs/reports/T011-11-CLOUDWATCH-MONITORING.md).
variable "monitoring_enabled" {
  description = "Erstellt CloudWatch-Dashboard, -Alarme und die Lambda-Log-Group (Retention)."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch-Log-Retention der Lambda-Log-Group in Tagen (kostenbewusst, monitoring-design.md §3)."
  type        = number
  default     = 7
}

# Cognito-Bereitstellungsart (MAYS-ORDERS-EXTERNAL-COGNITO-INTEGRATION-01):
# null (Default) = MANAGED: das Modul erstellt und verwaltet den eigenen
# Cognito User Pool + App Client + Gruppe "staff" (bisheriges Verhalten).
# Objekt gesetzt  = EXTERNAL: ein vorhandener Pool/Client des integrierenden
# Projekts wird verwendet; das Modul erzeugt KEINE Cognito-Ressourcen und
# verändert KEINE fremden Ressourcen. Der JWT-Authorizer bleibt in beiden
# Varianten aktiv (fail-closed: unvollständige Referenzen werden abgelehnt).
variable "external_cognito" {
  description = "Externe Cognito-Referenzen (EXTERNAL) oder null fuer eigenen Pool (MANAGED, Standard)."
  type = object({
    user_pool_endpoint  = string # Pool-Endpoint OHNE Scheme (api-Modul ergaenzt https://)
    user_pool_client_id = string # App-Client-ID (Audience des JWT-Authorizers)
  })
  default = null

  validation {
    condition = var.external_cognito == null || (
      can(regex("^cognito-idp\\.[a-z0-9-]+\\.amazonaws\\.com/[a-zA-Z0-9_-]+$", var.external_cognito.user_pool_endpoint))
      && var.external_cognito.user_pool_client_id != ""
    )
    error_message = "external_cognito erfordert einen vollstaendigen user_pool_endpoint im Format 'cognito-idp.<region>.amazonaws.com/<pool-id>' (ohne https://) und eine nicht leere user_pool_client_id - unvollstaendige Referenzen werden fail-closed abgelehnt."
  }
}
