# API Module - Ground Zero

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Deployment environment (dev, test, prod)"
  type        = string
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  type        = string
}

variable "cognito_user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda function name"
  type        = string
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

resource "aws_apigatewayv2_api" "ris_api" {
  name          = "${var.project_name}-${var.environment}-api"
  protocol_type = "HTTP"
  description   = "Mays Recruiting Intelligence System Ground Zero API"

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
  name             = "${var.project_name}-${var.environment}-jwt-authorizer"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [var.cognito_user_pool_client_id]
    issuer   = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${var.cognito_user_pool_id}"
  }

  tags = merge({ "Project" = var.project_name }, var.tags)
}

data "aws_region" "current" {}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.ris_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_name}:$LATEST/invocations"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "health" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /health"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "NONE"
}

resource "aws_apigatewayv2_route" "submit_work" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /work"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "get_work" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /work/{workId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "list_work" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /work"
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

output "api_id" {
  value = aws_apigatewayv2_api.ris_api.id
}

output "api_endpoint" {
  value = aws_apigatewayv2_api.ris_api.api_endpoint
}

output "api_stage_name" {
  value = aws_apigatewayv2_stage.default.name
}