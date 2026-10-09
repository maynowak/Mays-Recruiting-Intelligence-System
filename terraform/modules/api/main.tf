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
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
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

# Gate-02 P2: profile deletion (handler _handle_me_profile_delete).
# Exposes the existing, tested profile-deletion capability. Scope is
# USER_PROFILE_TABLE only -- this is PROFILE DELETION, not account
# erasure (see docs/reports/GATE-02-P2-PRIVACY-API.md).
resource "aws_apigatewayv2_route" "profile_delete" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "DELETE /me/profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

# Gate-05 (G5): privacy erasure lifecycle. Deliberately a SEPARATE route
# from DELETE /me/profile, which stays profile-deletion-only. This is the
# only operation that revokes the caller's machine credentials.
# POST, not DELETE: erasure is an ordered, retryable lifecycle, not an
# idempotent single-resource delete.
resource "aws_apigatewayv2_route" "erasure" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /me/erasure"
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
# P19: APIProfile management HTTP (Human JWT only). Closes the P17
# blocker "no productive APIProfile management entry point": the P10
# domain functions (create_profile, get_profile, list_profiles,
# update_profile, transition_status) existed and were tested but had no
# productive caller. Explicit method/path routes, existing JWT authorizer
# + proxy integration reused; no new authorizer, integration, permission,
# table, role, or Lambda change. No $default, no ANY, no greedy route.
# set_client_ref / set_expires_at / renew_profile stay unpublished
# (internal domain support, see P19 report).
resource "aws_apigatewayv2_route" "apiprofiles_create" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "apiprofiles_list" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/apiprofiles"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "apiprofiles_get" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/apiprofiles/{apiProfileId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "apiprofiles_update" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "PATCH /v1/apiprofiles/{apiProfileId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "apiprofiles_status" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/apiprofiles/{apiProfileId}/status"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

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

# Machine plane: dedicated machine entry point for the opaque `ris_...`
# credential. It reuses the EXISTING integration (no second integration, no
# $default route, no greedy/ANY route).
#
# P21-01 changed the authorization type from NONE to JWT and reused the
# existing Cognito authorizer, so that Cognito is the Managed Authentication
# Boundary for the machine API as well. Cognito answers "is this caller
# authenticated and allowed to reach this protected RIS API?"; the APIProfile /
# Credential / Entitlement chain answers "which additional product/machine
# context may this authenticated caller use?".
#
# The two credentials therefore arrive in SEPARATE channels:
#   Authorization: Bearer <Cognito JWT>  -> validated by the gateway authorizer
#   X-Api-Credential: ris_...            -> validated inside the Lambda by the
#                                           central verify_api_credential()
# A single `Authorization` header cannot carry both values (a JWT has three
# dot-separated segments, the opaque secret none), and no new credential
# mechanism was introduced: same secret, same digest store, same verifier.
#
# The opaque credential is NOT removed and NOT replaced by Cognito. Both checks
# are mandatory; neither substitutes the other, and there is no downgrade path
# that would let a request skip Cognito.
resource "aws_apigatewayv2_route" "m2m_agent_execute" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/m2m/agents/{agentId}/execute"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

# Product Admin: Offer -> Entitlement provisioning (P23-01).
#
# All routes are Cognito JWT protected (same authorizer as the other 27) and
# the domain refuses every write for non-admins, so JWT is the authentication
# boundary and offers._is_admin(actor["groups"]) is the product boundary.
# `admins` is a Cognito group; it grants no AWS rights whatsoever.
#
# Offer management and the grant share one route family: an offer without its
# grant is not a usable product object.
resource "aws_apigatewayv2_route" "offers" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/offers"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "offers_create" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/offers"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "offers_item" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "GET /v1/offers/{offerId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "offers_update" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "PATCH /v1/offers/{offerId}"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "offers_status" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/offers/{offerId}/status"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "offers_grant" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/offers/{offerId}/grant"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "offers_withdraw" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "POST /v1/offers/{offerId}/withdraw"
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