variable "project_name" {
  description = "Name des Projekts; wird als Prefix fuer Ressourcen-Namen verwendet."
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "tags" {
  description = "Zusaetzliche Tags, die den Cognito-Ressourcen mitgegeben werden."
  type        = map(string)
  default     = {}
}

variable "email_verification_enabled" {
  description = "E-Mail als zu verifizierendes Attribut (Gate 11: Registrierung abschliessen)."
  type        = bool
  default     = false
}

variable "email_subject" {
  description = "Betreff der Verifikations-Mail (muss {####}-frei sein; Cognito setzt Code ein)."
  type        = string
  default     = "Willkommen bei May's Job Matcher – E-Mail-Adresse bestätigen"
}

variable "email_message" {
  description = "Text der Verifikations-Mail (Platzhalter {####} fuer den Code)."
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

variable "sender_mode" {
  description = "Versandmodus: nur cognito_default (AWS-managed, keine eigene Domain). Andere Werte werden abgewiesen."
  type        = string
  default     = "cognito_default"

  validation {
    condition     = var.sender_mode == "cognito_default"
    error_message = "Nur sender_mode=cognito_default wird unterstuetzt (keine eigene Domain/SES-Identitaet vorhanden; s. Gate-11-Report)."
  }
}

# Gate 13A: optionale Google-Federation (Default AUS = keine Aenderung).
# Secrets (client_secret) stehen NIE im Code — nur per --var beim Apply,
# nie committen, nie loggen (TF-State-Backend ist verschluesselt).
variable "google_client_id" {
  description = "Google OAuth Client-ID (leer = Federation deaktiviert)."
  type        = string
  default     = ""
}

variable "google_client_secret" {
  description = "Google OAuth Client-Secret (leer = deaktiviert; nur per --var)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_callback_urls" {
  description = "OAuth-Redirect-URIs (Pflicht bei aktivierter Federation; keine Defaults erfunden)."
  type        = list(string)
  default     = []
}

variable "google_logout_urls" {
  description = "Logout-Redirect-URIs (Pflicht bei aktivierter Federation)."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------------------
# Browser-Login (OAuth 2.0 Authorization Code + PKCE) fuer den public App-Client.
#
# Bewusst ENTKOPPELT von der Google-Federation: der Authorization-Code-Flow mit
# Scopes openid/email/profile braucht keinen externen IdP. Cognito unterstuetzt
# PKCE fuer public Clients (generate_secret=false) automatisch, sobald der
# `code`-Flow aktiviert ist -- es gibt kein separates PKCE-Flag im Provider-Schema.
#
# Default AUS = rueckwaertskompatibel: ein Modul ohne diese Variablen erzeugt
# exakt das bisherige Verhalten (OAuth nur bei Google-Federation).
# ---------------------------------------------------------------------------
variable "oauth_enabled" {
  description = "Authorization-Code-Flow (+PKCE) am public App-Client aktivieren (Default AUS)."
  type        = bool
  default     = false
}

variable "oauth_scopes" {
  description = "OAuth-Scopes des App-Clients (nur bei oauth_enabled wirksam)."
  type        = list(string)
  default     = ["openid", "email", "profile"]
}

variable "oauth_callback_urls" {
  description = "Erlaubte Redirect-URIs (Callback) des App-Clients (nur bei oauth_enabled wirksam; Pflicht, fail-closed)."
  type        = list(string)
  default     = []
}

variable "oauth_logout_urls" {
  description = "Erlaubte Logout-Redirect-URIs des App-Clients (nur bei oauth_enabled wirksam)."
  type        = list(string)
  default     = []
}

variable "custom_domain_enabled" {
  description = "Cognito Custom Domain fuer den Pool aktivieren (Default AUS). Erfordert Domain + us-east-1-ACM-Zertifikat."
  type        = bool
  default     = false
}

variable "custom_domain" {
  description = "Vollqualifizierter Custom-Domain-Name (z. B. auth.mays-job-matcher.app). Nur bei custom_domain_enabled wirksam."
  type        = string
  default     = ""
}

variable "custom_domain_certificate_arn" {
  description = "ARN des vorhandenen, ISSUED ACM-Zertifikats in us-east-1 (Cognito verlangt us-east-1). Keine Neuanforderung."
  type        = string
  default     = ""

  validation {
    condition     = var.custom_domain_certificate_arn == "" || can(regex(":acm:us-east-1:", var.custom_domain_certificate_arn))
    error_message = "Cognito Custom Domains verlangen ein ACM-Zertifikat in us-east-1."
  }
}