# RIS-COGNITO-BACKEND-FINALIZE-05

**Status:** ANALYZE → VERIFIED
**Date:** 2026-10-22
**Scope:** Mays-RIS ONLY – Backend Only

## 1. Review lambda/pre_sign_up.py
Existing implementation:
- Requires email attribute present
- Basic format validation
- autoConfirmUser false, autoVerifyEmail false

Code is minimal validation, no role or deployment.

## 2. Necessity Assessment
Cognito User Pool eu-central-1_ojbmoiYGM has:
- email attribute optional in schema
- auto_verified_attributes = ["email"]
- No Pre Sign-up Lambda configured

Enforcing mandatory email via Pre Sign-up Lambda would:
- Block self-sign-up without email
- Also block AdminCreateUser if email not provided
- Impact other clients sharing the pool

Frontend validation can enforce email requirement without backend enforcement.
Given existing admin workflows and multi-client pool, backend hard enforcement via Lambda introduces risk of breaking AdminCreateUser and existing integrations.

Conclusion: Lambda not strictly necessary for backend readiness. Frontend contract can enforce email mandatory.

## 3. Impact Analysis
- Existing users: No impact, Lambda only runs on sign-up
- Admin accounts: AdminCreateUser would fail if email missing → risk
- Other Cognito clients: Shared pool, would be affected
- Existing auth flows: USER_PASSWORD_AUTH and OAuth unchanged

## 4. Terraform Integration Decision
Lambda integration deferred to avoid destructive impact.
No Terraform changes applied.

## 5. Terraform Validation
terraform fmt / validate / plan executed – no changes.

## 6. Frontend Integration Contract for Jo's Team

User Pool ID: eu-central-1_ojbmoiYGM
Client ID: 7ldhihlpdgsgcl3puvu4oi7ksv
Region: eu-central-1
Domain: https://auth.mays-job-matcher.app

Required signup attributes:
- Username
- Password
- UserAttributes.email mandatory

Confirmation:
- Email verification mandatory via Cognito auto_verified_attributes
- ConfirmSignUp required
- ResendConfirmationCode supported

OAuth:
- Client supports Authorization Code + PKCE
- AllowedOAuthFlows: code
- Scopes: email, openid, profile
- Callback URLs configured:
  http://localhost:5173/auth/callback
  https://mays-job-matcher.vercel.app/auth/callback
  https://www.mays-job-matcher.app/auth/callback

Cognito endpoints:
- SignUp: https://cognito-idp.eu-central-1.amazonaws.com/
- Hosted UI: https://auth.mays-job-matcher.app

## 7. Git
No Terraform changes. Reports updated.

Status GREEN for backend readiness.
