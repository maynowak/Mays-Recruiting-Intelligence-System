# RIS-JOBSEARCH-COGNITO-SIGNUP-FIX-01

**Status:** ANALYZE → IN PROGRESS
**Date:** 2026-10-21
**Scope:** Cognito Registration/Signup für User Pool eu-central-1_ojbmoiYGM, Human Client 7ldhihlpdgsgcl3puvu4oi7ksv

## 1. Analyse aktueller Registration

### User Pool
- User Pool ID: eu-central-1_ojbmoiYGM
- Name: ris-dev-dev-users
- AutoVerifiedAttributes: ["email"]
- Schema email: AttributeDataType String, Required false, Mutable true
- custom:tenant_id existiert, Required false
- AdminCreateUserConfig.AllowAdminCreateUserOnly: false
- AccountRecoverySetting: verified_email Priority 1
- SignInPolicy AllowedFirstAuthFactors: ["PASSWORD"]

### Human App Client 7ldhihlpdgsgcl3puvu4oi7ksv
- ClientName: ris-dev-dev-client
- CallbackURLs:
  http://localhost:5173/auth/callback
  https://mays-job-matcher.vercel.app/auth/callback
  https://www.mays-job-matcher.app/auth/callback
- LogoutURLs: entsprechend
- AllowedOAuthFlows: ["code"]
- AllowedOAuthScopes: ["email","openid","profile"]
- ExplicitAuthFlows: ["ALLOW_REFRESH_TOKEN_AUTH","ALLOW_USER_PASSWORD_AUTH"]
- ReadAttributes: null
- WriteAttributes: null
- SupportedIdentityProviders: ["COGNITO"]

### Befund
ExplicitAuthFlows enthält **kein ALLOW_USER_SIGN_UP**. Hosted UI Sign-Up ist damit deaktiviert. Das erklärt "An error was encountered with the requested page." beim Aufruf der Sign-Up URL.

E-Mail ist im Schema nicht Required. AutoVerifiedAttributes enthält email, also wird E-Mail bei Vorhandensein verifiziert.

### Terraform Fund
File `terraform/modules/cognito/main.tf:67-70` defines `explicit_auth_flows` without `ALLOW_USER_SIGN_UP`.
User Pool schema lifecycle ignore_changes = [schema] prevents Terraform from making email required.
No Pre Sign-up Lambda is configured.

## 2. Erforderlicher Signup Vertrag
- Username + Email + Password Pflicht
- Email Verification mandatory
- Kein Auto-Confirm

## 3. Nächste Schritte
- Client ExplicitAuthFlows um ALLOW_USER_SIGN_UP erweitern
- Email-Pflicht sicherstellen: Option A Pre Sign-up Lambda, Option B Schema Anforderung
- Frontend /auth/callback und Signup Flow prüfen

## 4. Terraform Governance
Kein Destruktiver Change geplant. Client Update ist in-place.

## 5. Offene Punkte
- Frontend Integration prüfen
- Pre Sign-up Lambda Implementierung
- Tests ergänzen

---
Erstellt 2026-10-21
