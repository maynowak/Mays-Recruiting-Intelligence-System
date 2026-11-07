# Isolierter Partner-Zugang (Variante B).
#
# Eigene HTTP-API mit eigenem JWT-Authorizer (ein Issuer pro Authorizer ist eine
# API-Gateway-Grenze). Die bestehende Kernel-API bleibt unveraendert; beide APIs
# teilen sich dieselbe Lambda und damit dieselbe Geschaeftslogik.

locals {
  routes = toset([
    "POST /v1/partner/agents/{agentId}/execute",
    "GET /v1/partner/me/manual-search-profiles",
    "POST /v1/partner/me/manual-search-profiles",
    "GET /v1/partner/me/manual-search-profiles/{profileId}",
    "PUT /v1/partner/me/manual-search-profiles/{profileId}",
    "DELETE /v1/partner/me/manual-search-profiles/{profileId}",
    "GET /v1/partner/me/cvs",
    "POST /v1/partner/me/cvs",
    "GET /v1/partner/me/cvs/{cvId}",
    "PATCH /v1/partner/me/cvs/{cvId}",
    "DELETE /v1/partner/me/cvs/{cvId}",
    "POST /v1/partner/me/cvs/{cvId}/document/upload",
    "POST /v1/partner/me/cvs/{cvId}/document/complete",
    "GET /v1/partner/me/cvs/{cvId}/document",
    "GET /v1/partner/me/cvs/{cvId}/search-profiles",
    "POST /v1/partner/me/cvs/{cvId}/search-profiles",
    "GET /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}",
    "PUT /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}",
    "DELETE /v1/partner/me/cvs/{cvId}/search-profiles/{searchProfileId}",
    "GET /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles",
    "POST /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles",
    "GET /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}",
    "PUT /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}",
    "DELETE /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/{atsSearchProfileId}",
    "GET /v1/partner/me/consents",
    "POST /v1/partner/me/consents",
    "POST /v1/partner/me/consents/withdraw",
    "GET /v1/partner/me/consents/history",
    "GET /v1/partner/me/applications",
    "GET /v1/partner/me/applications/metrics",
    "POST /v1/partner/me/applications",
    "GET /v1/partner/me/applications/{applicationId}",
    "PATCH /v1/partner/me/applications/{applicationId}",
    "POST /v1/partner/me/applications/{applicationId}/status",
    "POST /v1/partner/me/applications/{applicationId}/history",
    "POST /v1/partner/me/applications/{applicationId}/cover-letter-versions",
    "GET /v1/partner/me/applications/{applicationId}/export",
    "DELETE /v1/partner/me/applications/{applicationId}",
    "GET /v1/partner/me/privacy/inspect",
    "GET /v1/partner/me/privacy/export",
  ])
}

resource "aws_apigatewayv2_api" "partner" {
  name          = "${var.project_name}-jobsearch-api"
  protocol_type = "HTTP"
  description   = "Isolierter Partner-Zugang fuer Mays-Jobsearch (eigener Issuer, bestehende RIS-Logik)."

  dynamic "cors_configuration" {
    for_each = length(var.cors_origins) > 0 ? [1] : []

    content {
      allow_origins = var.cors_origins
      allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
      allow_headers = ["Authorization", "Content-Type", "X-Api-Credential", "X-Api-Profile"]
      max_age       = 3600
    }
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.partner.id
  authorizer_type  = "JWT"
  name             = "${var.project_name}-jobsearch-jwt"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [var.cognito_client_id]
    issuer   = var.cognito_issuer
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.partner.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "partner" {
  for_each = local.routes

  api_id             = aws_apigatewayv2_api.partner.id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.partner.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.partner.execution_arn}/*/*"
}
