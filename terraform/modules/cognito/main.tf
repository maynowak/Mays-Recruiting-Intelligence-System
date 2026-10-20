# Cognito Module

locals {
  # Browser-Login ist aktiv, wenn OAuth explizit freigeschaltet ODER die
  # Google-Federation konfiguriert ist. Nur dann werden OAuth-Flow, Scopes
  # und Redirect-Listen gesetzt (sonst null = Argument weglassen = kein Diff).
  oauth_active = var.oauth_enabled || var.google_client_id != ""

  # Wenn OAuth aktiv ist, gelten die expliziten oauth_*-Listen; die Google-Listen
  # bleiben als Rueckfall fuer den reinen Federation-Fall erhalten.
  callback_urls = var.oauth_enabled ? var.oauth_callback_urls : var.google_callback_urls
  logout_urls   = var.oauth_enabled ? var.oauth_logout_urls : var.google_logout_urls
}

resource "aws_cognito_user_pool" "users" {
  name = "${var.project_name}-${var.environment}-users"

  # Schema is managed out-of-band: AWS forbids removing schema items while
  # the provider validates every declared name (max 20 chars; live standard
  # attribute `phone_number_verified` has 21). The live pool carries all
  # standard attributes + custom:tenant_id (verified via describe-user-pool),
  # so drift is ignored instead of fought. The tenant_id block below documents
  # intent (Claim `custom:tenant_id`, read by the Lambda handler) and applies
  # on fresh pool creation. See RIS-COGNITO-SCHEMA-19.
  lifecycle {
    ignore_changes = [schema]
  }

  password_policy {
    minimum_length    = 8
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
  }

  # Gate 11: E-Mail-Verifikation (Cognito-managed Versand, keine eigene
  # Domain). auto_verified_attributes=[] = Verhalten wie vor Gate 11.
  # G3: der Root-Default ist jetzt true (siehe terraform/variables.tf), damit
  # ein ungepinter Plan keinen Abschalt-Drift mehr erzeugt.
  auto_verified_attributes = var.email_verification_enabled ? ["email"] : []

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = var.email_subject
    email_message        = var.email_message
  }

  # Custom tenant attribute (see lifecycle note above).
  schema {
    attribute_data_type = "String"
    name                = "tenant_id"
    mutable             = true
    required            = false
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cognito_user_pool_client" "client" {
  name            = "${var.project_name}-${var.environment}-client"
  user_pool_id    = aws_cognito_user_pool.users.id
  generate_secret = false

  # Login via USER_PASSWORD_AUTH + Refresh (proven Mays-Orders pattern:
  # public client without secret; users authenticate via Cognito/JWT).
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Browser-Login: OAuth 2.0 Authorization Code (+PKCE, public client) gilt,
  # sobald oauth_enabled ODER Google-Federation aktiv ist. PKCE ist bei
  # generate_secret=false + `code`-Flow implizit -- kein eigenes Flag.
  #
  # Fail-closed: bei aktiviertem OAuth verlangt Cognito nicht-leere
  # callback_urls; leere Listen lassen den Plan/Apply bewusst fehlschlagen,
  # statt eine offene/ungueltige Konfiguration zu schreiben.
  supported_identity_providers         = local.oauth_active ? (var.google_client_id != "" ? ["COGNITO", "Google"] : ["COGNITO"]) : null
  allowed_oauth_flows_user_pool_client = local.oauth_active
  allowed_oauth_flows                  = local.oauth_active ? ["code"] : null
  allowed_oauth_scopes                 = local.oauth_active ? var.oauth_scopes : null
  callback_urls                        = local.oauth_active ? local.callback_urls : null
  logout_urls                          = local.oauth_active ? local.logout_urls : null
  # NOTE: aws_cognito_user_pool_client supports no `tags` argument
  # (provider schema) — Project scoping lives on pool/groups.
}

# Gate 13A: optionaler Google IdP (Default AUS — keine Ressource, kein Diff).
# Erfordert echte Credentials per --var (nie Dummy-Werte applyen) plus
# Redirect-URIs (leere Listen lassen den Apply fehlschlagen: fail-closed).
resource "aws_cognito_identity_provider" "google" {
  count = var.google_client_id != "" ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.users.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_client_id
    client_secret    = var.google_client_secret
    authorize_scopes = "openid email profile"
  }

  attribute_mapping = {
    email       = "email"
    given_name  = "givenName"
    family_name = "familyName"
    name        = "name"
  }
}

resource "aws_cognito_user_group" "candidates" {
  name         = "candidates"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "recruiters" {
  name         = "recruiters"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "admins" {
  name         = "admins"
  user_pool_id = aws_cognito_user_pool.users.id
}

# Standard groups (user decision, verbatim names): Admin / Staff /
# user-user / user-requier. Existing groups untouched.
resource "aws_cognito_user_group" "standard_admin" {
  name         = "Admin"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "standard_staff" {
  name         = "Staff"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "standard_user_user" {
  name         = "user-user"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "standard_user_requier" {
  name         = "user-requier"
  user_pool_id = aws_cognito_user_pool.users.id
}

# Cognito erlaubt pro Pool ENTWEDER eine Prefix-Domain ODER eine Custom Domain,
# nicht beide. Die beiden Ressourcen sind daher wechselseitig exklusiv:
#   custom_domain_enabled = false (Default) -> Prefix-Domain (Bestandsverhalten)
#   custom_domain_enabled = true            -> Custom Domain (Prefix wird entfernt)
# Das Entfernen der Prefix-Domain ist eine Cognito-Vorgabe, kein Versehen; sie
# wird nirgends sonst referenziert (nur die Pool-/Client-IDs sind relevant).
resource "aws_cognito_user_pool_domain" "domain" {
  count = var.custom_domain_enabled ? 0 : 1

  domain       = "${var.project_name}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.users.id
}

# Browser-Login-Domain (reuse des vorhandenen us-east-1-ACM-Zertifikats).
# Keine Neuanforderung eines Zertifikats; die Domain-Verifikation (DNS-Record)
# erfolgt separat ausserhalb von Terraform (Phase 2b).
resource "aws_cognito_user_pool_domain" "custom" {
  count = var.custom_domain_enabled ? 1 : 0

  domain          = var.custom_domain
  certificate_arn = var.custom_domain_certificate_arn
  user_pool_id    = aws_cognito_user_pool.users.id
}

resource "aws_cognito_resource_server" "ris_api" {
  name         = "${var.project_name}-${var.environment}-ris-api"
  identifier   = "ris-api"
  user_pool_id = aws_cognito_user_pool.users.id

  scope {
    scope_name        = "m2m:execute"
    scope_description = "Machine-to-machine execution scope for agent execution"
  }
}

resource "aws_cognito_user_pool_client" "m2m" {
  name                                 = "${var.project_name}-${var.environment}-m2m-client"
  user_pool_id                         = aws_cognito_user_pool.users.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${aws_cognito_resource_server.ris_api.identifier}/m2m:execute"]
  # Least privilege: no explicit auth flows, no refresh, no user password auth
}

output "user_pool_id" {
  value = aws_cognito_user_pool.users.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.client.id
}

output "user_pool_endpoint" {
  value = aws_cognito_user_pool.users.endpoint
}

output "user_pool_m2m_client_id" {
  description = "M2M client ID for client credentials flow"
  value       = aws_cognito_user_pool_client.m2m.id
}

output "user_pool_m2m_client_secret" {
  description = "M2M client secret for client credentials flow"
  sensitive   = true
  value       = aws_cognito_user_pool_client.m2m.client_secret
}

output "resource_server_identifier" {
  description = "Cognito resource server identifier"
  value       = aws_cognito_resource_server.ris_api.identifier
}

output "domain" {
  description = "Aktive Cognito-Domain des Pools (Custom Domain bei custom_domain_enabled, sonst Prefix-Domain)."
  value       = var.custom_domain_enabled ? var.custom_domain : "${var.project_name}-${var.environment}"
}