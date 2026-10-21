# RIS-JOBSEARCH-COGNITO-SIGNUP-FIX-02

**Status:** ANALYZE → IN PROGRESS
**Date:** 2026-10-21
**Scope:** Cognito Signup Mandatory Email Verification

## 1. Terraform Cleanup

ALLOW_USER_SIGN_UP wurde aus Terraform entfernt. Aktueller Stand `terraform/modules/cognito/main.tf`:
explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH","ALLOW_REFRESH_TOKEN_AUTH"]

Keine Rekreation von User Pool oder App Client.

## 2. User Pool Inspection

User Pool ID: eu-central-1_ojbmoiYGM
- AdminCreateUserConfig.AllowAdminCreateUserOnly: false
- SchemaAttributes email: AttributeDataType String, Required false, Mutable true
- AutoVerifiedAttributes: ["email"]
- LambdaConfig: {}
- ManagedLoginVersion: 1
- Custom Domain: auth.mays-job-matcher.app ACTIVE

App Client 7ldhihlpdgsgcl3puvu4oi7ksv:
- ExplicitAuthFlows: ALLOW_USER_PASSWORD_AUTH, ALLOW_REFRESH_TOKEN_AUTH
- AllowedOAuthFlows: ["code"]
- AllowedOAuthScopes: email,openid,profile
- CallbackURLs korrekt
- ReadAttributes/WriteAttributes null

## 3. Ursache Hosted UI Error

Frontend Signup ist UI-only Placeholder:
- src/components/RegisterForm.tsx: validiert Email/Passwort lokal, kein fetch, kein Cognito
- src/components/LoginForm.tsx: UI-only
- App.tsx Routen /registrieren und /anmelden renderen nur UI-Komponenten

Kein Backend-Wiring zu Cognito. Hosted UI Error entsteht bei manuellem Aufruf der Cognito Hosted UI:
- Client erlaubt kein ALLOW_USER_SIGN_UP
- Email ist im Schema optional
- Kein Pre Sign-up Lambda aktiv

## 4. Frontend Signup Implementierung

RegisterForm sammelt:
- email
- password
- passwordRepeat
- privacy
- terms

Kein Username Feld. Username wird vermutlich per Email.

Formular ist unverbunden, submit setzt nur prepared=true.

## 5. Pre Sign-up Lambda

lambda/pre_sign_up.py existiert:
- Prüft email Anwesenheit und Format
- autoConfirmUser false, autoVerifyEmail false

Integration in Terraform noch offen:
- Lambda execution role
- Cognito invoke permission
- User Pool LambdaConfig PreSignUp trigger

## 6. Nächste Schritte

- Pre Sign-up Lambda in Terraform integrieren
- Terraform fmt/validate/plan
- Frontend an Cognito verdrahten oder Hosted UI nutzen

Status YELLOW – Analyse abgeschlossen, Integration offen
