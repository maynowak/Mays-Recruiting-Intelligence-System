# RIS-ANALYSIS-OFFER-E2E-15 — STEP E1B Final Canary Gate

**Date:** 2026-11-21
**Status:** **CORRECTION REQUIRED** — RIS technical gate is ready; one
cross-repo Mays-Orders binding gap remains.
**No apply, no synthetic activation, no real data.**

---

## 1. Binding fix (RIS)

`_build_synthetic_verifier()` now maps explicitly between the Identity contract
(snake_case) and the persisted WorkItem schema (camelCase):

| Identity | WorkItem |
|---|---|
| `tenant_id` | `tenantId` |
| `user_id` | `userId` |
| `partner_application_id` | `partnerApplicationId` |
| `issuer` | `issuer` |

The verifier still requires `status=RUNNING`, all values non-empty and exact.
Missing row, non-RUNNING status, any mismatch, or a DynamoDB exception returns
deny. No DynamoDB write and no worker-recheck relaxation.

## 2. Real verifier tests (no injected lambda)

`tests/test_analysis_synthetic_profile.py` now drives the real
`_build_synthetic_verifier` with a controlled table:

- exact RUNNING row → PASS;
- missing row / QUEUED / COMPLETED / FAILED / CANCELLED → DENIED;
- wrong tenant/user/partner/issuer → DENIED;
- DynamoDB error (AccessDenied/Timeout analogue) → DENIED;
- outer identity A + nested identity B → `identity_conflict`, no parser call;
- positive CV run through the real verifier to `CVParserResultBody`.

Plus all previous negatives (mode disabled, expiry, wrong installation, direct
invoke, missing entitlement, real identity) and positives (CV, job, comparison,
optional ATS).

## 3. RIS_KEY / Cognito path

### RIS API Execute — verified in code and tests

- Cognito access JWT (`token_use=access`), separate `X-Api-Credential: ris_…`
  header, never `Authorization`.
- `verify_api_credential` → credential/profile store → owner/tenant binding,
  expiry/revocation, entitlement re-check, catalog executable check.
- Partner registry binding: JWT `client_id` → Partner Application →
  `apiProfileId`/`tenantId`; mismatch denied.
- Authorized context (`ownerUserId`, `tenantId`, `apiProfileId`) is the only
  source for `_enqueue_agent_work`; request/header cannot choose the subject.
- Tests: credential verification (missing/invalid/revoked/disabled/expired/
  foreign tenant/no entitlement), machine entrypoint, partner security boundary,
  API profile propagation.

### Mays-Orders ORDER_DISPATCH — finding (Mays-owned)

- Mays stores the client-supplied `agentOrder.metadata.apiProfileRef` and uses
  it as `contextRef` in `build_dispatch_envelope` (`dispatch.py`).
- `order_service.create_order` / `prepare_dispatch` verify order ownership, but
  **do not verify that `apiProfileRef` belongs to the order owner/partner**.
- RIS `dispatch_ingress.resolve_context` resolves any **ACTIVE** APIProfile
  from the profile store; the dispatch queue policy only restricts the sender
  role. Therefore the RIS side cannot prove that the referenced profile belongs
  to the order's owner.
- Risk: a Mays user who can create an agent order could reference another
  active profile; RIS would execute under that profile's tenant/owner
  (cross-tenant/cross-owner risk).
- **Owner:** Mays-Orders. Required correction: bind/validate `apiProfileRef`
  (and `partnerApplicationRef`) server-side against the verified owner/partner
  at order creation/prepare_dispatch, or introduce a signed server binding.
  RIS must not trust metadata. This package does **not** change the foreign
  Mays module.

RIS contribution to containment: no RIS key is forwarded in SQS, WorkItems,
result bodies or logs; the WorkItem carries only opaque `apiProfileId`; the
agent-order validator rejects credential-shaped values.

## 4. Regression

- 414 passed, 6 subtests passed in the final focused run (analysis, synthetic,
  offers, ecosystem, credentials, machine entrypoint, partner boundary, Mays
  dispatch/result handoff).
- Addition agent unchanged; dispatch → work queue → worker, replay/claim,
  entitlement revoke, subject fence, ORDER_RESULT and terminal ORDER_FAILED
  remain green.
- DLQ exhaustion without ORDER_FAILED remains an explicit open ecosystem item.

## 5. New Terraform plan (old plans retired)

The analysis bundle changed (verifier mapping), so `7426ba4a…` is invalid.

| Item | Value |
|---|---|
| Plan | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc18/plan.out` |
| Plan SHA-256 | `9a0324a0523486b9d4850c9215030a084c35b8807508a6a55bd2e26596a4c7a6` |
| Plan JSON SHA-256 | `c1360c511e53f6cadcf48b26f49c94d90d551578e83fc97be8b758ae7f5cb391` |
| Adds / changes / destroys / replacements | **4 / 3 / 0 / 0** |
| State | serial **67**, lineage `a0bd361d-5cd1-a207-a8c0-e6888f0be082` |
| Guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `28125fe103f39496069bb419586a3f328dc2d60f343f2b4f6f415af65ab433e6` |
| Analysis bundle | `fcc2a008b3234a8dd769e605b6e005a8b6690d06f216c4f391ca16efffb1e75a` |
| Parser artifact | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |

IAM: analysis gets only WorkItems `GetItem` for the verifier; no write, no
Entitlements/Order permission. Env default `ANALYSIS_SYNTHETIC_MODE=false`.
No new queue/table, no Cognito/CloudFront/DNS, no global consent.

## 6. Security assessment

- Synthetic authorization needs exact env profile **and** persisted RUNNING
  WorkItem with exact identity; direct invoke without that row is denied.
- Expiry is rechecked per execution; installation must be `ris-dev2`.
- RIS API path is JWT + RIS key + registry/profile/tenant/entitlement/catalog
  bound; no key leaves the request boundary.
- **Blocker for real order-driven canary:** Mays `apiProfileRef` binding gap
  (section 3). Synthetic canary that bypasses Mays could run, but must not be
  presented as proof of the Mays order path.

## 7. Separate approvals

**A.** Exact technical apply `9a0324a0…` (4/3/0), deny-by-default.
**B.** Exact synthetic profile (tenant/user/partner/issuer/entitlements/expiry/
installation), still separate.
**C.** Mays-Orders correction for `apiProfileRef` binding before any real
order-driven user traffic.

## 8. Cleanup / rollback

Disable synthetic mode, remove allowlist/expiry/test entitlement, delete
synthetic WorkItems/job objects, verify no catalog/offer seed or real consent;
post-apply read-only plan clean; guard re-check. No auto-destroy.

## 9. Verdict

**CORRECTION REQUIRED.** The RIS identity binding, real DynamoDB verifier,
RIS-key/Cognito API path and new 4/3/0 plan are ready. The Mays-Orders
`apiProfileRef` ownership binding is a real cross-repo gap and must be fixed
there before claiming a secure order-driven full canary. No apply was made.
