# RIS Agent Lifecycle 12 — Shared Infrastructure Safety

**Project:** ris-dev2 · account 262370457690 · region eu-central-1
**Baseline:** RIS-AGENT-LIFECYCLE-11
**Date:** 2026-11-18
**Status:** GUARD IMPLEMENTED + HARDENED · LIVE PLAN PROOF · NO AWS MUTATION

---

## 1. Root cause

`terraform/main.tf` derives the dispatch transport from flags:

```
agent_dispatch_enabled = var.enable_agent_transport && local.orders_enabled
module "agent_transport" { count = local.agent_dispatch_enabled ? 1 : 0 }
```

`enable_agent_transport` and `orders_agent_result_enabled` default to `false`;
`orders_lifecycle=external|disabled` also removes the Orders component. In
Lifecycle-11 a plan without `--var enable_agent_transport=true` planned the
**destruction of the whole dispatch module** (11 resources) while the live
state still contained it. A missing flag is not a decommission order.

## 2. Guard

`installer/shared_infra_guard.py` (pure, no AWS):

- **Classification:** every `delete`/`replace`/`forget` is matched against
  shared modules (`agent_transport`, `mays_orders`, `lambda`, `dynamodb`,
  `cognito`, `orders_reader`, `api`, `sqs`, `iam`, `health_plane`,
  `health_public`, `health`, `monitoring*`, `documents`, `cloudtrail`,
  `jobsearch_edge`, `partner_edge`) and shared resource types (SQS, Lambda
  incl. permissions/aliases, ESM, DynamoDB, Secrets Manager, Cognito, API
  Gateway v2 incl. routes/integrations/stages/authorizers, CloudFront, IAM,
  EventBridge, log groups, S3 buckets, CloudTrail, KMS, SNS). Name markers
  cover both AWS hyphens and Terraform underscores.
- **Fail-closed plan shape:** a document without `resource_changes`, with
  non-list/non-string actions, `change: null`, `errored: true` or
  `complete: false` is refused (`PLAN_SHAPE_INVALID`), never treated as safe.
- **Flag diagnosis:** `enable_agent_transport`, `orders_agent_result_enabled`
  and `orders_lifecycle` are read from the plan. A shared teardown with a
  missing/false flag returns `MISSING_OR_FALSE_TRANSPORT_FLAG` and names the
  flag as the cause.
- **Teardown intent:** `--shared-teardown-intent <ref>` is validated
  (6–128 chars, no control/format characters, restricted charset),
  bound to the reviewed plan's SHA-256 and recorded in the decision
  (`TEARDOWN_INTENT_INVALID` otherwise).
- **Decision codes:** `NO_SHARED_DESTROY`, `MISSING_OR_FALSE_TRANSPORT_FLAG`,
  `SHARED_DESTROY_WITHOUT_INTENT`, `SHARED_TEARDOWN_AUTHORIZED`,
  `TEARDOWN_INTENT_INVALID`, `PLAN_SHAPE_INVALID`, `GUARD_UNREADABLE`.

Wiring in `installer/ris.py`:

- `_cmd_plan` always writes a plan file (`<workspace>-plan.tfplan`) and guards
  it; relative paths resolve in the runner workdir, not the installer cwd;
- `_cmd_apply`, `_cmd_install` and `_cmd_destroy` guard **before** the state
  mirror and before apply; a missing/unreadable plan is refused;
- `_plan_unchanged` re-hashes the plan before apply (TOCTOU);
- `terraform_runner.show_json` resolves relative to the working dir and does
  not select/create a workspace just to inspect a plan;
- `_print_command` redacts `-var` values so secrets never reach logs;
- `destroy` requires an explicit teardown reference.

## 3. Live plan proof (read-only, ris-dev2)

| Scenario | Result |
|---|---|
| Missing `enable_agent_transport` (the hazard) | **exit 1**, `MISSING_OR_FALSE_TRANSPORT_FLAG`, names `enable_agent_transport`, lists all 11 `module.agent_transport[0]` resources + reader dispatch policy |
| Live flags (`enable_agent_transport=true`, `orders_agent_result_enabled=true`) | **exit 0**, `NO_SHARED_DESTROY`, plan has **0 changes** (sha `c2a879bb…`) |

No apply, no state mutation, no resource change in this task.

## 4. Lifecycle contract re-verified

| Gate | Scope | Effective for |
|---|---|---|
| Agent catalog | discovery, partner/m2m API | not the worker, not the order reader |
| Entitlement | reader admission, dispatch ingress, worker execution | **all** execution paths |

Catalog status alone does **not** block every path
(`executionGates.catalogAloneBlocksExecution=false`). The dispatch ingress now
fails closed when `ENTITLEMENTS_TABLE` is missing instead of silently running
without authorization.

Synthetic fixtures: DISABLE removes no binding and reports the entitlement
withdrawal it requires; repeated DISABLE stays stable; DETACH removes only the
agent-scope entitlement (`scope: agent` enforced), keeps the partner
application (`action: retained`) and marks external references PENDING;
UNINSTALL is idempotent and keeps history/shared resources; retail and other
agents stay unaffected.

## 5. Removal-impact report

`removalImpact` is part of every plan/result manifest; `--impact-report <path>`
writes it standalone:

- `partnerApplications` (retained), `remainingExternalReferences`,
  `pendingExternalChanges` (`PENDING`);
- `agentAllowlist` (validated list + count), `entitlementStatus`,
  `entitlementsToWithdraw`, `entitlementWithdrawRequired`;
- `openOrders`, `openResults`;
- `notifications` — targeted only: `ris-runtime-team`, `operations`,
  `partner-team`, `security-privacy`, each only when affected; read-only
  actions never notify partner/security;
- `retained.sharedResources`, `retained.history`,
  `retailOrdersAffected=false`, `observedRetailOrders`,
  `evidenceSources` (observed vs declared), `secretValueRead=false`.

The audit entry is written **before** the state mutation and carries
`planDigest`, `lifecycleDigest` and `inventoryDigest`. `agent_install --action`
forwards actor/approval/reason.

## 6. Tests

| Suite | Result |
|---|---|
| `tests/test_shared_infra_guard.py` | **31 passed** |
| `tests/test_agent_lifecycle.py` | **24 passed** |
| `tests/test_dispatch_ingress_env.py` | **3 passed** |
| Installer/guard/state suites | **93 passed** |
| Combined run | **129 passed** |

Covered: missing/false/contradictory flags, `orders_lifecycle`, explicit and
malformed intent, malformed plan shapes, `forget`, replace, IAM/health/edge
classification, underscore labels, unrelated deletes, plan/apply/install/
destroy wiring, relative plan paths, missing plan, TOCTOU tamper, redaction,
and the lifecycle contract above.

## 7. Independent review outcomes

Two read-only reviews (QA of the guard, security of the impact/fail-closed
behaviour) found and we fixed:

- **P0** apply/install/destroy inspected a different plan path than they
  applied (missing plan = "safe") → paths now resolve in the runner workdir and
  a missing plan is refused; install and destroy now run the guard; plan
  always writes a plan file.
- **P0** `-var` values were printed → centralized redaction.
- **P1** classification gaps (IAM, health, edge, permissions, event rules,
  S3, CloudTrail, KMS, SNS) and hyphen/underscore marker mismatch → fixed.
- **P1** malformed plan JSON fail-open (`actions` as string, `change: null`,
  missing `resource_changes`, errored plans) → strict `PLAN_SHAPE_INVALID`.
- **P1** any non-empty intent authorized everything → validated, charset- and
  length-bounded, bound to the plan SHA-256 and recorded.
- **M** inventory `openOrders` shape, binding `scope` enforcement, declared vs
  observed evidence, audit-before-state, actor plumbing, targeted
  notifications, worker/ingress resolver fail-open, state-mirror permissions
  → fixed.

Accepted/remaining (documented, not changed here):

- `state push` can still remove resources from state without a plan; it
  requires `--yes` but not a teardown reference.
- Intent authorizes the whole reviewed plan, not individual addresses.
- The lifecycle YAML parser is line-based and comment-blind.
- `mirror_dir_for` validates the label but not the project name charset.
- Catalog remains discovery-only; PURGE remains blocked.

## 8. Commits

- `98c458d` — initial guard, wiring, impact report, tests.
- hardening commit (this report + fixes).
