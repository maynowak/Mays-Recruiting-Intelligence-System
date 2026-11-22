# RIS-AGENT-FACTORY-PNP-ANALYSIS-16A — Composite Agent Reference

**Date:** 2026-11-22
**Mode:** documentation/template reconciliation only; no runtime change, no
Terraform apply, no AWS mutation, no real data.
**Status:** **PACKAGE RECONCILED / LOCAL VALIDATED. AWS CANARY PENDING.**

---

## 1. Scope and guardrails

The existing Analysis Agent is documented as the plug-and-play reference for a
**composite agent**: one installable agent, multiple offers, one outer
order/WorkItem, reusable internal capabilities and parsers.

Guardrails kept:

- No new queue, table, Cognito client, agent or parser implementation.
- No second order management or per-offer state machine.
- No analysis-owned result transport or result API.
- No main merge, production deployment, Terraform apply or real-user
  activation.
- No claim of AWS verification, legal approval, entitlement grant or catalog
  activation that did not happen.

## 2. Verified basis

| Item | Value |
|---|---|
| RIS | `feature/ris-analysis-integration-07` @ `c245512a99f3a9122e38a408747e04f6ca45c6c1` |
| Jobsearch | `feature/ris-analysis-parser-cli-04` @ `e77ee94`; parser artifact source `c40bf78` |
| Mays-Orders generated module | source `016cdfd6ac62565dcec9a2fee78cb898fb919e59` (module-builder manifest) |
| RIS Mays pin file | `5cf50a0` (v0.5.0-rc.2) |
| Local Mays checkout | `9627eb2` (review reference, not the generated module source) |
| Latest evidence | `docs/reports/RIS-ANALYSIS-OFFER-E2E-15-FINAL-CANARY-GATE.md` |
| Technical plan | `9a0324a0…`, 4 add / 3 change / 0 destroy, state serial 67, guard `NO_SHARED_DESTROY`, **not applied** |

**Pin distinction:** the RIS pin file, the generated module and the local Mays
checkout are three different states. The local `9627eb2` `lambda/src` does not
contain `dispatch.py`, `identity.py`, `result_consumer.py` or
`result_envelope.py`; statements about dispatch/result behavior are taken from
the generated module `016cdfd`, not from the local RC line.

## 3. Reconciliation performed

| File | Correction |
|---|---|
| `manifest.yaml` | Current RIS SHA `c245512`; Jobsearch `e77ee94` + artifact source `c40bf78`; composite fields (`composite`, `offers`, internal capabilities, external entitlements); dedicated Node parser Lambda described accurately. |
| `offers.yaml` | Added `executionModel` (one outer order, internal calls are technical subfunctions, Mays billing); separated external entitlements from internal parser capabilities; three DRAFT offers unchanged. |
| `entitlements.yaml` | Declared internal parser capabilities separately; grants still empty, approvals still PENDING. |
| `lifecycle.yaml` | Correction-14 path (dispatch ingress → work queue → worker → AgentBody); added work queue/DLQ; result retrieval via existing order view; `automaticAgentResume: false`; agent-specific compute listed as exclusive. |
| `operations.md` | One order/WorkItem, internal parser calls, result/error semantics, retrieval and the resume gap. |
| `risks.md` | Not-deployed status, Mays `apiProfileRef` cross-repo risk, DLQ limitation, no auto-resume, no credential transport, stop conditions. |
| `handoff.md` | Current pins, E1B evidence, open approvals A/B/C, explicit no-resume. |
| `tests/README.md` | Real counts and commands; local vs not-covered split. |
| `contracts/README.md` | Composite boundary, request/result versions, order/WorkItem/result semantics. |
| `partner-bindings.md` | Logical partner identity vs no technical Cognito user; M2M client not profile-bound; Mays finding. |
| `uninstall.md` | Agent-specific compute removal only after drain; shared transport/history retained; purge blocked. |
| `agent-installations/README.md` | Composite-agent development path and live baseline; fixed stale “all four” count. |
| `agent-installations/_template/{README.md,manifest.yaml,offers.yaml}` | Optional composite scaffold; no installer schema change. |
| `docs/operations/RIS-AGENT-FACTORY-RUNBOOK.md` | Correction-14 order/result lifecycle; terminal `ORDER_FAILED` semantics; result retrieval; explicit open auto-resume; composite operations. |

No file under `agents/`, `lambda/`, `terraform/` or `installer/` was changed.

## 4. Composite execution model

```
One outer order / WorkItem (analysis.run, agent_analysis_agent)
  -> registry/Discovery/Eligibility -> AgentBody
  -> AnalysisOrchestrator
       -> parse.cv  (internal technical call)
       -> parse.job (internal technical call)
       -> parse.ats (internal technical call, optional ats.tags)
       -> deterministic compare.tags
  -> requested result bodies
  -> shared ORDER_RESULT / ORDER_FAILED
```

- `analysis.cv` -> `cv.tags`; `analysis.job` -> `job.tags`;
  `analysis.match` -> `comparison` plus optional `ats.tags`.
- External entitlements: `parse.cv`, `parse.job`, `compare.tags`, optional
  `analyze.job`.
- Internal parser calls never create an order, queue or separate charge.
- Pricing/billing stays Mays-Orders; RIS defines no price.
- Result retrieval stays the existing order view: Mays
  `GET /orders/{orderId}` -> `processing.status/result/error`, or the RIS
  owner-scoped reader. No new result API.

## 5. Evidence matrix

### IMPLEMENTED

| Item | Evidence |
|---|---|
| Composite agent identity/work type | `agents/analysis_agent/agent.py` (`analysis-agent`, `analysis.run`, `agent_analysis_agent`) |
| Registry/AgentBody registration | `agents/analysis_agent/registry.py` |
| Request validation, entitlement/consent, requested-only parsing | `agents/analysis/orchestrator.py`, `agents/analysis/contracts.py` |
| Three DRAFT offers | `agent-installations/analysis-agent/offers.yaml` |
| Shared Correction-14 pipeline | `lambda/dispatch_ingress.py`, `agents/runtime/pipeline.py`, shared work queue/worker |
| Terminal `ORDER_FAILED` for order work | `agents/runtime/pipeline.py`; `docs/reports/RIS-ANALYSIS-ECOSYSTEM-CORRECTION-14.md` |
| Result retrieval | Mays `order_service.to_public_processing`, RIS `lambda/orders_reader.py::_public_processing` |
| Synthetic identity gate | `lambda/analysis_runner.py`, `agents/analysis_agent/agent.py`; default false |
| Package validation | `installer/agent_install.py` |

### LOCAL TESTED

| Check | Result |
|---|---|
| `tests/test_analysis_pipeline.py` | 31 passed |
| `tests/test_analysis_offers.py` | 14 passed |
| `tests/test_analysis_entitlements.py` | 12 passed |
| `tests/test_analysis_synthetic_profile.py` | 17 passed |
| `tests/test_analysis_ecosystem_wiring.py` | 9 passed |
| Parser adapters/modes/timeouts | 17 + 17 + 5 passed |
| Focused factory/analysis/auth regression | **567 passed, 41 skipped, 6 subtests passed** |
| E1B prior focused run | 414 passed + 6 subtests |
| `installer.agent_install --stage validate` | all five packages VALIDATED |
| Template YAML + `_template` rejection | PASS (scaffold not deployable) |

### AWS VERIFIED

| Item | Status |
|---|---|
| Analysis Lambda / three offers | **NONE** — not deployed |
| Parser Lambda | Terraform-gated; no canary evidence in this step |
| Analysis order E2E | **NONE** — no apply, no synthetic activation |
| Existing addition/ATS live baselines | Unchanged from Release 13; not re-verified here |

### PENDING

1. **A** — exact technical apply `9a0324a0…` (4/3/0, `NO_SHARED_DESTROY`).
2. **B** — exact synthetic profile (tenant/user/partner/issuer/entitlements/
   expiry/installation).
3. Legal notice `analysis-processing` 1.0, entitlement grants, catalog seed.
4. Mays-Orders price/billing contract and offer activation.
5. Partner/Jobsearch result-retrieval contract for the paid offer path.

### BLOCKED

1. **Mays `apiProfileRef` ownership binding (C):** client-supplied profile is
   not bound to the order owner/partner in Mays. Real order-driven traffic must
   wait for the Mays fix. RIS correctly does not trust metadata.
2. **DLQ exhaustion without `ORDER_FAILED`:** no DLQ-consumer Lambda; an
   exhausted WorkItem reaches the DLQ without a terminal order result.
3. **Automatic agent resume:** no `WAITING` state, no wake-up, no end-to-end
   parent propagation. A parent agent is not resumed by
   `ORDER_RESULT`/`ORDER_FAILED`.
4. **Technical Cognito agent principal / agent-created order:** no technical
   Cognito user and no agent-order create path; the agent-to-agent flow remains
   blocked and is separate from this single analysis order.

## 6. Acceptance check

- Analysis Agent is documented as one composite plug-and-play agent with three
  DRAFT offers: **yes**.
- Reusable internal parsers vs separately orderable agents: **documented**.
- One outer order/WorkItem; no additional orders for parser calls:
  **documented and tested**.
- Registry/AgentBody/WorkItem/shared SQS reuse: **documented**.
- Verified identity/APIProfile/entitlement/consent: **documented; open
  blockers named**.
- Unified status/result/test/lifecycle contracts: **documented**.
- No unsupported AWS/approval/activation claim: **yes**.
- Factory validation: **PASS**.
- No apply/merge/production/real-user change: **yes**.

## 7. Verdict

**PACKAGE RECONCILED AND LOCALLY VALIDATED.** The Analysis Agent is a complete,
reusable composite-agent reference package, and the factory can validate it
with its existing routines. AWS verification, offer activation, the Mays
`apiProfileRef` binding, DLQ-exhaustion failure semantics and automatic agent
resume remain open and are explicitly separated from this step.
