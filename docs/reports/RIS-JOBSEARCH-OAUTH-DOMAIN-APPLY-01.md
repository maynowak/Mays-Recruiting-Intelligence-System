# RIS-JOBSEARCH-OAUTH-DOMAIN-APPLY-01

**Modus:** APPLY (mit Freigabe) + Verification  
**Datum:** 2026-10-21  
**Account:** 240571105849 (eu-central-1) · **Workspace:** ris-dev  
**Basis-Plan:** RIS-JOBSEARCH-OAUTH-DOMAIN-FIX-01 (HEAD 1f6871c)

## 1. Preflight
- Git HEAD: `1f6871c` (clean)
- Workspace: `ris-dev`
- State: unverändert zum geprüften Plan

## 2. Geplante Änderungen geprüft
Plan vor Apply: **0 to add, 5 to change, 0 to destroy**
- Lambda filename/last_modified Diffs nur kosmetisch (relativer/absoluter Pfad) → kein Code-/Runtime-Config-Update
- Keine Replacements/Destructions
- Keine Änderungen an M2M-Client, Orders, DynamoDB, IAM-Neuaufbau, CloudFront

## 3. Apply
Ausgeführt via Terraform (Backend S3/DynamoDB):
- `module.cognito.aws_cognito_user_pool_client.client` — **Modifications complete**
- `module.api.aws_apigatewayv2_api.ris_api` — **Modifications complete**
- `module.health_plane.aws_lambda_function.health_writer` / `health_publisher` — Modifications complete
- `module.orders_reader.aws_lambda_function.reader` — Modifications complete

**Ergebnis:** `Apply complete! Resources: 0 added, 5 changed, 0 destroyed.`

## 4. Verifikation (Live)

| Check | Ergebnis |
|---|---|
| Cognito CallbackURLs | `["http://localhost:5173/auth/callback", "https://mays-job-matcher.vercel.app/auth/callback", "https://www.mays-job-matcher.app/auth/callback"]` ✅ |
| Cognito LogoutURLs | `["http://localhost:5173/", "https://mays-job-matcher.vercel.app/", "https://www.mays-job-matcher.app/"]` ✅ |
| API Gateway CORS AllowOrigins | `["https://www.mays-job-matcher.app", "http://localhost:5173", "https://mays-job-matcher.vercel.app"]` ✅ |
| localhost/Vercel erhalten | ✅ |
| M2M-Client unverändert | `ris-dev-dev-m2m-client` ✅ |

## 5. Post-Apply Plan
```bash
terraform plan -var-file=/tmp/ris-dev-tfvars.tfvars
→ No changes. Your infrastructure matches the configuration.
```
**0 to add, 0 to change, 0 to destroy**

## 6. Status
**GREEN** — Änderungen angewendet, verifiziert, Drift behoben.

**AWS Apply:** `EXECUTED` (5 in-place changes)  
**Nächster Schritt:** Phase 3 Frontend-Auth-Implementierung (separater Auftrag)
