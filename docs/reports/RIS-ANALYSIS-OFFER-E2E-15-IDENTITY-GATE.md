# RIS-ANALYSIS-OFFER-E2E-15 — STEP E1A Trusted Identity Gate

**Date:** 2026-11-21
**Status:** **READY FOR EXACT-PLAN APPLY APPROVAL**
**No apply. Synthetic profile remains disabled in the plan.**

---

## 1. Verified identity path

```
VerifiedContext (server-side profile lookup)
  → canonical WorkItem (tenant/user/partner/issuer, bound workId)
  → persisted WorkItems row + work queue
  → shared worker (QUEUED→RUNNING claim, entitlement, fence)
  → AgentBody → LambdaAgentHandler
  → analysis Lambda (executionMode=agent)
  → AnalysisAgent._identity
```

| Field | Authoritative source | Payload trust |
|---|---|---|
| tenant/user/partner/issuer | verified context written into the WorkItem; for synthetic mode re-checked against the persisted RUNNING row | **not** from event payload alone |
| workId/orderId/correlation | server/transport binding | not client-chosen |
| payload | request/agentOrder data | untrusted data |

`payload`/nested WorkItems cannot override the outer verified identity: the
agent now raises `identity_conflict` when outer and nested identity fields are
both present and differ. Original WorkItem vs runtime wrapper is detected by the
`workId` + `userId`/`tenantId` marker used by the existing runtime contract.

## 2. Synthetic profile hardening

Additions (defaults unchanged, mode false):

- `ANALYSIS_SYNTHETIC_MODE=false`
- exact `ANALYSIS_SYNTHETIC_TENANT_ID` / `_USER_ID` /
  `_PARTNER_APPLICATION_ID` / `_ISSUER`
- explicit `ANALYSIS_SYNTHETIC_ENTITLEMENTS`
- required future `ANALYSIS_SYNTHETIC_EXPIRES_AT`
- `ANALYSIS_SYNTHETIC_INSTALLATION=ris-dev2` and `PROJECT_NAME=ris-dev2`;
  any other installation disables the profile.

New trusted-binding check: even an exact event identity is insufficient. The
analysis Lambda reads the **persisted WorkItem** (`dynamodb:GetItem` only) and
requires:

- status `RUNNING`,
- exact tenant/user/partner application/issuer,
- all values non-empty.

Without that row/status, the event identity receives the normal deny
configuration. Direct invocation with a self-declared synthetic identity is
therefore denied. Synthetic consent is represented by `Identity.synthetic=True`;
`analysis-processing` remains DRAFT and real `consent_notice_approved` stays
false.

## 3. Tests

`tests/test_analysis_synthetic_profile.py` (15 tests) plus the broad set:

- mandatory: outer verified identity A + nested synthetic identity B →
  `identity_conflict`, **no parser call**;
- persisted identity mismatch with matching event → deny;
- direct invoke with synthetic fields but no persisted RUNNING WorkItem → deny;
- wrong installation (`PROJECT_NAME`/installation) → deny;
- missing/empty/expired/invalid profile values → deny;
- each single identity-field mismatch → deny;
- missing entitlement → `entitlement_denied`;
- real identity with mode active → deny;
- positive CV, job, comparison and optional ATS projection;
- existing worker entitlement revoke, subject fence, cross-tenant,
  addition-agent regression, replay/claim, ORDER_RESULT/ORDER_FAILED.

Result: **378 passed, 9 skipped**.

## 4. Ecosystem regression

Dispatch → ingest → work queue → worker, remote adapter, WorkItem idempotency,
addition agent, result transport and terminal failure semantics are unchanged.
Analysis still has no order mutation and no CV/job payloads in logs.
DLQ exhaustion without ORDER_FAILED remains a separate open case.

## 5. New Terraform plan (previous plans retired)

The analysis bundle changed again; plan `b432e8f4…` is not valid.

| Item | Value |
|---|---|
| Plan | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc17/plan.out` |
| Plan SHA-256 | `7426ba4aaa9dd799e4e8164f9506d55a108549035d1a44a99a4f1ee06571b3f6` |
| Plan JSON SHA-256 | `5649a311b782632503d399a8aa52f3069c02e739b800b1e99bd252af5d8d108f` |
| Adds / changes / destroys / replacements | **4 / 3 / 0 / 0** |
| State | serial **67**, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `28125fe103f39496069bb419586a3f328dc2d60f343f2b4f6f415af65ab433e6` |
| Analysis bundle | `a932330191fc7e557948705633a18972174c3beaecb777bd03e15c3fa6eeca80` |
| Parser artifact | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |

IAM delta: analysis data policy now adds **`dynamodb:GetItem` on WorkItems
only** for the persisted synthetic-binding check (no Put/Update/Query, no
Entitlements read). Env adds `WORK_ITEMS_TABLE`, `PROJECT_NAME` and
`ANALYSIS_SYNTHETIC_MODE=false`. No queue/table/Cognito/CloudFront/DNS change,
no global consent.

## 6. Security assessment

- Synthetic authorization requires **both** exact env profile and a persisted
  RUNNING WorkItem with the same identity.
- Environment binding is hard-coded to `ris-dev2`/matching `PROJECT_NAME`.
- Expiry is re-evaluated on every execution path that builds the analysis
  config (`_execute_agent` per invocation), not cached from cold start.
- No catalog/offer seed, no real entitlement grant, no real consent/notice.
- Direct invokes are IAM-scoped to worker/ingress principals; operator
  credentials are privileged and still need a matching persisted WorkItem.
- Residual trust: an operator with both Lambda invoke and WorkItems write could
  fabricate a synthetic row; that is an administrative capability, not a
  request/payload path. Ordinary API/SQS callers cannot.

## 7. Separate approvals

**A. Technical apply** — exact plan `7426ba4a…` (4/3/0), deny-by-default.
**B. Synthetic profile** — exact tenant/user/partner/issuer/entitlements/
expiry/installation values; A does not include B.

## 8. Cleanup / reset

Disable `ANALYSIS_SYNTHETIC_MODE`, remove allowlist/expiry/test entitlements;
delete synthetic WorkItems, temporary job objects and test entitlement; verify
no catalog/offer seed or real consent; post-apply read-only plan must be clean;
guard re-check. No auto-destroy.

## 9. Git

Implementation/tests and the identity-gate manifest/report are committed after
the audit run; no apply.

## 10. Verdict

**READY FOR EXACT-PLAN APPLY APPROVAL.**
The synthetic profile now depends on a trusted persisted binding, rejects
identity conflicts and wrong environments, and remains fully disabled by
default. Technical apply and synthetic profile still require two separate
explicit approvals.
