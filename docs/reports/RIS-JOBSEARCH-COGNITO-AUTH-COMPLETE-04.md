# RIS-JOBSEARCH-COGNITO-AUTH-COMPLETE-04

**Status:** PLAN → BLOCKED
**Date:** 2026-10-22

## Context
User Pool eu-central-1_ojbmoiYGM, Client 7ldhihlpdgsgcl3puvu4oi7ksv
Frontend React/Vite at https://www.mays-job-matcher.app

## 1. Complete Registration
RegisterForm.tsx currently has username field and Cognito SignUp stub implemented in previous step.
Missing:
- Full error mapping for UsernameExistsException, InvalidPasswordException etc.
- Password not logged
Implementation requires frontend repo commit.

## 2. Email Verification
Confirmation UI not implemented.
Need component for code input, ConfirmSignUp, ResendConfirmationCode handling.

## 3. Login with OAuth PKCE
LoginForm.tsx is UI-only placeholder.
OAuth PKCE implementation requires:
- Authorization URL construction
- code_verifier / code_challenge
- /auth/callback route handling
- Token exchange
- Session storage
Not implemented.

## 4. Server-side Email Requirement
pre_sign_up.py exists.
Terraform integration pending:
- Lambda execution role
- Cognito invoke permission
- User Pool LambdaConfig PreSignUp
Impact assessment needed for other clients.

## 5. Terraform Validation
No changes applied. terraform fmt/validate/plan not run.

## 6. Frontend Deployment
Environment variables VITE_COGNITO_USER_POOL_ID, VITE_COGNITO_CLIENT_ID, VITE_AWS_REGION need verification in Vercel.
RIS_API_KEY must stay server-side.

## 7. Live Verification
Cannot verify without frontend implementation and deployment.

## Blockers
- Frontend repo installer/projects/mays_jobsearch is gitignored in main repo, commits cannot be pushed via current workspace.
- No environment variable verification access.
- OAuth PKCE requires routing changes in App.tsx.

## Success Criteria
Not met.

Status RED/BLOCKED.
