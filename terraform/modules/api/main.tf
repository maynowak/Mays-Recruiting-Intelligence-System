# API Module - Ground Zero

data "aws_region" "current" {}

resource "aws_apigatewayv2_api" "ris_api" {
  name          = "${var.project_name}-${var.environment}-api"
  protocol_type = "HTTP"
  description   = "Ground Zero Platform API"

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.ris_api.id
  name        = "$default"
  auto_deploy = true

  tags = merge({ "Project" = var.project_name }, var.tags)
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.ris_api.id
  authorizer_type  = "JWT"
  name             = "${var.project_name}-${var.environment}-jwt"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [var.cognito_user_pool_client_id]
    issuer   = "https://${var.cognito_user_pool_endpoint}"
  }
  # NOTE: aws_apigatewayv2_authorizer supports no `tags` argument
  # (provider schema) — Project scoping lives on api/stage resources.
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.ris_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /health"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_route" "platform" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /platform"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "me" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /me"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "profile" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /me/profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "profile_create" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /me/profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "profile_update" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "PUT /me/profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "agents" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /agents"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

# P13: read-only capability introspection (Human JWT + X-Api-Profile;
# handler _handle_introspection, prepared in P12). No machine path,
# no new authorizer, no new integration (existing JWT + proxy used).
resource "aws_apigatewayv2_route" "introspection" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/introspection"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

# P16: credential management HTTP (Human JWT only; handler section
# "P15: Credential Management HTTP"). Explicit method/path routes —
# no $default substitute, no ANY, no greedy proxy. Existing JWT
# authorizer + proxy integration reused; no new authorizer,
# integration, permission, table, role, or Lambda change.
resource "aws_apigatewayv2_route" "credentials_create" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles/{apiProfileId}/credentials"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "credentials_list" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/apiprofiles/{apiProfileId}/credentials"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "credentials_get" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "credentials_rotate" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/rotate"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "credentials_disable" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/disable"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "credentials_enable" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/enable"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "credentials_revoke" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles/{apiProfileId}/credentials/{credentialId}/revoke"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_lambda_permission" "api_gateway" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.ris_api.execution_arn}/*/*"
}