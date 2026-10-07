# RIS-CONSOLIDATION-GATE-02 — FINAL

Status: **GREEN locally** / AWS branch **BLOCKED** pending deployment approval.
Canonical HEAD: `8fd657224d88f94cc3313bb94a7106de7e498d33` (branch `main`)

Built on the verified Truth-Recovery state (`8b567c4`). Superseded Gate-01
and Gate-02 claims are not reused. Truth-Recovery report retained as
historical evidence.

---

## EXECUTION GRAPH — completed

```
VERIFIED STATE 8b567c4
   |
   +-- P1 UTC/WARNINGS  -> dfbd1c9  (SECURITY fix; warning hygiene ACTIVE)
   +-- P2 PRIVACY/API   -> 803f89f
   +-- P3 HEALTH        -> 8fd6572
   |
   v
P4 GLOBAL JOIN / RECONCILIATION
   v
P5 CROSS-REVIEW
   v
P6 FULL LOCAL REGRESSION
   v
AWS BRANCH — BLOCKED (no deploy performed)
```

## P1 — UTC / WARNING HYGIENE

**SECURITY FIX: GREEN. WARNING HYGIENE: ACTIVE (not GREEN).**

Fail-open authorization defect found and fixed (`lambda/handler.py:2449`).
A naive `datetime.utcnow()` compared against `dateutil` bounds raised
`TypeError`, which the same `except` used for parse failures swallowed, so
**any** offset-bearing window evaluated as VALID — expired and not-yet-valid
entitlements both passed ingress.

Ingress was more permissive than the worker gate that guards execution — the
inverse of the required invariant. Fixed by deleting the duplicate
implementation and delegating to the single canonical
`worker_authorization.is_entitlement_valid`.

Invariant recorded: **INGRESS AUTHORIZATION must never be more permissive than
WORKER AUTHORIZATION.** The 21 parity tests are permanent security
regression tests.

| Metric | Before | After |
|---|---|---|
| `utcnow()` sites (real) | 43 | 43 — **not migrated** (see below) |
| Warnings | 236 | 208 |
| Tests | — | +21 |

The "52 sites" figure was wrong: 9 were already-migrated `_utcnow()` helpers.

**Warning hygiene remains ACTIVE.** The 208 remaining warnings are
first-party `utcnow()` deprecations in `agents/`, `lambda/`, `jobsearch/` and
test fixtures. They were deliberately **not** bulk-migrated:
`jobsearch/domain_models.py` round-trips `createdAt`/`updatedAt` through
`.isoformat()`/`fromisoformat` into API responses, and
`datetime.now(timezone.utc).isoformat()` emits a `+00:00` suffix that
`utcnow().isoformat()` does not. Migrating it is a wire-format contract
change requiring its own decision and tests — not warning cleanup.

## P2 — PRIVACY / API GOVERNANCE

**GREEN locally. NOT deployed.**

- `DELETE /me/profile` added as a real Terraform route, reusing the existing
  integration and JWT authorizer (no second integration).
- **Governance defect fixed:** the P20 contract suite compared dispatch
  branches by PATH only, so `GET /me/profile` satisfied the exposure check
  for `DELETE /me/profile`. Route identity is now (METHOD, PATH), pinned by
  the new invariant in `API-STANDARD.md`. Verified by removing the route
  again: 3 tests fail; restoring it: 21 pass.
- **Route count reconciled with evidence:** the old docstring breakdown
  (18+7+4=29) contradicted its own assertion of 32. Counted from
  `terraform_routes()`: 29 agent + 4 orders-reader = 33. Assertion now pins
  total *and* split *and* the presence of the new route.
- **Privacy lifecycle documented.** `DELETE /me/profile` = PROFILE DELETION.
  It is **not** account deletion or personal-data erasure. Only
  `USER_PROFILE_TABLE` is affected; credentials, API profiles, entitlements,
  work items, job searches and documents are all RETAIN. No retention
  durations invented — none exist in the repository.
- **OpenAPI deliberately not created.** See "Deliberately not done".

```
tests/test_p20_api_contract_consistency.py   21 passed (was 19)
tests/test_profile_deletion.py                8 passed
terraform fmt -check -recursive               clean
terraform validate                            Success!
```

## P3 — HEALTH / TRACEABILITY

**GREEN locally.**

`TriggerType.HEALTH_*` were three enum members referenced by nothing
(verified by grep before starting). New `agents/ecosystem/health_plane.py`
provides a per-(component, tenant) state machine emitting through the
existing EventHook vocabulary. No new queue, table or monitoring platform.

Semantics enforced by tests, not just documented:

| Rule | Verified |
|---|---|
| `DEGRADED` only on transition out of HEALTHY | 50 failures → 1 event |
| `RECOVERED` only after observed `DEGRADED` | 10 successes → 0 events |
| no duplicate `RECOVERED` | cycle emits exactly 2 events |
| heartbeats rate-limited | 5-min interval |
| tenant isolation | tenant A failure leaves B healthy |
| no payload/PII/credential leakage | closed reason vocabulary; unknown reason coerced |
| instrumentation fail-safe | broken tracker cannot fail a job |

Wired into `process_record` at existing boundaries: entitlement-store outage,
agent exception, agent failure result, success. **Entitlement DENIED
deliberately emits nothing** — a denial is correct behaviour, and treating it
as degradation would mask real failures.

No new correlation identifier: `workId`/`tenantId`/`agentId`/`attempt`
already propagate.

`/health` untouched and still dependency-free liveness.

```
tests/test_health_plane.py             19 passed
tests/test_health_plane_integration.py  7 passed
```

## P4 — GLOBAL JOIN / RECONCILIATION

| Check | Result |
|---|---|
| Entitlement validation single source | yes — handler delegates to `worker_authorization` |
| Pipeline imports correct module | yes — `health_plane` |
| Terminology: redundant `correlationId` | none introduced (`credentials.py` one is pre-existing, commit `e0b95ff`) |
| Terminology: `workId` vs `work_id` | pre-existing serialization boundaries (`chain.py`, `monitor.py`), not introduced here |
| Health metadata vs privacy | `apiProfileId` appears only in the forbidden-key denylist |
| Health events vs traceability | reference existing identifiers only |
| Terraform ↔ dispatcher ↔ docs | method-level consistent, 21 contract tests |
| UTC changes vs serialization | contract-sensitive sites untouched |

No reconciliation code changes were required. P1/P2/P3 write sets did not
overlap (`lambda/handler.py` + terraform/docs vs `agents/`).

## P5 — CROSS-REVIEW

| Reviewer | Verdict | Evidence |
|---|---|---|
| Security | GREEN | 21 entitlement parity tests, 8 deletion authz tests, health metadata leak tests |
| Privacy | YELLOW | profile-only deletion documented honestly; cascade deletion **not** implemented (needs own gate) |
| Architecture | GREEN | no new infrastructure; no second monitoring platform; existing EventHook vocabulary reused |
| Runtime | GREEN | fail-safe instrumentation; `health_tracker=None` preserves legacy behaviour |
| OpenAPI/Contract | YELLOW | method-level governance fixed; platform OpenAPI still absent (OPEN-1) |
| Test/Evidence | GREEN | 1111 collected / 1103 passed / 0 failed; matrix regenerated and re-read |

## P6 — FULL LOCAL REGRESSION

```
collected:  1111
passed:     1103
failed:        0
skipped:       8
warnings:    236
```

Baseline history this gate: 1062 → 1083 → 1085 → 1111 collected. All growth
is new tests (21 entitlement + 2 governance + 26 health). No test weakened,
skipped or disabled.

Evidence matrix regenerated from a real junit run at HEAD `8fd6572`:
**56 non-empty entries**, re-read after writing.

Skips, all classified: 6 Observability + 2 Lambda Packaging, all gated on
`get_caller_identity().Account == "240571105849"`.

## AWS LIVE — BLOCKED (no deploy performed)

Status: **BLOCKED**, by instruction not by defect.

Live state verified with `--profile mayaws` (account 240571105849,
eu-central-1):

| Item | State |
|---|---|
| `DELETE /me/profile` route in gateway | **absent** — Terraform has it, not applied |
| 6 Observability live tests | **PASS** |
| `test_h_reader_hash_matches` | **PASS** |
| `test_e_noop_live_hash_matches` | **FAIL** — deployment drift |
| Lambda drift | no commit in 281 rebuilds to live `CodeSha256` |

The deployment decision must reconcile **both** the new route and the Lambda
drift in one deliberate apply against final canonical state, not as two
sequential deploys. Not performed here.

## COMMITS

| SHA | Content |
|---|---|
| `dfbd1c9` | **security**: entitlement window fail-open fix + 21 parity tests |
| `803f89f` | **feat(api)**: `DELETE /me/profile` Terraform route + method-level governance |
| `8fd6572` | **feat(health)**: real health-plane emission from runtime pipeline |

Preceded by `8b567c4` (truth recovery) — retained as historical evidence.

## GIT

```
branch:  main
HEAD:    8fd6572
worktree: modified (evidence matrix regenerated — see below)
pre-existing terraform changes: main.tf, cognito, monitoring,
  orders_reader, sqs, variables.tf — NOT touched by this gate,
  NOT staged, NOT committed
```

## DELIBERATELY NOT DONE

1. **Platform OpenAPI** — `jobsearch/openapi.yaml` describes an external
   service. A platform spec would cover 33 routes across two different error
   envelopes (OPEN-2), and OPEN-2 explicitly defers unifying them. A partial
   spec would imply a canonical contract that does not exist; a full one is a
   project requiring its own decisions. OPEN-1 stays honestly open.
2. **Cascade deletion** — credentials, API profiles, entitlements, work
   items, job searches, documents are retained. Real privacy work needing its
   own authorization decisions.
3. **Bulk `utcnow()` migration** — 43 sites remain. Deferred pending the
   timestamp serialization contract decision.
4. **Health event persistence/transport** — events are returned to the
   caller, not stored. Should follow a real consumer existing.
5. **`/health/runtime` endpoint** — `snapshot()` is groundwork; a new read
   endpoint needs its own route, auth decision and governance.
6. **AWS deployment** — see AWS LIVE.

## REMAINING TODO

| Item | Priority | Note |
|---|---|---|
| AWS deploy (route + Lambda drift, one apply) | needs approval | BLOCKED by instruction |
| Timestamp serialization contract decision | P1 | gates 43 sites |
| Cascade deletion design | P2 | privacy |
| Platform OpenAPI | P2 | OPEN-1 |
| Health event consumer/transport | P3 | needs a real sink decision |

## GATE VERDICT

**GREEN** for local implementation, cross-review and regression.

**Not GREEN overall**, because the AWS branch is BLOCKED and two reviewer
verdicts are YELLOW (privacy cascade, OpenAPI) by deliberate scope decision
rather than oversight. The two substantive defects found this gate — the
fail-open entitlement window and the unreachable deletion route — are fixed
and proven by negative controls.