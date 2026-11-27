# RIS-AGENT-ENTITLEMENT-BILLING-01

**Status:** BACKLOG — not implemented, not authorized, no provider or AWS
configuration changed.

## Objective

Design and implement a commercial authorization and billing contract for
RIS-executed agents. The contract must make the entitled owner, execution
scope, usage, price, retry behavior, and maximum financial exposure explicit
and enforceable before a provider call is made.

## Required capabilities

1. **Owner/tenant-bound entitlements**
   - Require verified `userId` and `tenantId`; deny missing or mismatched
     identity.
   - Define lifecycle, validity, revocation, audit, and cleanup semantics.
2. **Execution scope**
   - Bind grants optionally or mandatorily to `apiProfileId` as policy requires.
   - Enforce both `capability` and WorkItem `type` (Work-Type) at execution
     authorization, not only at the API/dispatch boundary.
   - Document whether grants can cover multiple operations and agents.
3. **Atomic usage limits**
   - Reserve/decrement use or monetary allowance atomically before execution;
     prevent concurrent requests from overspending the same balance.
   - Define behavior for denial, timeout, cancellation, partial completion,
     and expired/revoked entitlements.
4. **Idempotent cost reservation and settlement**
   - Use stable operation/idempotency identity across API, WorkItem, retries,
     and settlement.
   - Model `RESERVED → SETTLED` or `RELEASED` with conditional writes and
     recovery for ambiguous outcomes; prevent duplicate reservation/charge.
5. **`unitPrice` monetary semantics**
   - Specify currency, decimal precision/minor units, rounding, tax/fees,
     quantity, line totals, and whether `unitPrice` means a customer price,
     provider cost, or both.
   - Validate SKU/price against an authoritative catalog; do not infer price
     from a default integer.
6. **Retry-safe provider charging**
   - Require provider idempotency keys where supported and define reconciliation
     for a timeout after a provider may have accepted a request.
   - Define which errors are permanent/retryable and ensure retry/DLQ behavior
     cannot duplicate billable provider work.
7. **Enforceable cost ceilings**
   - Enforce per-operation, per-owner/tenant, and optionally per-period caps
     synchronously before any cost-incurring action.
   - Define fail-closed behavior when pricing, reservation, or provider
     idempotency cannot be verified. Alerts and retrospective usage reports do
     not satisfy this acceptance criterion.

## Acceptance criteria

- Cross-owner, cross-tenant, wrong-profile, wrong-capability, and wrong-
  Work-Type requests are denied before provider execution.
- Concurrent requests cannot reserve beyond the configured use/cost limit.
- Replaying the same idempotency identity cannot double-reserve, double-settle,
  or produce an unbounded second provider charge.
- An ambiguous provider timeout is reconciled safely; it is not blindly
  reissued as a new billable operation.
- Currency, price, rounding, refunds/releases, and maximum exposure have
  executable contract tests and auditable persisted states.
- A hard cap is enforced in the request path; monitoring-only budgets are not
  represented as hard limits.
- Existing SQS/DLQ behavior is changed only with a separately reviewed,
  narrowly scoped migration and explicit approval; no broad retry disablement
  is implied by this backlog item.

## Explicit non-scope for this record

- No implementation, schema migration, Terraform/IAM change, entitlement
  grant, provider contract, or deployment is authorized by this backlog
  capture.
- No change to the synthetic technical canary approval gates.
- No weakening of identity, consent, privacy, retry, or cost controls.

## Source context

Recorded by the Gate Reconciliation in
`docs/reports/RIS-DEV2-FINAL-LIVE-ACCEPTANCE-20-21.md`. The current
`foundation_entitlements` seed lacks profile/capability/Work-Type and
single-use/balance enforcement; the Orders adapter accepts integer `unitPrice`
without an authoritative monetary catalog; and the ATS worker can be retried
after an external request without verified provider-side charging idempotency.
