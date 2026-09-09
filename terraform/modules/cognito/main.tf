# Cognito Module

resource "aws_cognito_user_pool" "users" {
  name = "${var.project_name}-${var.environment}-users"

  password_policy {
    minimum_length    = 8
    require_uppercase = true
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
  }

  account_attributes {
    name  = "custom:tenant_id"
    type  = "String"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "${var.project_name}-${var.environment}-client"
  user_pool_id = aws_cognito_user_pool.users.id
  generate_secret = false

  explicit_authentic_authentication_factors = ["USERNAME"]
  preferred_authentic_authentications     = ["USERNAME"]

  tags = merge({ "Project" = var.project_name }, var.tags)
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