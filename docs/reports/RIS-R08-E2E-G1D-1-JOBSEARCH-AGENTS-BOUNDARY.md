# R08-E2E-G1D-1 — JOBSEARCH / AGENTS BOUNDARY REPAIR

**Status:** COMPLETE / TARGETED GATE GREEN

## Baseline and root cause

- Baseline HEAD: `1a947d40fbeebcbdc58e8f37d0ef703c5a4c359e`
- G1C identified the only confirmed RIS regression in
  `jobsearch/partner_profile_repository.py`.
- Commit `8c5bcdc` added the direct import:
  `agents.ecosystem.privacy_erasure_contract.freeze_resource_id`.
- The repository is a lower-level Jobsearch persistence component. Its
  contract test explicitly forbids imports from `agents`, `openai`, Bedrock or
  Anthropic. The imported function is pure key derivation; it does not require
  Agent runtime behavior.

The intended existing contract is the stable `erasure-freeze#<sha256>` key
projection. The canonical JSON fields, sorting, separators and hash encoding
were verified against `agents/ecosystem/privacy_erasure_contract.py`.

## Repair

`jobsearch/partner_profile_repository.py` now contains a private pure
`_freeze_resource_id` projection with the exact existing contract algorithm.
The direct `jobsearch → agents` import was removed. No Agent functionality,
freeze behavior, transaction guard, or Erasure activation behavior was
removed or changed.

A focused regression assertion was added to
`tests/test_partner_profile_write_freeze.py`, covering both the USER and CV
freeze keys.

## Verification

| Test scope | Result |
|---|---:|
| Contract reconciliation, freeze guards, erasure contract/repository | **45 passed** |
| Jobsearch unit tests, ATS gate, freeze guards, erasure repository | **135 passed** |
| Direct boundary test (`test_repository_module_has_no_agent_or_model_import`) | **passed** |

No AWS calls, installations, deployments or Terraform changes were made.
The two G1C State-Mirror findings were not modified.

## Remaining baseline

The unrelated G1C findings remain unchanged:

- 2 State-Mirror component defects: SHA-256 recording and newest-entry
  rotation.
- 42 environment, Builder/baseline, Windows test-assumption or planned-scope
  failures.
- 56 explicitly scoped skips.

These were not reclassified or hidden by this repair.

## Cleanup

- No test service was started.
- No Java/DynamoDB Local process was started.
- Existing 39 untracked files were preserved.
- No productive Receipt or Erasure activation occurred.

## Commit

```text
fix(ris): restore jobsearch agents module boundary
```
