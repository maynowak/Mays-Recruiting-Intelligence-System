# RIS-DEV2 Final Live Acceptance Orchestration — 20 / 21

**Current result: STOP at APPROVAL GATE 1.** Read-only 20A2 preparation found
an existing synthetic Cognito identity and matching active owner profile, but
no required live ATS entitlement. The internal synthetic Analysis validity has
expired. Existing SQS event-source mappings allow automatic retries, one
existing Work DLQ message is present, and no enforceable all-in cost ceiling
was established. No Gate 1 authorization was provided; **no identity,
entitlement, configuration, queue, or other AWS mutation was made**. Phases
20A3, 20B and 21 were not executed. Do not continue automatically.

## Baseline and reuse

- Baseline: branch `feature/ris-analysis-integration-07`, HEAD
  `bfb9a666b623dbb7a8aae55035dac67d8e77c665`; AWS account `262370457690`,
  region `eu-central-1`, workspace `ris-dev2`.
- State remains serial `76`, lineage
  `a0bd361d-5cd1-a207-a8c0-e6888f0be082`, S3 VersionId
  `M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T`.
- Reused deployment verification from
  `docs/reports/RIS-DEV2-WORKER-CONTROLLED-APPLY-19H.md`: Agent-Worker and
  Dispatch-Ingress are Active/Successful with the approved Worker bundle;
  Analysis/Reader remained unchanged; `ANALYSIS_SYNTHETIC_MODE=true`.
- Reused 19F8 E2E and original Mays `orderDescription` suite evidence. Mays
  source is `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`; the original tests
  passed 15/15. 19F8 E2E is local and mocks DynamoDB/SQS/HTTP; it is not live
  authentication, entitlement, ATS-provider, billing, or readback evidence.
- Existing 20A report remains a historical snapshot. In 20A2, a targeted
  lookup of the already-configured synthetic subject (not a user-table scan)
  closed the identity-discovery gap described there. No raw subject, tenant,
  profile ID, token, or personal data is included here or in evidence.

## 20A2 — consolidated read-only findings

### A — Identity and entitlement

- A filtered Cognito lookup for the existing Analysis synthetic subject found
  exactly one user; it is Enabled and `CONFIRMED`. Its configured tenant
  attribute matched the synthetic tenant already bound in the Analysis
  configuration.
- A targeted APIProfiles owner-index query found one ACTIVE profile for that
  subject; its owner and tenant binding matched. This establishes a candidate
  test identity/profile only. No JWT was issued or tested.
- A targeted Entitlements `gsi-user` query for that same subject found **no**
  `ats-agent` entitlement (and no relevant Analysis-agent row). No scan was
  used. Therefore `ats-agent` / `analyze.job` authorization is not ready.
- The worker entitlement contract checks user, tenant, agent, optional
  `apiProfileId`, and `validFrom`/`validUntil`. It has no one-use count or
  remaining-balance field. A grant is not itself a one-order or billing cap.

### B — Synthetic authorization and available management mechanism

- Live `ANALYSIS_SYNTHETIC_MODE` remains `true`, but
  `ANALYSIS_SYNTHETIC_EXPIRES_AT=2026-11-26T17:40:28Z` is expired. The current
  capability allowlist need not be broadened for this proposal.
- The existing root Terraform variable `analysis_synthetic_expires_at` drives
  the Analysis Lambda environment. Minimal proposed validity is the scheduled
  20B start time `T0` minus one minute through `T0 + 15 minutes` (the existing
  10-minute observation cap plus a five-minute buffer). This is a proposal,
  not a change; the exact UTC values must be approved and entered before any
  plan.
- The existing synthetic grant mechanism is Terraform
  `foundation_entitlements`, backed by
  `aws_dynamodb_table_item.foundation_entitlement`; the current var-file map is
  empty. It can express one user/tenant/agent row with a validity window.
- Important scope limitation: although the input type declares optional
  `apiProfileId`, the current resource implementation does **not** write that
  attribute. This mechanism creates a user/tenant/agent-wide entitlement, not
  an APIProfile-bound entitlement. It also intentionally omits DynamoDB
  `expiresAt`; `validUntil` stops authorization in application code, but the
  row remains until a separately approved Terraform removal. The approver must
  explicitly accept this residual scope and later cleanup requirement.
- The profile-scoped `grant_offer` code has no verified productive caller and
  requires an ACTIVE offer; no live profile-scoped grant path was established.
  No grant was created, extended, or changed.

### C — Cost boundary and retry behavior

- The RIS adapter only validates `unitPrice` as a positive integer and passes
  it through. No maximum, non-billable test SKU, zero-charge guarantee, or
  all-in per-order price was verified. The ATS agent also posts the synthetic
  job/profile to the external
  `https://mays-jobsearch.vercel.app/api/ats-analysis`; provider pricing and
  any usage charges are unknown.
- One order also consumes API Gateway, Lambda, SQS, DynamoDB and logging
  operations. Available evidence does not provide an enforceable upper bound
  for these costs. No cost ceiling can be inferred from `unitPrice: 1` or from
  the one-order operator limit.
- The existing dispatch, work, and result queues each use redrive
  `maxReceiveCount=3`, and their Lambda event-source mappings are enabled.
  Failed processing can therefore be automatically delivered again; 20B's
  `AUTOMATIC_RETRY=false` cannot be guaranteed by the current verified
  configuration. The `ris-dev2-dev-dlq` currently reports approximately one
  visible message. Only approximate counts were read; no DLQ or queue message
  body was received. No historical message was changed.
- Changing retry/DLQ behavior would be an additional AWS mutation affecting
  existing queue processing, and could route failures into the already
  non-empty Work DLQ. It is not included in the proposed Gate 1 change set and
  requires a separate scope/impact review and explicit approval. Alternatively
  the canary policy must explicitly accept the deployed retry semantics; this
  request does not authorize that exception.
- A billing owner must confirm whether the proposed single ATS line item is
  chargeable, provide an exact maximum charge, and confirm external ATS
  provider cost treatment. Until then `BILLING_SCOPE` is blocked.

Sanitized findings are in
`docs/reports/evidence/20A2/read-only-findings.json`.

## Single proposed approval template — Gate 1 / 20A3, NOT GRANTED

This template covers only the two identified Terraform-backed changes. It
does **not** authorize a live canary, queue-policy change, order, direct
invocation, or Main integration. Values in angle brackets must be resolved
through the approved secure channel; do not place identity data or credentials
in Git.

```text
I authorize preparation of one Terraform plan for the following exact
RIS-DEV2 synthetic authorization changes only. This is not 20B authorization.

Baseline account / region / workspace:
  262370457690 / eu-central-1 / ris-dev2
Baseline State:
  serial 76; lineage a0bd361d-5cd1-a207-a8c0-e6888f0be082;
  S3 VersionId M1N4isxd7i0.iAsxP4jLq0U47ymxlw9T
Verified existing test identity/profile:
  the already-configured synthetic Cognito subject and its one ACTIVE,
  owner-/tenant-matching APIProfile, identified through secure owner evidence
  (do not paste subject, profile ID, token, or personal data here)

Change 1 — one temporary foundation entitlement:
  exactly one foundation_entitlements map entry
  entitlementId: <unique 20A3 synthetic identifier>
  userId: <verified subject from secure record>
  tenantId: <the already-matching synthetic tenant from secure record>
  agentId: ats-agent
  validFrom: <scheduled 20B start T0 minus 1 minute, UTC>
  validUntil: <T0 plus 15 minutes, UTC>
  apiProfileId: not persisted by current Terraform resource; this is
    user/tenant/agent-wide. I explicitly ACCEPT this scope: [YES/NO]
  No other users, tenants, agents, or grants.

Change 2 — synthetic Analysis validity only:
  analysis_synthetic_expires_at = <the same T0 plus 15 minutes, RFC3339 UTC>
  Keep ANALYSIS_SYNTHETIC_MODE=true and the current capability allowlist;
  do not change runtime source or other configuration.

Expected intended actions (not a plan result): one entitlement table-item add
and one Analysis Lambda environment update; no other resource changes.
If the actual reviewed plan differs, STOP. A fresh explicit plan review and
separate Apply approval remain mandatory under existing controls.

Acknowledgment: the entitlement's validUntil blocks authorization but the
Terraform seed omits DynamoDB TTL; row-removal cleanup needs a later separately
approved Terraform change. No automatic cleanup is authorized.

Approver / authority / timestamp / approval reference: <required>
Decision: NOT GRANTED by 20A2. Gate 1 remains closed.
```

Even if Gate 1 is later approved and 20A3 passes, 20B remains blocked until
the cost owner supplies an enforceable all-in cap and the retry conflict above
is resolved through explicit scope/approval. A separate Gate 2 must then
include the final resolved payload/hash, identity/profile evidence,
entitlement window, idempotency key, maximum one order, cost limit, and
observation limits. The existing 20A report contains the draft 20B contract;
its profile placeholder and cost proposal are not authorization.

## Gate 1 continuation — consolidated change review and limits

This section makes the approval proposal concrete without repeating 20A2 or
performing AWS reads/writes. Owner and tenant are deliberately referenced by
the exact already-verified configuration bindings rather than copied as raw
identifiers into Git:

- **Owner/user:** `var.analysis_synthetic_user_id`, the same configured
  Cognito `sub` that owns the one verified ACTIVE APIProfile
  (`ownerUserId == sub`).
- **Tenant:** `var.analysis_synthetic_tenant_id`, the tenant already bound to
  that owner and matched by the verified Cognito tenant attribute and profile.
- **Requested operation:** agent `ats-agent`, capability `analyze.job`,
  WorkItem type `ats_process`. The entitlement row schema stores `agentId`,
  not capability or WorkItem type; therefore the proposed grant cannot
  technically restrict use to only `analyze.job`/`ats_process`. Do not describe
  it as capability-scoped.

| Mutation | Verified current state | Exact proposed state | Verification if separately approved |
|---|---|---|---|
| Temporary entitlement seed | `foundation_entitlements` input map is empty; targeted lookup found no required ATS row. | Add exactly one map entry with key `ris-dev2-live-acceptance-ats-agent-2026-11-27`; `userId=var.analysis_synthetic_user_id`; `tenantId=var.analysis_synthetic_tenant_id`; `agentId=ats-agent`; `validFrom=T0-PT1M`; `validUntil=T0+PT15M`. No other entry. | Before Apply: independently review saved plan and require exactly one `aws_dynamodb_table_item.foundation_entitlement` add. After separately approved Apply: targeted `GetItem` for the exact entitlementId; compare user/tenant/agent/window, then read-only confirm the active worker authorization check accepts only the intended owner/tenant/agent during that window and denies outside it. Never scan. |
| Analysis synthetic expiry | `ANALYSIS_SYNTHETIC_MODE=true`; expiry is `2026-11-26T17:40:28Z` (expired); current capability allowlist unchanged. | Root Terraform input `analysis_synthetic_expires_at = <T0+PT15M formatted RFC3339 UTC>`; retain mode `true`, current allowlist, and all other environment values. T0 must be an explicitly scheduled UTC 20B start entered in the approval before a plan; no guessed or rolling timestamp. | Before Apply: review saved plan for exactly the intended Analysis Lambda environment update and no other actions. After separately approved Apply: read-only `GetFunctionConfiguration` comparison of expiry, `ANALYSIS_SYNTHETIC_MODE=true`, allowlist, and unrelated environment values; verify function update is successful. |

The timestamp expressions above are exact intervals but intentionally are not
fabricated calendar timestamps: no canary schedule has been approved. The
approver must enter a concrete UTC `T0`, from which the entitlement values and
Lambda expiry are mechanically derived, before a Terraform plan is prepared.
If the Terraform input cannot represent an ISO timestamp for the entitlement
window in the existing accepted format, STOP and resolve that in plan review;
do not change runtime code or schema under this approval.

**Important authorization limit:** the Terraform seed drops optional
`apiProfileId`, and the stored entitlement has no capability, WorkItem-type,
use-count, or balance field. Its `validUntil` limits time only; within the
window it permits repeated authorized executions for that same user/tenant/
agent. It is not a one-time grant. The above proposal accepts that broader
user/tenant/agent scope only if the approver explicitly writes `ACCEPT`; if
one-use or profile/capability restriction is mandatory, the existing seed
mechanism cannot meet the requirement and Gate 1 must remain closed. Expiry
also does not delete the DynamoDB row: later Terraform removal is separate,
requires separate approval, and is not automatic.

### Cost, idempotency, retries, and DLQ — Gate 2 remains blocked

- **Estimated cost:** no defensible numeric estimate is available from the
  accepted evidence. The order `unitPrice` is a positive integer passed
  through by RIS; no verified price schedule, maximum, or non-billable SKU
  defines its monetary meaning. The external ATS endpoint's pricing/charge
  behavior is unknown. AWS request counts, duration, logs, data transfer, and
  pricing dimensions for the actual run are also not pinned. A cost estimate
  must therefore be reported as **unknown / not estimable from verified
  inputs**, not as `$0` or as the literal `unitPrice`.
- **Technically enforceable cost ceiling:** none was verified. A one-order
  operator limit, entitlement time window, idempotency key, AWS Budgets alert,
  or retrospective Cost Explorer reading is not an all-in per-order hard cap;
  none prevents an external provider charge. The concrete blocker is the lack
  of a verified provider price/charge contract and an enforceable cap spanning
  both provider and AWS charges. Until the provider/billing owner supplies a
  binding maximum and a mechanism that refuses execution above it, Gate 2
  cannot be approved.
- **Existing retry/DLQ behavior:** dispatch, work, and result queues retain
  their existing redrive policies (`maxReceiveCount=3`); the reused deployment
  evidence records enabled mappings. In the checked-in Terraform, Dispatch
  Ingress reports partial batch failures, while the core worker mapping has
  `batch_size=5` and no `function_response_types` override (so do not assume
  per-record retry isolation there). Result-consumer mapping details are not
  inferred beyond the reused deployment evidence. A processing failure can be
  redelivered up to the configured receive limit and then sent to its existing
  DLQ. The Work DLQ already had an approximate visible count of one in the
  20A2 read. No queue setting, message, DLQ, mapping, or existing order is to
  be changed as part of this proposal. Do not disable retries or drain/re-drive
  the existing DLQ.
- **Idempotency:** preserve the single canary's one order ID/work ID and stable
  keys through dispatch and result delivery. The result transport derives
  `messageId=msg_<workId>_order_result` and
  `idempotencyKey=<orderId>:<workId>:ORDER_RESULT`; duplicate deliveries are
  intended to avoid duplicate completion. Reused Worker Claim Fix 19C evidence
  establishes conditional `QUEUED→RUNNING` initial claim and suppresses a
  competing claim; a retry from `FAILED` conditionally increments the attempt
  and transient errors still raise for SQS redelivery. This is duplicate and
  attempt control, not a spend cap: an error after an external request may
  result in a later retry attempt, a new order with a different key is
  distinct, and provider-side idempotency/charge deduplication is not
  established by the existing evidence. Any exact canary key belongs in Gate
  2, not in this Gate 1 approval.
- **Retry exposure:** maximum receive count is known per queue, but the total
  number of external ATS calls and chargeable effects per logical order is not
  bounded by evidence because cross-stage retries and provider-side
  idempotency/charging are not jointly proven for the live path. The 19C claim
  guard suppresses a competing claim for the same active WorkItem; it does not
  prove that a downstream timeout/error after an ATS request is non-billable or
  deduplicated on a later FAILED attempt. Do not multiply per-queue receive
  counts into a purported dollar bound. Accepting deployed retries would
  require an explicit, informed exception at Gate 2; it still would not solve
  unknown billing.

Thus the requested “maximum one new order including possible automatic
retries” is an operator-level order limit only. It is **not** currently an
enforceable maximum of one external execution or one charge. No broad retry
deactivation or infrastructure redesign is proposed. The existing behavior
must remain unchanged unless a narrowly scoped, separately reviewed change is
later explicitly authorized; no such change is needed or authorized for Gate 1.

### Immediately usable Gate 1 decision text — NOT GRANTED

```text
Decision for RIS-DEV2 Gate 1 / 20A3 (not Gate 2 / not live-canary approval):

I authorize only preparation and review of one Terraform plan against the
verified baseline in this report, for exactly these two input changes:
1) one foundation_entitlements entry:
   key = ris-dev2-live-acceptance-ats-agent-2026-11-27
   userId = the existing var.analysis_synthetic_user_id (verified Cognito sub
            and ACTIVE APIProfile owner)
   tenantId = the existing var.analysis_synthetic_tenant_id (verified matching
              owner/profile/Cognito tenant)
   agentId = ats-agent
   validFrom = <approved T0 minus 1 minute, RFC3339 UTC>
   validUntil = <approved T0 plus 15 minutes, RFC3339 UTC>
2) analysis_synthetic_expires_at = <the same approved T0 plus 15 minutes,
   RFC3339 UTC>; retain ANALYSIS_SYNTHETIC_MODE=true and current allowlist.

Approved T0 (UTC): ____________________
I understand and ACCEPT that this seed is user/tenant/agent-wide, not
apiProfileId-, analyze.job-, ats_process-, or single-use-scoped: YES / NO
I understand the entitlement row remains after validUntil and later removal
requires a separate approved Terraform change: YES / NO

Expected plan is exactly one entitlement item add plus one Analysis Lambda
environment update. Any other action, replacement, delete, or drift: STOP.
Plan review approval: separate named approver/reference ____________________
Apply approval after reviewing the exact saved plan: separate approval only.

No permission is granted here for an order, Lambda invocation, queue receive,
retry-policy change, redrive, recovery, cleanup, live canary, or Main merge.
Billing/cost blocker acknowledged; Gate 2 remains closed: YES / NO

Approver / authority / timestamp / reference: ____________________
Decision: NOT GRANTED. Gate 1 remains closed until a complete explicit
approval is recorded; a NO or blank field means STOP.
```

If the approver requires strict one-time/capability-level authorization, or
requires an enforceable all-in cost cap, this proposal is **not approvable as
written**. Do not silently broaden this Gate 1 change set to solve either
limitation.

## 20A3, 20B and 21 status

| Phase / gate | Result |
|---|---|
| 20A2 identity discovery | PASS for existing confirmed synthetic user and matching ACTIVE owner profile |
| 20A2 entitlement readiness | BLOCKED — no required ATS entitlement for that identity |
| 20A2 synthetic validity | BLOCKED — Analysis synthetic expiry is past |
| 20A2 billing/cost boundary | BLOCKED — no verified all-in cap or non-billable test SKU |
| 20A2 retry boundary | BLOCKED — existing SQS retry policy allows up to three receives; one Work DLQ item exists |
| `APPROVAL GATE 1` | **STOP — no approval; no mutations** |
| 20A3 controlled authorization | NOT STARTED |
| `APPROVAL GATE 2` | NOT REACHED |
| 20B live canary | NOT RUN; orders 0; invocations 0; redrives 0 |
| 21 release acceptance | NOT READY — live execution/HMAC/result/owner readback remain unverified |
| Main integration | NOT prepared or performed |

The 19H deployment and 19F8/19G QA evidence remain valid for their documented
scopes, but they do not establish live Agent execution, live signed result
consumption, or live owner GET `orderDescription` roundtrip. The target status
`RIS-DEV2 LIVE E2E VERIFIED — READY FOR MAIN REVIEW` has **not** been achieved.

No Terraform plan/Apply, AWS mutation, entitlement write, order, Lambda
invocation, queue receive/delete/visibility change, retry, redrive, recovery,
or cleanup occurred in 20A2. The protected unstaged
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` remains
untouched. **STOP at Gate 1. No automatic continuation.**

## Gate reconciliation — synthetic technical canary vs commercial operation

**Review baseline:** `189b5c79acd00b56f1811258d1bd00f5bdb9a565`.
This reconciliation reuses 20A2 AWS evidence and the 19H/19F8 artifacts; it
does not repeat AWS reads, deployment verification, or QA.

### A — Synthetic technical live acceptance

**Decision: `LIVE_CANARY=BLOCKED`; Gate 1 and Gate 2 remain closed.**

The configured `ANALYSIS_SYNTHETIC_MODE=true` does **not** reliably exclude all
external provider calls in the proposed live canary:

1. The planned order targets `ats-agent` / `analyze.job`. Its actual worker path
   is `Agent-Worker → ATSAgent → ATSHttpClient → POST
   https://mays-jobsearch.vercel.app/api/ats-analysis` with the job and
   optional profile. `ATSAgent` does not read `ANALYSIS_SYNTHETIC_MODE`.
2. That flag is consumed by the separate dedicated `analysis_runner` /
   `AnalysisAgent` identity gate. It only grants an exact synthetic identity
   for that internal analysis capability after matching persisted WorkItem
   identity/status and unexpired configuration. It neither redirects nor
   disables the ATS agent's HTTP request. Its configured expiry
   `2026-11-26T17:40:28Z` is expired; this blocks that internal synthetic
   analysis path but is not a necessary configuration change for a canary that
   exclusively targets `ats-agent`. The prior proposal to extend that expiry
   must not be treated as a requirement or authorization for this ATS canary.
3. The RIS ATS client sends only `{job, profile?}`; it does not send the
   optional `ai` opt-in. The pinned Jobsearch API contract says AI defaults
   off and its documented deterministic path does not use an LLM. This is
   evidence against an intentional AI-provider request by this client, **not**
   proof that the currently deployed external service has no variable charge,
   that its live implementation still honors the pin, or that its hosting/API
   request is free. The endpoint is an external, independently deployed and
   mutable service; no current billing attestation or enforceable price bound
   is in the accepted evidence.
4. HTTP-library selection (`httpx`, else `requests`, else stdlib `urllib`) is
   only a transport-library fallback to the same URL; it is not a local or
   free-provider fallback. There is no explicit retry loop in `ATSHttpClient`.
   HTTP/network/contract errors become unsuccessful agent results. The worker
   classifies `ATSAPIError`/`ATSContractError` as non-permanent, persists the
   failed attempt and raises; the existing SQS work-queue redelivery can then
   start a new attempt and call the ATS endpoint again. Worker conditional
   claims suppress a competing delivery while an item is RUNNING, but a
   `FAILED` retry is a new attempt. With the existing `maxReceiveCount=3`, one
   WorkItem has at most three receives/agent attempts under that queue policy;
   each valid ATS attempt can make one POST. This is a finite call-count bound
   per WorkItem, **not** a monetary bound or provider idempotency guarantee.
   Result-queue redelivery concerns result delivery, not another ATS analysis.

**Cost boundary:** AWS charges remain possible even if the Jobsearch AI branch
is not used: API Gateway, Lambda (including retries), SQS, DynamoDB, and
CloudWatch Logs are on the path. The existing retry policy bounds receives per
message but does not impose a dollar ceiling. Metered AWS usage is not zero,
and the existing evidence contains neither a per-canary price calculation nor
an inline spend stop. The external Jobsearch request/hosting charge and any
provider-side charge are likewise unverified. No defensible numeric total or
all-in enforceable cap can be stated from the current code/evidence. Therefore
a “no monetary billing” guarantee, and a cost-safe approval without new
provider evidence or a synthetic no-egress path, are **not demonstrated**.

**Minimum technical path to a non-provider-billed technical E2E:** add a
default-off, exact-identity synthetic ATS adapter in the existing `ats-agent`
execution path which returns a deterministic fixture and fails closed without
any outbound HTTP when selected; test that the real worker/dispatch/result
path executes while the HTTP client is never called. Keep production routing,
entitlements, retries, and billing untouched. This requires a runtime source
change and redeployment, so it is outside this request and is not implemented.
It would test orchestration/roundtrip, not the external Jobsearch integration.
If the external endpoint itself must be exercised, obtain a dated service-owner
and billing-owner statement for the exact live endpoint/deployment confirming
AI disabled and maximum/no-variable charge for up to three ATS POST attempts,
plus an explicit accepted AWS usage allowance. If a hard all-in monetary cap
is required, the current stack has no synchronous enforcement; add a narrowly
scoped spend-control design or provider-side cap before reopening Gate 2. Do
not disable shared retries or use a budget alert as if it were a hard stop.

No revised approval template is issued: neither no-provider-egress nor a
verified external-provider/AWS cost limit is presently established. The earlier
20A3 approval text remains historical preparation only; it does not authorize
mutations and its Analysis expiry extension is not part of the ATS-agent path.

### B — Commercial agent entitlement and billing backlog

Recorded separately as
`docs/roadmap/RIS-AGENT-ENTITLEMENT-BILLING-01.md` (**BACKLOG; NOT
IMPLEMENTED, NOT AUTHORIZED**). Scope includes owner/tenant-bound entitlement;
`apiProfileId`, Capability, and Work-Type scoping; atomic usage limits;
idempotent cost reservation/settlement; explicit currency and monetary meaning
of `unitPrice`; retry-safe provider charging; and enforceable cost ceilings.
No code, schema, Terraform, IAM, or provider configuration for this work item
was changed. It is a commercial-agent capability, separate from this blocked
synthetic technical canary.

### Reconciled release gates

| Target | Decision |
|---|---|
| A — `ANALYSIS_SYNTHETIC_MODE=true` as provider-cost exclusion | **NO** — applies only to the separate internal Analysis identity path; ATS order path still POSTs externally |
| Synthetic technical canary with no external provider charge | **BLOCKED** — needs a strict no-egress synthetic ATS adapter or provider-owner cost evidence |
| All-in cost boundary using current mechanisms | **NOT ESTABLISHED** — finite SQS receives per WorkItem, no enforceable dollar cap; AWS usage remains billable |
| B — `RIS-AGENT-ENTITLEMENT-BILLING-01` | **BACKLOG ONLY** — not implemented |
| Gate 1 | **CLOSED** — no authorization for mutations or runtime changes |
| Gate 2 / live canary | **CLOSED; `LIVE_CANARY=BLOCKED`** |
| Orders, invocations, retries, redrive, AWS mutations | **0 performed in this reconciliation** |

The protected 19F2 results file was not included in these changes. No Main
merge, deployment, Terraform plan/Apply, or new QA was performed.

## Controlled suspension — final disposition

**Suspended at baseline `3e855b27ac8c8a35139dd72c437471060d62ea43`. STOP.**
This is a controlled pause, not a release-readiness or live-canary approval.

| Area | Final status | Existing evidence to reuse |
|---|---|---|
| Development | `VERIFIED` | Completed implementation and existing source/contract evidence; no development work reopened. |
| Unified full QA | `PASS` | Existing unified QA result and original Mays tests recorded in the referenced reports; do not rerun. |
| Mays module | `LOCAL_VERIFIED` | Existing pinned module/build/contract verification; no Mays module change. |
| OrderDescription | `LOCAL_E2E_VERIFIED` | 19F8 local mocked end-to-end contract and original Mays `orderDescription` suite evidence; not live proof. |
| Worker fix | `DEPLOYED` | `docs/reports/RIS-DEV2-WORKER-CONTROLLED-APPLY-19H.md` and `docs/reports/evidence/19H/post-apply-verification.json`. |
| Infrastructure | `VERIFIED` | Reused 19H deployment verification and State baseline documented above; no new AWS verification. |
| Live canary | `BLOCKED` | 20A2 targeted read-only findings, 20A preflight, and Gate Reconciliation in this report. |
| Approval Gate 1 | `CLOSED` | No authorization for entitlement/configuration mutation or Terraform activity. |
| Approval Gate 2 | `CLOSED` | No authorization for order creation or live execution. |
| Commercial readiness | `NO_GO` | External Jobsearch/provider cost is unverified; AWS spend has no proven all-in enforceable cap; retry-side provider billing is not contractually deduplicated. |

The statuses above distinguish completed engineering/local verification from
live and commercial readiness. They do not imply live Agent execution, a
provider charge of zero, a bounded all-in AWS cost, or readiness for Main.
`RIS-AGENT-ENTITLEMENT-BILLING-01` remains a separate backlog item at
`docs/roadmap/RIS-AGENT-ENTITLEMENT-BILLING-01.md`; it is not implemented.
No ATS test adapter will be implemented as part of this suspended
orchestration.

### Conditions to resume — all must be met; no automatic continuation

1. Resume only from a fresh, explicitly named operator/approver decision that
   references the then-current branch/commit and selects the exact next step.
   Gate 1 and Gate 2 are independent approvals; neither this suspension nor
   earlier proposal text grants either one.
2. Before any Gate 1 mutation, settle the synthetic-path scope: for the planned
   `ats-agent/analyze.job` order, `ANALYSIS_SYNTHETIC_MODE` is not the provider
   cost control and its expired Analysis Lambda setting is not to be extended
   as an unrelated side effect. Identify the actual execution path, owner and
   tenant binding, required entitlement scope, and approved mechanism. The
   current foundation seed's user/tenant/agent-wide scope and lack of
   single-use/profile/capability/work-type enforcement must be expressly
   accepted or Gate 1 remains closed. Any Terraform plan requires fresh
   baseline/state verification, exact plan review, and separate Apply approval.
3. Before Gate 2, provide authoritative current evidence from the Jobsearch
   service/billing owner for the exact endpoint's AI/provider behavior and
   maximum charge under the permitted retry count, plus an accepted AWS usage
   allowance or other enforceable all-in cost boundary. The pinned contract's
   AI-default-off rule alone is insufficient. If this cannot be supplied,
   `LIVE_CANARY=BLOCKED` remains.
4. Gate 2 must separately approve the verified identity/profile, exact
   synthetic payload/hash, entitlement window, stable idempotency identity,
   maximum one order, cost boundary, treatment of the existing SQS retries,
   polling/observation limits, and explicit STOP behavior. Existing retry/DLQ
   settings and historical DLQ contents remain untouched unless a later
   separately scoped approval explicitly says otherwise.
5. After approvals, perform only the approved next step and its required
   read-only verification. Do not repeat passed QA or deployment work without
   a concrete discrepancy. No order, invocation, retry, recovery, redrive, or
   Main merge is authorized by this suspension record.

At suspension: AWS mutations `0`; Terraform plans/applies `0`; live orders `0`;
live invocations `0`; recoveries/redrives `0`; Main merges `0`. The protected
`docs/reports/RIS-MAYS-ORDERS-UNIFIED-TESTSUITE-19F2.results.json` was not
staged or changed by this documentation update. **STOP.**
