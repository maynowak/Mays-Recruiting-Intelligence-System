# RIS–Mays-Orders Integration — Current Status

**Status at 2026-11-28:** both authorized entitlement Applies completed with
their reviewed saved plans; the latest post-Apply read-only verification
**PASS** (State serial 78). **STOP at Live-Order gate**: no live order, retry,
redrive, further Terraform operation, or Main merge was performed.

## Final Addition live E2E — STOP before POST (auth context unavailable)

Baseline `12a1d49f9991575a63ff166da41797ad3a51750b`. Immediately before the
intended single request, read-only preflight confirmed account
`262370457690`, region `eu-central-1`, workspace `ris-dev2`, State serial `78`,
lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 version
`Nv9DBw9WQi48972QdhqULqPlpG3Ddi4y`, the enabled/confirmed verified synthetic
identity, its ACTIVE owner/tenant profile, and one valid `addition_agent`
entitlement through `2026-11-28T14:36:29Z` (12,793 seconds remained at check).
The deployed `POST /orders` route on API `r95qvhg2p3` was confirmed JWT
authorized. The exact prepared body reproduced the approved payload SHA-256
`9db3d7ecf238bd5b3875ab3958ea9a4a9cb0173d07c04270a21caeea8790d907` and
Request-ID/Idempotency-Key
`ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c`.

**Execution stopped before sending:** no valid bearer token or approved
authentication credential context for the test identity was available in the
execution environment. No password reset, credential guessing, or identity
mutation was attempted. No HTTP POST was made; no order, dispatch, WorkItem, or
result was created. Therefore the requested live roundtrip was **NOT RUN** and
has no pass/fail result. No retry, redrive, Terraform operation, or cleanup
operation was performed. The pre-existing local foreign-owner-404 test evidence
remains the only such evidence; no live foreign-owner request was made.

**Next gate:** provide/authorize a secure authentication context for the
existing test identity, then repeat read-only checks of grant, payload hash,
State, and endpoint immediately before any separately approved single POST.
This block does not authorize use of the request after the grant expiry. Since
the live test did not succeed, no entitlement-cleanup plan was prepared; cleanup
remains separately gated.

### Follow-up endpoint reconciliation — resolved; STOP at live-order gate

The initial 2026-11-28 route check used only the first page of API Gateway
routes and incorrectly reported that `POST /orders` was absent. A paginated,
read-only inventory corrected that observation: RIS API `r95qvhg2p3`
(`ris-dev2-dev-api`) has 75 routes and includes `POST /orders`, JWT authorizer
`0iqec5`, and integration `o2ci057` to Lambda
`ris-dev2-dev-orders-reader`. Its `$default` stage has auto-deploy enabled.
The corresponding Terraform State serial 78 records the same API endpoint,
route key, route ID, authorizer, and integration. No `ANY` or proxy route is
needed for this path.

The separate API `7ency74vs0` (`ris-dev2-mays-orders-api`) also has four
explicit order routes, including `POST /orders`, but its authorizer uses a
different Cognito issuer/pool and audience. It is not interchangeable with the
RIS endpoint for the existing test identity. The documented historical
Addition pilot and the approved payload therefore reconcile to
`POST https://r95qvhg2p3.execute-api.eu-central-1.amazonaws.com/orders`.
The RIS authorizer issuer/audience match the existing RIS pool and Human Client;
the established authentication method is `USER_PASSWORD_AUTH`, returning the
ID token accepted by that JWT authorizer. No Cognito authentication or token
request was made in this reconciliation.

The existing Addition grant was read-only verified valid from
`2026-11-28T10:36:29Z` through `2026-11-28T14:36:29Z` at 11:18:54Z. Request-ID
and approved payload remain unchanged. **STOP at the live-order gate:** this
task authorizes discovery only; no POST, token acquisition, configuration
change, Terraform operation, retry, or cleanup was performed. No endpoint
correction to the prior live-order authorization is needed. The roundtrip
remains **NOT RUN** and cleanup remains separately gated.

## Four-hour entitlement renewal Apply — PASS; STOP at Live-Order gate

- At checkpoint `d2592867572b88bee8d7607ceed2d8ea1e76ae1d`, immediately
  confirmed saved-plan SHA-256
  `5bba7cfce9b84e6bdd24d7ff6a7120907b78b3aeee78fec684ecbfa43589fd7f`, account
  `262370457690`, region `eu-central-1`, workspace `ris-dev2`, backend
  `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate`, State serial
  77, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, and prior S3 version
  `zOnRrKUXkb3CvoHhGcosBHYkAExMwHmT`. All preserved Worker, Analysis, parser,
  and Reader hashes matched; guard **PASS** (`NO_SHARED_DESTROY`). Grant had
  13,816 seconds remaining before its approved end `2026-11-28T14:36:29Z`.
- Applied the exact saved plan once; Terraform exit code 0. No replan or retry.
  Scope remained **0 Add / 1 Change / 0 Destroy / 0 Replace**: in-place update
  of the already-existing Addition entitlement, changing only `validFrom` and
  `validUntil`. No new entitlement, ATS change, or other resource action.
- Post-Apply AWS read-only verification **PASS**: Addition entitlement exists
  and is currently valid through `2026-11-28T14:36:29Z`; ATS catalog remains
  `INACTIVE`, zero valid ATS entitlements, and Addition catalog remains
  `ABSENT`. State advanced to serial `78`, same lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, latest S3 version
  `Nv9DBw9WQi48972QdhqULqPlpG3Ddi4y`.
- Comparing pre/post State versions found exactly one changed managed resource:
  the existing entitlement instance. All other State resources, including
  shared infrastructure, were unchanged. Live Worker, Dispatch-Ingress,
  Analysis and Orders-Reader code hashes still match preserved artifacts.
- The previously prepared live-order candidate is unchanged and remains
  separately gated: request/idempotency ID
  `ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c`, payload SHA-256
  `9db3d7ecf238bd5b3875ab3958ea9a4a9cb0173d07c04270a21caeea8790d907`.
  **No live order is authorized or performed here.** Reconfirm State/grant and
  obtain separate explicit approval for this exact request before sending;
  do not execute after grant expiry. No Terraform command was run after Apply.

## Four-hour Addition entitlement renewal plan — PASS; pre-Apply checkpoint

Baseline `ae8a72525e43ee69f09ae1266a38fa02c47753d4`; State serial 77. Reused
the exact 19G5 inputs, backend configuration, and preserved artifacts; no FULL
QA or bundle build. Read-only preflight confirmed account `262370457690`,
region `eu-central-1`, workspace `ris-dev2`, bucket `ris-dev2-tf-state-dev`,
effective key `env:/ris-dev2/dev/terraform.tfstate`, lock table ACTIVE, State
lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, and current S3 version
`zOnRrKUXkb3CvoHhGcosBHYkAExMwHmT`. Existing temporary entitlement and its
managed Terraform key were reused; no second grant was added. ATS remains
`INACTIVE`, Addition catalog remains `ABSENT`.

- One separate renewal tfvars file (outside the repository) updates only
  `validFrom` and `validUntil` on the existing entitlement. SHA-256
  `129a1395bbbab10d7112074d80ef0ad3de94f2a9f43b15d1159b8507328b625d`;
  validity `2026-11-28T10:36:29Z` through `2026-11-28T14:36:29Z`, exactly four
  hours. User, tenant, agent and entitlement key are unchanged.
- Exactly one Terraform `1.17.0` full-refresh plan was created, with normal
  state locking. Saved plan:
  `%TEMP%\opencode\ris-dev2-addition-renewal-4h-ae8a725.tfplan`; SHA-256
  `5bba7cfce9b84e6bdd24d7ff6a7120907b78b3aeee78fec684ecbfa43589fd7f`.
  Summary: **0 Add / 1 Change / 0 Destroy / 0 Replace / 274 No-op**.
- The only non-no-op action is an **in-place update** of the existing
  `module.dynamodb.aws_dynamodb_table_item.foundation_entitlement[<redacted>]`;
  only the two time fields change. No create, delete, replacement, ATS
  reactivation, Lambda, IAM, Queue, or other resource action.
- Shared-infrastructure guard **PASS** (`NO_SHARED_DESTROY`). The initial
  inspection wrapper stopped on an incorrect expectation of 273 rather than
  274 no-op resources; no second plan was run. Read-only inspection of the one
  saved plan confirmed the exact approved scope and guard.
- At this plan checkpoint, **Apply had not yet been performed**. The subsequent
  explicit Apply approval and successful execution are recorded above. The
  existing live-order candidate remains pending: request ID
  `ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c`, payload SHA-256
  `9db3d7ecf238bd5b3875ab3958ea9a4a9cb0173d07c04270a21caeea8790d907`; it must
  be revalidated after renewal Apply and separately approved before sending.

### Apply approval record — subsequently approved and applied

> User explicitly approved one Apply. Proposed action: one Apply of saved
> plan SHA-256
> `5bba7cfce9b84e6bdd24d7ff6a7120907b78b3aeee78fec684ecbfa43589fd7f` for
> account `262370457690`, region `eu-central-1`, workspace `ris-dev2`, State
> serial 77 / lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`; exact scope
> `0 Add / 1 Change / 0 Destroy / 0 Replace`, updating only the existing
> Addition entitlement's validity interval to four hours. Guard
> `NO_SHARED_DESTROY` PASS. Apply authorization: **GRANTED and executed once**.
> This grants no live-order, cleanup, retry, redrive, or ATS authorization.

## Addition live E2E — payload prepared, execution BLOCKED; STOP at gate

Fresh read-only checks confirmed the single enabled/confirmed synthetic test
identity still matches the verified 19G5 identity, its owner profile is ACTIVE
and tenant-matched, State remains serial `77` / lineage
`a0bd361d-5cd1-a207-a8c0-e6888f0be082` / S3 version
`zOnRrKUXkb3CvoHhGcosBHYkAExMwHmT`, and the deployed RIS-DEV2 `POST /orders`
route is JWT-authorized. However, the temporary Addition entitlement expired
at `2026-11-28T10:28:22Z`; the read-only check at `10:29:53Z` found no valid
owner grant. Therefore **no live order was sent** and this candidate cannot be
executed without a separately authorized fresh entitlement path and renewed
preflight.

### One-order proposal — exact payload binding; pending, not approval

- Endpoint: `POST https://r95qvhg2p3.execute-api.eu-central-1.amazonaws.com/orders`
- Request-ID and idempotency key:
  `ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c`
- Exact UTF-8 compact-JSON payload SHA-256:
  `9db3d7ecf238bd5b3875ab3958ea9a4a9cb0173d07c04270a21caeea8790d907`
- Payload (the `orderDescription` string is canonical compact JSON):

```json
{"orderType":"agent.execution","customer":{"name":"Synthetic Addition QA","email":"addition-qa@example.invalid"},"items":[{"sku":"ADD","quantity":1,"unitPrice":1}],"currency":"EUR","orderDescription":"{\"input\":{\"data\":{\"left\":19,\"right\":23},\"schemaVersion\":\"1.0\"},\"metadata\":{\"apiProfileRef\":\"aprof_cdbd3b6f803744bf\",\"idempotencyKey\":\"ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c\",\"requestId\":\"ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c\",\"source\":\"ris-addition-live-e2e\"},\"schemaVersion\":\"1.0\",\"target\":{\"agentId\":\"addition_agent\",\"capability\":\"math.add\"}}"}
```

Requested semantics: one synthetic `addition_agent/math.add` execution (`19 +
23`, expected `42`), preserve the exact `orderDescription`; no ATS, second
order, retry, direct invocation, or queue operation. Approval of this hash is
not sufficient to bypass the expired entitlement. **Live-order approval: NOT
GRANTED; execution blocked.** If a renewed grant is separately authorized,
reconfirm this exact hash/request ID and all live preconditions before sending.
No second authorized Cognito identity exists; reuse only the existing local
foreign-owner-404 evidence (`tests/test_agent_order_dispatch_e2e.py`), not a
live foreign-owner request.

### Entitlement cleanup — approval preparation only

Prepare a separate reviewed Terraform change limited to deleting the one
temporary `module.dynamodb.aws_dynamodb_table_item.foundation_entitlement`
Addition grant instance. Preserve the ATS catalog state, all order/work/result
evidence, shared infrastructure, and all other resources. No cleanup plan or
Apply was run or is authorized here; recheck current State and exact instance
address, then request explicit approval before any future Terraform operation.

## Authorized Apply — PASS; STOP at Live-Order gate

- Applied exactly once the saved plan SHA-256
  `ca0933a296610d2cae2ad80e12c8d27a3aeed892856ed2ee18d155abdf4fcd3b` after
  immediate preflight passed at checkpoint `59150628246d718d1e38d70dbb5748c5afb94258`.
  Account `262370457690`, `eu-central-1`, workspace `ris-dev2`; State serial 76,
  lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, and S3 version
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T` matched. Plan scope was exactly 1 Add / 1
  Change / 0 Destroy / 0 Replace; guard PASS (`NO_SHARED_DESTROY`). Reader
  SHA-256 was independently checked against 19G4/19G5/19H and saved-plan
  identity: `610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b`.
- At the immediate pre-Apply check, the grant had 717 seconds remaining and
  expired at `2026-11-28T10:28:22Z`. Terraform Apply exited successfully. No
  retry, replan, or second Apply.
- AWS read-only verification passed: ATS catalog `INACTIVE`; zero valid ATS
  entitlements; exactly one valid `addition_agent` entitlement (two Addition
  rows total, one expired); Addition catalog `ABSENT`. The active grant expires
  at `2026-11-28T10:28:22Z`.
- State advanced to serial `77`, same lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, latest S3 version
  `zOnRrKUXkb3CvoHhGcosBHYkAExMwHmT`. Comparing the before/after S3 state
  versions showed exactly two managed-resource changes: ATS catalog seed
  update and one foundation entitlement create. All other managed resources,
  including shared infrastructure, were unchanged.
- Read-only Lambda verification found the Worker, Dispatch-Ingress, Analysis,
  and Orders-Reader code hashes unchanged and update status successful. No live
  order or redrive. No further Terraform operation is authorized or performed.

### Live-Order approval request — pending; not authorization

> **Requested action:** approve at most one authenticated `POST /orders` to the
> RIS-DEV2 Orders endpoint, account `262370457690`, region `eu-central-1`, using
> the existing verified synthetic owner/profile. Exactly one synthetic order:
> customer `Addition QA` / `customer@example.invalid`; one `ADD` item, quantity
> 1, unit price 1 EUR; `orderType=agent.execution`; target
> `addition_agent/math.add`; inputs `left=19`, `right=23`; expected result `42`.
> No ATS, external provider, or AI execution. No second POST, retry, direct
> Lambda invocation, queue receive/redrive, or foreign-owner request. One
> matching owner-result readback may be used only if included in the approval.
>
> Approval authority/date: **NOT PROVIDED**. Exact serialized payload SHA-256
> and unique requestId/idempotency key: **MUST be filled and approved before
> sending**; no order has been constructed or sent. Grant expiry:
> `2026-11-28T10:28:22Z`; do not execute after expiry. Live-order approval:
> **NOT GRANTED**. Any grant cleanup requires a separately reviewed IaC plan
> and approval.

## Apply preflight correction — PASS; Apply remains disabled

The previous preflight stop was caused by an incorrect expected-value literal
in the checker (it omitted the final `b`), not by a changed artifact. The
historical value was independently confirmed against 19G4 local validation and
path reconciliation, 19G5 artifact matrix, and 19H deployed Lambda
`CodeSha256`; the saved plan itself records the matching reader path, code hash,
and `no-op` action. Local bytes match the same SHA-256:
`610004f6eae3531e4c87236439e491bcbf0c102ea29161fef247c2713c81ae6b`. No
artifact was built, replaced, or modified.

- Read-only recheck passed for the unchanged saved plan hash
  `ca0933a296610d2cae2ad80e12c8d27a3aeed892856ed2ee18d155abdf4fcd3b`, account
  `262370457690`, region `eu-central-1`, workspace `ris-dev2`, expected backend
  bucket/key, lock table ACTIVE, State serial `76`, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, and S3 version
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`. 19G5 base inputs still match SHA-256
  `1ada876c6c98080206c9d29ca55549b4b8f254e1f2a5c0e915f9d6097016e6e7`.
- Saved plan was inspected read-only; no Terraform plan or Apply command ran.
  Shared-infrastructure guard **PASS** (`NO_SHARED_DESTROY`). At the preflight
  check, the 60-minute grant remained valid with 1,099 seconds before expiry
  (`2026-11-28T10:28:22Z`).
- Apply remains **NOT PERFORMED / NOT AUTHORIZED by this correction task**;
  live-order execution remains disabled and separately gated. Stop at Apply
  gate. No change was made to protected 19F2 results.

## Newly authorized RIS-DEV2 60-minute plan — PASS; STOP at Apply gate

Comparison baseline: passing plan
`33c0e65ef0ada1bb046c487502d796e95d1251b6ce378eb76e48397c9745d515`; checkpoint
commit `8831a44e2f510660887e329015063f3c6d285a4e`. The one new plan was run
against unchanged verified 19G5 inputs, backend metadata, artifacts and paths.

- Read-only preflight reconfirmed account `262370457690`, region `eu-central-1`,
  bucket `ris-dev2-tf-state-dev`, effective key
  `env:/ris-dev2/dev/terraform.tfstate`, workspace `ris-dev2`, lock table
  `ris-dev2-tf-lock`, State serial `76`, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 version
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`; state was not migrated.
- Reused 19G5 base input SHA-256
  `1ada876c6c98080206c9d29ca55549b4b8f254e1f2a5c0e915f9d6097016e6e7` (83
  inputs). Worker, Analysis, parser and Orders-Reader artifacts retained their
  verified hashes and historical paths; no bundle was built or changed.
- Read-only identity/profile/catalog/entitlement checks passed: same verified
  test identity and tenant, active owner profile, ATS catalog `ACTIVE`,
  Addition catalog `ABSENT`, and no valid ATS or Addition entitlement.
- Separate fresh grant tfvars SHA-256
  `5bd76b7b89330cdd39dcffea226de9de5baced728456a2acebbbd1040e3af796` provided
  exactly one `addition_agent` entitlement for that identity/tenant. Effective
  saved-plan values and after-image match the file. Validity:
  `2026-11-28T09:28:22Z`–`2026-11-28T10:28:22Z` (exactly 60 minutes). File is
  outside the repository and was not committed.
- Exactly one Terraform `1.17.0` full-refresh plan, normal state lock:
  `%TEMP%\opencode\ris-dev2-addition-acceptance-60m-8831a44.tfplan`; SHA-256
  `ca0933a296610d2cae2ad80e12c8d27a3aeed892856ed2ee18d155abdf4fcd3b`.
  Scope: **1 Add / 1 Change / 0 Destroy / 0 Replace / 273 No-op**.
- Only changes: ATS catalog seed `ACTIVE→INACTIVE`; create exactly one
  temporary Addition entitlement. No Lambda, IAM, Queue, or other resource
  changes. Shared-infrastructure guard **PASS** (`NO_SHARED_DESTROY`); transport
  remains enabled and lifecycle managed.
- **Apply approval: NOT GRANTED.** Saved plan is review-only. Do not apply or
  place a live order. Any further plan requires a new explicit authorization.

### Apply approval template — pending; not authorization

> Approver/authority/date: **NOT PROVIDED**. Proposed action: at most one Apply
> of plan SHA-256
> `ca0933a296610d2cae2ad80e12c8d27a3aeed892856ed2ee18d155abdf4fcd3b` in account
> `262370457690`, region `eu-central-1`, workspace `ris-dev2`, State serial 76 /
> lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`; exact scope 1 Add / 1 Change /
> 0 Destroy / 0 Replace (one temporary Addition entitlement, ATS catalog
> `ACTIVE→INACTIVE`). Grant expires `2026-11-28T10:28:22Z`. Apply authorization:
> **NOT GRANTED**. No live order; separately gated.

## Authorized corrected RIS-DEV2 plan — PASS; STOP at Apply gate

Baseline: `e115b201542706266c274e2d223ac58bf3e80ad0`. One explicit plan
authorization was used exactly once. No plan retry, Apply, or Live Order.

- Fresh read-only checks passed: account `262370457690`, region `eu-central-1`,
  bucket `ris-dev2-tf-state-dev`, effective key
  `env:/ris-dev2/dev/terraform.tfstate`, workspace `ris-dev2`, lock table
  `ris-dev2-tf-lock`, state serial `76`, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, latest S3 version
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`. 19G5 TF_DATA_DIR backend metadata and
  exact 83-input base file hash
  `1ada876c6c98080206c9d29ca55549b4b8f254e1f2a5c0e915f9d6097016e6e7`
  matched. No state migration or backend resource creation.
- Worker/Dispatch bundle `507bc17…`, Analysis `276b4e44…`, Analysis parser
  `fb741fb2…`, and Orders-Reader `610004f6…` matched their preserved archive
  hashes and historical path inputs. No build or bundle edit occurred.
- Fresh read-only owner/profile/entitlement/Catalog checks matched the approved
  synthetic identity and tenant. ATS Catalog=`ACTIVE`, Addition Catalog=`ABSENT`;
  one expired-only global entitlement row each for ATS and Addition; none
  currently valid and no current owner Addition grant. No raw identity or
  entitlement IDs are included here.
- A separate fresh grant tfvars file was created immediately before planning,
  with exactly one `addition_agent` row for the verified user/tenant and
  validity `2026-11-28T09:06:19Z` through `2026-11-28T09:22:19Z` (15 minutes).
  File SHA-256:
  `d1aaec733a5298c2a04ac1358faa046c0a28d1c2e03f93f3732b2ac09df5059e`.
  The serialized plan's effective `foundation_entitlements` map was verified
  to contain exactly that one row and matching times/agent/owner/tenant. The
  temporary file is outside the repository; do not commit it.
- Exactly one Terraform `1.17.0` plan ran with default full refresh, normal
  state locking, and the 19G5 base plus separate grant tfvars. Saved plan:
  `%TEMP%\opencode\ris-dev2-addition-acceptance-e115b20.tfplan`; SHA-256
  `33c0e65ef0ada1bb046c487502d796e95d1251b6ce378eb76e48397c9745d515`.
  Result: **1 Add / 1 Change / 0 Destroy / 0 Replace / 273 No-op**.
- Exact non-noop scope only:
  `module.dynamodb.aws_dynamodb_table_item.agent_catalog_seed["ats-agent"]`
  updates `ACTIVE→INACTIVE`; one
  `module.dynamodb.aws_dynamodb_table_item.foundation_entitlement[<redacted>]`
  is added. The planned entitlement after-image matches the separate tfvars.
  No Lambda, IAM, Queue, Analysis, shared transport, or other resource action.
- Shared-infrastructure guard:
  `installer.shared_infra_guard.evaluate_plan` **PASS** (`NO_SHARED_DESTROY`);
  flags `enable_agent_transport=true`, `orders_lifecycle=managed`. The plan
  matches the authorized `1/1/0/0` scope and all allowed resource addresses.
- **Apply gate: NOT APPROVED.** The saved plan is review-only. Do not apply or
  test after the grant expires at `2026-11-28T09:22:19Z`; after expiry, stop and
  request a new grant window plus explicit plan authorization. No cleanup or
  live-order authorization is implied.

### Apply approval template — pending; not authorization

> Approver/authority/date: **NOT PROVIDED**. Proposed action: at most one Apply
> of saved plan SHA-256
> `33c0e65ef0ada1bb046c487502d796e95d1251b6ce378eb76e48397c9745d515` for
> account `262370457690`, region `eu-central-1`, workspace `ris-dev2`, current
> state serial `76` / lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`; exact scope
> `1 Add / 1 Change / 0 Destroy / 0 Replace` (one Addition grant row, ATS
> Catalog `ACTIVE→INACTIVE`), no other resources. Grant expiry:
> `2026-11-28T09:22:19Z`; no Apply/test after expiry. Apply authorization:
> **NOT GRANTED**. Live order and cleanup remain separately gated.

## Initial bundled plan — REJECTED ON SCOPE DEVIATION

**2026-11-28, baseline `6ef378e327fcf9cfc35e7f04f2ad032bbd5d4569`.** Requested
modes: `TEST_FIX_RETEST`; AWS read-only; backend reconciliation; reuse existing
RIS-DEV2 installation; exactly one full-refresh Terraform plan; no apply, live
order, state migration, or AWS resource mutation; status update, commit/push;
no main merge.

- Installation/backend verification passed read-only: account `262370457690`,
  region `eu-central-1`, bucket `ris-dev2-tf-state-dev`, effective key
  `env:/ris-dev2/dev/terraform.tfstate`, workspace `ris-dev2`, lock table
  `ris-dev2-tf-lock`, state serial `76`, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, and latest S3 version
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`. No state migration or backend resource
  creation occurred.
- Historical artifacts were restored byte-for-byte using
  `scripts/stage_preserved_ris_dev2_artifact_paths.py`: Worker
  `507bc17…`, Analysis `276b4e44…`, Reader `610004f6…`. No new bundle content
  was used in the plan; the prior bundle-build step had regenerated canonical
  local outputs, so the existing staging procedure restored the preserved
  deployed bytes and historical filename paths.
- Current read-only entitlement check confirmed one enabled synthetic user,
  one ACTIVE tenant-matched profile, no current test-owner Addition grant, and
  no currently valid global ATS or Addition entitlement. Exactly one temporary
  Addition grant was supplied to the plan input with a 15-minute window
  `2026-11-28T08:13:07Z`–`2026-11-28T08:29:07Z`.
- Exactly one normal full-refresh Terraform plan was created after the explicit
  plan authorization. Plan file (outside the repository):
  `%TEMP%\opencode\ris-addition-bundled-6ef378e.tfplan`; SHA-256
  `29af00f2a2597d0ddd759aa860164ed72b62f9bae0e016c5ead318c6a0312ddb`.
  The shared-infrastructure guard rejected it. Read-only inspection found
  **0 Add / 4 Change / 13 Destroy / 0 Replace**, not the authorized
  `1 Add / 1 Change / 0 Destroy`. The Addition entitlement add is absent from
  the plan; it also includes deletes of Analysis resources and shared IAM,
  permissions, and logs, plus unexpected Worker/Ingress/policy changes.
- **STOP:** the plan is invalid for this request and MUST NOT be applied. No
  second plan was created. Terraform Apply `0`; AWS resource mutations `0`;
  live orders `0`; state migration `0`. The ordinary plan lock was used by the
  runner; no state/resource write was authorized or performed. Keep this plan
  only as rejected evidence. The temporary tfvars input is outside the repo.
- Apply approval is **NOT GRANTED**. Any corrected plan requires reconciliation
  of the exact 19G5/19H Terraform inputs and a new explicit authorization before
  creating another full-refresh plan. If the 15-minute entitlement window has
  expired, do not apply or test with this grant/plan; request a fresh window and
  authorization. No live-order gate was entered.

The protected 19F2 results file remains untouched by this follow-up and is not
included in the checkpoint commit.

## Plan input reconciliation — PREPARED; replan gate CLOSED

**2026-11-28, baseline `e98b9ef5621a9b04d19139d76db08debeb9c2924`.** Modes:
existing rejected-plan read only; installation-input reconciliation; local
configuration preparation; AWS mutations `false`; Terraform plan/apply
`false`; runtime/artifact changes `false`; live order `false`; status/commit/
feature push `true`; main merge `false`.

The rejected plan hash was verified locally against
`29af00f2a2597d0ddd759aa860164ed72b62f9bae0e016c5ead318c6a0312ddb`. The
successful historical 19G5 plan was also verified locally against
`d78c0fcfaee991c774895c583604f0ea270dee600f59af7e37c9cf1e804985c3`; 19H
applied that exact plan and changed only Worker/Ingress code. Comparing both
serialized plan inputs identified these 20 differences:

| Parameter(s) | 19G5/19H expected | Rejected plan effective input | Effect / interpretation |
|---|---|---|---|
| `enable_analysis_runtime`; `analysis_lambda_zip_path`; `analysis_parser_zip_path` | `true`; `analysis-lambda.zip`; preserved parser path | `false`; empty; empty | Analysis module was disabled. This accounts for the two root Analysis Lambda permissions and eight Analysis Runtime/parser resources in the 13 destroys. |
| `analysis_synthetic_mode`; `analysis_synthetic_user_id`; `analysis_synthetic_tenant_id`; `analysis_synthetic_partner_application_id`; `analysis_synthetic_issuer`; `analysis_synthetic_entitlements`; `analysis_synthetic_expires_at` | Enabled and populated from the prior approved installation input | `false`; remaining values empty | Historical Analysis environment inputs were not restored. Reuse the 19G5 values unchanged; do not refresh/rewrite this Analysis configuration in this task. Values remain only in the external local tfvars file. |
| `order_result_secret_arn` | Present in 19G5/19H | Empty | Accounts for the three result-secret IAM policy deletes, the `dispatch_result_secret` IAM-policy update, and removal of `ORDER_RESULT_SECRET_ARN` from both Worker and Dispatch-Ingress environments. |
| `orders_table_name`, `orders_table_arn`, `orders_queue_url`, `orders_queue_arn` | Present in the 19G5 input set | Empty | Installation-input mismatch. With `orders_lifecycle=managed`, the root derives these from the managed Mays-Orders module; no separate plan action was attributed to these four values. Retain them for exact configuration reproduction. |
| `enable_agent_transport` | Boolean `true` | String-form `"true"` from the project overlay | Semantically enabled in both plans; not a cause of destroy. Restore the typed 19G5 input. |
| `identity_m2m_enabled`, `identity_oauth_enabled`, `identity_custom_domain_enabled` | Boolean `true`, `false`, `false` | String-form values from the project overlay | Same effective toggles; representation differs, not a cause of the observed plan actions. Restore the typed 19G5 inputs. |
| `filename` | `../lambda/dist/orders-reader.zip` | Absolute checkout path emitted by the Installer | Raw input form differs, but the evaluated Reader filename/artifact is unchanged; no Reader action appeared. The corrected template uses the 19G5 input form from the repository Terraform root, preserving the 19G4/19G5 resolved path. |

**Action attribution.** The 13 destroys are exactly 10 Analysis-related resources
(two `aws_lambda_permission.analysis_*` entries plus eight resources under
`module.analysis_runtime`) gated by `enable_analysis_runtime=false`, and three
result-secret IAM policies gated by the missing `order_result_secret_arn`.
The four changes are: the intended ATS catalog item update; Worker and
Dispatch-Ingress environment updates caused by the missing Analysis function
settings and result-secret ARN; and the `dispatch_result_secret` policy update
caused by the missing secret ARN. No artifact hash difference caused those
Worker/Ingress changes. The Addition resource was absent because the rejected
plan's effective `foundation_entitlements` value was `{}` and there was no
`aws_dynamodb_table_item.foundation_entitlement` Add action. An attempted
ambient `TF_VAR_foundation_entitlements` input was not reflected in the
effective plan; the next plan input must pass the temporary grant explicitly
through a supplemental JSON tfvars file and verify the resulting planned Add.
Its sole map entry must have the existing mechanism's shape:
`{ "<unique-entitlement-id>": { "userId": "<verified-sub>", "tenantId":
"<matching-tenant>", "agentId": "addition_agent", "validFrom": "<T0-1m>",
"validUntil": "<T0+15m>" } }`; do not add `apiProfileId`, `expiresAt`, or an
Addition catalog row.

**Local corrected base input prepared (not committed; contains installation-
specific identity/configuration values):**
`%TEMP%\ris-addition-final-e2e\ris-dev2-19g5-installation-inputs.tfvars.json`,
SHA-256 `1ada876c6c98080206c9d29ca55549b4b8f254e1f2a5c0e915f9d6097016e6e7`.
It was reconstructed read-only from the hash-verified 19G5 saved plan and
contains its 83 effective inputs except `foundation_entitlements`. A separate
grant tfvars file is intentionally **not** created yet; generate it only
immediately before a newly authorized plan, with exactly one verified owner,
tenant and `addition_agent` row, and the then-current 15-minute validity
window. Do not commit either file.

Historical artifact identities and resolved paths were checked locally and
remain unchanged: Worker `507bc17…`; Analysis `276b4e44…`; Analysis parser
`fb741fb2…`; Orders-Reader `610004f6…`. The 19G4 staging procedure is the only
approved byte-copy restoration path. No new bundles or artifact edits were
made in this reconciliation.

**Corrected plan template — documentation only; NOT executed:** from the
repository Terraform root, reuse the verified `ris-dev2` backend context and
historical base tfvars above, then add one separately created, time-limited
grant tfvars file:

```text
$env:TF_DATA_DIR = '<existing 19G5 TF_DATA_DIR>'
$env:TF_WORKSPACE = 'ris-dev2'
terraform -chdir=terraform plan -input=false -lock=true -out=<new external plan path> -var-file=<19G5 installation-inputs.tfvars.json> -var-file=<fresh addition-grant.tfvars.json>
```

Use the existing `TF_DATA_DIR`/backend configuration for bucket
`ris-dev2-tf-state-dev`, region `eu-central-1`, effective state key
`env:/ris-dev2/dev/terraform.tfstate`, lock table `ris-dev2-tf-lock`, and
workspace `ris-dev2`; do not reconfigure/migrate State or create backend
resources. Immediately before any future plan, verify current state and the
grant identity/window. Inspect the one plan for exactly **1 Add / 1 Change / 0
Destroy**, with only the Addition entitlement row and ATS catalog status
transition; any Lambda, IAM, queue, Analysis, or other action is a STOP. No
plan was run in this reconciliation. Replan requires a new explicit approval;
Apply remains separately unauthorized.

| Work package | Soll | Ist / mode | Implementation / deployment | Test result | Offene Abweichung | Nächster Schritt | Commit / Evidenz |
|---|---|---|---|---|---|---|---|
| A — Historical ATS deactivation | Deactivate `ats-agent` through existing lifecycle; retain results and shared infrastructure | **Read-only inventory complete; live disable NOT APPLIED**. Local `DISABLE` dry-run returned `DRY_RUN`, zero blockers. | Catalog is `ACTIVE`; global ATS entitlement query found one expired-only historical row and no currently valid row. `INACTIVE` is a discovery gate, not the worker execution gate. No uninstall/purge. | All 4 ATS orders in the live Orders index have `processing=COMPLETED`; no open ATS order/result. Dispatch, work and result queues are 0. Shared worker DLQ has 1 approximate visible message; its body was not read/received. | Rejected plan had additional deletes and unexpected Lambda/policy changes. Expired entitlement is not in current state; do not delete it manually. DLQ untouched. | Reconcile exact 19G5/19H variable set. A new plan requires explicit authorization; preserve shared resources/history and stop on any other action. | Lifecycle `installer/agent-installations/ats-agent/lifecycle.yaml`; dry-run inventory digest `38fd2c0f…`; backend/state evidence 2026-11-28; rejected plan hash above. |
| B — Addition identity and local roundtrip | Reuse existing identity/profile and `addition_agent` / `math.add`; signed result and owner readback | **Read-only identity check complete; local evidence reused**, not rerun. Mays source pin `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`. | One enabled Cognito test user and one ACTIVE owner/tenant-matched profile exist. The identity has no entitlements; global Addition query found one expired-only row. Addition catalog remains ABSENT/dispatch-only. | Prior local suites: 70 and 11 passed. | One temporary `addition_agent` entitlement is necessary. A live foreign-owner 404 requires a second valid Cognito principal; pool currently has one user. | Include only the short-lived Addition grant in the combined plan; request separate explicit approval for a temporary second principal, or report foreign-owner 404 as local-only. | `tests/test_agent_order_dispatch_e2e.py`; read-only Cognito/profile/entitlement checks; integrated Mays source. |
| C — Addition live authorization | One synthetic order `19 + 23 = 42`; signed result, consumer persistence, `COMPLETED`, owner GET; preserve idempotency/privacy | **NOT RUN**; no live order authorized | Deterministic Addition runtime; no ATS/AI provider. Shared transport reused. | Local evidence retained; no live test. | No valid test entitlement or execution-time token available in repository. Existing Analysis-agent has two unrelated PENDING orders; untouched. | After explicit gates, use one authenticated POST only, no retry; verify exact WorkItem/result/owner readback. Prepare exact serialized payload hash for approval. | Prior local evidence `RIS-AGENT-INSTALLATION-09-ADDITION-PILOT.md`; current checkpoint baseline `21aa96a`. |
| D — Shared contracts/security | Keep `ORDER_DISPATCH`, WorkItem, worker, HMAC `ORDER_RESULT`, Mays result consumer, idempotency and owner-only result projection | **LOCAL TESTED / HISTORICAL LIVE EVIDENCE REUSED** | No contract or shared infrastructure change. | The new test verifies same order/work correlation, signed result acceptance, `processing=COMPLETED`, exact result 42, unchanged `orderDescription`, no public `agentOrder`, and foreign-owner GET 404. Existing suites cover stable dispatch/result idempotency and auth/privacy negatives. | Live repeat of these assertions remains unverified at current state. | Recheck only within the one approved live order/readback; do not replay or redrive. | New test `test_addition_order_round_trip_and_authorized_read_back`; prior local and live evidence cited above. |
| E — ATS/API scope | Exclude HTTP ATS canary; preserve historical source/tests/results | **SCOPE EXCLUDED**, not erased | No ATS source, AnalysisAgent, JS parser, historical result, or test was deleted or modified. | No ATS integration test or ATS provider call was executed in this Addition-only checkpoint. | Actual ATS deactivation is still pending Phase A lifecycle approvals; excluding ATS from the test scope alone does not disable it. | Complete Phase A before claiming deactivation; leave historical evidence intact. | Prior history retained in existing ATS reports and tests. |

## Local execution record

- Baseline branch `feature/ris-analysis-integration-07`, starting HEAD
  `b915f5731a76fb9f024acda7d8afa390d2c87be4`.
- Addition/authorization/lifecycle command:
  `python -m pytest tests/test_addition_agent.py tests/test_mo_addition_authorization_matrix.py tests/test_agent_lifecycle.py -q`
  → **70 passed**.
- Cross-repository command used only the read-only integrated Mays checkout:
  `MO_ORDERS_SRC=installer/projects/mays_order_builder/lambda/src python -m pytest tests/test_agent_order_dispatch_e2e.py::TestAgentOrderDispatchE2E::test_addition_order_round_trip_and_authorized_read_back tests/test_mo_dispatch_handoff.py -q`
  → **11 passed**.
- The new test uses synthetic identity/table/queue boundaries and the actual
  RIS reader, dispatch ingress, pipeline, AdditionAgent, Transport V1, Mays
  signed-result validation/consumer and owner projection. No AWS or external
  HTTP/ATS endpoint is contacted.
- Read-only AWS preflight 2026-11-28 verified account `262370457690`, region
  `eu-central-1`, identity pool with one enabled synthetic user, one ACTIVE
  tenant-matched profile, zero current test-owner entitlements, and one
  expired-only global row each for ATS and Addition. The four ATS and four
  Addition historical orders are all `processing=COMPLETED`; no open relevant
  work or results. Shared worker DLQ approximate visible count is 1; not
  received or inspected.
- Lifecycle `DISABLE` dry-run used a fresh redacted inventory and returned
  `DRY_RUN`, zero blockers, `ACTIVE→INACTIVE`, `expired_only`, and no
  entitlement withdrawals. Inventory digest starts `38fd2c0f`; output remains
  outside the repo at `%TEMP%\ris-addition-final-e2e\ats-disable-impact-current.json`.
- Terraform context was verified read-only: workspace `ris-dev2`, state serial
  `76`, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082`; only the catalog seed
  is managed in state, no foundation-entitlement resources. At that pre-plan
  checkpoint, no plan/apply had been made; the rejected plan and its scope
  deviation are documented in the follow-up section above.
- No code/runtime defect was established. Phase 2 changes the Terraform ATS
  catalog seed to `INACTIVE` and updates its seed regression. The targeted seed
  regression passed (**26 passed**); no existing Addition/live test suite was
  repeated. The required deployment bundle build completed; agent bundle SHA
  prefix `507bc17d`, analysis bundle `370890d4`, reader bundle `bea4c3e5`.

## Remaining approval gates — Apply and live order not approved

Target scope: account `262370457690`, region `eu-central-1`, workspace
`ris-dev2`, latest read-only state serial `76`, lineage
`a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 version
`M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`. Re-verify immediately before any newly
authorized plan.

### A. Disable historical ATS agent

1. Review fresh, read-only inventory for ATS agent-scoped entitlements, open
   orders/results and in-flight queue state. Existing 20A2 evidence confirms
   zero `ats-agent` entitlement rows only for one synthetic identity; it is not
   sufficient to define the global withdrawal set.
2. Use `installer.agent_lifecycle` **DISABLE** only. No UNINSTALL, DETACH,
   PURGE, deletion of orders/work/results, or shared-resource changes.
3. Plan exact withdrawal of any still-valid `ats-agent`-only entitlement(s)
   using the established provisioning plane, plus the agent-catalog row update
   `ats-agent: ACTIVE → INACTIVE` if it is still active. Any unexpected plan
   action, shared-resource change, or unreviewed entitlement is a stop.
4. Approval needed: exact inventory digest/entitlement IDs (redacted in report),
   reviewed plan hash, actor/authority, and explicit Apply authorization.
   Catalog INACTIVE is not treated as the worker gate; entitlement withdrawal
   is required to stop authorized dispatch/worker execution. Keep all shared
   transport and historical data.

### B. One Addition order

1. Current read-only check found one enabled user in the target pool and one
   ACTIVE profile with matching tenant claim. Do not create a user/profile
   unless separately listed and approved.
2. Freshly check only the exact test owner's `addition_agent` entitlements and
   open/queued work. If missing, request exactly one short-lived row using the
   existing Terraform foundation-entitlement mechanism:
   `userId=<verified synthetic sub>`, `tenantId=<matching tenant>`,
   `agentId=addition_agent`, `validFrom=T0-1m`, `validUntil=T0+15m`.
   That seed is user/tenant/agent-wide (no `apiProfileId` binding) and does not
   populate TTL; it must be explicitly removed through the same IaC lifecycle
   after the test. Do not activate an Addition catalog row; it remains
   dispatch-only.
3. Request permission for **at most one initial** authenticated `POST /orders`
   at the verified RIS-DEV2 Orders endpoint. Payload: synthetic customer
   `Addition QA`, `customer@example.invalid`; one item `ADD`, quantity 1,
   unitPrice 1 EUR; `orderType=agent.execution`; `agentOrder.target` is
   `addition_agent/math.add`; inputs `left=19`, `right=23`; a unique fixed
   requestId/idempotency key and exact payload SHA-256 must be filled into the
   approval after final serialization. No ATS/API/AI provider execution.
4. Permit only the single matching owner GET and, if a second existing
   synthetic identity is available and separately approved, one foreign-owner
   GET. Otherwise retain the existing local 404 evidence and report that
   foreign-owner denial was not live-tested. No second order, manual POST
   retry, direct Lambda invocation, queue receive/redrive, recovery or cleanup
   outside the exact approved entitlement cleanup.
5. Accept existing SQS automatic retry behavior (`maxReceiveCount=3`) for this
   one logical work item; no queue configuration changes. Stop on any failed,
   ambiguous or mismatched status; do not retry the order.
6. Cleanup is a separate IaC mutation: remove only the temporary
   `addition_agent` entitlement seed, retaining order/work/result evidence and
   all shared infrastructure. Its exact cleanup plan requires review/approval.

Approver/authority/date; fresh inventory/state digest; ATS lifecycle plan hash
and exact scope; Addition entitlement add/cleanup plan hashes; final request
payload SHA-256 and idempotency key; one-order approval; retry acceptance;
owner-read permission: **not supplied**. Gate A Apply: **NOT APPROVED**. Gate B
entitlement Apply: **NOT APPROVED**. Gate C initial order: **NOT APPROVED**.

No further live action is taken until those approvals are explicit. The first
plan was rejected; the corrected plan passed scope and guard, as recorded above.
Do not use the rejected binary. Apply remains unauthorized and is constrained
by the temporary grant expiry. Main merge was not performed. The protected
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` was not used
as output or touched/staged by this follow-up.

## Final Addition live E2E — PASS; cleanup awaits separate approval

On 2026-11-28 at 12:01Z, final execution gates passed: AWS account
`262370457690`, region `eu-central-1`, workspace `ris-dev2`, State serial 78,
the approved State S3 version, matching owner profile and active Addition grant,
and paginated `POST /orders` on API `r95qvhg2p3`. Exact request-body SHA-256:
`9db3d7ecf238bd5b3875ab3958ea9a4a9cb0173d07c04270a21caeea8790d907`.
Authentication used existing `USER_PASSWORD_AUTH`; the Cognito ID token's
signature, issuer, audience, subject, tenant and expiry were checked in memory.
No credentials or token were persisted or logged.

Exactly one POST was sent to
`https://r95qvhg2p3.execute-api.eu-central-1.amazonaws.com/orders`; HTTP 201
created order `ord_e83b1c15a32901a2622acc7f`. No manual retry was sent.
Read-only verification established:

- Persisted and owner-GET `orderDescription` exactly match the approved
  canonical description; Request-ID and idempotency key remain
  `ris-addition-live-f871426bc9444d4c98e4a9fb24dc925c`.
- Dispatch `SENT`; correlated WorkItem `work-dae09d78518965e1`,
  `addition_agent/math.add`, inputs 19 and 23, status `COMPLETED`, sum 42;
  `orderResultDelivery.status=SENT`.
- The matching `ORDER_RESULT` message ID is recorded in the completed Orders
  processing projection. The deployed result consumer was Active with its SQS
  event-source mapping Enabled. Its result-handler contract verifies HMAC before
  `apply_result`; the correlated result was applied as `processing=COMPLETED`,
  sum 42. Result queue, result DLQ and dispatch DLQ had zero visible/in-flight
  messages at readback.
- Authenticated owner `GET /orders/{orderId}` returned HTTP 200 with the same
  `orderDescription` and completed result 42.

### Entitlement cleanup — proposed only; separate approval required

No cleanup was executed. Proposed narrowly scoped operation: delete only the
temporary row in `ris-dev2-dev-entitlements` with primary key
`entitlementId=addition-acceptance-b939b2ba7c27430b`, scoped to the verified
synthetic test identity and `addition_agent`. Do not change/delete the user,
owner profile, order/work/result evidence, queues or any other entitlement.
Re-read the exact row and obtain explicit approval immediately before cleanup;
no Terraform operation is part of this proposal.

## Addition entitlement cleanup plan — BLOCKED; Apply not authorized

Baseline `726541164a80bed28cc46250d273d553851965a2`. Read-only preflight
confirmed account `262370457690`, region `eu-central-1`, workspace `ris-dev2`,
backend `ris-dev2-tf-state-dev` / `env:/ris-dev2/dev/terraform.tfstate`, lock
table `ris-dev2-tf-lock`, State serial 78 / lineage
`a0bd361d-5cd1-a207-a8c0-e6888f0be082` / S3 VersionId
`Nv9DBw9WQi48972QdhqULqPlpG3Ddi4y`. The only Terraform-managed foundation
entitlement is the approved key
`addition-acceptance-b939b2ba7c27430b`; its live DynamoDB row matches the
verified test owner and `addition_agent`. ATS catalog remains `INACTIVE`,
Addition catalog `ABSENT`; completed order/work evidence remains present.
Reused the existing 19G5 input file unchanged (SHA-256
`1ada876c6c98080206c9d29ca55549b4b8f254e1f2a5c0e915f9d6097016e6e7`), preserved
artifacts, existing TF_DATA_DIR/workspace, and Terraform 1.17.0. No build or
artifact change occurred.

Created only an external supplemental Terraform input setting
`foundation_entitlements={}`; file SHA-256
`85cb711ee43e1ce30542037df3431459576a5db0f4a3c89cc1e6445abe0d4405`.
Exactly one full-refresh, normally locked `terraform plan` invocation was
attempted. It exited 1 before saving a plan. The diagnostic was not retained by
the invocation wrapper, so the failure cause is unknown. No saved plan exists;
there is no plan hash or scope to approve. The shared-infrastructure guard could
not be evaluated and **PASS is not established**. Do not retry/replan under the
single-plan authorization; a new explicit plan authorization is required after
the failure cause is resolved.

Post-attempt read-only checks confirmed State remains serial 78 and the same S3
version; no active Terraform lock record was found (only backend checksum
metadata). No Apply, entitlement deletion, or other AWS mutation occurred.
Cleanup Apply remains **NOT AUTHORIZED**. Status/audit checkpoint only; protected
19F2 results JSON remains untouched and unstaged.

## Cleanup-plan correction — PASS; awaiting Apply authorization

Baseline `c6b764ec94a19d9e950d49a2c50817d4e20883c3`. Local diagnostics found the
previous runner had pointed `TF_DATA_DIR` at the parent of the actual Terraform
data directory. Terraform therefore lacked module-install metadata. The
correct existing RIS-DEV2 `.terraform` directory had the exact cached backend
and workspace, but four local module entries added since that cache was made
were missing. Ran ordinary `terraform init -input=false -lockfile=readonly`
against that existing cache: it installed those local modules and reused the
locked AWS/time providers; no backend reconfiguration/migration occurred and
`terraform/.terraform.lock.hcl` remained unchanged. `terraform validate` then
passed (with existing deprecation warnings). No build, runtime change, or AWS
infrastructure mutation.

Immediately before the single authorized plan, preflight reconfirmed account
`262370457690`, region `eu-central-1`, workspace `ris-dev2`, State serial 78 /
lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / S3 VersionId
`Nv9DBw9WQi48972QdhqULqPlpG3Ddi4y`; exact target row and sole managed
`foundation_entitlement`; ATS catalog `INACTIVE`; Addition catalog `ABSENT`;
and preservation of the completed live order/work evidence. Existing 19G5
inputs and artifact hashes matched. The only supplemental variable remained
`foundation_entitlements={}`.

Exactly one full-refresh plan ran with normal state locking using the corrected
existing `TF_DATA_DIR`. Terraform 1.17.0 exit code **0**. Complete stdout and
stderr were captured and redacted outside the repository:

- stdout: `%TEMP%\opencode\ris-dev2-addition-entitlement-cleanup-c6b764e.stdout.redacted.txt`
  (41,668 characters)
- stderr: `%TEMP%\opencode\ris-dev2-addition-entitlement-cleanup-c6b764e.stderr.redacted.txt`
  (0 characters)
- Saved plan:
  `%TEMP%\opencode\ris-dev2-addition-entitlement-cleanup-c6b764e.tfplan`
- Plan SHA-256: `d4c14cfb45105b76e689aa81b65ef6b645ba802cc1c59f7fe3f4b647265ccb10`

Plan scope **exactly 0 Add / 0 Change / 1 Destroy / 0 Replace**. The sole
action is delete of
`module.dynamodb.aws_dynamodb_table_item.foundation_entitlement["addition-acceptance-b939b2ba7c27430b"]`;
the planned prior item matches table `ris-dev2-dev-entitlements`, the approved
entitlement ID, owner, tenant and `addition_agent`. No other resource action.
The shared-infrastructure guard returned `safe=true`,
`SHARED_TEARDOWN_AUTHORIZED`, with the exact scoped cleanup intent and this plan
hash; its sole finding is that one entitlement item in the shared DynamoDB
module. No shared table or infrastructure resource is planned for deletion.
Remote State version remained unchanged and the Terraform lock was released.

### Apply approval — pending; NOT GRANTED

> Approve at most one Apply of saved plan SHA-256
> `d4c14cfb45105b76e689aa81b65ef6b645ba802cc1c59f7fe3f4b647265ccb10` in AWS
> account `262370457690`, region `eu-central-1`, workspace `ris-dev2`, State
> serial 78 / lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / S3 VersionId
> `Nv9DBw9WQi48972QdhqULqPlpG3Ddi4y`. Exact scope: 0 Add / 0 Change / 1 Destroy
> / 0 Replace, deleting only the foundation entitlement
> `addition-acceptance-b939b2ba7c27430b` from
> `ris-dev2-dev-entitlements`. ATS remains INACTIVE; Addition catalog remains
> ABSENT; retain user, profile, Orders/WorkItem/result evidence, queues and all
> shared infrastructure. Apply authorization: **NOT GRANTED**.

**STOP at the cleanup-Apply gate.** No Apply or cleanup was performed. Recheck
the exact target row, State serial/version, saved-plan hash and guard immediately
before any separately approved Apply. Protected 19F2 results JSON remains
untouched and unstaged.

## Final cleanup Apply — PASS; post-Apply verification complete

Baseline `1c98bd681619bd02f19be6711495a185f35f2657`. Immediately before Apply,
reconfirmed the approved saved-plan SHA-256
`d4c14cfb45105b76e689aa81b65ef6b645ba802cc1c59f7fe3f4b647265ccb10`, AWS
account `262370457690`, region `eu-central-1`, workspace `ris-dev2`, State
serial 78 / lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` / S3 VersionId
`Nv9DBw9WQi48972QdhqULqPlpG3Ddi4y`, exact target item and resource address,
correct cached backend/TF_DATA_DIR, guard `safe=true` /
`SHARED_TEARDOWN_AUTHORIZED` for exactly that entitlement, and preserved
artifact hashes. The plan remained exactly 0 Add / 0 Change / 1 Destroy / 0
Replace.

Applied the saved plan once, with Terraform 1.17.0; exit code 0. No replan,
retry, or Terraform command followed. Complete stdout/stderr were captured and
redacted outside the repository (stdout 3,695 characters; stderr 0):

- `%TEMP%\opencode\ris-dev2-addition-entitlement-cleanup-c6b764e.apply.stdout.redacted.txt`
- `%TEMP%\opencode\ris-dev2-addition-entitlement-cleanup-c6b764e.apply.stderr.redacted.txt`

Read-only post-Apply verification **PASS**:

- `addition-acceptance-b939b2ba7c27430b` is absent from
  `ris-dev2-dev-entitlements` and no longer managed in State. State diff removed
  only `module.dynamodb.aws_dynamodb_table_item.foundation_entitlement["addition-acceptance-b939b2ba7c27430b"]`;
  no resource address was added.
- ATS catalog remains `INACTIVE`; Addition catalog remains `ABSENT`.
- State lineage is unchanged; serial advanced `78 → 79`; new S3 VersionId
  `69Mksseizux6JercRCm0BTdIVF5S5GeUF`. Terraform lock released.
- Entitlements table ARN/schema/index configuration and all 10 managed
  RIS-DEV2 Lambda `CodeSha256` values are unchanged. Preserved local artifact
  hashes also remain unchanged.
- Live order `ord_e83b1c15a32901a2622acc7f` and WorkItem
  `work-dae09d78518965e1` rows are byte/value-equivalent to their pre-Apply
  readbacks: processing remains `COMPLETED`, sum 42; WorkItem remains
  `COMPLETED`, result delivery remains `SENT`.

Cleanup is **COMPLETE**. No Orders, WorkItems, results, catalog rows, queues,
users, profiles, shared tables, Lambda functions or other infrastructure were
deleted or changed. No live order, redrive, Main merge, or QA/build was run.
Feature branch integration is prepared for final approval; no main merge was
performed. Protected 19F2 results JSON remains untouched and unstaged.

## Final main-integration readiness — VERIFIED; merge gate remains closed

Closeout baseline: feature HEAD `bb7aa1b393865a84e4a796720004e613a51249a6`;
`origin/main` `97a60df83a5db56ea750e4342d7a01b00c8ad56b`; merge-base
`54dbf3527fa439944e686fe338e43fbfe92322bd`. Main has one commit not on the
feature branch (merge commit for PR #16); the feature branch has 141 commits
since that merge-base. `git merge-tree --write-tree HEAD origin/main` produced
candidate tree `6f6526c4081b2c2d7f688d0d9c2464a1aeb120cd` with no conflicts.
This was a read-only merge-tree calculation; neither branch was merged or
rewritten. PR #16
(`https://github.com/maynowak/Mays-Recruiting-Intelligence-System/pull/16`)
is already MERGED and corresponds to shared baseline `54dbf35`. Therefore the
current closeout commits require a new PR. No current open PR or successful
check run for head `bb7aa1b` was found at review time.

### CI/deployment impact

- `.github/workflows/ci-cd.yml` (`Ground Zero CI`) triggers on PRs targeting
  `main` and pushes to `main`. It runs Terraform format and backend-free static
  validation only; comments state that it uses no AWS credentials and does no
  plans, applies, or automated deployment. A PR schedules this static check;
  a merge push to main schedules it again. No deployment trigger was found in
  the reviewed workflows.
- `.github/workflows/mays-compatibility-qa.yml` is push-scoped to the feature
  branch and selected paths, plus manual dispatch; it is not a main-merge
  deployment workflow. Latest successful run found was `46123512652` at
  `6ef378e` (not current head `bb7aa1b`). Existing QA artifacts and focused
  evidence are reused; no new build or FULL QA was run for this documentation-
  only closeout.
- Existing successful Ground Zero CI for PR #16 is run `45043508991`, head
  `54dbf35`; historical evidence only, not a check on the current head.

### Acceptance and reused evidence

| Gate | Status | Evidence |
|---|---|---|
| `TECHNICAL_INTEGRATION` | VERIFIED | Existing integration/QA reports and evidence under `docs/reports/` and `docs/reports/evidence/19F*`–`20A2`; conflict-free merge-tree |
| `ADDITION_LIVE_E2E` | PASS | Existing live E2E report/auditlog: exactly one POST, result 42, owner GET; OrderDescription unchanged |
| `ATS_HTTP_AGENT` | DISABLED | ATS catalog `INACTIVE`; Addition catalog `ABSENT` |
| `TEMPORARY_ENTITLEMENT_CLEANUP` | COMPLETE | One approved row removed; post-Apply read-only verification recorded above |
| `SHARED_INFRASTRUCTURE` | UNCHANGED | State diff removed only the approved entitlement resource; shared table shape and 10 Lambda code hashes unchanged |
| `STATE_SERIAL` | 79 | Lineage unchanged; S3 VersionId `69Mksseizux6JercRCm0BTdIVF5S5GeUF` |

No source/runtime change was made during reconciliation, so no targeted
regression was indicated. The working tree contains the pre-existing protected
local modification to `docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json`;
it was not staged, changed, or included in the proposed PR. The feature-side
diff from the shared base covers 203 paths (approximately 25.5k insertions and
247 deletions); review the generated PR file list and current-head required CI
before approval. No AWS, Terraform, live-order, build, redrive, or Main-merge
action was performed.

### PR and Main-merge approval request

Prepare a new PR from `feature/ris-analysis-integration-07` at
`bb7aa1b393865a84e4a796720004e613a51249a6` into `main`; do not reuse merged PR
#16. After the new PR's required current-head checks pass and the complete file
list is reviewed, recommended action is a regular merge of this exact head.
The expected automated Main-side action is read-only Ground Zero CI. This is a
request for a separate explicit Main-merge decision, not authorization to merge.

**MAIN_MERGE=false — STOP at Main-merge gate.** Protected 19F2 file remains
unstaged and untouched.

### PR opened — current approval target

New PR #17 is open: `https://github.com/maynowak/Mays-Recruiting-Intelligence-System/pull/17`,
base `main` at `97a60df83a5db56ea750e4342d7a01b00c8ad56b`, feature head
`a2b7d8127341220e019b359e596fcbc45531fb48`. GitHub reports `MERGEABLE`; the
required `terraform-static` Ground Zero CI check for this head is
**IN_PROGRESS**. Review decision is pending. The concrete requested decision
is: after this check completes successfully and the PR file list/review
requirements are satisfied, authorize a regular merge of PR #17 at its then-
current head into `main`. That authorization has not been granted here; do not
merge while CI is running.
