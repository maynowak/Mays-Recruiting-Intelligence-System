# RIS-COGNITO-MANAGED-LOGIN-DESIGN-01

**Status:** ANALYZE
**Date:** 2026-10-22
**Scope:** Cognito User Pool eu-central-1_ojbmoiYGM, Domain auth.mays-job-matcher.app

## 1. Current Cognito Feature Plan
User Pool `ris-dev-dev-users` eu-central-1_ojbmoiYGM
- Status: ACTIVE
- ManagedLoginVersion: 1
- Custom Domain: auth.mays-job-matcher.app ACTIVE
- Certificate ARN: arn:aws:acm:us-east-1:240571105849:certificate/0bfb2603-a919-4b06-b4b9-da246c4edf75
- CloudFront Distribution: d1xd3gat3vr3ss.cloudfront.net
- AutoVerifiedAttributes: ["email"]
- Email verification: CONFIRM_WITH_CODE

Feature plan: Standard Cognito User Pool. No Advanced Security Features enabled. Free tier applicable for <50k MAUs.

## 2. Costs of Managed Login
Cognito Hosted UI and Managed Login UI are included in base User Pool pricing.
- First 50k MAUs free
- $0.0055 per MAU beyond 50k
- No additional cost for custom domain with ACM certificate
- No paid Managed Login upgrade required for current version.

## 3. Domain Branding Version
ManagedLoginVersion: 1
Current UI uses classic Hosted UI. Branding customization limited to logo, CSS via Cognito User Pool domain branding settings. No custom branding resource applied.

## 4. Impact on Existing App Clients
Clients in pool:
- ris-dev-dev-client 7ldhihlpdgsgcl3puvu4oi7ksv
  ExplicitAuthFlows: ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH
  AllowedOAuthFlows: code
  Callback URLs: localhost:5173, mays-job-matcher.vercel.app, www.mays-job-matcher.app
- ris-dev-dev-m2m-client

Changes to User Pool UI or branding do not replace pool or client. Existing clients remain functional.

## 5. Email-required Signup Options
Options:
A. Frontend validation only – safe, no backend change
B. Pre Sign-up Lambda enforcing email present/format – safe, no schema change
C. Make email required in schema – not feasible due to lifecycle ignore_changes and potential migration impact

Recommended: Frontend enforcement + optional Pre Sign-up Lambda with impact review.

## 6. Preserve Users and Admin Access
No changes to User Pool or clients. Existing users retained. AdminCreateUser unaffected.

## 7. Mays-Jobsearch Branding Concept
Safe options without infrastructure change:
- Custom domain already branded auth.mays-job-matcher.app
- Logo upload via Cognito console
- Custom CSS limited
- No new paid resources

## 8. Future Google Identity Provider
Terraform module supports Google IdP via google_client_id/google_client_secret variables.
Currently disabled. Enabling requires credentials and redirect URI updates. No pool replacement needed.

## 9. Safe Implementation Options
- Keep ManagedLoginVersion 1
- No User Pool replacement
- No domain change
- Use frontend validation for email mandatory
- Optional Pre Sign-up Lambda with dry-run

Status GREEN for analysis, no deployment.
