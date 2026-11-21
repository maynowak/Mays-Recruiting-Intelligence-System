# RIS-ANALYSIS-OFFER-E2E-15 — STEP E1 Synthetic Identity Isolation

**Date:** 2026-11-21
**Status:** **READY FOR CONTROLLED AWS CANARY APPROVAL** (two separate gates:
technical apply + synthetic profile).
**No apply, no real consent, no catalog/offer activation, no real data.**

---

## 1. Verified identity boundary

| Field | Source | Trust |
|---|---|---|
| `tenantId`, `userId` | verified server-side context in ingress/API, copied into WorkItem | trusted |
| `partnerApplicationId`, `issuer` | resolved `VerifiedContext` / authenticated profile | trusted |
| `workId`, `orderId`, `correlationId` | transport / server-side binding | trusted |
| `payload` | request/agentOrder input | **untrusted data**, never identity |
| `executionMode` | worker/ingress remote adapter | not a consent trigger |

The synthetic profile is **environment-only**. No WorkItem, API or SQS payload
can switch it on. Direct invocation remains IAM-restricted to the worker/ingress
roles (resource-based permissions); an operator credential is privileged and
still needs the complete exact allowlist to reach synthetic mode.

## 2. Synthetic profile

Default in Terraform and runtime:

```
ANALYSIS_SYNTHETIC_MODE=false
ANALYSIS_ENTITLEMENTS=""      ANALYSIS_CONSENT=false
ANALYSIS_NOTICE_APPROVED=false
```

Optional, separately approved test profile:

```
ANALYSIS_SYNTHETIC_MODE=true
ANALYSIS_SYNTHETIC_TENANT_ID=<synthetic tenant>
ANALYSIS_SYNTHETIC_USER_ID=<synthetic user>
ANALYSIS_SYNTHETIC_PARTNER_APPLICATION_ID=<synthetic partner app>
ANALYSIS_SYNTHETIC_ISSUER=<synthetic issuer>
ANALYSIS_SYNTHETIC_ENTITLEMENTS=parse.cv,parse.job,compare.tags[,analyze.job]
ANALYSIS_SYNTHETIC_EXPIRES_AT=<future ISO timestamp>
```

Rules enforced in `analysis_runner._synthetic_profile` and
`AnalysisAgent._matches_synthetic`:

- all four identity fields must be non-empty and match **exactly**;
- no wildcard/prefix/partial matching;
- entitlements must be explicitly listed;
- expiry must parse and be in the future; missing/invalid/past disables the
  profile;
- only the matched synthetic identity gets synthetic entitlements; every other
  tenant/user keeps the deny configuration;
- `Identity.synthetic=True` is a separate flag from
  `consent_notice_approved`; `require_capabilities` accepts it only for that
  matched identity. **`analysis-processing` remains DRAFT and no real consent
  or notice approval is simulated for real users.**

## 3. Positive and negative tests

New `tests/test_analysis_synthetic_profile.py` (12 tests):

Positive:
- CV-only (structured), job-only, comparison, optional ATS projection;
- synthetic identity receives only the configured synthetic entitlements;
- synthetic `synthetic=True` passes the notice gate without a real approval
  flag; the same identity without the flag is denied.

Negative:
- mode disabled → deny;
- missing any allowlist value / missing entitlements / missing expiry → deny;
- expired and invalid expiry → deny;
- wrong tenant, user, partner application or issuer → deny each;
- manipulated nested WorkItem (foreign identity) → deny;
- real identity while mode active → deny;
- missing capability → `entitlement_denied`;
- direct invoke with incomplete context → deny;
- payload fields cannot enable the mode;
- real Identity without synthetic flag still requires the approved notice.

Existing worker tests cover entitlement revoke, subject fence and cross-tenant;
no security gate was weakened.

## 4. Ecosystem regression

- Addition Agent unchanged through dispatch → work queue → worker.
- Analysis remote adapter and execution-only mode unchanged.
- WorkItem `QUEUED→RUNNING` claim, idempotency/replay, SQS retry, terminal
  ORDER_FAILED, ORDER_RESULT dedup and result persistence unchanged.
- Analysis still has no order mutation and no CV/job payloads in logs.
- DLQ exhaustion without ORDER_FAILED remains an explicit open ecosystem case.
- Broad focused set: **375 passed, 9 skipped**.

## 5. New Terraform plan (old plan invalid)

The analysis bundle changed (synthetic profile), so the previous plan
`11fb32d8…` is **not applicable**.

| Item | Value |
|---|---|
| Plan | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc16/plan.out` |
| Plan SHA-256 | `b432e8f417cf99ffb2f1517325246d225860f3eb11a46c2c96ed2474ef9ad28c` |
| Plan JSON SHA-256 | `d91423e29062929112cb3b7e2493abc79a0079f26aad1c33f8b9fb81a51a449b` |
| Adds / changes / destroys / replacements | **4 / 3 / 0 / 0** |
| State | serial **67**, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `5a0f330581517e9c8095b56b5154f656bc5c2b2d3c68e077bccaf872c1a60cf4` |
| Analysis bundle | `1897a68ed5b2fbe754c51b4ad2fa2743a65bc267f8c07bf1329df687e965c2b2` |
| Parser artifact | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |

Adds: 2 invoke permissions, analysis Lambda, reduced data policy.
Changes: ingress policy (`SendToWorkQueue`), ingress Lambda, worker Lambda
(analysis env + `ANALYSIS_SYNTHETIC_MODE=false` + new bundle hash).
No queue/table/IAM-policy/Cognito/CloudFront/DNS change; no global consent.

## 6. Security assessment

- Synthetic mode cannot be activated by data; only exact env profile.
- Exact match of four independent identity fields; no empty values.
- Expiry bounds the test window; disable by setting mode false and removing
  the allowlist values.
- No catalog/offer seed, no real entitlement grant, no real consent.
- Statistical risk of a real identity colliding with the synthetic tenant/user/
  partner/issuer is avoided by using reserved non-production values; the
  operator must choose them explicitly.
- Trust assumption: only worker/ingress IAM principals can invoke the analysis
  Lambda; operator direct invoke is privileged. There is no public route.

## 7. Separate approvals

**A. Technical apply** — exact plan `b432e8f4…` (4/3/0), deny-by-default.
**B. Synthetic profile** — separate approval for the exact tenant/user/partner/
issuer/entitlements/expiry values; A does not include B.

## 8. Cleanup / reset

1. Set `ANALYSIS_SYNTHETIC_MODE=false` and remove allowlist/entitlements/expiry
   (or revert to the plan env) via the approved config change.
2. Revoke/delete the test entitlement; delete synthetic WorkItems and temporary
   job S3 objects; remove synthetic order/test records per Mays policy.
3. Verify no catalog/offer seed and no real consent changes.
4. Post-apply read-only plan must show no drift; guard re-checked.
5. No auto-destroy; a reviewed reverse plan if the infrastructure is removed.

## 9. Git

- Synthetic profile implementation/tests, plan manifest/report.
- Commits recorded after the test/audit run (see audit log). No apply.

## 10. Verdict

**READY FOR CONTROLLED AWS CANARY APPROVAL.**
The analysis compute now has a fail-closed, exact-match synthetic profile with
expiry and no global consent. The technical plan and the synthetic profile are
separate approvals; no activation or real data is included.
