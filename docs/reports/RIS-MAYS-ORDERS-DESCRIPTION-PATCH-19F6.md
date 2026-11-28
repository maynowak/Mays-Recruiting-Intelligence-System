# RIS-MAYS-ORDERS-DESCRIPTION-PATCH-19F6

**Outcome:** OrderDescription is already present in the integrated Mays-Orders
source/module. The selected commit is not a safe patch overlay on that source;
no persistent source, pin, or module change was made.  
**RIS branch:** `feature/ris-analysis-integration-07`  
**Starting RIS HEAD:** `93c6c2faca2a252b5f30a8a6e0be1603f360c890`

## Source identity and boundaries

- Integrated Mays source: `db4f9e79980443de1cd3d5b688a33c0cf0eb771f`.
- Patch commit: `80a84ca2f146d5efaa31d41ba425359283333f21` —
  `feat(orders): add optional orderDescription field`.
- The integrated source and patch commit are separate history lines; the
  integrated source is not an ancestor of the patch commit.
- Clean isolated checkout at `db4f9e7` was used for patch applicability and
  baseline tests. No Mays ref or source was modified.
- Existing generated module manifest continues to identify `db4f9e7` and its
  Lambda artifact hash; existing builder pin is unchanged.

## Patch scope and dry-run

The feature commit changes 16 paths in total: API/database/docs, one binary ZIP,
three Lambda source files (`order_service.py`, `order_types.py`, `validation.py`),
and a new 328-line Lambda test file. Only the functional Python files and that
test file were considered; the unrelated full source tree and documentation
were not copied.

`git apply --check` was run against a clean detached `db4f9e7` clone using only
those four paths. **It failed**:

- `lambda/src/order_service.py`: hunk near line 280 did not apply.
- `lambda/src/order_types.py`: hunk near line 45 did not apply.
- `lambda/src/validation.py`: hunk near line 16 did not apply.
- `lambda/tests/test_order_description.py`: file already exists in the base.

No patch was applied. The failure is due to source divergence and pre-existing
implementation, not a cleanly applicable patch waiting to be installed.

## Existing feature and preservation evidence

The `db4f9e7` source already contains:

- optional `orderDescription` validation (trimmed non-empty text, max 1,024
  characters, forbidden control/separator characters rejected);
- persistence for both retail and agent orders, with existing strict unknown
  field validation retained;
- privacy inspection/export and removal on anonymization;
- Mays-owned `lambda/tests/test_order_description.py` (15 dedicated tests).

The generated RIS module carries the same feature while retaining the integrated
transport/consumer, HMAC, security, and lifecycle files. Its manifest source is
still `db4f9e7`; no generated module files were changed.

## Tests

Unified runner provenance was verified against the clean `db4f9e7` checkout.

| Gate | Result |
|---|---|
| Mays OrderDescription original tests | **15/15 PASS** |
| Unified `MAYS_MODULE` | **BLOCKED**: Lambda 240 PASS; Builder 88 PASS / 12 FAIL (+6 subtests); Installer 69 PASS / 11 errors / 1 skipped; Seeds 28 PASS; Cognito backup 2 PASS |
| Unified `XREPO_CONTRACT` | **PASS**: 133 passed + 4 subtests |
| Unified `XREPO_E2E` | **PASS**: 39 passed |
| Unified `FULL` | **BLOCKED**: Mays Builder/Installer failures above; RIS Native also has collection errors (`moto` unavailable; `requests` unavailable; 3 tests skipped). RIS Builder contract 57/57 and generated-module artifact 9/9 pass. |

The original Builder/Installer failures are recorded, not waived. The unified
runner's `UPGRADE_GATE` is not valid for an uncommitted overlay: it requires a
clean checkout at one exact version-map SHA and a generated module manifest
whose `source.commit` matches that SHA. The repository Builder exposes only a
single source pin; it has no versioned patch-overlay input. It generates from
the pinned checkout, validates the result, and the Installer replaces the
module directory rather than merging source files from an older module.

## Decision / next step

No patch overlay is needed for the requested feature: it is already implemented
and passes its focused original tests and the RIS cross-repository contract/E2E
gates at the integrated source. Do not reapply the divergent feature commit or
replace the module with the patch commit's full source tree.

If a new attributable release/source identity is required, the next integration
must be a reviewed Mays-owned commit based on the integrated line (or an
explicitly designed RIS-owned immutable patch artifact), followed by a Builder
and Unified runner that can validate that exact provenance. That integration is
outside this dry-run and requires a new authorization. No permanent source
change, module pin update, module installation, Terraform validation/plan/apply,
AWS mutation, LIVE test, or Main merge occurred. `MODE=true` was unchanged.
