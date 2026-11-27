# Separate Fix Request — OpenAPI APIProfile Binding Route

**Owner:** RIS API / OpenAPI contract maintainers (not Mays-Orders).
**Status:** `OPEN / REQUIRED`; confirmed during 19F3, not changed within the Mays
QA blocker-resolution scope.

## Finding

The canonical route inventory, Terraform API Gateway, and Lambda dispatcher
declare `POST /v1/apiprofiles/{apiProfileId}/binding`, but
`docs/api/openapi-platform.yaml` has no corresponding operation. Three existing
tests correctly fail on this single discrepancy:

- `TestCoverageOfTerraformRoutes.test_every_terraform_route_is_documented`
- `TestOpen3ImperativeRoutes.test_terraform_routes_are_not_marked_imperative`
- `TestDispatcherCoverageAndExceptions.test_reachable_dispatcher_branches_are_documented`

## Evidence

- `terraform/modules/api/main.tf`: route uses JWT authorization and the existing
  API integration.
- `lambda/handler.py::_handle_apiprofile_binding`: POST handler is admin-only;
  issuer comes from the verified JWT; partner is checked against the
  authoritative registry; request fields are `partnerApplicationId` and
  `reason`; success is 200.
- `docs/API/API-STANDARD.md`: route is documented as JWT (admin), 200, with
  400/403/404 errors.
- `tests/test_apiprofile_management_http.py`: local route behavior and auth tests
  already exist.
- `tests/test_platform_openapi_contract.py`: the existing gate establishes the
  OpenAPI omission. No test weakening is warranted.

## Required follow-up

Add the matching OpenAPI operation with the existing security scheme, exact
request/response schemas and error semantics; preserve admin authorization and
verified-issuer/partner-binding behavior. Run the three failing assertions, all
of `test_platform_openapi_contract.py`, and relevant APIProfile HTTP/auth tests.
Do not add or alter runtime routes as part of this documentation fix unless a
separate runtime finding is established. No deployment or AWS action is implied.
