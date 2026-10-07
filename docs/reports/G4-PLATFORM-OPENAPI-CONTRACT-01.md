# G4-PLATFORM-OPENAPI-CONTRACT-01

Creates the canonical machine-readable OpenAPI contract for the Mays-RIS
Platform API, closing **OPEN-1**.

Base: `1207eff` · **Status: GREEN** · **OPEN-1: CLOSED**

---

## W1 — ROUTE INVENTORY (METHOD + PATH)

Four independent sources reconciled. No path-only matching anywhere.

| Source | Count |
|---|---|
| Terraform declarations | **33** |
| Live API Gateway (`aboqolpm0f`) | **36** |
| OpenAPI operations authored | **36** |
| Difference (live − Terraform) | **3** = the OPEN-3 document routes |

**Reconciliation: 33 Terraform + 3 OPEN-3 = 36 live = 36 spec.** No
unexplained mismatch. Every live route was checked against both the
Terraform declaration and the corresponding dispatcher branch.

### Classification

| Class | Count | Detail |
|---|---|---|
| Terraform-managed | 33 | all `authorization_type: JWT` except `GET /health` (`NONE`) |
| Imperatively live / OPEN-3 | 3 | `POST /me/documents`, `GET /me/documents/{docId}`, `DELETE /me/documents/{docId}` |
| Code-only / unreachable (OPEN-5) | 8 branches over 3 prefixes | `/api/agents`, `/work`, `/me/jobsearches` |
| Live-only drift | **0** | — |

### Authoring error caught by the reconciliation

The first draft contained `PATCH /v1/offers/{offerId}/status` and omitted
`PATCH /v1/offers/{offerId}` and `POST /v1/offers/{offerId}/status`. The spec
had 35 operations against 36 sources. The discrepancy was detected by
diffing against `terraform_routes()` before any test was written, and
corrected against the Terraform source. Recorded because it is exactly the
class of error the contract tests now prevent.

## W2 — HANDLER CONTRACT

Taken from handler source, not inferred from route names.

| Operation | Success | Errors | Auth |
|---|---|---|---|
| `GET /health` | 200 | — | **NONE** |
| `GET /platform` | 200 | 401 | JWT |
| `GET /me` | 200 | 401 | JWT |
| `GET /me/profile` | 200 | 401, 404 | JWT |
| `POST /me/profile` | 201 | 400, 401, 409, 500 | JWT |
| `PUT /me/profile` | 200 | 400, 401, 404, 500 | JWT |
| `DELETE /me/profile` | **204** | 401, 404, 500 | JWT |
| `POST /me/documents` | 200 | 400, 401, 500 | JWT |
| `GET /me/documents/{docId}` | 200 | 400, 401, 404, 500 | JWT |
| `DELETE /me/documents/{docId}` | 200 `{deleted, docId}` | 400, 401, 404, 500 | JWT |
| `GET /agents` | 200 | 401 | JWT |
| `GET /v1/introspection` | 200 | 401, 404, 503 | JWT + `X-Api-Credential` |
| `POST /v1/m2m/agents/{agentId}/execute` | 202 | 400, 401, 403, 500, 503 | JWT + `X-Api-Credential` |
| `/orders*` (4) | 200 | 400 (`ErrorObject`) | JWT |

Verified specifics rather than assumed:

- `DELETE /me/profile` returns **204**, not 200 — `handler.py:658`.
- `DELETE /me/documents/{docId}` returns **200** with `{deleted, docId}` —
  different from profile deletion. The spec keeps them distinct.
- `POST /me/profile` uses a conditional write → 409.
- `GET /agents` filters by `is_executable_status` and entitlement validity.

## W3 — SCHEMAS / ERROR ENVELOPES

### OPEN-2 — both envelopes represented honestly

| Family | Shape | Source of truth |
|---|---|---|
| `ErrorString` | `{"error": "<string>"}` | agent/platform Lambda — **77 occurrences** in `lambda/handler.py` |
| `ErrorObject` | `{"error": {"code", "message", "details"?}}` | orders-reader Lambda — `_err()` at `orders_reader.py:88` |

They are structurally distinct (`string` vs `object`) and the contract tests
assert that every `/orders*` operation declares `x-error-envelope:
ErrorObject` and no agent operation does. **Nothing was unified** — that
remains an open design item.

### Domain objects

`HealthResponse`, `PlatformResponse`, `UserContext`, `UserProfile` +
`UserProfileWritable`, `DocumentUploadTicket`, `DocumentDownloadTicket`,
`Agent`, `ApiProfile`, `Credential` + `CredentialIssued`,
`IntrospectionResponse`, `Offer`, `GrantResult`, `WorkAccepted`, `Order`.

`UserProfileWritable` is `additionalProperties: false` with exactly the three
mutable v1 fields, matching the Gate 12 field policy. `Order` omits the
persistence-internal fields that `INTERNAL_FIELDS` strips
(`pk, sk, gsi1pk, gsi1sk, version, isTestData`) — verified as absent from
`properties`. `CredentialIssued.secret` is `writeOnly: true`.

## W4 — THE SPECIFICATION

```
docs/api/openapi-platform.yaml
openapi: 3.0.3
operations: 36   (unique operationIds: 36/36)
```

Placed in `docs/api/` next to `API-STANDARD.md`. `jobsearch/openapi.yaml` is
**untouched** — it describes an external service, as OPEN-1 recorded.

Per-route vendor extensions carry the governance status explicitly:

```yaml
x-infrastructure-governance: terraform-managed | imperative-open-3
x-error-envelope: ErrorObject        # orders routes only
x-serving-lambda: mays-ris-dev-orders-reader
x-deletion-scope: USER_PROFILE_TABLE-row-only
x-is-account-erasure: false
```

### `DELETE /me/profile` contract

Documented as **profile deletion, not account deletion**, with the retained
stores named in the description (credentials, entitlements, work items,
agent runs, events, job searches, documents). No `requestBody` — identity
comes from the JWT, so a caller cannot select a target.

## W5 — MACHINE CONTRACT TESTS

`tests/test_platform_openapi_contract.py` — **26 tests**.

**The route inventory is REUSED from the canonical P20 helper**
(`terraform_routes`, `handler_dispatch_routes`, `reader_dispatch_routes`,
`IMPERATIVE_ONLY_ROUTES`, `WILDCARD_DISPATCH_PATHS`) rather than
reimplemented, so this suite and the existing P20 route-governance suite can
never disagree. No existing test was weakened; `test_p20_api_contract_consistency.py`
still passes 21/21.

Invariants covered: Terraform coverage; no invented routes; method-level
matching; DELETE-profile semantics; OPEN-3 labelling both directions; OPEN-2
both families; dispatcher coverage with explicit exceptions; unreachable
prefixes absent from the spec.

### Negative controls — all four required, all demonstrated

| Control | Result |
|---|---|
| Remove `DELETE /me/profile` from spec | **8 failed, 18 passed** |
| Change `DELETE` to a different method | **8 failed, 18 passed** |
| Relabel an OPEN-3 operation as Terraform-managed | **1 failed, 25 passed** |
| Remove an OPEN-3 route entirely | **3 failed, 23 passed** |
| Introduce an unclassified invented route | **1 failed, 25 passed** |

**A negative control of mine was itself wrong, and I corrected it rather than
accepting the pass.** My first OPEN-3 relabelling control used
`sed '0,/.../'`, which matched the explanatory prose on line 40 instead of an
operation line, so the spec was never actually altered and the suite passed
26/26. That green result was meaningless. The control was rebuilt to target
an operation line specifically, and it then correctly failed. Recording this
because a vacuously-passing control is the same failure mode as a
vacuously-passing test.

## OPENAPI VALIDATION

No new dependency added. Validation uses `yaml.safe_load` (PyYAML already
required by the suite) plus structural assertions:

```
YAML parse            : OK
openapi version       : 3.0.3
operations            : 36
unique operationIds   : 36 / 36
distinct $refs        : 30
unresolved $refs      : NONE
external $refs        : NONE
```

## CROSS-REVIEW

| Reviewer | Verdict | Evidence |
|---|---|---|
| R1 Architecture | **GREEN** | 0 references to `/me/jobsearches`, `/work`, `/api/agents` — unreachable code is not advertised; 36 == 36 reconciliation |
| R2 Security / Auth | **GREEN** | 35 JWT-protected, exactly 1 unauthenticated (`GET /health`), matching the P20 invariant; credential secret `writeOnly: true` |
| R3 Privacy | **GREEN** | `x-is-account-erasure: false`, `x-deletion-scope: USER_PROFILE_TABLE-row-only`, no `requestBody` on delete, retained stores named |
| R4 Test / Evidence | **GREEN** | 5 negative controls demonstrated; P20 suite unregressed |

One review check initially flagged the `Order` schema as leaking internal
fields. That check was naive — the field names appear in the description to
explain that they are stripped. Verified directly against `properties`: no
internal field is exposed.

## FULL REGRESSION

```
collected 1146   passed 1138   failed 0   skipped 8   warnings 236
```

Baseline 1120 → 1146 (+26, all new). Skips remain the 8 AWS-gated ones.
Warning count unchanged.

## EVIDENCE VERIFIER: VERIFIED

| Claim | Verified |
|---|---|
| Terraform routes | 33 |
| Live routes | 36 |
| Spec operations | 36 |
| Reconciliation | 33 + 3 OPEN-3 = 36 ✓ |
| Unclassified mismatches | 0 |
| OPEN-3 explicitly marked | 3, none mislabelled |
| OPEN-2 both families | present, structurally distinct, correctly attributed |
| `$ref` resolution | 30/30 resolve, none external |
| operationId uniqueness | 36/36 |
| Contract tests | 26 passed |
| Negative controls | 5/5 demonstrated |
| Full regression | 1138 passed, 0 failed |

## NEW FINDINGS

1. **Authoring error caught pre-test** — `PATCH /v1/offers/{offerId}/status`
   was invented; corrected to `PATCH /v1/offers/{offerId}` +
   `POST /v1/offers/{offerId}/status`.
2. **Two of my own test bugs** — the orders-reader comparison used strings
   against a tuple-keyed set, and the OPEN-5 prefix assertion compared a
   string against a set of tuples. Both fixed; neither masked a spec defect.
3. **A negative control that could not fail** — see W5.
4. **Spec is now a third governance consumer** of the canonical route
   inventory, alongside the P20 Terraform suite and the OpenAPI suite. All
   three share one helper, so they cannot disagree.

## NEXT PACKAGE RECOMMENDATION

**Privacy cascade / erasure.** This is now the sharpest remaining gap, and
G4 made it more visible rather than less: the spec now states plainly that
`DELETE /me/profile` retains credentials, API profiles, entitlements, work
items and documents. That machine-readable statement is currently stronger
than the implementation warrants as a *user-facing* capability — a caller
reading the contract has no way to achieve account erasure at all.

It should be scoped as: decide whether cascade deletion is in scope at all;
if yes, define its authorization model (does deleting a profile revoke
machine credentials? what happens to in-flight work items?) and its
idempotency; if no, say so explicitly in the spec rather than leaving the
gap implicit.

Two carried-forward items, neither urgent:

- **OPEN-2 error-envelope unification** is now precisely specified in two
  places, which makes it a well-defined candidate for a future package.
- The 3 OPEN-3 document routes remain unmanaged by Terraform. They are
  documented honestly, but `terraform apply` still does not own them.