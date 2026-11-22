# RIS-ANALYSIS-OFFER-E2E-15 — STEP E0 Canary Gate

**Date:** 2026-11-21
**Status:** **SYNTHETIC TEST DESIGN NEEDS APPROVAL**
Technical apply gate: READY FOR EXACT-PLAN APPLY APPROVAL (deny-by-default).
**No apply performed. No operator approval assumed.**

---

## 1. Plan / state readback

| Item | Verified value |
|---|---|
| Caller / account / region | `arn:aws:iam::262370457690:user/devnemo` / `262370457690` / `eu-central-1` |
| Backend / workspace | `ris-dev2-tf-state-dev` / `dev/terraform.tfstate` / lock `ris-dev2-tf-lock` / `ris-dev2` |
| State serial / lineage | **67** / `a0bd361d-5cd1-a207-a8c0-e6888f0be082` (283 resources) |
| Plan file | `C:/Users/DCI-Student/AppData/Local/Temp/opencode/rc15/plan.out` |
| Plan SHA-256 | `11fb32d81b68780f1cdaa3a9856287a3282552af2c6a648d41cb3fe8f802cee2` |
| Plan JSON SHA-256 | `caeaea14bde50c8333a9db2a646a5e6c2c4af9e659cae279b3233b2b42a98cb4` |
| Adds / changes / destroys / replacements | **4 / 3 / 0 / 0** |
| Shared guard | **`NO_SHARED_DESTROY`** |
| Worker bundle | `0d49527e3a74c7e84d0a7ac9c6e0fcfa3673ae510a17ad075848f2e30fc61b37` |
| Analysis bundle | `83eef8e691e15ada27bd9afa109b551c00dae766fe0b8a57c4ce1fc637df1184` |
| Parser artifact | `fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a` |

The saved plan was re-checked against the manifest and authoritative resources.
No code/Terraform change since the plan; the old 4/2/0 and 2/0/0 plans remain
retired. Analysis Lambda is not deployed (`ResourceNotFoundException`).

## 2. IAM and resources

Adds (4):

1. `aws_lambda_permission.analysis_invoke_ingress[0]`
2. `aws_lambda_permission.analysis_invoke_worker[0]`
3. `module.analysis_runtime.aws_iam_role_policy.analysis_runtime_data[0]`
4. `module.analysis_runtime.aws_lambda_function.analysis[0]`

Changes (3, in place):

- ingress role policy: `sqs:SendMessage` on the existing work queue,
- ingress Lambda: new code + `WORK_QUEUE_URL` + analysis env,
- worker Lambda: new code + analysis env.

No queue, table, secret, Cognito, CloudFront or DNS resource is created,
replaced or destroyed. The analysis data policy is reduced to
PartnerProfiles read only (no WorkItems write, no Entitlements read).
The analysis Lambda env is deny-by-default:

```
ANALYSIS_ENTITLEMENTS=""  ANALYSIS_CONSENT="false"
ANALYSIS_NOTICE_APPROVED="false"  ANALYSIS_CALLER_PARTNER_ID="ris-internal"
```

## 3. Synthetic identity isolation — finding

**Current design cannot safely enable positive synthetic tests without a
separate change.**

The analysis configuration is function-global:

- `analysis_runner.py:72-79`: `ANALYSIS_ENTITLEMENTS`, `ANALYSIS_CONSENT`,
  `ANALYSIS_NOTICE_APPROVED` are read once per function environment;
- `agents/analysis_agent/agent.py:59-83`: every WorkItem receives those global
  entitlements/consent values; tenant/user are only used for owner checks and
  are not compared against any allowlist.

Consequences:

- setting `ANALYSIS_CONSENT=true` / `ANALYSIS_NOTICE_APPROVED=true` would apply
  the consent/notice approval **to every identity** processed by the function,
  not just a synthetic one;
- a DDB entitlement scoped to one test user would still leave the global consent
  flag active for any future entitled user;
- there is no synthetic tenant/user allowlist, no per-invocation test marker
  that is verified against trusted context, and no separate test profile.

The deny-by-default plan itself is safe. The **positive-test configuration** is
not safely scopeable with the current plan.

### Minimal proposal (not implemented, needs approval)

**Option A (recommended): allowlist-gated synthetic profile.**

- Add an explicit env allowlist (e.g. `ANALYSIS_SYNTHETIC_TENANT_ID` +
  `ANALYSIS_SYNTHETIC_USER_ID`, or a single JSON pair).
- In `analysis_config_from_env`/`AnalysisAgent._identity`, apply the test
  entitlements/consent only when the WorkItem tenant **and** user match the
  allowlist; all other identities keep the deny configuration even if the
  function flags are set.
- Reject if the allowlist is unset/ambiguous; no wildcard.
- Keep the test tenant non-production, no catalog/offer seed, one DDB
  entitlement row for the test user only.
- New read-only plan + separate env approval; no new Lambda, queue or IAM
  policy beyond the env configuration.

**Option B (not recommended): separate test Lambda** with test env and no
production dispatch binding — extra compute/IAM and a parallel deployment.

**Option C:** apply only the deny-by-default plan and test only the denial
paths; no positive CV/job/matching canary. This does not satisfy STEP E's
positive matrix.

## 4. Full AWS E2E procedure (after A + B approvals)

Two independent approvals are required: **A** exact plan apply, **B** synthetic
profile configuration.

1. Apply the exact saved plan; verify 4/3/0, no drift, guard, state.
2. Confirm analysis Lambda is Active, env is deny-by-default, parser unchanged.
3. Apply the approved synthetic allowlist config; verify it is tenant/user
   scoped and no global consent.
4. Synthetic chain:
   - Mays `ORDER_DISPATCH` (synthetic order) → dispatch SQS → ingress →
     WorkItem + work SQS → shared worker → registry/eligibility.
   - Analysis Lambda under its real role → parser Lambda; CV-only, job-only,
     ATS-only, comparison, full; PDF via S3 test object.
   - `ORDER_RESULT` success; terminal `ORDER_FAILED`; idempotent replay;
     result deduplication.
   - Addition-agent regression on the same queue.
   - Negatives: entitlement revoke after enqueue, consent denial, cross-tenant,
     subject fence, malformed/oversize input.
5. Evidence per case: `PASS`/`FAIL`/`BLOCKED` with request IDs, SQS message IDs,
   WorkItem IDs, log stream names, plan hashes — no payloads/CV content.
6. Cleanup: delete synthetic work items/job objects, revoke test entitlement,
   restore deny env, post-apply read-only plan (expect no drift), guard.
7. DLQ exhaustion: documented `BLOCKED`/open — no automatic ORDER_FAILED.

## 5. Stop conditions

- plan/JSON hash differs from the values in section 1;
- state serial/lineage differs from 67 / `a0bd361d…`;
- any resource beyond the 4/3/0 manifest, or a queue/IAM-policy change;
- worker/analysis/parser bundle hash mismatch;
- synthetic config is global or not tenant/user-scoped;
- any real CV/job/order data or production order;
- any catalog/offer seed or entitlement grant beyond the test user;
- any sensitive payload in logs;
- guard != `NO_SHARED_DESTROY`.

## 6. Cleanup / rollback

- Env: revert to deny defaults via the approved config change; no global
  consent left behind.
- Data: delete synthetic WorkItems, temporary job S3 objects, test entitlement;
  keep audit evidence IDs only.
- Terraform: no auto-destroy; a reviewed reverse plan if needed. Parser and
  existing runtime stay untouched.
- Orders: no order mutation by analysis; any synthetic order follows the
  existing Mays lifecycle and is not a billable real order.

## 7. Tests

Focused gate set: 70 passed (offers, ecosystem wiring, runner, work queue,
dispatch ingress, result path). No code/Terraform change in this gate.

## 8. Verdict

**SYNTHETIC TEST DESIGN NEEDS APPROVAL.**

The exact plan is technically ready for apply approval, but the current
function-global env cannot isolate a positive synthetic identity. A minimal
allowlist-gated test profile (Option A) must be approved separately before STEP
E. No apply and no approval is assumed here.
