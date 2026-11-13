# RIS-STRUCTURED-CV-API-ROUTES-01

**Status:** `API ROUTES IMPLEMENTED / LOCAL VERIFIED / DEPLOYMENT BLOCKED`

**Date:** 2026-11-13

**Branch:** `feature/ris-structured-cv-api-routes-01`

**Baseline:** preflight `2371fbb`

## 1. Scope

Added only the missing API Gateway routes for the existing Structured-CV
backend. No repository contract, handler behavior, consent state, IAM, Cognito,
CloudFront, DNS or existing PDF/search-profile route was changed.

## 2. Routes added

All routes use the existing Lambda proxy integration and the existing human JWT
authorizer:

| Method | Path |
|---|---|
| GET | `/v1/partner/me/cv-builder-profiles` |
| POST | `/v1/partner/me/cv-builder-profiles` |
| GET | `/v1/partner/me/cv-builder-profiles/{profileId}` |
| PATCH | `/v1/partner/me/cv-builder-profiles/{profileId}` |
| DELETE | `/v1/partner/me/cv-builder-profiles/{profileId}` |
| GET | `/v1/partner/me/cv-builder-profiles/{profileId}/export` |

No wildcard, `ANY` or `{proxy+}` route was added. The export route has the same
JWT/proxy integration and remains hidden behind the default-off feature flag.

## 3. Security and activation

- Authorizer: `aws_apigatewayv2_authorizer.jwt.id` on every route.
- Lambda's existing `_partner_profile_context` still enforces the partner
  credential and server-derived identity.
- `STRUCTURED_CV_PROFILE_ENABLED` remains `false` by default in Lambda and
  Terraform.
- Routes do not consent to storage; RIS's consent gate remains authoritative.
- Existing CV, search-profile, consent and privacy routes are unchanged.

## 4. Contract inventory

- `docs/api/API-STANDARD.md` now documents all six methods with JWT +
  `X-Api-Credential`.
- `tests/test_p20_api_contract_consistency.py`: route inventory adjusted from
  74/70 to **80/76** with explicit checks for all six routes; the former
  feature-flag allowlist was removed because the routes are now declared.
- New `tests/test_structured_cv_api_routes.py`: six explicit routes, JWT,
  integration, no wildcard/proxy, default-off flag and fixed dispatcher.
- Existing partner-profile route harness remains green.

## 5. Local evidence

```text
pytest tests/test_structured_cv_api_routes.py \
       tests/test_p20_api_contract_consistency.py \
       tests/test_partner_profile_integration_harness.py
64 passed, 343 subtests passed

terraform fmt -check -recursive terraform          PASS
terraform init -backend=false                     PASS
terraform validate                                PASS (deprecation warnings)
```

No AWS plan, apply, state access, API call, Cognito/CloudFront/DNS mutation or
real CV write was performed.

## 6. Remaining blockers

- The route change requires a reviewed AWS plan and explicit G4/G6 approval.
- Real DynamoDB GSI/transaction verification is still pending.
- C2B product activation remains blocked by legal/privacy notice and consent
  approval.
- Real authenticated live E2E is not executed.

## 7. Commit

Committed on `feature/ris-structured-cv-api-routes-01`.
