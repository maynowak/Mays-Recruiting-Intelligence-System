# RIS-DEV2-AUTH-05B — Authorization Hardening

## Result

```text
PASS — FAIL-CLOSED APPLICATIONV1 AUTHORIZATION COVERAGE
```

The existing dual-auth boundary was retained. No authentication bypass,
fallback tenant, alternate registry, or direct data access path was added.

## Change

`_partner_profile_context` now rejects a structurally malformed
`X-Api-Credential` before constructing or querying introspection stores. This
uses the existing `valid_secret_format` contract and maps the input to the
neutral 401 response. Structurally valid credentials still proceed through the
existing credential/profile/registry/tenant checks; unavailable stores remain
503 rather than being misreported as invalid credentials.

The ApplicationV1 dispatcher is wired to the existing `_application_routes`
implementation, so authorization runs before repository access and the former
`NameError` cannot escape as HTTP 500.

## Covered cases

| Case | Expected | Verified |
|---|---:|---:|
| Missing JWT/identity | 401 | PASS |
| Invalid/missing credential | 401 | PASS |
| Malformed credential with unconfigured stores | 401 | PASS |
| Unknown well-formed credential | 401 | PASS with configured doubles |
| Inactive partner | 403 | PASS with configured doubles |
| Tenant conflict/no fallback | 403 | PASS with configured doubles |
| Backend/store unavailable | 503 | PASS |
| Application repository reached without authorization | no | PASS by boundary tests |

Responses contain only stable external error text and `code` values
(`unauthorized`, `forbidden`, `unavailable`). Internal exception, credential,
registry and tenant details are not exposed.

## Validation

- Focused auth/application/tenant/contract suite: **53 passed, 7 subtests
  passed** before the additional 05B matrix.
- 05B boundary matrix: **6 passed**.
- Existing credential/machine/application E2E regression: **90 passed**.
- API contract documentation updated in `docs/api/API-STANDARD.md`.

These are local tests only. No AWS Lambda deployment was performed; protected
DEV2 infrastructure remains unchanged.
