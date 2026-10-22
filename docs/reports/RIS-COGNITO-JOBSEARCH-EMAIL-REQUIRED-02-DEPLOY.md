# RIS-COGNITO-JOBSEARCH-EMAIL-REQUIRED-02-DEPLOY

**Status:** DEPLOYED
**Date:** 2026-10-22
**Scope:** Isolated Cognito User Pool for Mays-Jobsearch with email required

## Deployment Summary

Deployed isolated Cognito User Pool for Mays-Jobsearch with email as username, mandatory email verification, self-registration enabled, OAuth Authorization Code + PKCE, separate authentication domain.

Existing RIS User Pool eu-central-1_ojbmoiYGM and domain auth.mays-job-matcher.app preserved.

## Resources Created

### User Pool
- **Pool Name:** ris-dev-jobsearch-dev-users
- **Pool ID:** eu-central-1_ZURSMpD2O
- **ARN:** arn:aws:cognito-idp:eu-central-1:240571105849:userpool/eu-central-1_ZURSMpD2O
- **Username Attributes:** email
- **Auto Verified Attributes:** email
- **Email Required:** true (schema required)
- **Self-registration:** enabled (AllowAdminCreateUserOnly=false)
- **Password Policy:** MinimumLength=8, RequireUppercase=false, RequireLowercase=false, RequireNumbers=false, RequireSymbols=false
- **Email Verification Subject:** Verify your email for Mays Jobsearch
- **Email Verification Message:** Your verification code is {####}

### App Client
- **Client Name:** ris-dev-jobsearch-dev-client
- **Client ID:** 5hb3f6dj5ialg77jf4blur9g6g
- **Generate Secret:** false (public client)
- **Allowed OAuth Flows:** code
- **Allowed OAuth Flows User Pool Client:** true (PKCE enabled)
- **Allowed OAuth Scopes:** openid, email, profile
- **Callback URLs:**
  - http://localhost:5173/auth/callback
  - https://mays-job-matcher.vercel.app/auth/callback
- **Logout URLs:**
  - http://localhost:5173/
  - https://mays-job-matcher.vercel.app/

### User Pool Domain
- **Domain Prefix:** ris-dev-jobsearch-dev
- **Domain URL:** https://ris-dev-jobsearch-dev.auth.eu-central-1.amazoncognito.com
- **Status:** ACTIVE
- **Managed Login Version:** 1

### JWT Issuer
- **Issuer:** https://cognito-idp.eu-central-1.amazonaws.com/eu-central-1_ZURSMpD2O

## Verification

Commands executed:
- aws cognito-idp describe-user-pool --user-pool-id eu-central-1_ZURSMpD2O
- aws cognito-idp describe-user-pool-client --user-pool-id eu-central-1_ZURSMpD2O --client-id 5hb3f6dj5ialg77jf4blur9g6g
- aws cognito-idp describe-user-pool-domain --domain ris-dev-jobsearch-dev

All resources verified ACTIVE.

## Preservation Checks

Existing resources untouched:
- User Pool eu-central-1_ojbmoiYGM (ris-dev-dev-users)
- Domain auth.mays-job-matcher.app

## Cost Impact

Cognito free tier applies. No additional charges for user pool domain prefix.

## Notes

- No client secret created.
- Email verification mandatory via AutoVerifiedAttributes.
- Domain is separate from existing RIS domain.
