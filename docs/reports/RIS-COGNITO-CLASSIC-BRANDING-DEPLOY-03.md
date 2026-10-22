# RIS-COGNITO-CLASSIC-BRANDING-DEPLOY-03

**Status:** DEPLOYED & VERIFIED
**Date:** 2026-10-22
**Scope:** Cognito Classic Hosted UI Branding Deployment

## 1. Inspection
Existing UI customization empty.
ManagedLoginVersion 1, Classic UI.

## 2. CSS Validation
Used supported Classic UI selectors:
.background-customizable
.submitButton-customizable
.idpButton-customizable
.inputField-customizable
.label-customizable

## 3. Deployment
Command executed:
aws cognito-idp set-ui-customization --user-pool-id eu-central-1_ojbmoiYGM --client-id 7ldhihlpdgsgcl3puvu4oi7ksv --css ...

CSSVersion: 20261022081324

## 4. Verification
get-ui-customization confirms CSS applied.

## 5. Testing
Login, Signup, Forgot Password pages render with branding colors.
Desktop and mobile appearance preserved.

## 6. Preservation
User Pool, App Client, Domain, OAuth callbacks unchanged.

## 7. Documentation
Deployed CSS:
.background-customizable{background-color:#0A1931!important;}
.submitButton-customizable{background-color:#7B2CBF!important;color:#fff!important;}
.idpButton-customizable{background-color:#00C9A7!important;color:#fff!important;}
.inputField-customizable{border-color:#00C9A7!important;}
.label-customizable{color:#E6E8F0!important;}

Status GREEN.
