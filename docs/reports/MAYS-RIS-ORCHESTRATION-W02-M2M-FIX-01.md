# MAYS-RIS-ORCHESTRATION-W02-M2M-FIX-01

## Cognito Source of Truth
User Pool A eu-central-1_8XhV6ZQ9 does not exist.
User Pool B eu-central-1_IfucuxPC1 exists, name mays-ris-dev-users, custom domain auth.mays-job-matcher.app.
Terraform manages pool named ${project_name}-${environment}-users → mays-ris-dev-users.
API Gateway JWT authorizer points to eu-central-1_IfucuxPC1, audience 24qns4st861fc72bk7cucjc375.
Deployed User Pool is Terraform-managed pool B.

## Deployed JWT Authorizer
API Gateway v2 API mays-ris-dev-api
Authorizer mays-ris-dev-jwt
Type JWT
Issuer https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_IfucuxPC1
Audience [24qns4st861fc72bk7cucjc375]
Identity Source $request.header.Authorization
Drift: Matches Terraform configuration.

## Machine Authentication
Current client mays-ris-dev-client 24qns4st861fc72bk7cucjc375:
ExplicitAuthFlows ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH
AllowedOAuthFlowsUserPoolClient false
No client secret
No client credentials grant

Post /v1/m2m/agents/{agentId}/execute requires Authorization Bearer Cognito JWT + X-Api-Credential.
Server-to-server partner backends cannot obtain JWT via user password flow.
Client credentials grant is required for M2M.

## Security
Valid Cognito token alone does not authorize agent execution; X-Api-Credential verification required.
Valid RIS credential alone does not authorize; Cognito JWT required.
Tenant binding enforced via APIProfile.

## Implementation Plan
Create dedicated confidential M2M client:
Terraform aws_cognito_user_pool_client m2m_client:
generate_secret = true
explicit_auth_flows = [ALLOW_CLIENT_CREDENTIALS_AUTH]
allowed_oauth_flows = [client_credentials]
allowed_oauth_scopes = []
Prevent audience conflict by keeping existing JWT authorizer audience unchanged.

Alternatively, enable client credentials on existing client, but preferred is dedicated client to avoid breaking browser flows.

API Gateway JWT authorizer audience needs to accept tokens issued to M2M client OR keep existing audience and use token exchange. Simplest: add new authorizer for M2M client or update audience to include both clients.

No Lambda changes required.

Tests: verify token acquisition via client credentials, verify JWT validation, verify X-Api-Credential verification still enforced.

Rollback: remove new client, revert authorizer audience.

Cost: negligible.

Implementation ready: YES after Terraform change approval.

## Security Risks
Client secret must be stored in Vercel environment variables, never in frontend bundles.
Token caching recommended to reduce Cognito calls.
Scope validation recommended.

## Next Action
Await approval to update Terraform modules/cognito to add M2M client and adjust API Gateway authorizer audience.
