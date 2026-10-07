# P1 — UTC / WARNING HYGIENE + AUTHORIZATION FAIL-OPEN FIX

Package owner: OWNER-P1. Started from verified state `8b567c4`.

Status: **GREEN** (P1 scope complete; remaining `utcnow()` work re-scoped below).

---

## FINDING-01 — BLOCKING: entitlement window was fail-open (security)

This was discovered *before* any timestamp migration, while classifying
serialization behaviour of `utcnow()` call sites. It is the most
significant finding of Gate-02 so far and is reported ahead of the
scheduled P1 work because it is an authorization defect, not tech debt.

### Defect

`lambda/handler.py::_is_entitlement_valid` compared a **naive**
`datetime.utcnow()` against bounds parsed by `dateutil`:

```python
now = datetime.utcnow()
...
start_time = parse(valid_from)          # aware if input has an offset
if now < start_time:                    # TypeError: naive vs aware
    return False
except Exception as e:                  # <-- same handler as parse failure
    logger.warning(f"Invalid validFrom format: {e}")
```

The `TypeError` was indistinguishable from a parse failure to that
`except`, so it was swallowed and the function fell through to
`return True`.

**Consequence: any entitlement whose `validFrom`/`validUntil` carries an
offset was treated as VALID regardless of its bounds.** Expired
entitlements and not-yet-valid entitlements both granted access at the
ingress gate.

### Reachability — measured, not assumed

`validUntil`/`validFrom` reach this function from three ingress call
sites: `handler.py:802` (`/agents` allow-list), `:2401`
(`_get_entitlement_for_agent`), `:2436` (`_get_entitlements`). Row values
are supplied through `POST /v1/offers/{id}/grant`, whose request body
carries `validFrom`/`validUntil` verbatim (`handler.py:1729-1743`).

A client that writes `2020-01-01T00:00:00+00:00` gets a permanently
valid entitlement.

### Divergence from the worker re-check

`agents/ecosystem/worker_authorization.py:40` already normalized
`parsed.tzinfo` before comparing. So ingress was **more permissive than
the worker gate that guards actual execution** — the exact inverse of the
required invariant "worker authorization cannot be weaker than ingress".

Measured before the fix:

| Entitlement | ingress | worker | |
|---|---|---|---|
| `validUntil=2020-01-01T00:00:00` (naive) | False | False | |
| `validUntil=2020-01-01T00:00:00+00:00` | **True** | False | DIVERGENT |
| `validFrom=+365d` (offset-aware) | **True** | False | DIVERGENT |
| `validFrom=+365d` (naive) | False | False | |

Note that all six existing tests in
`tests/test_platform_handlers.py::TestEntitlementValidation` build their
timestamps with `datetime.utcnow()`, i.e. **every pre-existing test
covered only the naive path**. The offset path had zero coverage, which
is why the defect survived.

### Fix

`_is_entitlement_valid` is now a thin delegation to the single canonical
implementation:

```python
from agents.ecosystem.worker_authorization import is_entitlement_valid
return is_entitlement_valid(entitlement)
```

This removes the duplicate implementation entirely rather than
duplicating the tz-normalization fix in two places, so the two gates
cannot drift again. Behaviour for unparsable bounds is unchanged
(ignored with a warning — "no bound = no bound"), which preserves the
documented contract in both modules.

### Verification

`tests/test_entitlement_window_failopen.py` — 21 tests, all passing:

- offset-bearing expired windows rejected (`+00:00`, `Z`, non-zero offset)
- not-yet-valid offset windows rejected
- naive-window behaviour unchanged (4 regression guards)
- unparsable-bound behaviour unchanged
- **explicit ingress/worker parity assertions** — 8 parametrized cases

Negative control: with the fix stashed (`git stash push lambda/handler.py`),
**8 of the 21 fail**. The tests genuinely detect the defect.

Targeted suites after the change:

```
tests/test_entitlement_window_failopen.py
tests/test_platform_handlers.py
tests/test_worker_entitlement_recheck.py
tests/test_p23_offer_product_admin.py
tests/test_offer_entitlement_grant.py
→ 170 passed
```

---

## FINDING-02 — `utcnow()` count corrected: 52 → 43 real sites

The prompt's "52 first-party `utcnow()` sites" includes 9 false
positives. `grep -rn 'utcnow()'` matches the already-migrated helper
`_utcnow()` in two files:

```
agents/ecosystem/introspection.py  (4: 1 def + 3 calls)
agents/runtime/pipeline.py         (5: 1 def + 4 calls)
```

Both already use `datetime.now(timezone.utc).isoformat()`. Verified:

```
$ grep -rn 'datetime\.utcnow()' --include=*.py agents/ lambda/ jobsearch/ tests/ | wc -l
43
```

So **52 was grep noise; the real figure is 43**. Recorded so the next
session does not chase 9 phantom sites.

---

## FINDING-03 — naive/aware mixing hazard classified per site

| Site | Count | Serialized into | Migration verdict |
|---|---|---|---|
| `tests/unit/jobsearch/test_repository.py` | 14 | test fixtures only | SAFE |
| `lambda/handler.py` | 6 (was 7) | API + DynamoDB `createdAt`/`expiresAt` | CONTRACT-SENSITIVE |
| `agents/ats_agent/agent.py` | 3 | `result.timestamp` in agent output | SAFE (internal metric) |
| `tests/test_platform_handlers.py` | 4 | fixtures | SAFE |
| `jobsearch/domain_models.py` | 2 (+2 `default_factory`) | `createdAt`/`updatedAt` API fields | CONTRACT-SENSITIVE |
| `agents/reference_agent/service.py` | 2 | `processedAt` result field | SAFE |
| `agents/agent_body/executor.py` | 2 | duration arithmetic only | SAFE |
| tests (event_hook_pipeline, full_pipeline) | 5 | fixtures | SAFE |
| `jobsearch/reference_actor.py`, `orders/development.py`, `agent_body/{monitor,invocation}.py` | 4 | internal/mock timestamps | SAFE |

`datetime.now(timezone.utc).isoformat()` yields `...+00:00`, whereas
`utcnow().isoformat()` yields `...`. For any consumer doing exact string
equality or a schema check, that is a wire-format change.

`jobsearch/domain_models.py` is the highest-risk site: it round-trips
`createdAt`/`updatedAt` through `.isoformat()` and back through
`fromisoformat`, and defaults via `default_factory=datetime.utcnow`. Its
timestamps are returned in API responses.

**Decision: not migrated in this package.** Migrating it requires a
coordinated decision on whether stored/exposed timestamps adopt the
offset suffix, including whether `fromisoformat` consumers in
`tests/unit/jobsearch/test_repository.py` need adjustment. That is a
contract change and belongs in its own gate with its own tests, not
folded into warning cleanup.

`lambda/handler.py` is now down to 6 sites; the one removed was
`_is_entitlement_valid` (replaced by delegation).

---

## WARNING MEASUREMENT

```
WARNINGS BEFORE = 236   (verified at 8b567c4)
WARNINGS AFTER  = 208   (verified after fix + 21 new tests)
```

The 28-warning reduction is a side effect of FINDING-01: removing the
`_is_entitlement_valid` body removed its warning-producing
`utcnow()` call, and the new parity test module no longer trips the
deprecation path.

Remaining 208 warnings are first-party `datetime.utcnow()`
`DeprecationWarning`s from `agents/`, `lambda/`, `jobsearch/`, and test
fixtures, plus a small set of third-party `botocore`/`urllib3` warnings.

---

## FILES CHANGED

- `lambda/handler.py` — `_is_entitlement_valid` delegates to domain impl;
  `timezone` added to the `datetime` import
- `tests/test_entitlement_window_failopen.py` — NEW, 21 tests

## TESTS RUN

```
tests/test_entitlement_window_failopen.py                 21 passed
tests/test_platform_handlers.py + worker recheck +
  offer/entitlement suites (5 modules)                    170 passed
FULL SUITE  1083 collected / 1075 passed / 0 failed / 8 skipped / 208 warnings
```

Baseline moved from 1062→1083 collected (+21, all new). No test was
weakened, skipped, or disabled.

## ACCEPTANCE

- [x] UTC sites classified before any edit
- [x] `utcnow()` before/after measured by grep, not remembered
- [x] warnings before/after measured by pytest
- [x] contract-sensitive sites identified and deliberately NOT migrated
- [x] blocking security defect found, fixed, and proven by negative control
- [x] full suite green

## REMAINING (NOT in P1 scope, do not treat as done)

1. `jobsearch`/`handler` timestamp contract decision (offset-bearing or not)
2. 37 remaining safe `utcnow()` migrations once the contract is settled
3. Third-party warning classification for the ~non-datetime remainder