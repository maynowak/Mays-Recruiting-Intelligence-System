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