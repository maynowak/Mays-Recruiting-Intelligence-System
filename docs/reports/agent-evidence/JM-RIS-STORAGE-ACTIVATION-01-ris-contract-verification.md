# JM-RIS-STORAGE-ACTIVATION-01 — RIS contract verification (B → A evidence)

**Date:** 2026-11-07
**Repository:** `Mays-Recruiting-Intelligence-System` (RIS / B side)
**Worktree:** `worktrees/ris-storage-activation-01`
**Branch:** `feature/jm-ris-storage-activation-01`
**Status:** `CONTRACT VERIFIED LOCAL` — tests + documentation only.
**No activation, no deployment, no push, no AWS/Terraform change, no Jobsearch edit.**

Counterpart handoff (read-only):
`mays-jobsearch@324ad18`, `docs/reports/agent-evidence/JM-RIS-STORAGE-ACTIVATION-01-jobsearch-requirements.md`.

---

## 1. Verdict (short)

| Question | Result |
|---|---|
| Jobsearch gate is fail-closed and cannot cause an unauthorized grant | **PASS** |
| Jobsearch gate matches the RIS grantability contract exactly | **REWORK_REQUIRED** |
| RIS can currently be activated | **NO** (notice `1.0` is `DRAFT`, server-side notice enforcement not wired) |

The only behavioural mismatch is that Jobsearch accepts **only `ACTIVE`**, while
RIS defines `APPROVED` **and** `ACTIVE` as grantable. This is fail-safe (it can
never grant against a draft or superseded notice) but it rejects a notice state
that the published RIS contract explicitly allows. Details and the exact fix
are in §9. Nothing is exploitable in the current state.

---

## 2. Answers to the seven questions

### Q1 — Is the catalogue always a top-level `catalog` array on `GET /v1/partner/me/consents`?

**Yes.** `lambda/handler.py:665-673`:

```python
if path == '/v1/partner/me/consents' and method == 'GET':
    purpose = params.get('purpose')
    purposes = [validate_purpose(purpose)] if purpose else sorted(CONSENT_PURPOSES)
    return _application_response(200, {
        'items': [repo.get(ctx, p) for p in purposes],
        'catalog': [entry for p in purposes for entry in catalog_payload(p)],
        'externalRefs': [entry for p in purposes
                         for entry in external_refs_payload(p)],
    })
```

Exact shape:

```jsonc
{
  "items":        [ /* per-purpose status row */ ],
  "catalog":      [ /* per-purpose notice entries */ ],
  "externalRefs": [ /* known-but-not-equivalent partner refs */ ]
}
```

- `catalog` is always present on a **200 GET** and always an array (possibly
  empty only if a purpose has no registered versions — not the case today).
- **Per-purpose scoping:** with `?purpose=application-storage` all three arrays
  contain only that purpose; without `purpose` the handler iterates
  `sorted(CONSENT_PURPOSES)` (today exactly one purpose).
- An **unknown** purpose is rejected before any array is built:
  `validate_purpose` → `ConsentContractError("UNKNOWN_PURPOSE")` →
  `404 UNKNOWN_PURPOSE` (`handler.py:688-690`). It is never an empty catalogue.
- Each entry carries `purpose`, so a consumer may filter on it. `payload()` in
  `jobsearch/consent_contract.py:79-89` always emits `purpose`.
- The **POST** grant response is `{"consent": {...}}` only — there is **no
  `catalog`** on POST. A partner must re-read GET before writing (Jobsearch
  does exactly that in `consentsHandler.mjs`).

Evidence: `tests/test_consent_notice_catalog_contract.py::CatalogShapeTests`
(`test_catalog_is_a_top_level_array_of_objects`,
`test_catalog_entry_carries_the_fields_the_partner_gate_reads`,
`test_catalog_is_scoped_to_the_requested_purpose`,
`test_unknown_purpose_fails_closed_instead_of_returning_an_empty_catalog`,
`test_grant_response_does_not_include_a_catalog`).

### Q2 — Exact `noticeState` values and grantability. Does `ACTIVE`-only wrongly block `APPROVED`?

`jobsearch/consent_contract.py:40-53`:

```python
NOTICE_DRAFT      = "DRAFT"
NOTICE_APPROVED   = "APPROVED"
NOTICE_ACTIVE     = "ACTIVE"
NOTICE_SUPERSEDED = "SUPERSEDED"
GRANTABLE_NOTICE_STATES = frozenset({NOTICE_APPROVED, NOTICE_ACTIVE})
```

Exactly four uppercase values. There is **no** `PUBLISHED`/`APPROVED_ACTIVE`
alias (test-asserted).

| State | Meaning | Grantable (enforced) |
|---|---|---|
| `DRAFT` | text exists, no legal approval | **no** |
| `APPROVED` | legally approved, not yet rolled out | **yes** |
| `ACTIVE` | approved and offered to new users | **yes** |
| `SUPERSEDED` | replaced; existing grants stay valid | **no** |

**Yes, `ACTIVE`-only blocks `APPROVED`.** With `APPROVED`, the catalogue returns
`noticeApproved=true`, `acceptedForNewGrant=true`, and RIS accepts the grant
under enforcement — but Jobsearch returns `409 notice_not_active`.

**Intended activation state:** `ACTIVE` is the intended *rollout* state for this
notice (offered to new users) and the state RIS operations must set before
`APPLICATION_CONSENT_ENFORCED=true`. `APPROVED` is a legitimate intermediate
state that the grant API accepts; a contract-faithful partner gate must accept
it too. This is the single required Jobsearch code change.

Evidence:
`test_state_enum_is_exactly_four_uppercase_values`,
`test_approved_is_legitimately_grantable_under_enforcement`,
`test_approved_and_active_grants_pass_under_enforcement`.

### Q3 — Are `noticeApproved` / `acceptedForNewGrant` authoritative strict booleans? What does DRAFT/SUPERSEDED report with enforcement off?

Both are strict booleans (`type(...) is bool`, test-asserted), computed in
`consent_contract.py:199-226`:

```python
"noticeApproved": entry.approved,                    # state in APPROVED_NOTICE_STATES
"acceptedForNewGrant": entry.grantable or not notice_state_enforced(),
```

`notice_state_enforced()` (`consent_contract.py:164-173`) reads
`CONSENT_NOTICE_STATE_ENFORCED`, default `"false"`.

| State | `noticeApproved` | `acceptedForNewGrant` (enforced=false) | `acceptedForNewGrant` (enforced=true) |
|---|---|---|---|
| `DRAFT` | `false` | **`true`** (technical grant) | `false` |
| `APPROVED` | `true` | `true` | `true` |
| `ACTIVE` | `true` | `true` | `true` |
| `SUPERSEDED` | `true` | **`true`** | `false` |

Important corrections for the Jobsearch handoff:

1. The A→B document predicts `acceptedForNewGrant: false` for `DRAFT`. That is
   **wrong while `CONSENT_NOTICE_STATE_ENFORCED=false`** (the current default
   and the deployed value): it is `true`.
2. Therefore `noticeApproved && acceptedForNewGrant` alone is **not** a safe
   gate: `SUPERSEDED` satisfies both while enforcement is off, yet a new grant
   against it is not grantable. The **state check is load-bearing**.
   Jobsearch's `noticeState === "ACTIVE"` check is what currently blocks
   `DRAFT`/`SUPERSEDED`, not `acceptedForNewGrant`.
3. Neither flag may be upgraded client-side; they are server-owned.

Evidence: `test_flag_matrix_with_enforcement_on_and_off`,
`test_approved_and_accepted_flags_alone_do_not_imply_grantable`.

### Q4 — Current status of `application-storage/1.0`; independent of privacy policy v1.1?

`consent_contract.py:94-104`:

```python
NOTICE_REGISTRY = {
    "application-storage": {
        "1.0": NoticeVersion(
            purpose="application-storage",
            version="1.0",
            state=NOTICE_DRAFT,
            label="RIS application-storage notice v1 (technical draft)",
            legal_approval_ref=None,
        ),
    },
}
```

Confirmed: `state=DRAFT`, `legalApprovalRef=null`, `noticeApproved=false`,
`grantableWhenEnforced=false`. It is **not approved** and must not be treated as
such by any partner.

**Independent of privacy policy v1.1.** `consent_contract.py` and
`consent_repository.py` contain no privacy-policy version, no `privacyPolicyVersion`
field and no `v1.1` reference (grep: no matches). The consent registry is keyed
only by `(purpose, noticeVersion)`. Publishing privacy policy v1.1 (Jobsearch
commit `509d12b`) does not alter the consent notice state. The catalogue entry
also has no privacy field (test-asserted).

Evidence: `test_current_notice_1_0_is_draft_without_legal_approval`.

### Q5 — Does the grant endpoint itself reject non-active/non-approved notices under `CONSENT_NOTICE_STATE_ENFORCED=true`? And when false?

**Yes under enforcement.** `consent_repository.grant` validates the identifier
once (`require_active=False`, so a repeat of an existing grant stays idempotent)
and then re-validates state **only when a new/regranted consent is written**
(`consent_repository.py:115-141`). `validate_notice_version`
(`consent_contract.py:181-196`) raises `ConsentContractError("NOTICE_NOT_ACTIVE")`
when the state is not in `GRANTABLE_NOTICE_STATES`. The handler maps that to
**HTTP 422 `NOTICE_NOT_ACTIVE`** (`handler.py:688-690`).

**When false:** a known identifier (today only `1.0`) is accepted, so a `DRAFT`
can be recorded. That is deliberate for synthetic/technical runs and is **not**
a legal approval.

**Defence-in-depth status: incomplete in deployment.** `CONSENT_NOTICE_STATE_ENFORCED`
is read by the code but is **not wired into Terraform** (`terraform/modules/lambda/main.tf`
sets only `APPLICATION_CONSENT_ENFORCED`; repo-wide grep finds the flag only in
Python/docs/tests). It therefore defaults to `false` in every deployed
environment unless set out-of-band. Jobsearch's BFF gate is currently the only
effective notice-approval barrier. This is an RIS activation blocker (see §8),
not something this task changed.

Evidence: `test_draft_grant_is_rejected_with_422_semantics_under_enforcement`,
`test_draft_grant_is_accepted_only_while_enforcement_is_off`,
`test_superseded_new_grant_is_rejected_under_enforcement`.

### Q6 — Withdrawal in every state; `APPLICATION_CONSENT_ENFORCED` write coverage

**Withdrawal stays possible in every notice state.** `consent_repository.withdraw`
validates the stored (or explicitly requested) version with
`require_active=False` (`consent_repository.py:202-207`) and never consults
`notice_state_enforced()`. Test:
`test_withdrawal_remains_possible_in_every_notice_state` (grant recorded while
enforcement is off, then `DRAFT` and `SUPERSEDED` under enforcement → withdraw
succeeds, version 2). The existing lifecycle test also withdraws a
`SUPERSEDED` grant (`test_existing_grant_survives_superseding_and_stays_idempotent`).

**`APPLICATION_CONSENT_ENFORCED=true` gates exactly five ApplicationV1 write
paths** (`handler.py`): `POST /applications` (create, line 774),
`PATCH /applications/{id}` (799), `POST .../status` (810),
`POST .../history` (819), `POST .../cover-letter-versions` (825). Denial is
`403 CONSENT_REQUIRED`.

**Reads/export/delete are not gated:** `GET /applications` (list), `GET
/applications/{id}`, `GET /applications/metrics`, `GET .../export`,
`DELETE /applications/{id}` have no consent check. Test-asserted statically by
`tests/test_consent_gate.py::test_gate_covers_every_application_write_path`
(exactly 5 call sites) and behaviourally by
`tests/test_consent_e2e_joint.py::test_eight_step_synthetic_scenario` steps 5–6
(patch denied after withdrawal; get/export/delete still succeed). Gate fail-closed
behaviour when the consent store is unavailable:
`test_gate_fails_closed_when_store_is_unavailable`.

### Q7 — Exact activation blockers (nothing activated)

1. **Primary blocker — notice `1.0` is `DRAFT` with `legalApprovalRef=null`.**
   No legal approval record exists. Neither RIS nor Jobsearch may invent one.
2. **`CONSENT_NOTICE_STATE_ENFORCED` is not wired in Terraform** and is
   therefore `false` in deployment. Server-side defence in depth is inactive;
   a caller that bypasses the BFF could still record a `DRAFT` grant. It must
   be added to the Lambda environment (new variable/plan) and enabled before
   enforcement is claimed.
3. **`APPLICATION_CONSENT_ENFORCED=false`** (`terraform/variables.tf:345-349`,
   default `false`; deployed value `false`). It must only be set after
   Jobsearch ships its gate and the notice is `ACTIVE`.
4. **Jobsearch-side flags:** `RIS_APPLICATION_STORAGE_ENABLED` (BFF, default
   off), `RIS_CONSENT_SERVICE_ENABLED` (consent BFF, default off),
   `RIS_CONSENT_NOTICE_VERSION` (server-owned mapping, currently `1.0`) and
   `VITE_RIS_CONSENT_UI_ENABLED` / `VITE_RIS_APPLICATION_STORAGE_ENABLED`
   (browser opt-ins). None were changed here.
5. **Ordering:** legal approval for `1.0` (or a mapped successor) → registry
   state `APPROVED`/`ACTIVE` with `legalApprovalRef` → wire + enable
   `CONSENT_NOTICE_STATE_ENFORCED` → synthetic live grant/withdraw/regrant →
   `APPLICATION_CONSENT_ENFORCED=true`. Enabling the ApplicationV1 gate before
   the notice is grantable would lock out all writes.
6. `PARTNER_SURFACE_ENABLED` must stay `true` for the consent routes to be
   reachable at all (`handler.py:177-196`).

---

## 3. Test evidence (real, local, moto)

```
$ PYTHONPATH=/tmp/opencode/pydeps python3 -m pytest \
    tests/test_consent_notice_lifecycle.py \
    tests/test_consent_notice_catalog_contract.py \
    tests/test_consent_gate.py \
    tests/test_consent_e2e_joint.py \
    tests/test_consent_repository.py -q
40 passed in 6.24s

$ PYTHONPATH=/tmp/opencode/pydeps python3 -m pytest \
    tests/test_consent_notice_catalog_contract.py -q
16 passed in 2.24s

$ PYTHONPATH=/tmp/opencode/pydeps python3 -m pytest \
    tests/test_application_repository.py tests/test_application_auth_boundary.py \
    tests/test_application_privacy_contract.py tests/test_application_erasure.py \
    tests/test_application_api_security.py tests/test_application_contract.py -q
39 passed in 2.14s
```

New file: `tests/test_consent_notice_catalog_contract.py` (16 tests) locking the
catalogue shape, purpose scoping, state enum, flag matrix with enforcement
on/off, the `APPROVED`-is-grantable gap, the `SUPERSEDED` trap, current
`1.0` status, grant rejection under enforcement, and withdrawal in every state.

---

## 4. Jobsearch verdict: `REWORK_REQUIRED` (fail-safe, low risk)

No security defect: the gate fails closed, re-reads the catalogue before
writing, never trusts client input for the version, and blocks `DRAFT` and
`SUPERSEDED`. Required changes:

**R1 (code, one line).** Mirror `GRANTABLE_NOTICE_STATES`:
`api/_lib/ris/consentNotice.mjs` currently does
`entry.noticeState.toUpperCase() !== "ACTIVE"`. Accept
`APPROVED` **or** `ACTIVE` (e.g. `!["APPROVED","ACTIVE"].includes(state)`),
keeping everything else unchanged. Do not add `SUPERSEDED` or `DRAFT`.

**R2 (documentation, required for the audit trail).** In
`docs/reports/agent-evidence/JM-RIS-STORAGE-ACTIVATION-01-jobsearch-requirements.md`
correct the claim that `DRAFT` reports `acceptedForNewGrant: false`. RIS reports
`true` while `CONSENT_NOTICE_STATE_ENFORCED=false`. State explicitly that the
`noticeState` check — not `acceptedForNewGrant` — is what blocks `DRAFT`, and
that `SUPERSEDED` reports `noticeApproved=true` + `acceptedForNewGrant=true`
with enforcement off.

**R3 (coordination, no Jobsearch code).** Treat RIS
`CONSENT_NOTICE_STATE_ENFORCED` being unwired (`false` in deployment) as a
blocker: the BFF gate is currently the only notice-approval barrier.

**Confirmed correct, no change:** top-level `catalog` requirement; strict
boolean handling; purpose filtering; re-reading the catalogue immediately
before POST; withdraw pass-through independent of notice state; 409/503 error
mapping; no legal refs in browser responses.

---

## 5. Explicit non-claims

- Local tests only. **No live persistence, grant, withdraw, or API evidence.**
- No deployment, no push, no merge, no AWS/DynamoDB access, no Terraform
  change, no environment/flag activation.
- No Jobsearch file was edited.
- `APPLICATION_CONSENT_ENFORCED` and `CONSENT_NOTICE_STATE_ENFORCED` remain
  `false`/unset; the notice remains `DRAFT`.
