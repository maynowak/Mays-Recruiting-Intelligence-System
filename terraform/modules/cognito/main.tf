# Cognito Module

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
  name         = "${var.project_name}-${var.environment}-client"
  user_pool_id = aws_cognito_user_pool.users.id
  generate_secret = false

  # Login via USER_PASSWORD_AUTH + Refresh (proven Mays-Orders pattern:
  # public client without secret; users authenticate via Cognito/JWT).
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
  # NOTE: aws_cognito_user_pool_client supports no `tags` argument
  # (provider schema) — Project scoping lives on pool/groups.
}

resource "aws_cognito_user_group" "candidates" {
  name       = "candidates"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "recruiters" {
  name       = "recruiters"
  user_pool_id = aws_cognito_user_pool.users.id
}

resource "aws_cognito_user_group" "admins" {
  name       = "admins"
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

resource "aws_cognito_user_pool_domain" "domain" {
  domain       = "${var.project_name}-${var.environment}"
  user_pool_id = aws_cognito_user_pool.users.id
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