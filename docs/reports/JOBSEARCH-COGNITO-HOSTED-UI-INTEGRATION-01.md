# JOBSEARCH-COGNITO-HOSTED-UI-INTEGRATION-01

**Status:** ANALYSIS & INTEGRATION CONTRACT
**Date:** 2026-10-22

## Cognito Configuration
- Region: eu-central-1
- User Pool: eu-central-1_ZURSMpD2O
- App Client: 5hb3f6dj5ialg77jf4blur9g6g
- Domain: https://auth.mays-job-matcher.app
- OAuth: Authorization Code + PKCE
- Scopes: openid email profile

## 1. Existing Implementation Analysis
Current Jobsearch frontend contains custom RegisterForm.tsx and LoginForm.tsx components.
Auth flow currently uses custom backend validation. No iframe usage detected.
Guest mode is separate and must remain unchanged.

## 2. Hosted UI Integration Approach
- Redirect to Cognito Hosted UI for login/signup: https://auth.mays-job-matcher.app/login?client_id=5hb3f6dj5ialg77jf4blur9g6g&response_type=code&scope=openid+email+profile&redirect_uri=...
- Use Authorization Code + PKCE flow, no client secret in frontend
- Preserve existing navigation and design by keeping app shell, only auth redirects change
- Callback route handles code exchange via backend or PKCE
- Session management via ID token storage in memory, httpOnly cookies recommended
- Logout via Cognito logout endpoint

## 3. OAuth PKCE Integration
Existing PKCE implementation to be reused/verified. Ensure code_verifier generation and code_challenge=s256.

## 4. Email Verification Handling
After registration, user redirected to Hosted UI confirm page. App must handle unconfirmed users: block access until email_verified=true.

## 5. Gastmodus
Unverändert lassen. Gastzugriff ohne Auth.

## 6. Security
Keine Secrets im Frontend. Client ID public, Client Secret nicht verwendet. Redirect URIs whitelisten.

## 7. Testing Checklist
- Login page redirect
- Signup page redirect
- Email verification flow
- Callback handling
- Session persistence
- Logout
- Mobile layout
- Guest mode still works

## 8. RIS Backend Impact
Keine Änderungen am RIS Backend oder AWS Ressourcen ohne gesonderte Freigabe.

Status: Integration contract ready. Frontend changes pending Jo's Team implementation.
