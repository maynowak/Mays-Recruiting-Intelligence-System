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
| 20A2 synthetic validity | Analysis synthetic expiry is past; **not applicable to the `ats-agent` canary path** |
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

**Decision: `LIVE_CANARY=BLOCKED`; Gate 1 and Gate 2 remain closed for the
existing authorization reasons below, not because a paid AI-provider call was
established.**

1. The target order is `ats-agent` / `analyze.job`. The actual path is
   `Agent-Worker → ATSAgent → ATSHttpClient → POST
   https://mays-jobsearch.vercel.app/api/ats-analysis`, sending job and optional
   profile. `ATSAgent` does not read `ANALYSIS_SYNTHETIC_MODE`.
2. `ANALYSIS_SYNTHETIC_MODE` and its expired value
   `2026-11-26T17:40:28Z` gate the distinct internal `analysis_runner` /
   `AnalysisAgent` path. The expiry is **not a blocker** for an order that
   exclusively selects `ats-agent`; do not extend it for this canary.
3. `ATSHttpClient.analyze` constructs only `{job, profile?}`. The Jobsearch
   handler source inspected at checkout `656566b9dcb14114f3c6c91a18e076b400a50e02`
   always runs deterministic analysis and only enters its AI/provider branch
   when both `body.ai.enabled === true` and `body.ai.consent === true`. Since
   this client omits `ai`, that inspected handler would not execute its AI
   provider branch. The RIS-pinned Jobsearch source is `29d8b730...`, however,
   and the inspected checkout is not that pin or verified deployed code. Thus
   do not claim either provider execution or provider non-execution by the
   deployed service. A network POST to the external API is established; its
   service/hosting price is unknown, not presumed paid or free.
4. Transport fallback (`httpx`/`requests`/`urllib`) targets the same endpoint;
   it is not a local fallback. No explicit retry loop exists in the client.
   Existing worker/SQS redelivery can repeat a POST after a failed attempt,
   up to the queue's `maxReceiveCount=3`; this is a request-count bound, not
   evidence of provider billing or a cost amount.
5. The concrete current authorization blocker is the 20A2 read-only finding:
   the exact confirmed synthetic user/profile has **zero `ats-agent`
   entitlement rows**. Gate 1 is closed and no entitlement mutation is
   authorized. Gate 2 is also closed; no live order/invocation was authorized.
   The expired Analysis synthetic setting is unrelated. AWS usage cost and the
   external endpoint's price are unknown; no charge is asserted. Existing
   safety approvals still prohibit unapproved mutations or live execution.

No adapter, synthetic mode, runtime change, deployment, or entitlement was
introduced. The correct next live prerequisites are explicit authorization
for the narrowly scoped existing entitlement mechanism (if its broad
user/tenant/agent scope is accepted), then a separately explicit one-order
Gate 2 approval with the final payload/hash and retry acceptance. If the
approver requires a cost guarantee, obtain actual endpoint and AWS cost terms;
do not infer a paid provider invocation from this request path. No billing
architecture or hard-cap implementation is proposed here.

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
| ATS execution path provider behavior | **No provider call established** — RIS omits `ai`; inspected handler gates provider branch on explicit enabled+consent; deployed code identity differs/is unverified |
| `ANALYSIS_SYNTHETIC_MODE` expiry | **NOT APPLICABLE** to the `ats-agent` order path |
| Exact `ats-agent` entitlement | **BLOCKED** — 20A2 found zero rows for the verified synthetic identity |
| External API/AWS price | **UNKNOWN** — neither paid provider execution nor zero cost is asserted |
| B — `RIS-AGENT-ENTITLEMENT-BILLING-01` | **BACKLOG ONLY** — not implemented |
| Gate 1 | **CLOSED** — entitlement absent; no mutation authorization |
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

## RIS–Mays-Orders integration completion reconciliation

**Review baseline:** `ad4886d1f23bf40f65a05e3b3b8744c9cd740131`.
This section consolidates existing evidence. It does not repeat completed QA,
deployment, plan/apply, or AWS checks.

### Integrated source and completed local scope

- The active generated-module provenance is Mays-Orders source
  `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`, cross-referenced by
  `installer/mays-orders-builder.pinned.json`, the builder, and generated
  manifest in the cited 19F2/19F4/19F8 evidence. The legacy clone pin
  `5cf50a0...` is not the generated-module source identity.
- Mays `orderDescription` is already implemented in this integrated source:
  optional opaque text validation, verbatim persistence/projection, privacy
  handling, and original Mays tests. The original Mays suite passed **15/15**.
  The attempted `80a84ca...` patch was not applicable to the integrated tree and
  was not applied; no patch or source change is needed.
- JSON Transport V1, dispatch/context binding, stable work/result identifiers,
  signed `ORDER_RESULT` HMAC contract, result-consumer validation, lifecycle
  completion, owner-only reader behavior, and negative security cases are
  indexed in `docs/reports/RIS-MAYS-ORDERS-CONTRACT-EVIDENCE-19F2.md` and
  `docs/reports/RIS-ATS-RESULT-LINK-01.md`. The latter's local integration
  test fakes only persistence/sender/ATS HTTP boundaries and runs the worker
  pipeline, ATS result body, Transport V1 mapping, and real reader handler.
- DSGVO/privacy coverage is part of the cited Mays ownership/projection and
  `orderDescription` originals plus RIS Native privacy/erasure suites. It is
  local contract/test evidence, not a new production-data or live-erasure test.

### QA and functional acceptance evidence

- The later reference-platform run in
  `docs/reports/RIS-DEV2-ORDER-DESCRIPTION-E2E-GATE-19F8.md` supersedes the
  earlier Windows `FULL`-blocked snapshot for the integrated source: Ubuntu
  Unified `FULL` run `45996079592` passed with zero failures/collection errors.
  Recorded groups include RIS Native 3,291 passed; Mays Lambda 240; Mays module
  builder 100 plus 6 subtests; installer 81; seed 28; Cognito backup 2; XRepo
  Contract 133 plus 4 subtests; XRepo E2E 39; RIS builder 57; generated module
  artifact 9. Original Mays `orderDescription` tests passed 15/15 at the exact
  integrated source. No new FULL or candidate QA was run for this completion.
- The existing 19F8 roundtrip verifies locally: Create 201 → exact
  `orderDescription` persisted → initial WorkItem claim and mocked agent
  execution → signed `ORDER_RESULT` accepted → `processing.status=COMPLETED` →
  owner GET 200 returns the exact description. Foreign-owner denial and
  transport/result negative cases are included. It is **mocked local E2E**,
  not a live AWS/provider result.
- Independently reusable local scenarios include the Mays original
  `orderDescription` suite, XRepo contracts, XRepo E2E, and the ATS result-link
  integration test. Their existing PASS evidence is reused; none was rerun.
  No separate live, mutation-free scenario exercises the same full order flow:
  Create is a mutation and the current live profile is locked pending explicit
  identity, cost, and execution approvals.

### Plan, Apply, deployment, and live boundary

- Existing approved Terraform evidence is
  `docs/reports/RIS-DEV2-WORKER-CONTROLLED-REPLAN-19G5.md` and
  `docs/reports/RIS-DEV2-WORKER-CONTROLLED-APPLY-19H.md`, with machine evidence
  at `docs/reports/evidence/19H/post-apply-verification.json`. The approved
  saved plan was applied once: 0 added, 2 changed, 0 destroyed (Agent Worker
  and Dispatch-Ingress only); read-only verification passed and State reached
  serial 76. This proves deployment of the Worker fix and verified
  infrastructure state; it does **not** prove a live order or result roundtrip.
- The existing Unified `LIVE` harness was invoked once at this checkpoint with
  its JSON output directed outside the repository to
  `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-addition-e2e-live-locked.json`.
  It returned `BLOCKED / LOCKED_NOT_EXECUTED` by design, with zero test groups;
  it performed no network/AWS operation. The report's selected integrated
  version key and bundle hash are metadata, not a fresh Mays checkout or AWS
  provenance verification.
- **Live status remains blocked:** no authenticated live Create, actual AWS
  queue-driven Agent run, deployed result-consumer transaction, or live owner
  readback was performed under this completion request. Gates 1 and 2 remain
  closed; no external paid execution is authorized.

### RC4 / upgrade distinction and defect disposition

- The integrated Mays module remains at `db4f9e7`. RC4
  `v0.6.0-rc.1` / `5bc154e...` was separately tested locally in the 19F3/19F4
  candidate gates; its original suites passed, but candidate XRepo/dispatch-
  result compatibility and generated Terraform validation failed. RC4 was not
  installed or deployed to AWS and did not pass live E2E. The failure report is
  `docs/reports/RIS-MAYS-ORDERS-COMPATIBILITY-RESOLUTION-19F4.md`; the required
  compatibility fixes are Mays-owned. Do not label RC4/RC4++ as deployed or
  accepted.
- No confirmed defect was found in the already integrated `db4f9e7` local
  contract/E2E evidence requiring a RIS runtime correction. No runtime,
  infrastructure, Mays source, module pin, or adapter change was made.

### Completion disposition

| Scope | Result |
|---|---|
| Original RIS/Mays integration on current integrated source | **LOCAL ACCEPTANCE COMPLETE**; reuse the cited test/evidence set |
| `orderDescription`, JSON transport, dispatch, HMAC/result consumer, owner/privacy contracts | **LOCAL CONTRACT/E2E VERIFIED** |
| Unified full QA and Mays originals | **PASS on the cited Ubuntu integrated-source run**; not repeated |
| Worker fix and Terraform deployment | **DEPLOYED / VERIFIED** for the exact 19H scope only |
| AWS live order/result E2E | **NOT VERIFIED; LIVE HARNESS LOCKED** |
| RC4/RC4++ upgrade | **NOT ACCEPTED / NOT DEPLOYED**; candidate compatibility gates fail |
| Confirmed in-scope runtime defect | **NONE**; no fix required |
| Main merge | **NOT PERFORMED**; documentation/evidence is prepared for review |

No additional work is authorized by this reconciliation. Keep the live canary
blocked until the existing approval gates are explicitly reopened. The
commercial entitlement/billing backlog remains separate. The protected 19F2
JSON was not read as a test output, staged, or changed; no test used its default
output path.

## Functional test execution — current checkpoint

**Execution baseline:** `2f1a6f1332b1bd61889ad950bb531c263248d0e8` on
`feature/ris-analysis-integration-07`; integrated Mays version key `integrated`
(`db4f9e79980443de1cd3d5b688a33c0cf0eb771f`). These are targeted local
integration tests, not another FULL QA run.

| Test | Result | Execution boundary |
|---|---:|---|
| Unified `XREPO_CONTRACT` | **PASS — 133 passed + 4 subtests** | Process-isolated runner; exact integrated Mays checkout provenance verified; no AWS/network operation. JSON outside repo: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-xrepo-contract-current.json`. |
| Unified `XREPO_E2E` | **PASS — 39 passed** | Existing RIS↔Mays dispatch/agent/result harness; process-isolated; no AWS/network operation. JSON outside repo: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-xrepo-e2e-current.json`. |
| `tests/test_ats_result_link.py` | **PASS — 10 passed** | Existing local result-link harness; ATS client and AWS credentials isolated, outbound network blocked, infrastructure boundaries faked. |
| Unified `LIVE` | **BLOCKED — `LOCKED_NOT_EXECUTED`, zero test groups** | Existing harness refuses live execution absent a separate approved live-test task. JSON outside repo: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-mo-live-locked.json`. No AWS call was made. |

The exact integrated Mays original `orderDescription` tests (15/15) and
reference-platform FULL pass remain reused from 19F8; they were not repeated.
The focused reruns had no failures, so no defect was confirmed and no fix,
rebuild, deployment, or Terraform action was necessary. Local functional
acceptance is PASS. The external live order/agent/result/owner-readback path
remains untested and blocked.

### Bundled request for remaining live actions — NOT APPROVED

No already-granted authorization covers a live Create/dispatch/Agent execution.
If a future operator wants that test, one combined approval decision must
authorize the following exact scope, while still recording Gate 1 and Gate 2
separately as explicit decisions:

```text
Target: RIS-DEV2 / account 262370457690 / eu-central-1 / workspace ris-dev2
Source: feature/ris-analysis-integration-07 at the reviewed then-current HEAD
Worker artifact: existing deployed Worker fix; do not deploy or change pins
Mays source: integrated db4f9e79980443de1cd3d5b688a33c0cf0eb771f

Gate 1 (AWS mutation, only if separately approved): add exactly one temporary
foundation_entitlements row for the already verified synthetic test owner and
matching tenant, agentId=ats-agent, validFrom=T0-1 minute, validUntil=T0+15
minutes. This existing seed is user/tenant/agent-wide; it does not enforce
apiProfileId, capability, WorkItem type, or one-use. Explicitly accept this
scope or do not authorize the change. No ANALYSIS_SYNTHETIC_EXPIRES_AT update:
the target ats-agent path does not use that separate Analysis identity gate.
Expected Terraform plan: exactly one entitlement item add; otherwise STOP.
Plan review and Apply require their own approvals.

Gate 2 (live execution): at most one authenticated POST /orders, using the
final synthetic agent.execution payload for ats-agent/analyze.job and the
final exact payload SHA-256 + idempotency key supplied in the approval. No
manual POST retry, second order, direct Lambda invocation, queue receive,
redrive, recovery, or cleanup. Observe only the matching work/order and
authorized owner GET; stop on ambiguity or mismatch.

Existing retry behavior: the work queue allows maxReceiveCount=3. A failed
WorkItem can therefore lead to up to three agent attempts and up to three ATS
POSTs for one logical order. Gate 2 must explicitly accept this exposure; this
request does not disable or alter shared retries.

Cost disclosure (currently unknown, not presumed chargeable): the inspected RIS
request omits the API's AI opt-in, and the inspected handler runs its provider
branch only with explicit enabled+consent. The checked-out handler is not the
pinned/deployment identity, so this does not prove deployed behavior or endpoint
pricing. Before Gate 2, the approver must either accept this unresolved
service/AWS usage exposure explicitly or require verified price evidence as a
condition. Do not describe a paid provider invocation as expected or proven.
`unitPrice=1` and a budget alert are not monetary caps if a cap is required.

Approver / authority / date / T0 / payload SHA-256 / idempotency key /
explicit acceptance or resolution of unknown endpoint/AWS usage exposure /
retry acceptance / plan hash and Apply reference (if Gate 1): <required>
Gate 1 decision: NOT GRANTED. Gate 2 decision: NOT GRANTED.
```

This is a request for a future decision, not permission to prepare a plan or
execute a live test. Current concrete blockers remain missing entitlement and
closed Gate 1/Gate 2. Endpoint/AWS cost is unknown; this report does not treat a
paid provider call as a fact or claim the test is cost-bounded.

At this checkpoint: XRepo contract `133 + 4` PASS; XRepo E2E `39` PASS;
ATS result-link `10` PASS; LIVE profile blocked; new orders `0`; AWS
invocations/mutations `0`; deployment/plan/apply `0`; recovery/redrive `0`.
The protected 19F2 JSON was not used as a test output, staged, or changed.
**STOP at the live approval gate.**
