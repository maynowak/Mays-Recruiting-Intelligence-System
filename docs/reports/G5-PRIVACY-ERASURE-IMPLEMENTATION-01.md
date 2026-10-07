# G5-PRIVACY-ERASURE-LIFECYCLE-01 (continued) — IMPLEMENTATION

Base for this phase: `0202ec3` · Approved decisions D1–D4 applied.

**Local implementation: complete and GREEN. AWS mutation: NONE — stopped at
the deployment approval gate.**

---

## WHAT WAS BUILT

### D2 — index foundation

Attribute names were read from code, not guessed:

| Table | Attribute | Evidence |
|---|---|---|
| `credentials` | `ownerUserId` | `credentials.py:216` `"ownerUserId": owner` |
| `work_items` | `userId` | `handler.py:2172` `'userId': user_id` |

Naming follows the existing convention exactly — `gsi-owner` (as
`api_profiles`) and `gsi-user` (as `entitlements`/`jobsearches`), both with
`projection_type = "ALL"`. `work_items.gsi-user` adds `range_key = "status"`
so erasure can target non-terminal work without reading terminal history.

`DynamoDBCredentialStore.list_by_owner` was a **full table scan**. It now
queries `gsi-owner`. No scan remains in the erasure path.

#### A propagation bug the index would have exposed

A sparse GSI is useless if the attribute is not written. `_register_processing`
— the worker's own registration path — **omitted the user entirely**. Work
reaching the worker without a pre-written item (the `_create_work` path emits
`requestedBy` but never persists) would have been invisible to any per-user
lookup.

Fixed: registration now normalises `userId`, accepting `requestedBy` as a
fallback because that is what `_create_work` emits.

### D1/D4 — ordered erasure lifecycle

`agents/ecosystem/privacy_erasure.py`. Ordering is the security property:

```
1. revoke credentials      <- capability dies here, first
2. revoke API profiles     <- closes the capability surface
3. cancel non-terminal work
4. delete documents
5. delete profile row      <- keyed by, so last
```

`ErasureResult.complete` is `True` only when **every** step succeeded. A
partial run returns HTTP **207** with per-step `ok` flags. No code path
reports erasure complete while a credential is still live.

D3 respected: non-terminal work (`CREATED/QUEUED/RUNNING/RETRY`) transitions
to `CANCELLED` under `attribute_exists(workId)`. Terminal work is
**retained** — deleting it would remove the `TERMINAL_DUPLICATE_STATES`
suppression and re-admit duplicate execution. No retention duration invented.

Entitlements retained (no capability once credentials are revoked; TTL
governs). Orders untouched (Mays-Orders owns them).

### Public API — separate contract

`POST /me/erasure`, JWT, `x-is-account-erasure: true`.

`POST` rather than `DELETE`: erasure is an ordered, retryable lifecycle, not
an idempotent single-resource delete. No `requestBody`, no parameters — the
target is always the JWT subject, so another user cannot be addressed.

`DELETE /me/profile` is **unchanged in meaning**; a test asserts its handler
imports neither `PrivacyErasure` nor any other table.

`lambda/documents.py::delete_all_for_user` was added for step 4. Keys are
tenant-scoped and the tenant is not itself in the key, so it matches the
user-scoped path suffix; Cognito `sub` is tenant-unique.

---

## OPENAPI

Updated only for behaviour that exists. `ErasureResult` /
`ErasureStepResult` added; `POST /me/erasure` documented with
200/207/401/500/503.

The 26 OpenAPI contract tests and 21 P20 route-governance tests pass
unmodified — they caught the route-count and documentation drift, which was
fixed rather than worked around.

---

## SECURITY ACCEPTANCE

**Previous SECURITY RED → GREEN.**

| Requirement | Test |
|---|---|
| successful erasure leaves no usable credential | `test_no_credential_remains_usable` |
| other users' credentials untouched | `test_other_users_credentials_are_untouched` |
| user A cannot reach user B | `test_user_a_cannot_reach_user_b_data` |
| repeat erasure safe | `test_repeat_erasure_is_safe` |
| partial failure ≠ success | `test_credential_revocation_failure_marks_incomplete` |
| failure still revokes (fail-safe direction) | `test_credentials_still_revoked_when_later_step_fails` |
| in-flight follows D3 | `test_non_terminal_work_is_cancelled_not_deleted`, `test_terminal_work_is_retained_for_idempotency` |
| external ownership intact | `test_orders_are_never_touched` |
| profile delete stays separate | `test_delete_handler_does_not_import_erasure` |

### Negative controls

| Control | Result |
|---|---|
| reorder so profile delete precedes revocation | **1 failed** |
| remove credential revocation entirely | **6 failed** |

Ordering and capability are enforced, not merely documented.

### Evidence-test premise updates

Three G5 premise tests asserted the *absence* of the indexes and of an
erasure endpoint. Those were deliberate guards against documenting
unimplemented capability. They were **inverted, not deleted**:

- index assertions now pin the new index set and assert the scan fallback
  does not return
- the "no erasure endpoint" guard became
  `test_advertised_erasure_matches_implementation`, asserting 207 is
  representable, no target parameter exists, and the documented ordering
  matches the code's first step (regex against source)

---

## FULL REGRESSION

```
collected 1192   passed 1184   failed 0   skipped 8   warnings 236
```

Baseline 1167 → 1192 (+25). No test weakened or disabled.

---

## AWS DEPLOYMENT — APPROVAL GATE REACHED

**STOPPING HERE. No apply performed.**

```
$ terraform plan   (profile mayaws, eu-central-1, account 240571105849)
Plan: 1 to add, 2 to change, 0 to destroy.
```

| Resource | Action | Class |
|---|---|---|
| `module.api.aws_apigatewayv2_route.erasure` | **create** | G5 route |
| `module.dynamodb.aws_dynamodb_table.credentials` | **update in-place** | `+ gsi-owner`, `+ attribute ownerUserId` |
| `module.dynamodb.aws_dynamodb_table.work_items` | **update in-place** | `+ gsi-user`, `+ attribute userId` |

**add 1 · change 2 · replace 0 · destroy 0**

### Safety analysis

- Both table changes are **in-place GSI additions**. DynamoDB supports this;
  it is not a replacement.
- The plan renders `gsi-digest` / `gsi-status` as remove-then-re-add with
  identical definitions — a Terraform **list-reordering artifact**, not a
  semantic change. The `+` side confirms both existing indexes survive.
- **Backfill: none required.** Sparse GSIs populate for existing items
  automatically. Old rows lacking `ownerUserId` / `userId` simply do not
  appear — which is correct, because erasure cannot act on a row that never
  recorded an owner.
- **Rollback:** applying the prior config removes the two GSIs. No data loss
  — GSI removal does not delete items. No row is modified by this
  deployment, so existing credentials keep working throughout.
- **Risk: LOW.** No table replaced, no item rewritten, no IAM or Cognito
  change.

### Two behaviours change only after the Lambda deploy

The route and indexes are inert until the new code ships:
`POST /me/erasure` 404s until the route exists, and
`DynamoDBCredentialStore.list_by_owner` would fail against the old index
set. Both resolve by applying this plan together with the Lambda package,
per the standard `package → plan → apply` contract.

### Post-deploy verification

```
1. aws apigatewayv2 get-routes --api-id aboqolpm0f
     --query "Items[?RouteKey=='POST /me/erasure'].RouteKey"  -> non-empty
2. aws dynamodb describe-table --table-name mays-ris-dev-credentials
     --query 'Table.GlobalSecondaryIndexes[].IndexName'         -> gsi-owner
3. aws dynamodb describe-table --table-name mays-ris-dev-work-items
     --query 'Table.GlobalSecondaryIndexes[].IndexName'         -> gsi-user
4. AWS_PROFILE=mayaws pytest tests/test_observability_foundation.py \
     tests/test_lambda_packaging.py -v                           -> 8/8 PASS
5. AWS_PROFILE=mayaws pytest tests/ -q -rs                        -> 0 failed
```

### Recommendation

**APPLY.** The plan is exactly the approved scope: one route, two in-place
index additions, zero destroys, zero replacements, no backfill.