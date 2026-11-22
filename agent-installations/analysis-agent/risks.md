# Analysis Agent — Risks

- **AWS infrastructure applied, not live E2E:** 16C2 Apply A installed
  analysis and dedicated Node parser Lambdas plus verified invocation
  permissions in ris-dev2 (4/3/0, state 67 -> 69), with deny-by-default
  runtime configuration. No synthetic Analysis end-to-end invocation
  has been verified; B and C are separate future gates.
- **Composite boundary:** one outer WorkItem/order, internal parser calls only.
  A second order or a per-parser charge would violate the offer contract.
- **Optional processing:** only requested parsers run; ATS-only does not run
  the job parser; matching runs CV and job parsing once.
- **CV privacy:** CVs are resolved server-side; no CV bytes in WorkItems or
  logs. CV access is owner/tenant-only.
- **Comparison:** deterministic, no AI, no provider cost; the ATS score stays
  separate from the comparison score.
- **Job storage:** opaque refs, 2 h default, 4 h maximum, 1 MiB.
- **Identity:** entitlements, consent and the draft notice are env-driven and
  fail closed. The synthetic test profile requires an exact env profile and a
  persisted `RUNNING` WorkItem; it is not real consent.
- **Mays `apiProfileRef` binding:** Mays stores a client-supplied profile
  reference and does not prove it belongs to the order owner/partner. RIS
  resolves any ACTIVE profile. This is a cross-repo blocker for secure
  order-driven traffic and is owned by Mays-Orders.
- **DLQ exhaustion:** a WorkItem that exhausts SQS retries reaches the DLQ
  without `ORDER_FAILED`. A separate redrive/consumer decision is required.
- **No automatic resume:** `ORDER_RESULT`/`ORDER_FAILED` update the order;
  there is no `WAITING` state or parent-agent wake-up. Do not claim an
  agent-to-agent round trip.
- **Parent correlation:** parent fields exist in the schema, but the current
  dispatch builders and result carrier do not propagate them end to end. If a
  resume mechanism is introduced later, parent references must be validated to
  prevent spoofing.
- **No credential transport:** no RIS key, JWT or secret is placed in SQS,
  WorkItems, result bodies or logs. The WorkItem carries only opaque ids.

## Stop conditions

- Missing parser artifact or parser Lambda -> do not enable.
- Missing consent/entitlement -> fail closed.
- Expired jobRef or cross-tenant/CV-owner mismatch -> fail closed.
- Any request to add a second parser engine -> stop and escalate.
- Any request for a per-parser order or second order state machine -> stop.
- Mays `apiProfileRef` ownership binding unverified -> no real order-driven
  traffic.
- No `ORDER_FAILED` guarantee for DLQ exhaustion -> do not claim full failure
  coverage.
