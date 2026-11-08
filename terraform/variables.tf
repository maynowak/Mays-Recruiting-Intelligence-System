variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "mays-ris"

  validation {
    condition     = length(var.project_name) >= 3 && can(regex("^[a-z0-9][a-z0-9-]*$", var.project_name))
    error_message = "project_name must be at least 3 characters and contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be dev, test, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-central-1"
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

variable "identity_mode" {
  description = "Identity ownership mode. external uses supplied Cognito references only."
  type        = string
  default     = "managed"

  validation {
    condition     = contains(["managed", "external"], var.identity_mode)
    error_message = "identity_mode must be either managed or external."
  }
}

variable "identity_m2m_enabled" {
  description = "Whether this identity module provisions its own M2M client."
  type        = bool
  default     = true
}

variable "identity_m2m_fallback_issuer" {
  description = "Existing M2M JWT issuer preserved when managed Human-only mode is selected."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode != "managed" || var.identity_m2m_enabled || can(regex("^https://cognito-idp\\.${var.aws_region}\\.amazonaws\\.com/eu-central-1_[A-Za-z0-9]+$", var.identity_m2m_fallback_issuer))
    error_message = "identity_m2m_fallback_issuer is required when managed M2M is disabled."
  }
}

variable "identity_m2m_fallback_client_id" {
  description = "Existing M2M audience preserved when managed Human-only mode is selected."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode != "managed" || var.identity_m2m_enabled || can(regex("^[A-Za-z0-9]+$", var.identity_m2m_fallback_client_id))
    error_message = "identity_m2m_fallback_client_id is required when managed M2M is disabled."
  }
}

variable "external_cognito_user_pool_id" {
  description = "Existing Cognito User Pool ID used in external identity mode."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode == "managed" || can(regex("^${var.aws_region}_[A-Za-z0-9]+$", var.external_cognito_user_pool_id))
    error_message = "external_cognito_user_pool_id is required and must match the regional pool ID format."
  }
}

variable "external_cognito_account_id" {
  description = "AWS account that owns the externally managed Cognito pool; may differ from the RIS deployment account."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode == "managed" || can(regex("^[0-9]{12}$", var.external_cognito_account_id))
    error_message = "external_cognito_account_id is required and must be a 12-digit AWS account ID in external mode."
  }
}

variable "external_cognito_user_pool_arn" {
  description = "Existing Cognito User Pool ARN used in external identity mode."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode == "managed" || can(regex("^arn:aws:cognito-idp:${var.aws_region}:${var.external_cognito_account_id}:userpool/${var.external_cognito_user_pool_id}$", var.external_cognito_user_pool_arn))
    error_message = "external_cognito_user_pool_arn must reference the supplied external pool in this region."
  }
}

variable "external_cognito_issuer" {
  description = "Complete HTTPS issuer URL for the externally managed Cognito pool."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode == "managed" || can(regex("^https://cognito-idp\\.${var.aws_region}\\.amazonaws\\.com/${var.external_cognito_user_pool_id}$", var.external_cognito_issuer))
    error_message = "external_cognito_issuer must be the HTTPS issuer for the supplied pool."
  }
}

variable "external_cognito_human_client_id" {
  description = "Existing human/browser Cognito app client ID."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode == "managed" || can(regex("^[A-Za-z0-9]+$", var.external_cognito_human_client_id))
    error_message = "external_cognito_human_client_id is required in external mode."
  }
}

variable "external_cognito_m2m_client_id" {
  description = "Existing M2M Cognito app client ID for the machine authorizer."
  type        = string
  default     = ""

  validation {
    condition     = var.identity_mode == "managed" || can(regex("^[A-Za-z0-9]+$", var.external_cognito_m2m_client_id))
    error_message = "external_cognito_m2m_client_id is required in external mode."
  }
}

variable "external_cognito_domain" {
  description = "Optional external Cognito OAuth/discovery domain; never managed by this stack."
  type        = string
  default     = ""
}

variable "mays_orders_lambda_execution_boundary" {
  description = "Optional IAM permissions boundary ARN for the existing Mays-Orders SQS worker role. Null preserves module default; set explicitly to retain an existing deployed boundary."
  type        = string
  default     = null

  validation {
    condition     = var.mays_orders_lambda_execution_boundary == null || can(regex("^arn:aws:iam::[0-9]{12}:policy/", var.mays_orders_lambda_execution_boundary))
    error_message = "mays_orders_lambda_execution_boundary must be null or a valid IAM policy ARN."
  }
}

variable "orders_lifecycle" {
  description = "Orders lifecycle: managed, external, or disabled."
  type        = string
  default     = "managed"

  validation {
    condition     = contains(["managed", "external", "disabled"], var.orders_lifecycle)
    error_message = "orders_lifecycle must be managed, external, or disabled."
  }
}

variable "external_orders_table_name" {
  description = "Existing Orders table name used only in external Orders mode."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_lifecycle != "external" || can(regex("^[A-Za-z0-9_.-]+$", var.external_orders_table_name))
    error_message = "external_orders_table_name is required in external Orders mode."
  }
}

variable "external_orders_table_arn" {
  description = "Existing Orders table ARN used only in external Orders mode."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_lifecycle != "external" || can(regex("^arn:aws:dynamodb:${var.aws_region}:[0-9]{12}:table/[A-Za-z0-9_.-]+$", var.external_orders_table_arn))
    error_message = "external_orders_table_arn is required and must be a DynamoDB table ARN in this region."
  }
}

variable "external_orders_queue_url" {
  description = "Existing Orders queue URL used only in external Orders mode."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_lifecycle != "external" || can(regex("^https://sqs\\.${var.aws_region}\\.amazonaws\\.com/[0-9]{12}/[A-Za-z0-9_.-]+$", var.external_orders_queue_url))
    error_message = "external_orders_queue_url is required and must be an SQS URL in this region."
  }
}

variable "external_orders_queue_arn" {
  description = "Existing Orders queue ARN used only in external Orders mode."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_lifecycle != "external" || can(regex("^arn:aws:sqs:${var.aws_region}:[0-9]{12}:[A-Za-z0-9_.-]+$", var.external_orders_queue_arn))
    error_message = "external_orders_queue_arn is required and must be an SQS ARN in this region."
  }
}

# Gate 11: Identity-Mail-Konfiguration (per --var KEY=VALUE setzbar,
# Re-Run faehig via Terraform State; keine Secrets — Betreff/Text sind
# oeffentliche Anwendungstexte, Versand AWS-managed).
#
# Gate-11 (G3-COGNITO-CONFIG-PERSISTENCE-01): Default war `false` — der
# Stand VOR Gate 11. Der ausgelieferte dev-Pool wurde jedoch bewusst mit
# E-Mail-Verifikation provisioniert (live AutoVerifiedAttributes=["email"]).
#
# Solange Default `false` und kein tfvars existierten, plante jeder
# ungepinte `terraform plan` eine ABSCHALTUNG der Verifikation. Das wurde
# ueber `-var=identity_email_verification_enabled=true` kaschiert — in
# mindestens 8 Gates (11, 16, 17, P17, P20, ...), jeweils als bekanntes
# "Variablen-Default-Artefakt" dokumentiert und nie behoben.
#
# Der Default ist jetzt der ausgelieferte Soll-Zustand: true. Damit stimmen
# Repo-Konfiguration, `terraform plan` ohne Flags und der Installer-Pfad
# ueberein; die Live-Ressource bleibt unveraendert (kein Apply noetig).
# Rueckgaengig machbar durch explizites -var beim Apply.
variable "identity_email_verification_enabled" {
  description = "E-Mail-Verifikation bei Registrierung (Cognito-managed Versand)."
  type        = bool
  default     = true
}

variable "identity_email_subject" {
  description = "Betreff der Verifikations-Mail."
  type        = string
  default     = "Willkommen bei May's Job Matcher – E-Mail-Adresse bestätigen"
}

variable "identity_email_message" {
  description = "Text der Verifikations-Mail (Platzhalter {####})."
  type        = string
  default     = <<-EOT
    Sehr geehrte Benutzerin, sehr geehrter Benutzer,

    willkommen bei May's Job Matcher.

    Um Ihre Registrierung abzuschließen und May's Job Matcher nutzen zu
    können, bestätigen Sie bitte Ihre E-Mail-Adresse mit dem von uns
    bereitgestellten Bestätigungscode.

    Ihr Bestätigungscode lautet: {####}

    Mit freundlichen Grüßen
    May's Job Matcher
  EOT
}

variable "identity_sender_mode" {
  description = "Versandmodus (derzeit nur cognito_default)."
  type        = string
  default     = "cognito_default"
}

# Gate 13A: optionale Google-Federation (Defaults = deaktiviert).
# Secrets nur per --var beim Apply (nie committen); leere Redirect-Listen
# lassen einen aktivierten Apply gezielt fehlschlagen (fail-closed).
variable "identity_google_client_id" {
  description = "Google OAuth Client-ID (leer = deaktiviert)."
  type        = string
  default     = ""
}

variable "identity_google_client_secret" {
  description = "Google OAuth Client-Secret (nur per --var, nie committen)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "identity_google_callback_urls" {
  description = "OAuth-Redirect-URIs (Pflicht bei Aktivierung)."
  type        = list(string)
  default     = []
}

variable "identity_google_logout_urls" {
  description = "Logout-Redirect-URIs (Pflicht bei Aktivierung)."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Browser-Login (OAuth 2.0 Authorization Code + PKCE) fuer die Jobsearch-UI.
#
# Der Code-Flow mit PKCE richtet sich an den public App-Client des RIS-Pools
# und ist bewusst von der Google-Federation entkoppelt (kein externer IdP
# noetig). Defaults sind rueckwaertskompatibel (AUS); die Development-
# Installation ris-dev aktiviert den Flow gezielt.
#
# Callback-/Logout-URLs sind explizit (kein Wildcard); Domains sind OHNE
# Pfad-Sternchen erlaubt -- Cognito matcht exakt.
# ---------------------------------------------------------------------------
variable "identity_oauth_enabled" {
  description = "OAuth Authorization Code + PKCE am public RIS-App-Client aktivieren (Default AUS)."
  type        = bool
  default     = false
}

variable "identity_oauth_scopes" {
  description = "OAuth-Scopes des App-Clients (Default: openid/email/profile)."
  type        = list(string)
  default     = ["openid", "email", "profile"]
}

variable "identity_oauth_callback_urls" {
  description = "Erlaubte Callback-/Redirect-URIs (explizit, kein Wildcard)."
  type        = list(string)
  default     = []
}

variable "identity_oauth_logout_urls" {
  description = "Erlaubte Logout-Redirect-URIs (explizit, kein Wildcard)."
  type        = list(string)
  default     = []
}

variable "identity_custom_domain_enabled" {
  description = "Cognito Custom Domain (z. B. auth.mays-job-matcher.app) aktivieren (Default AUS)."
  type        = bool
  default     = false
}

variable "identity_custom_domain" {
  description = "Vollqualifizierter Custom-Domain-Name fuer den RIS-Cognito-Pool."
  type        = string
  default     = ""
}

variable "identity_custom_domain_certificate_arn" {
  description = "ARN des vorhandenen ISSUED ACM-Zertifikats in us-east-1 (keine Neuanforderung)."
  type        = string
  default     = ""
}

# CORS fuer die Browser-Frontends der Jobsearch-UI. Explizite Origins,
# KEIN Wildcard. Leer = CORS aus (Bestandsverhalten, kein Diff).
variable "applications_cursor_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the ApplicationV1 pagination HMAC key. Only the ARN is configured; the secret value must never be stored in Terraform, git or reports. Empty keeps pagination fail-closed."
  type        = string
  default     = ""
}

variable "application_consent_enforced" {
  description = "Enforce application-storage consent on ApplicationV1 writes (Default AUS fuer den Rollout)."
  type        = bool
  default     = false
}

variable "consent_notice_state_enforced" {
  description = "Reject new consent grants for non-grantable notice states (DRAFT/SUPERSEDED) in the Lambda runtime (Default AUS; separate activation gate)."
  type        = bool
  default     = false
}

variable "consent_pilot_allowlist" {
  description = "Comma/newline separated <issuer>|<sub> synthetic pilot identities. Empty means no scoped pilot identity. Non-secret configuration, never a credential."
  type        = string
  default     = ""
}

variable "partner_surface_enabled" {
  description = "Aktiviert die Partner-/Personen-Oberflaeche (Default AUS)."
  type        = bool
  default     = false
}

variable "jobsearch_cognito_issuer" {
  description = "Issuer des Jobsearch-Partner-Pools fuer den isolierten Partner-Gateway. Leer = kein Partner-Gateway."
  type        = string
  default     = ""
}

variable "jobsearch_cognito_client_id" {
  description = "App-Client des Jobsearch-Partners (Audience des Access-Tokens). Leer = kein Partner-Gateway."
  type        = string
  default     = ""
}

variable "jobsearch_edge_cors_origins" {
  description = "Explizite CORS-Origins des Jobsearch-Partner-Gateways (kein Wildcard)."
  type        = list(string)
  default     = []
}

variable "api_cors_origins" {
  description = "Erlaubte CORS-Origins der RIS-HTTP-API (explizit, kein Wildcard)."
  type        = list(string)
  default     = []
}

variable "queue_config" {
  description = "SQS queue configuration"
  type = object({
    visibility_timeout_seconds = number
    message_retention_seconds  = number
    dlq_max_receive_count      = number
  })
  default = {
    visibility_timeout_seconds = 300
    message_retention_seconds  = 1209600
    dlq_max_receive_count      = 3
  }
}

variable "table_config" {
  description = "DynamoDB table configuration"
  type = object({
    ttl_enabled   = bool
    ttl_attribute = string
  })
  default = {
    ttl_enabled   = true
    ttl_attribute = "expiresAt"
  }
}

variable "r08_pitr_enabled" {
  description = "Opt-in PITR for R08 recovery tables and durable deletion ledger; disabled by default."
  type        = bool
  default     = false
}

variable "lambda_config" {
  description = "Lambda function configuration"
  type = object({
    runtime            = string
    handler            = string
    timeout            = number
    memory_size        = number
    filename           = string
    log_retention_days = number
  })
  default = {
    runtime            = "python3.14"
    handler            = "handler.lambda_handler"
    timeout            = 30
    memory_size        = 128
    filename           = "lambda.zip"
    log_retention_days = 14
  }
}

variable "monitoring_enabled" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "dashboard_enabled" {
  description = "Enable CloudWatch overview dashboard"
  type        = bool
  default     = true
}

variable "alarm_period_seconds" {
  description = "Auswertungsperiode der Alarme in Sekunden (300 = 5 Minuten)."
  type        = number
  default     = 300
}

variable "alarm_evaluation_periods" {
  description = "Anzahl aufeinanderfolgender Perioden, bis ein Alarm auslöst."
  type        = number
  default     = 1
}

variable "api_5xx_threshold" {
  description = "API 5xx error threshold"
  type        = number
  default     = 5
}

variable "api_4xx_threshold" {
  description = "API 4xx error threshold"
  type        = number
  default     = 20
}

variable "lambda_error_threshold" {
  description = "Lambda error threshold"
  type        = number
  default     = 1
}

variable "lambda_duration_threshold_ms" {
  description = "Lambda duration threshold in milliseconds"
  type        = number
  default     = 30000
}

variable "lambda_throttle_threshold" {
  description = "Lambda throttle threshold"
  type        = number
  default     = 1
}

variable "dynamodb_throttled_threshold" {
  description = "DynamoDB throttled request threshold"
  type        = number
  default     = 1
}

# B5: opt-in synthetic foundation entitlements. Empty by default.
# See modules/dynamodb/variables.tf for the rationale (user-bound row, the
# Cognito sub is an input, row shape mirrors the existing grant contract).
variable "foundation_entitlements" {
  description = "Opt-in synthetic foundation entitlements (B5). Map key becomes entitlementId."
  type = map(object({
    userId       = string
    tenantId     = string
    agentId      = string
    validFrom    = optional(string)
    validUntil   = optional(string)
    apiProfileId = optional(string)
  }))
  default = {}
}

variable "filename" {
  description = "Deployment-Zip mit orders_reader.py am Root (absolute path required for isolated workdirs)"
  type        = string
}

variable "health_writer_zip_path" {
  description = "Deployment-Zip mit health_writer.py am Root (absolute path required for isolated workdirs)"
  type        = string
}

variable "health_publisher_zip_path" {
  description = "Deployment-Zip mit health_publisher.py am Root (absolute path required for isolated workdirs)"
  type        = string
}

# GLUE-01 (Composite Lifecycle): Werte der projekt-spezifischen
# Mays-Orders-Instanz, die zu DIESER RIS-Installation gehoert.
# NO DEFAULTS: Fail-closed binding. Composite-Installationen
# ueberschreiben diese Variablen via -var aus dem Orders-Output-Handoff
# (installer/ris.py, composite preflight/install).
# Fuer Standalone-Modus (-no-composite) muss ein expliziter Binding
# konfiguriert werden, sonst schlaegt der Planschritt fehl.
#
# FAIL-CLOSED LAYERING -- read before "fixing" the condition below.
# The validation on these four root variables can never be false:
#   x == ""  -> true  (empty is explicitly tolerated)
#   x != ""  -> length(x) > 0 is true
# So it is DECLARATIVE, not a gate. The actual rejection of an unbound
# install happens one layer down in
#   terraform/modules/orders_reader/variables.tf
# where the mirrored condition is `x != "" || can(regex(...))` and an empty
# value is refused with "Invalid value for variable".
# Verified with a real plan: no Orders binding -> plan fails at the module.
#
# Consequence worth remembering: an unbound install fails at the MODULE,
# not at the root, so a "clean" root-level validation proves nothing about
# whether the binding is actually present.
#
# Known gap carried over from installer/ris.py:validate_orders_binding --
# the ARN variables below are checked for FORMAT only (`^arn:`), never
# against the project name, so a name/ARN pair pointing at two different
# tables passes both layers.
variable "orders_table_name" {
  description = "Mays-Orders-Tabelle fuer den Orders-Reader (Composite: Output der Projekt-Orders-Instanz)."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_table_name == "" || length(var.orders_table_name) > 0
    error_message = "orders_table_name must be explicitly configured (empty default = fail-closed binding)"
  }
}

variable "orders_table_arn" {
  description = "ARN der Mays-Orders-Tabelle fuer den Orders-Reader (Composite: Output-Handoff)."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_table_arn == "" || can(regex("^arn:", var.orders_table_arn))
    error_message = "orders_table_arn must be an ARN or explicitly configured"
  }
}

variable "orders_queue_url" {
  description = "URL der Mays-Orders-Queue fuer Worker-Anstoss (nur SendMessage; Composite: Naming-Contract-Ableitung)."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_queue_url == "" || can(regex("^https://sqs\\..*\\.amazonaws\\.com/", var.orders_queue_url))
    error_message = "orders_queue_url must be a valid SQS URL or explicitly configured"
  }
}

variable "orders_queue_arn" {
  description = "ARN der Mays-Orders-Queue (nur SendMessage-Recht; Composite: Naming-Contract-Ableitung)."
  type        = string
  default     = ""

  validation {
    condition     = var.orders_queue_arn == "" || can(regex("^arn:aws:sqs:", var.orders_queue_arn))
    error_message = "orders_queue_arn must be an ARN or explicitly configured"
  }
}
