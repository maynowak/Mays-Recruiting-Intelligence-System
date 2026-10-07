# G5-PRIVACY-ERASURE-LIFECYCLE-01

**STATUS: GREEN** — decision, implementation, and deployment complete.

Base for the decision phase: `523ccd4`
Implementation: `cec412d` · Deployment: applied to `240571105849` / `eu-central-1`

| Phase | Outcome |
|---|---|
| Decision | classification **C** (design decision required) → D1–D4 approved |
| Implementation | erasure lifecycle, owner indexes, `POST /me/erasure` |
| Deployment | 1 add / 3 change / 0 replace / 0 destroy, applied |
| Security | RED → **GREEN** |

---

## DEPLOYMENT EVIDENCE

Applied with `--profile mayaws --region eu-central-1`, account `240571105849`.

```
terraform plan  → Plan: 1 to add, 3 to change, 0 to destroy.
terraform apply → Apply complete! Resources: 1 added, 3 changed, 0 destroyed.
post-apply plan → exit 0 (no drift)
```

| Resource | Action | Live verification |
|---|---|---|
| `module.api.aws_apigatewayv2_route.erasure` | create | `POST /me/erasure`, JWT, `integrations/ewy9u57` |
| `...dynamodb_table.credentials` | in-place | GSIs: `gsi-digest`, **`gsi-owner`** |
| `...dynamodb_table.work_items` | in-place | GSIs: **`gsi-user`**, `gsi-status` |
| `...lambda_function.agent` | in-place | `CodeSha256 = VTwwZh7mYss8DZSms+9PrZu5En2imFGodJfY2jyCAAo=` |

`credentials` key schema: `gsi-owner` HASH `ownerUserId`, projection ALL.
`work_items` key schema: `gsi-user` HASH `userId` RANGE `status`.

Both pre-existing indexes survived. No Cognito, IAM, monitoring, SQS or
orders-reader resource was touched.

### The deployment approval had to be corrected first

The originally approved plan (1 add / 2 change) **omitted the Lambda code
update**, and would have shipped a broken contract. `terraform/lambda.zip`
still held the previous artifact, and inspecting it showed:

```
privacy_erasure.py in bundle:    False
_handle_me_erasure in bundle:    False
delete_all_for_user in bundle:   False
```

Applying it would have made `POST /me/erasure` live with no handler behind
it — a gateway route that 404s, advertised by the OpenAPI contract. The
worker's `userId` propagation fix and the indexed credential lookup would
also have stayed undeployed.

Rebuilding via the repository's documented `package → plan → apply` contract
(`lambda/build_zip.py`, matching `installer/ris.py::_cmd_package`) produced
the corrected 4-resource plan, which was then approved and applied. The three
changes could not be split: route without code 404s, and code without the
indexes would make `list_by_owner` query a non-existent GSI.

### Live code proven, not just hash-matched

The deployed artifact was downloaded from Lambda and inspected:

```
privacy_erasure.py deployed       OK
_handle_me_erasure deployed       OK
POST /me/erasure dispatch         OK
indexed credential lookup         OK
no scan fallback                  OK
worker userId propagation         OK
delete_all_for_user               OK
CANCELLED status written          OK
revoke-first ordering             OK
terminal work retained            OK
```

### Non-destructive reachability

```
POST /me/erasure  (no JWT)  →  HTTP 401
```

Confirms the route is live **and** JWT-enforced at the gateway, without
executing an erasure. **No destructive erasure was performed against real
user data**; runtime behaviour is verified through fixtures.

---

## IMPLEMENTATION SUMMARY

Full detail in `G5-PRIVACY-ERASURE-IMPLEMENTATION-01.md`. In brief:

- **D2** — `gsi-owner` on `credentials`, `gsi-user` on `work_items`;
  `list_by_owner` no longer scans.
- **D1/D4** — `agents/ecosystem/privacy_erasure.py`: revoke credentials →
  revoke profiles → cancel non-terminal work → delete documents → delete
  profile row. `complete` is true only when every step succeeded; partial
  returns HTTP 207.
- **D3** — non-terminal work → `CANCELLED`; terminal work retained
  (deleting it would remove the `TERMINAL_DUPLICATE_STATES` suppression and
  re-admit duplicate execution). No retention duration invented.
- **API** — `POST /me/erasure`, separate from `DELETE /me/profile`, which
  keeps its narrow meaning and is asserted to still import neither the
  erasure workflow nor any other table.

---

## SECURITY ACCEPTANCE

| Invariant | Evidence |
|---|---|
| successful erasure leaves no usable credential | `test_no_credential_remains_usable` |
| cross-user isolation | `test_user_a_cannot_reach_user_b_data`, `test_only_the_named_user_is_queried` |
| idempotency | `test_repeat_erasure_is_safe` |
| partial failure never reported as success | `test_credential_revocation_failure_marks_incomplete` |
| fail-safe direction | `test_credentials_still_revoked_when_later_step_fails` |
| in-flight cancellation semantics | `test_non_terminal_work_is_cancelled_not_deleted`, `test_terminal_work_is_retained_for_idempotency` |
| external ownership intact | `test_orders_are_never_touched` |
| profile delete stays separate | `test_delete_handler_does_not_import_erasure` |

Negative controls: reordering profile deletion before revocation → **1
failed**; removing credential revocation → **6 failed**.

---

## TESTS

```
targeted G5 (erasure + lifecycle + profile)   54 passed
AWS live contract (observability+packaging)   13 passed  (8/8 live)
route + OpenAPI governance                    47 passed
FULL REGRESSION  1192 collected / 1184 passed / 0 failed / 8 skipped / 236 warnings
```

### Pre-existing environment-sensitive tests (NOT a regression)

Two tests in `tests/test_ris_installer.py` fail **only when `AWS_PROFILE` is
exported in the ambient environment**:

```
test_aws_context_flows_to_child_env
test_runner_without_context_unchanged
```

Root cause: both patch `os.environ` inside a `with` block, but assert
`assert "AWS_PROFILE" not in os.environ` **outside** it. Proven pre-existing
by running them at the pre-G5 commit `0202ec3`, where they fail identically.
Neither is related to erasure. Flagged for a follow-up package; the
authoritative full-suite result is the clean-environment run above.

---

## EVIDENCE VERIFIER: VERIFIED

Independently re-read: account, region, HEAD, live route + authorization +
integration, both live GSI definitions, both preserved GSIs, Lambda hash,
downloaded live code contents, targeted suites, live contract tests, route
governance, full regression, terraform state, post-apply drift. All matched.

---

## REMAINING FINDING FOR THE NEXT PACKAGE

`tests/test_ris_installer.py` has two assertions outside their
`patch.dict(os.environ)` context, making the suite fail under an exported
`AWS_PROFILE`. Unrelated to G5; worth fixing so that CI running with
credentials is green.

---

## LIFECYCLE MATRIX

Derived from `terraform/modules/dynamodb/main.tf`, verified against live
`describe-table`, and cross-checked against handler and domain source.

| Domain | Store | Key / user index | Targetable by user? | Candidate action | Blocker |
|---|---|---|---|---|---|
| User profile | `mays-ris-dev-user-profile` | `userId` (PK), `gsi-tenant` | yes (PK) | **DELETE** | none — implemented |
| Credentials | `mays-ris-dev-credentials` | `credentialId`, **`gsi-digest` only** | **NO** | REVOKE | **no owner index** |
| API profiles | `mays-ris-dev-api-profiles` | `apiProfileId`, `gsi-owner` | yes | **UNRESOLVED** | no lifecycle op exists |
| Entitlements | `mays-ris-dev-entitlements` | `entitlementId`, `gsi-user`, `gsi-agent` | yes | **RETAIN / EXPIRE** | none — TTL already expires them |
| Work items | `mays-ris-dev-work-items` | `workId`, **`gsi-status` only** | **NO** | **UNRESOLVED** | **no user index** |
| JobSearch | `mays-ris-dev-jobsearches` | `jobSearchId`, `gsi-user`, `gsi-status` | yes | DELETE | route is OPEN-5 unreachable |
| Documents | S3 `tenant/{t}/users/{sub}/documents/{uuid}` | path-scoped | yes | **DELETE** | none — module has `delete` |
| Orders | Mays-Orders (external) | — | n/a | **RETAIN** | not user-linked in RIS |
| Agent state / catalog | `agent-state`, `agent-catalog` | agent-scoped | n/a | unaffected | not user-owned |

```
domains:     9      delete: 2 (profile, documents)   revoke: 0
detach:      0      anonymize: 0                    retain: 3
unresolved:  3 (credentials, API profiles, work items)
```

### Two hard index blockers, found by reading the table definitions

I initially assumed credentials were reachable by owner. **They are not.**

```
work_items   GSIs: ['gsi-status']           # tenantId + status
credentials  GSIs: ['gsi-digest']           # the secret digest
api_profiles GSIs: ['gsi-owner']            # ownerUserId
```

`ownerUserId` and `requestedBy` are **written on every row but indexed on
neither**. Bulk erasure of either domain would require a full table scan, or
a Terraform index change plus a backfill decision for rows already stored.

This corrected my own working assumption before it reached the matrix.

---

## IDENTITY

- **Cognito** is the sole identity provider. Deleting a profile row does not
  affect authentication; the user can still obtain a fresh JWT.
- **Machine credentials are independent.** A credential is bound to an API
  profile, not to the user profile.
- **Ordering constraint:** revocation must precede, or accompany, any
  capability teardown — otherwise a race exists where a credential is still
  valid after the user believes their data is gone.
- **API profiles have no lifecycle operation.** The module docstring is
  explicit: *"NO TTL … deletion only via explicit admin cleanup, later
  gate"*. `transition_status` targets are `ACTIVE | DISABLED | REVOKED`
  (`handler.py:_APROF_STATUS_TARGETS`), so REVOKED is reachable today — but
  whether profile deletion should cascade into it is undecided.

## IN-FLIGHT WORK

`WorkItemStatus` defines `CREATED, QUEUED, RUNNING, COMPLETED, FAILED,
RETRY, DEAD_LETTER, CANCELLED, EXPIRED`. `CANCELLED` and `EXPIRED` exist as
constants but **nothing writes them**.

Deleting an in-flight work item is unsafe as a reflex:
- `_register_processing` uses a conditional write for idempotency
- a duplicate `COMPLETED` workId is suppressed via
  `TERMINAL_DUPLICATE_STATES`; removing the row re-admits duplicate execution
- retry semantics ride on SQS redelivery + `maxReceiveCount`/DLQ

So in-flight semantics need an explicit decision, not a delete call.

## DOCUMENTS / JOBSEARCH / ORDERS

**Documents** — `lambda/documents.py:43` builds
`tenant/{tenant}/users/{user_id}/documents/{doc_id}`. RIS-owned, user-scoped,
and the module already provides `delete`. The safest domain in the matrix.

**JobSearch** — user-owned and `gsi-user`-indexed, and a repository `delete`
exists. But its route is **OPEN-5: code-only and unreachable**, so no caller
can invoke it today.

**Orders** — Mays-Orders owns them. `lambda/orders_reader.py` contains no
`userId`; the only user linkage is `requestedBy` on the RIS work item.
Mays-RIS holds a *reference*, not ownership, and must not delete another
system's data.

## PUBLIC API

```
DELETE /me/profile   stays narrowly scoped — CONFIRMED
erasure API          NOT created, NOT documented
```

`x-is-account-erasure: false` and `x-deletion-scope:
USER_PROFILE_TABLE-row-only` remain accurate and are now backed by evidence
tests. No route was added; an unimplemented capability must not appear in
the contract.

---

## WHY NOT CLASSIFICATION B

Several actions *are* independently safe (delete documents; leave
entitlements to TTL). Implementing only those would produce an endpoint that
revokes nothing, deletes a couple of documents, and silently ignores
credentials and work items — while the user believes they closed their
account. That is **worse than no endpoint**, because it manufactures a false
erasure claim.

Partial implementation is safe only when the remainder is *inert*. Here the
remainder is **active authorization capability** (working credentials). So
partial implementation would violate the mission's own security invariant.

## DECISIONS REQUIRED

### D1 — Must `DELETE /me/profile` revoke machine credentials?

| Option | Security consequence | Privacy consequence | Runtime consequence |
|---|---|---|---|
| **1a. No** (today) | user retains working `ris_...` access after "deleting" their profile | data subject believes access ended; it has not | none |
| **1b. Yes — revoke all owned credentials** | capability ends with the profile | genuinely closes access | needs a `gsi-owner` on credentials + backfill |
| **1c. Yes — refuse unless credentials are revoked first** | strongest: no silent gap | explicit, user-visible | needs the same index |

*Recommendation: **1b**, requiring D2's index. Option 1a should not survive
this package's finding.*

### D2 — Add user-owner indexes to `credentials` and `work_items`?

| Option | Security | Privacy | Runtime | Data |
|---|---|---|---|---|
| **2a. Add both GSIs** | enables D1 | enables targeted erasure | `terraform apply`; GSI build is online but non-blocking | sparse-index cost; **backfill not required** — GSIs populate for existing items |
| **2b. Add credentials GSI only** | closes the capability gap | work items still untargetable | smaller change | less |
| **2c. No indexes, scan on erasure** | none | works but O(table) and slow | scan cost, throttling | none |

*Recommendation: **2a**. This is the smallest change that makes erasure
possible at all, and GSI creation does not require a backfill.*

### D3 — What happens to in-flight work?

| Option | Security | Privacy | Runtime |
|---|---|---|---|
| **3a. Cancel QUEUED/RUNNING, retain terminal** | — | in-flight payload retained for its natural life | needs CANCELLED to actually be written |
| **3b. Retain all work items** | — | work payload retained indefinitely | simplest |
| **3c. Delete all** | — | **breaks idempotency**; duplicate re-execution possible | unsafe |

*Recommendation: **3a**. Reject 3c outright — it can re-admit duplicate
execution and orphan retry state.

### D4 — Do API profiles cascade?

| Option | Security | Privacy | Runtime |
|---|---|---|---|
| **4a. Revoke profiles owned by the user** | capabilities all end | clean | `gsi-owner` exists; `transition_status` supports REVOKED |
| **4b. Retain** | profiles linger | orphaned capability surface | none |

*Recommendation: **4a**, gated on D1.

---

## NEGATIVE CONTROLS / EVIDENCE TESTS

`tests/test_privacy_lifecycle_evidence.py` — **21 tests**, no AWS required.

| Group | Pins |
|---|---|
| `TestProfileDeletionLeavesAuthorizationIntact` | the credential path never reads `USER_PROFILE_TABLE`; the delete handler reaches only the profile table; Cognito is the sole identity provider |
| `TestErasureTargetability` | the **actual** GSI set per table, including both blockers |
| `TestOwnershipBoundaries` | orders carry no `userId` in RIS; documents are user-scoped and deletable |
| `TestExistingLifecycleOperations` | `REVOKED` exists; API profiles have **no** delete; entitlements self-expire via TTL; nothing deletes work items |
| `TestNoFalseErasureClaim` | OpenAPI disclaims erasure; **no** erasure endpoint may be advertised |

These are guards, not coverage of a feature. If someone later adds an index,
revokes credentials, or introduces an erasure endpoint, the relevant test
fails and this decision must be re-read rather than inherited.

### Two of my own test bugs, corrected

1. I asserted credentials had a `gsi-owner` index. **They do not** — only
   `gsi-digest`. The corrected test now asserts the real index set, and the
   discovery became a headline finding.
2. I asserted the handler contains no `delete_item`. It does — the profile
   deletion. The test is now scoped to work items specifically.

---

## CROSS-REVIEW

| Reviewer | Verdict |
|---|---|
| security | **RED** — existing endpoint leaves active authorization capability |
| privacy | **YELLOW** — truthful about profile-only scope, but no erasure exists |
| runtime | **YELLOW** — in-flight semantics undefined |
| architecture | **RED** — two domains are untargetable without a schema change |
| api | **GREEN** — OpenAPI correctly disclaims erasure; nothing overclaimed |
| tests | **GREEN** — 21 evidence tests; regression clean |

Two REDs. Under the mission's classification this is **C**, not B.

## FULL REGRESSION

```
collected 1167   passed 1159   failed 0   skipped 8   warnings 236
```

Baseline 1146 → 1167 (+21). No AWS mutation. No production code changed.

## EVIDENCE VERIFIER: VERIFIED

Every matrix row traces to a file, a Terraform resource, or a live
`describe-table` call. Both index blockers were confirmed against the live
tables, not only the Terraform source.

---

## NEXT PACKAGE RECOMMENDATION

**G6-ERASURE-INDEX-FOUNDATION (D2)** — add `gsi-owner` to `credentials` and a
user index to `work_items`, then re-run this decision package with targeted
erasure actually possible.

Rationale: D1, D3 and D4 all become *implementable* the moment D2 lands.
Doing D1/D4 first would mean shipping scans, or shipping partial erasure that
misleads users. The index change is infrastructure-only, reversible, requires
no backfill, and unblocks every downstream privacy decision.

Carry-forward: OPEN-2 error-envelope unification (well-specified, low risk),
the 3 OPEN-3 unmanaged document routes, and the timestamp serialization
contract gating 43 `utcnow()` sites.