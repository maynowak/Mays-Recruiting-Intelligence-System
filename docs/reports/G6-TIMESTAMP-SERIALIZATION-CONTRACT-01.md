# G6-TIMESTAMP-SERIALIZATION-CONTRACT-01

STATUS: GREEN — contract pinned, migration complete, regression green. AWS deployment required.

## AWS_PROFILE preflight
**cause:** Two installer tests asserted about ambient `os.environ` after `patch.dict` exited, failing whenever CI exported `AWS_PROFILE`.
**fix:** Snapshot-compare environment before/after for `test_aws_context_flows_to_child_env`; read `_terraform_env()` inside patch with AWS keys stripped for `test_runner_without_context_unchanged`.
**with profile:** 36 passed
**without profile:** 36 passed

## TIMESTAMP INVENTORY
**before:** 45 first-party `datetime.utcnow()` sites measured from HEAD 6192b5b
**migrated:** 45 (21 production, 24 test/fixtures)
**remaining:** 0 executable calls. 1 deliberate negative-control call in `test_timestamp_contract.py` inside `assertWarns(DeprecationWarning)` to prove the defect exists.

Classification
- internal-only arithmetic: `agents/agent_body/executor`, `agents/ats_agent/agent`, `agents/agent_body/*`, `jobsearch/reference_actor`
- DynamoDB persistence: `lambda/handler` user-profile `createdAt/updatedAt`, work-item `createdAt/expiresAt`, `jobsearch/domain_models` `created_at/updated_at`
- API response: `GET /me/profile` returns stored naive-UTC strings unchanged; `PUT /me/profile` returns `updatedAt` unchanged
- agent invocation / queue payload: result `timestamp`, `processedAt`, `createdAt` serialized as legacy naive-UTC
- tests/fixtures: jobsearch repository fixtures, platform handler tests, event hook pipeline

Duplicate helpers found: `agents/runtime/pipeline._utcnow` already emitted `+00:00`; `agents/ecosystem/introspection._utcnow` already aware. Both preserved — no competing helper introduction.

## CONTRACT
**internal:** timezone-aware UTC via `agents.timeutil.utcnow()`
**API:** legacy naive-UTC ISO-8601, byte-identical to previous `datetime.utcnow().isoformat()`
**DynamoDB:** legacy naive-UTC strings preserved; new rows built from aware instant with offset stripped
**events / queue:** legacy naive-UTC strings preserved
**authorization:** internal aware objects compared against `dateutil.parser.parse` bounds; naive/aware comparison defect impossible

Decision rationale: preserving wire representation avoids rewriting already-stored rows and changes zero consumer contracts. Aware → strip-offset → isoformat is byte-identical to legacy production.

## WIRE COMPATIBILITY
**changed:** none
**unchanged:** API responses, DynamoDB attributes, SQS payloads, agent results
**evidence:** `test_timestamp_contract.TestWireRepresentation.test_wire_form_is_unchanged_by_migration` asserts byte identity for naive and microsecond cases; full platform handler tests green.

## WARNINGS
**before:** 45 first-party `datetime.utcnow()` deprecation sites (runtime warnings)
**after:** 0 first-party datetime deprecation warnings
**first-party datetime:** 0
**external:** botocore `datetime.utcnow()` warnings remain (not ours)
**other:** 1 intentional negative-control warning in contract test

## NEGATIVE CONTROLS
- `test_wire_form_is_unchanged_by_migration` fails if serialization emits `+00:00` or `Z`
- `test_offsets_are_normalized_to_utc_before_stripping` fails if offset dropped without conversion
- `test_no_naive_aware_comparison_error` fails if naive/aware comparison reintroduced
- `test_existing_helpers_delegate_to_the_canonical_one` records pre-existing mixed representation; would fail if pipeline representation changed

All controls mutate behaviour; no vacuous asserts.

## TARGETED TESTS
`tests/test_timestamp_contract.py`: 12 passed
`tests/test_platform_handlers.py`: 30 passed
`tests/unit/jobsearch/test_repository.py`: 10 passed
Installer AWS_PROFILE independence: 36 passed with/without ambient profile

## FULL REGRESSION
collected: 1196
passed: 1196
failed: 0
skipped: 8
warnings: 4 (3 external botocore, 1 intentional contract negative control)

## AWS DEPLOYMENT REQUIRED
YES
Canonical build: `python3 lambda/build_zip.py --bundle agent`
Artifact: `terraform/lambda.zip`
sha256: `21146c0b9badfc7441d1e95843333cfe783f430ba2b03f3607c60546c1591dad`
Source HEAD → canonical build → artifact verify → Terraform plan required before apply. Do not apply without explicit deployment approval gate.

## EVIDENCE VERIFIER
VERIFIED

## COMMITS
- `cc65749` test(installer): make AWS-context tests independent of ambient AWS_PROFILE
- `40ad181` feat(timestamps): canonical UTC helpers + serialization contract tests
- `7d42391` refactor(timestamps): migrate utcnow to canonical helpers with legacy wire preservation

## GIT
HEAD: 7d42391
worktree: main

## NEXT
G7 Health Event Sink / Consumer
