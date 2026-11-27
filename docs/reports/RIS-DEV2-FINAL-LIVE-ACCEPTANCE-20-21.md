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
