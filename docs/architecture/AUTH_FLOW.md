# Authentication Flow

## Login
1. User initiates login in Mays-Jobsearch
2. Redirect to Cognito Hosted UI with PKCE
3. Cognito authenticates, returns Authorization Code
4. Jobsearch exchanges code for tokens
5. Access token stored securely, session established

## Registration
1. User initiates registration
2. Redirect to Cognito Hosted UI
3. Email verification required
4. User profile created in RIS after first login

## Token Refresh
Access token expiry → refresh token exchange → new tokens

## Logout
1. Clear local session
2. Redirect to Cognito logout endpoint
3. Global sign-out optional

## API Authorization
Mays-RIS validates JWT issuer, audience, expiry, tenant claim
