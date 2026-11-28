# RIS–Mays-Orders Compatibility Resolution — 19F4

**Outcome:** RIS API contract, current integration gates, and cross-platform
bundle reproducibility pass. RC4 remains **not upgrade-ready** due Mays-owned
source and generated Terraform contract failures. Final Ubuntu run `45966656833`
on `4cd7042ff30b8c29f6c8e4d32f235776f6b349bb` completed with current `FULL`
passing and `UPGRADE_GATE` blocked only by expected RC4 contract/artifact
failures. No AWS/live/installation operations were performed.

## Identity and change boundaries

| Item | Identity / outcome |
|---|---|
| RIS branch | `feature/ris-analysis-integration-07` |
| Requested starting HEAD | `d181a2aa399da8f47cd14d42bde76d184c29ad5a` |
| Current integrated Mays source | `db4f9e79980443de1cd3d5b688a33c0cf0eb771f` (read-only) |
| RC4 candidate | tag `v0.6.0-rc.1`, tag object `79628819717e4609d828581dff53055f2b32f8ec`, commit `5bc154e079b4d7ee9eedbbf5b45b1ecca5c35420` (separate, read-only) |
| Worker historical hash | `78eb6edaed19026d4149a7a73e0ef22378e73fe3eff761b9f56b31fe54b51bf7` (retained; no pin change) |
| Final source scope | OpenAPI documentation, deterministic build tooling/tests, QA-only workflow, evidence/docs. No RIS worker/runtime semantic change and no compatibility adapter. |

## Gate summary

| Gate | Result | Evidence |
|---|---|---|
| `RIS_OPENAPI_CONTRACT` | **PASS** | APIProfile binding is implemented/routed/JWT admin-gated. Original 3 failures pass; relevant OpenAPI/API group 87 passed + 322 subtests. Commit `06f9181`. |
| `RIS_NATIVE_QA` | **PASS** | Full local `RIS_NATIVE`: 3,282 passed, 0 failed, 142 skipped, 450 subtests. Focused worker/build regression: 26 passed, 2 credential-gated skips, 4 subtests. |
| `BUNDLE_ROOT_CAUSE` | **VERIFIED** | Mixed checkout line endings changed source bytes; DEFLATE implementation and ZIP `create_system` markers differed across platforms. Builder canonicalizes source LF, stored compression, and `create_system=0`. |
| `BUNDLE_REPRODUCIBILITY` | **PASS** across Windows and Ubuntu | Two independent clean builds on each platform agree on worker `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d`, analysis `370890d459488304481d99255cfa6a2891b5f19a8c5df2723556905195c7c621`, and reader `bea4c3e59666bed8ad071ad4e405bcdfd57dafdac68096ce648667f0effb1b41`. |
| `BUNDLE_PIN_REVIEW_REQUIRED` | **YES** | New worker hash is review-only. No deployment pin changed. |
| `REFERENCE_PLATFORM_QA` | **PASS for current source; RC4 upgrade FAIL** | Final run `45966656833` at `4cd7042` completes current `FULL` profile and candidate `UPGRADE_GATE`; the latter fails only on RC4-generated contract and XRepo gates. |
| `CURRENT_MODULE_QA` | **PASS** | Ubuntu originals: Lambda 240; builder 100 + 6 subtests; installer 81; seed 28; Cognito backup 2. Current generated-module contract 9/9 and backend-free Terraform validate pass; current XRepo 133 + 4 and 39 pass. |
| `RC4_MODULE_QA` | **Original suites PASS / upgrade blocked** | Candidate originals pass: Lambda 440; builder 129; installer 81; seed 28; Cognito backup 2. RC4 generated Terraform validation fails; generated module contract 2 passed / 7 failed. |
| `CURRENT_XREPO_QA` | **PASS** | Exact current rerun: Contract 133 passed + 4 subtests; E2E 39 passed. |
| `RC4_XREPO_QA` | **FAIL** | Contract 120 passed / 13 failed + 4 subtests; E2E 3 passed / 36 failed, reproducible on exact candidate. |
| `GENERATED_TERRAFORM_VALIDATION` | **PASS current / FAIL RC4** | Current generated module 9/9 and backend-free validation pass. RC4 `fmt` and backend-free init pass, but validate fails on undeclared inputs and `module.privacy_secret` references. |
| `MAYS_SOURCE_FIX_REQUIRED` | **YES** | Request: `MO-RC4-RIS-COMPATIBILITY-FIX.md`. No safe RIS workaround exists for missing transport/consumer code and rejected required order data. |
| `WORKER_DEPLOYMENT_READINESS` | **BLOCKED** | Cross-platform verification passes; separate review/approval of candidate hash/pin remains. No deployment authorized. |
| `MAYS_ORDERS_UPGRADE_READINESS` | **BLOCKED** | RC4 source contracts, generated Terraform, and XRepo failures remain. |

## Root-cause grouping and ownership

The 49 failing XRepo checks are not 49 independent fixes:

1. **Transport/consumer modules absent in RC4 (Mays-Orders source).** Current
   source has `lambda/src/dispatch.py`, `result_envelope.py`, `result_handler.py`,
   `result_consumer.py`, and `agent_order.py`; RC4 lacks all five. This explains
   transport constant/schema failures and most dispatch/result E2E import and
   round-trip failures. Existing Mays originals cover transport/HMAC/lifecycle
   behavior in `test_hmac_contract.py`, `test_processing_result.py`,
   `test_sqs_handler.py`, and service/lifecycle tests; RC4 needs its missing
   module-level originals restored/added at Mays.
2. **Create contract mismatch (Mays-Orders validation).** The exact RC4
   `validation.validate_create_order` rejects the RIS request with
   `Unknown field 'orderDescription' at body`; four contract tests fail. The
   RIS adapter must not drop that data or weaken validation.
3. **Generated Terraform contract (Mays builder/release).** Seven variables are
   undeclared (`privacy_secret_enabled`, `privacy_kms_key_arn`, the four
   `sqs_*` controls, and `deployment_version`); `module.privacy_secret` is
   referenced but absent. Manifest source SHA is only `5bc154e`. Original
   generated-artifact tests are 2 passed / 7 failed; backend-free validate fails.
4. **Ubuntu test-path prerequisites (QA environment).** Mays originals use the
   fixed `/tmp/opencode` fixture directory and `/home/dci-student/projects/...`
   checkout path. Run `45964402191` verified current originals were blocked by
   these missing paths (builder 4 errors; installer 11 errors); candidate
   builder had 4 such errors. The final QA workflow creates isolated ephemeral
   aliases to the exact clones and does not edit Mays source or tests. Latest
   run confirms current builder/installer 100/81 pass and candidate builder/
   installer 129/81 pass.
5. **QA workflow provenance contamination (RIS CI, corrected).** The first
   workflow rebuilt `lambda/dist/lambda.zip` inside the exact-source checkout,
   making it dirty before unified provenance checks. Commit `2938021` now builds
   generated artifacts in a separate temporary clone and leaves the source
   checkout pristine. This is a test-harness issue, not a candidate pass/fail.
6. **ZIP platform metadata (RIS build tooling, corrected).** ZIP `create_system`
   defaulted to DOS on Windows and Unix on Ubuntu. The builder now sets it to 0
   explicitly in addition to LF normalization and stored entries.
7. **RIS native CI alias (RIS QA workflow, corrected).** Full Ubuntu profiles
   expect `installer/projects/mays_orders`; its absence caused three
   orchestrator-test failures. Commit `4cd7042` provisions the exact alias to
   the pinned clean current source, with guarded cleanup.

No adapter was implemented: missing candidate consumer/transport modules prevent
a versioned, security-preserving adapter, and candidate validation refuses the
order data RIS must preserve. HMAC verification, idempotency, context binding,
and tenant/owner checks remain fail-closed.

## Bundle provenance and review candidate

Historical ZIP comparison established 115 ordered entries, fixed timestamps,
permissions, and source content, and
no generated tests/caches. All uncompressed entry contents match source after
CRLF→LF normalization; differences were mixed working-tree line endings. The
additional Ubuntu artifact comparison proved both DEFLATE byte-stream and ZIP
creator-marker differences. For the small Python-only RIS bundles, the builder
uses stored entries and explicitly fixes `create_system=0`. Two independent
clean builds on Windows and Ubuntu agree on:

| Artifact | Review-only SHA-256 |
|---|---|
| Agent worker | `507bc17db9f2ee0932e42de039a508ab3f01e3bb2b5510ea79f2e54f95b3a58d` |
| Analysis | `370890d459488304481d99255cfa6a2891b5f19a8c5df2723556905195c7c621` |
| Orders reader | `bea4c3e59666bed8ad071ad4e405bcdfd57dafdac68096ce648667f0effb1b41` |

The historical worker digest remains in tests/evidence. These hashes do not
update Terraform/module deployment pins. Scope remains agent worker and dispatch
ingress; no runtime semantics changed.

## Ubuntu run record

- `45963168789` at `e0a65f6`: rejected before job creation (workflow context
  parser issue; 0 jobs).
- `45963374322` at `404714c`: runner started, dependency setup failed because
  full `requirements.txt` includes unavailable `types-all>=2024.1.0`.
- `45963538873` at `fb1715b`: executed valid Ubuntu test job; artifact available
  at `ris-mays-compatibility-qa-fb1715b61b1b23ef987a1ed45ec008c413c7a822`.
  Bundle double-build reproducibility passed. Candidate Lambda 440 and installer
  81 passed; candidate builder 125/4; RC4 contract 120/13 and E2E 3/36; RC4
  generated Terraform validate failed. Current module profiles were blocked by
  dirty-source contamination noted above.
- `45964402191` at `29380218d7a9e807e5f4a11dc7491c3654a21c9b`: corrected workflow
  with isolated build clones. It exposed missing fixed-path prerequisites,
  corrected by later workflow aliases.
- `45965830933` at `f61b295f692b85905f6513f67adee4d1fc2d633d`: all three bundle
  hashes match across platforms; current original Mays suites, current XRepo,
  and current generated module checks pass; candidate original Mays suites pass.
  RC4 Terraform/XRepo fail as expected. Three RIS-native assertions failed
  because `installer/projects/mays_orders` was absent; fixed in `4cd7042`.
- `45966656833` at `4cd7042ff30b8c29f6c8e4d32f235776f6b349bb`: final QA-only run
  with the exact RIS-native checkout alias. Current `FULL` passes: RIS Native
  3,291 passed / 133 skipped / 450 subtests; current Mays originals pass
  (240/100 + 6 subtests/81/28/2), current XRepo 133 + 4 and 39, builder contract
  57, generated module contract 9/9. RC4 original suites all pass; RC4 XRepo
  120/13 and 3/36 plus generated contract 2/7 and Terraform validation fail.
  These RC4 failures reproduce the source blockers in this report.

## Commit order / safety

| Commit | Change |
|---|---|
| `06f9181` | Document implemented APIProfile binding in canonical OpenAPI |
| `d588b5d` | Normalize worker source line endings |
| `587413b` | Record review-only bundle hashes, preserve historical SHA |
| `e0a65f6` | Add read-only Ubuntu compatibility QA workflow |
| `404714c` | Correct invalid Actions runner context |
| `fb1715b` | Install only QA dependencies |
| `2938021` | Stabilize ZIP bytes across platforms; isolate Mays build artifact |
| `f110f97` | Canonicalize ZIP creator metadata |
| `86783b8`, `1c84c27`, `dd80125`, `f61b295`, `4cd7042` | Correct QA-only runner prerequisites; no runtime changes |
| final 19F4 evidence commit | Report, JSON, contract index, audit entry (record hash/HEAD below) |

Final remote HEAD and worktree status are captured in the final evidence
checkpoint. Safety counters: AWS mutations
0; live invocations 0; redrives 0; module pin changes 0; module installations
0; Terraform plans/applies/state mutations 0. `LIVE` remained locked and
`MODE=true` was not changed.

**Stop point:** 19F4 only. No Terraform plan/apply, module install, deployment,
canary, or main merge follows this report.
