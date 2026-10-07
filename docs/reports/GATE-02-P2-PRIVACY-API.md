# P2 — PRIVACY / API GOVERNANCE

Package owner: OWNER-P2. Started from verified state `dfbd1c9`.
Route decision: **OPTION 1 APPROVED** — add the Terraform route.

Status: **GREEN** (local). Not deployed.

---

## P2A — TERRAFORM ROUTE

`terraform/modules/api/main.tf` gains one resource:

```hcl
resource "aws_apigatewayv2_route" "profile_delete" {
  api_id             = aws_apigatewayv2_api.ris_api.id
  route_key          = "DELETE /me/profile"
  target             = "integrations/${aws_apigatewayv2_integration.lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}
```

Reuses the **existing** integration and the **existing** JWT authorizer. No
second integration, no new authorizer, consistent with the `introspection`
route precedent already in the file.

Verification (with `--profile mayaws`; the default profile fails on backend
init):

```
terraform fmt -check -recursive   → clean
terraform validate                → Success! (deprecation warnings pre-existing)
```

`validate` with the **default** profile fails during backend init
(`AccessDeniedException` on `mays-ris-tf-lock`) — the recurring wrong-profile
trap, not a config error.

## P2B — METHOD-LEVEL ROUTE GOVERNANCE (real governance defect)

### The defect

`test_every_dispatch_branch_has_a_live_route` compared **paths only**. Adding
`DELETE /me/profile` to the handler passed, because `/me/profile` was already
"live" via GET/POST/PUT. A dispatcher branch with no reachable route was
therefore classified as live.

This is how a privacy endpoint shipped unreachable without any test noticing.

### Fix

New `handler_dispatch_routes()` returns **(METHOD, PATH)** pairs parsed from
`_handle_api_event`, instead of bare path literals. Branches without a method
condition (`/v1/offers`, `/v1/apiprofiles`) become `('*', path)` wildcards.
`path == '/x'` and `path.startswith('/x/')` are normalised to `/x` to avoid
phantom duplicates.

Three tests added:

| Test | Purpose |
|---|---|
| `test_method_is_part_of_route_identity` | negative control: `GET /me/profile` must not cover `DELETE /me/profile` |
| `test_no_unreachable_method_branch_on_live_paths` | generic sweep of the whole failure class |
| `test_every_dispatch_branch_has_a_live_route` | rewritten to (METHOD, PATH) |

`test_terraform_route_reaches_its_handler` was also tightened to prefer exact
(METHOD, PATH) matches, keeping the legacy prefix heuristic only as fallback.

### Negative control (verified, not asserted)

With the Terraform route removed:

```
FAILED ...test_route_count_is_32_terraform_35_live
FAILED ...test_documented_routes_exist_in_terraform_or_are_open
FAILED ...test_method_is_part_of_route_identity
3 failed, 18 passed
```

Route restored → 21 passed. The tests genuinely detect the condition.

### OPEN-3 documents routes — inspected, not silently misclassified

`POST /me/documents`, `GET|DELETE /me/documents/{docId}` are live in the
gateway but in no `.tf` file. Under method-level governance these are now
matched **by exact method** against `IMPERATIVE_ONLY_ROUTES`. They remain
documented as OPEN-3 — still absent from Terraform, still unmanaged by
`apply`. The new tests did not accidentally reclassify them as
Terraform-managed, and did not break their existing coverage.

## P2C — ROUTE COUNT (deliberate, evidence-based)

The old docstring claimed `18 Basis + 7 offers + 4 orders-reader = 29`, which
was already inconsistent with the asserted 32. Counted from
`terraform_routes()` instead of trusting either number:

| Group | Count |
|---|---|
| agent routes | **29** |
| orders-reader routes | **4** |
| **terraform declarations** | **33** |
| imperative documents routes (OPEN-3) | 3 |
| total live | 36 |

The assertion now pins **33** *and* the 29/4 split, plus the presence of
`DELETE /me/profile` itself — so a silent reversion of the route cannot pass.
This is not a magic-number bump: the breakdown was measured.

## P2D — OPENAPI

**Deliberately NOT created.** `docs/api/API-STANDARD.md` OPEN-1 records that
the only OpenAPI artifact (`jobsearch/openapi.yaml`) describes an external
service and covers no platform route.

Writing a platform OpenAPI spec would be a substantial new surface — 33 routes,
two different error envelopes (agent uses `{"error": "<string>"}`,
orders-reader uses `{"error": {"code","message"}}`, see OPEN-2), and
auth differences per route. A partial spec covering only `/me/profile` would
imply a canonical contract that does not exist, and a full one is a project in
itself requiring decisions about error schema unification that OPEN-2
explicitly defers.

`DELETE /me/profile` is documented in the canonical table with real status
codes (204 / 401 / 404 / 500). That is the same documentation standard every
other route currently meets. OPEN-1 stays open and honest.

## P2E — PRIVACY LIFECYCLE MATRIX

| Store | Owner key | Relation to profile | Action on `DELETE /me/profile` | Implemented? |
|---|---|---|---|---|
| `USER_PROFILE_TABLE` | `userId` | is the profile | **DELETE** | yes |
| `API_PROFILES_TABLE` | `apiProfileId`, GSI `userId` | owned by user | **RETAIN** | no |
| `CREDENTIALS_TABLE` | `credentialId`, GSI `apiProfileId` | via api profile | **RETAIN** | no |
| `ENTITLEMENTS_TABLE` | GSI `userId` | user-wide grants | **RETAIN** | no |
| `WORK_ITEMS_TABLE` | `workId` | `requestedBy` | **RETAIN** | no |
| JobSearch records | `jobSearchId` | user-owned | **RETAIN** | no |
| Documents (S3) | `tenant/{t}/users/{sub}/documents/{uuid}` | owned by user | **RETAIN** | no |
| Agent state / catalog | `agentId` | not user-owned | unaffected | n/a |
| Orders references | `orderId` | external system, `RealMaysOrdersAdapter` | unaffected | n/a |

**`DELETE /me/profile` = PROFILE DELETION. It is NOT account deletion and NOT
personal-data erasure.** Only the row in `USER_PROFILE_TABLE` is removed.
Credentials and API profiles — which together constitute the user's access
surface — survive. This is stated in the Terraform comment and in the API
table entry so it cannot be misread later.

No retention durations are asserted. Nothing in the repository defines a
statutory period, so none is invented. Extending deletion to credentials,
entitlements, work items, job searches and documents is real privacy work that
needs its own gate and its own authorization decisions (e.g. whether deleting
a profile must cascade to machine credentials, and what happens to in-flight
work items).

## TESTS

```
tests/test_p20_api_contract_consistency.py    21 passed  (was 19)
tests/test_profile_deletion.py                 8 passed
FULL SUITE  1085 collected / 1077 passed / 0 failed / 8 skipped / 208 warnings
```

Baseline moved 1083 → 1085 collected (+2, the two new governance tests).

## FILES CHANGED

- `terraform/modules/api/main.tf` — `profile_delete` route
- `docs/api/API-STANDARD.md` — route row + (METHOD, PATH) invariant
- `tests/test_p20_api_contract_consistency.py` — method-level governance

## NOT DONE

- No deploy (per instruction). The route is not live yet; the drifted Lambda
  is untouched.
- No platform OpenAPI (reasoning above).
- No cascade deletion beyond the profile row.