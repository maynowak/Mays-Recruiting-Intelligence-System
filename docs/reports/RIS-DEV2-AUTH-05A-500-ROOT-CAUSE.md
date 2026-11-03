# RIS-DEV2-AUTH-05A — HTTP-500 Root Cause

**Date:** 2026-11-03  
**Branch:** `feature/ris-application-persistence-v1`  
**Environment:** `ris-dev2` / `eu-central-1`

## Result

```text
ROOT CAUSE VERIFIED — LOCAL FIX APPLIED
```

The environment guard passed: account `262370457690`, region `eu-central-1`,
state serial `25`, and the expected state lineage were unchanged. No Terraform
operation, AWS deployment, partner provisioning, credential issuance, or
infrastructure mutation was performed.

## Failure chain

The previous live smoke test used a valid Cognito Human access JWT without a
RIS PartnerApplication/APIProfile/Credential binding. The request reached the
Lambda, but ApplicationV1 dispatch called:

```python
_handle_application_routes(event, context, method, path)
```

No function with that name exists. The implemented dispatcher target is:

```python
_application_routes(event, context, method, path)
```

This `NameError` occurred before `_application_ctx()` and therefore before the
existing `_partner_profile_context()` dual-auth boundary could evaluate the
missing credential, registry binding, tenant, or owner context. The unhandled
exception became HTTP 500. The missing partner binding was the triggering
test condition, but not the direct exception cause.

## Boundary distinction

1. **API Gateway JWT authentication:** valid in the prior PKCE evidence; the
   JWT signature, issuer, access-token use, client and subject were verified.
2. **RIS partner authorization:** was not established because no authorized
   binding existed.
3. **Tenant/owner resolution:** was never reached on the old ApplicationV1
   path because dispatch failed first.
4. **ApplicationV1 handler:** was never reached on the old path.
5. **HTTP translation:** no controlled authorization response was possible
   because the `NameError` escaped dispatch.

## Fix

The dispatcher now calls `_application_routes`. The existing authorization
boundary remains the only path; no bypass or parallel authorization mechanism
was introduced.

Additionally, malformed `X-Api-Credential` values are rejected before
introspection-store construction with the existing neutral 401 contract. A
structurally valid credential with unavailable backend stores still maps to
503, preserving the distinction between invalid input and service failure.

## Regression evidence

- `tests/test_application_auth_boundary.py`: dispatch reaches the boundary
  without 500; missing and malformed credentials are controlled 401 responses.
- Focused auth/application/tenant/contract run: **53 passed, 7 subtests passed**.
- Existing credential/machine/application E2E run: **90 passed**.

The code change is local only. It is not evidence of an AWS Lambda deployment;
AWS deployment remains unauthorized.
