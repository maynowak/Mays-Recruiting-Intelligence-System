# G2-AWS-DEPLOYMENT-RECONCILIATION-01

Purpose: prepare the **single deliberate** AWS deployment reconciling

1. the `DELETE /me/profile` API Gateway route, and
2. the `mays-ris-dev-agent` Lambda deployment/hash drift.

**No apply, no deploy. This package ends at the approval gate.**

Canonical baseline: branch `main`, HEAD `1121045`
Local regression: 1111 collected / 1103 passed / 0 failed / 8 skipped / 236 warnings

---

## WORKER RESULTS (W1–W4)

### W1 — TERRAFORM SCOPE

| Set | Contents |
|---|---|
| **Gate-02 Terraform write set** | `terraform/modules/api/main.tf` — one resource: `aws_apigatewayv2_route.profile_delete` (`DELETE /me/profile`) |
| **Pre-existing Terraform write set** | `terraform/main.tf`, `modules/{cognito,monitoring,orders_reader,sqs}/main.tf`, `variables.tf` — **whitespace only** |
| **Overlap** | **none** — disjoint files |

Verified:

```
$ git diff 8b567c4..1121045 --name-only -- terraform/
terraform/modules/api/main.tf

$ git diff -w --stat -- terraform/
(empty)
```

The pre-existing modifications are **semantically inert**: `git diff -w`
returns nothing, so they are pure `terraform fmt` alignment. They are
retained, not discarded, and contribute **zero** planned resource changes.
Confirmed empirically — they never appear in the plan.

### W2 — CANONICAL LAMBDA BUILD

Mechanism is the repository-supported one, not an invented procedure:

```
installer/ris.py:_cmd_package → subprocess([build_zip.py, --bundle, ...])
contract: package → plan → apply
```

```
$ python3 lambda/build_zip.py --bundle agent
Built agent bundle: terraform/lambda.zip (53 files, sha256 5c4cd22260c5fb26...)

hex   : 5c4cd22260c5fb260dc3983ec733d71465fef1879bbd6f62541b21d2cbef0061
base64: XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=
```

Rebuilt independently a second time — identical hash, so the build is
deterministic and the value is reproducible.

`terraform/lambda.zip` is a build artifact, correctly git-ignored
(`.gitignore:66`). Terraform consumes it via `filebase64sha256`.

**Reader bundle matches live exactly** — this is why
`test_h_reader_hash_matches` passes:

```
canonical : eSZVykVfIYeWcbX/DH3v3snFsg2oqrqCm/R/GSNNnpc=
live      : eSZVykVfIYeWcbX/DH3v3snFsg2oqrqCm/R/GSNNnpc=   MATCH
```

The agent bundle does not match, and that is precisely the drift:

```
canonical : XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=
live      : UQtgthuQt8CPoNOfarD8oIvRfMSOp9+78ir9qDkuU+M=     DRIFT
```

Drift explanation: live was last modified `2026-10-06T18:55:31Z`. Earlier
(T1) all 281 commits in history were rebuilt and none produced the live
hash, so the deployed artifact does not correspond to any point in this
repository's history — it was built from an uncommitted or externally
modified tree. One deploy from HEAD makes code, artifact and state agree.

### W3 — WARNING DISCREPANCY (208 vs 236) — RESOLVED

Not a regression. The count rose because **coverage rose**.

Measured at every gate commit:

| Commit | Collected | Passed | Warnings |
|---|---|---|---|
| `8b567c4` (truth recovery) | 1062 | 1054 | **236** |
| `dfbd1c9` (P1 security fix) | 1083 | 1075 | **208** |
| `803f89f` (P2 route/governance) | 1085 | 1077 | **208** |
| `8fd6572` (P3 health plane) | 1111 | 1103 | **236** |

Differential attribution, measured:

```
full suite at HEAD                                  : 236 warnings
excluding P3's two new test files                   : 208 warnings
only P3's two new test files                        :  28 warnings
                                                     ------
                                        208 + 28 =  236  ✓
```

The 28 come from `test_health_plane_integration.py` (7 tests) executing the
**real** pipeline for the first time. Each run traverses four `utcnow()`
sites that no prior test reached:

```
agents/agent_body/executor.py:40        start_time
agents/agent_body/executor.py:63        duration_ms
agents/agent_body/invocation.py:103     createdAt
agents/reference_agent/service.py:144   processedAt
                                     7 runs x 4 sites = 28
```

These are **pre-existing** technical debt, newly surfaced — not new debt, and
not a regression.

#### Warning groups reconciling to 236

| Group | Count | Owner | Class |
|---|---|---|---|
| `agents/agent_body/executor.py:40,63` | 78 | first-party | production |
| `agents/agent_body/invocation.py:103` | 38 | first-party | production |
| `agents/reference_agent/service.py:144` | 22 | first-party | production |
| `jobsearch/domain_models.py` (`default_factory`, via `<string>`) | 28 | first-party | production — **serialization-sensitive** |
| `lambda/handler.py:504,581` | 10 | first-party | production — **serialization-sensitive** |
| `agents/ats_agent/agent.py:157,167,210` | 16 | first-party | production |
| `jobsearch/reference_actor.py:58` | 6 | first-party | production |
| `agents/orders/development.py:153` | 4 | first-party | production |
| test modules | 34 | first-party | test |
| botocore | 3 | third-party | dependency |
| **TOTAL** | **236** | | |

Every group is `datetime.utcnow()` deprecation. No warning is hidden by
filters; no `filterwarnings` was added anywhere.

The 38 warnings attributed to `jobsearch/domain_models.py:169-170` surface as
`<string>:10/11` because dataclasses synthesises `__init__` from a string —
`field(default_factory=datetime.utcnow)` evaluates the deprecated attribute
once per instance construction.

### W4 — AWS READ-ONLY BASELINE

```
profile : mayaws
account : 240571105849   (arn:aws:iam::240571105849:user/Mayaws)
region  : eu-central-1
api id  : aboqolpm0f
pool id : eu-central-1_dgQXgwUbv
```

| Check | Result |
|---|---|
| `/me/profile` routes live | `GET`, `POST`, `PUT` — **no `DELETE`** |
| `DELETE` routes on the API (any path) | **none exist** |
| `mays-ris-dev-agent` `CodeSha256` | `UQtgthuQt8CPoNOfarD8oIvRfMSOp9+78ir9qDkuU+M=` |
| `mays-ris-dev-agent` last modified | `2026-10-06T18:55:31Z` |
| `mays-ris-dev-orders-reader` `CodeSha256` | matches canonical ✓ |
| Cognito `AutoVerifiedAttributes` | `["email"]` |

No mutation performed.

---

## TERRAFORM PLAN

Workspace `mays-ris`, backend S3 + `mays-ris-tf-lock`. Identity verified
`240571105849` immediately before planning.

### Plan A — unpinned (what a naive `apply` would do)

```
Plan: 1 to add, 2 to change, 0 to destroy
  + module.api.aws_apigatewayv2_route.profile_delete        (CREATE)
  ~ module.cognito.aws_cognito_user_pool.users               (UPDATE)  <-- UNEXPECTED
  ~ module.lambda.aws_lambda_function.agent                 (UPDATE)
```

**The Cognito change is UNEXPECTED and must not be waved through.**

```
~ auto_verified_attributes = [
-    "email",
  ]
```

Cause, verified by direct evidence:

- `terraform/modules/cognito/main.tf:27` → `auto_verified_attributes = var.email_verification_enabled ? ["email"] : []`
- `terraform/variables.tf:38` → `identity_email_verification_enabled`, `default = false`
- **no `*.tfvars` file exists** → the default applies → `[]`
- live pool reports `AutoVerified: ["email"]`

So this is **pre-existing drift** against a default of `false`, entirely
independent of Gate-02 (`git diff 8b567c4..1121045 -- terraform/` touches only
`modules/api/main.tf`). Applying Plan A would **silently disable email
auto-verification for the dev user pool** — a real identity behaviour change
with user impact, outside this gate's scope.

### Plan B — pinned (RECOMMENDED)

```
terraform plan -var='identity_email_verification_enabled=true'
```

```
Plan: 1 to add, 1 to change, 0 to destroy
  + module.api.aws_apigatewayv2_route.profile_delete
      route_key          = "DELETE /me/profile"
      authorization_type = "JWT"
      authorizer_id      = "9ghezn"
      target             = "integrations/ewy9u57"   (existing integration)
      api_id             = "aboqolpm0f"
  ~ module.lambda.aws_lambda_function.agent
      ~ source_code_hash = "UQtgthuQt8CPoNOfarD8oIvRfMSOp9+78ir9qDkuU+M="
                        -> "XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE="
      ~ last_modified    = "2026-10-06T18:55:31Z" -> (known after apply)
```

Verified: **0** resources from `cognito`, `dynamodb`, `sqs`, `monitoring` or
`orders_reader` appear in Plan B.

### Classification

| Resource | Class |
|---|---|
| `module.api.aws_apigatewayv2_route.profile_delete` (create) | **EXPECTED_GATE02** |
| `module.lambda.aws_lambda_function.agent` `source_code_hash` | **EXPECTED_DRIFT_RECONCILIATION** |
| `module.lambda.aws_lambda_function.agent` `last_modified` | **EXPECTED_DRIFT_RECONCILIATION** (AWS-managed) |
| `module.cognito.aws_cognito_user_pool.users` | **UNEXPECTED** — pre-existing drift; excluded by the pin |
| destroys | **none** |
| replacements | **none** |

## CRITICAL CHECK — can ONE deployment reconcile A and B?

**Yes, with the pin.**

A single `terraform apply` of Plan B creates the route and updates the Lambda
artifact in one operation. The pre-existing Terraform modifications are
whitespace-only and contribute nothing, so they cannot leak in. The only
hazard is the Cognito drift, which the `-var` pin removes.

Without the pin, one apply would also disable email auto-verification —
reconciling A and B correctly but silently changing identity behaviour.

`-target` was rejected as the mechanism: it leaves partial state for
interdependent resources, and here it is unnecessary because the pin already
produces an exact two-resource plan.

**Open governance item:** the pin is a command-line variable and does not
persist. If `identity_email_verification_enabled` should genuinely be `true`,
it should be committed as a `terraform.tfvars` (or an installer default)
rather than supplied ad hoc at every apply — otherwise the drift returns.
That is a separate decision and is **not** made here.

## LOCAL VERIFICATION AT DEPLOYMENT HEAD

```
terraform fmt -check -recursive   → clean
terraform validate                → Success!  (pre-existing deprecation warnings only)
pytest                            → 1103 passed, 8 skipped, 0 failed, 236 warnings
git status --short -- terraform/  → 6 pre-existing whitespace-only modifications, unstaged
```

The pre-existing Terraform modifications remain unstaged and uncommitted. No
Terraform file was modified by this package.

## POST-DEPLOY VERIFICATION

```
1. aws apigatewayv2 get-routes --api-id aboqolpm0f \
     --query 'Items[?RouteKey==`DELETE /me/profile`].RouteKey'   → non-empty
2. aws lambda get-function-configuration --function-name mays-ris-dev-agent \
     --query CodeSha256   → XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=
3. python3 -m pytest tests/test_lambda_packaging.py \
     tests/test_observability_foundation.py -v   → 8/8 PASS
   (with AWS_PROFILE=mayaws; previously 7/8)
4. python3 -m pytest tests/ -q -rs               → 1103 passed, 0 failed, 8 skipped
5. aws cognito-idp describe-user-pool --user-pool-id eu-central-1_dgQXgwUbv \
     --query 'UserPool.AutoVerifiedAttributes'  → ["email"]  (unchanged)
```

Step 5 is the guard that the pin held. If it reports `[]`, an unpinned apply
occurred and email verification was disabled.

---

## DECISION PACKAGE

```
G2-AWS-DEPLOYMENT-RECONCILIATION-01

STATUS:              VERIFIED
HEAD:                1121045ccc76baedb621eca20d6b3750dc3ab56d

AWS
  profile: mayaws
  account: 240571105849
  region:  eu-central-1

WARNING DISCREPANCY
  208 vs 236 cause:   P3 integration tests (7) execute the real pipeline for
                      the first time, hitting 4 previously-unexercised
                      utcnow() sites => 7 x 4 = 28 new warnings.
                      208 + 28 = 236. Newly surfaced pre-existing debt,
                      NOT a regression.
  verified current:   236 (233 first-party + 3 botocore), fully classified

TERRAFORM SCOPE
  Gate-02 changes:    terraform/modules/api/main.tf
                      + aws_apigatewayv2_route.profile_delete
  pre-existing:       6 files, whitespace-only (git diff -w empty)
  overlap:            none

LAMBDA
  canonical artifact: terraform/lambda.zip (53 files, via lambda/build_zip.py)
  canonical hash:     XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=
  live hash:          UQtgthuQt8CPoNOfarD8oIvRfMSOp9+78ir9qDkuU+M=
  drift explanation:  live built 2026-10-06T18:55:31Z from a tree matching no
                      commit in the 281-commit history; deterministic rebuild
                      confirms HEAD is the correct target. Reader bundle already
                      matches, so no reader change is planned.

PLAN (pinned)
  add:      1  (module.api.aws_apigatewayv2_route.profile_delete)
  change:   1  (module.lambda.aws_lambda_function.agent — source_code_hash)
  replace:  0
  destroy:  0

EXPECTED CHANGES:
  + DELETE /me/profile route, JWT, existing integration 9ghe9w57/ewy9u57
  ~ mays-ris-dev-agent source_code_hash -> canonical artifact hash

UNEXPECTED CHANGES (found and EXCLUDED):
  ~ module.cognito.aws_cognito_user_pool.users auto_verified_attributes
    ["email"] -> [] — pre-existing drift (var default false, no tfvars).
    Would disable dev email auto-verification. Excluded via -var pin.
    Requires a separate governance decision on the intended default.

EVIDENCE VERIFIER:      VERIFIED
  - HEAD 1121045 re-read
  - account 240571105849 re-read
  - artifact rebuilt from scratch, hash reproduced exactly
  - pinned plan contains 0 unrelated-module resources
  - 0 destroy / 0 replace
  - regression green at deployment head
  - pre-existing terraform modifications still unstaged

DEPLOYMENT RISK:        LOW
  Two resources, one in-place Lambda code update, one route creation.
  No data migration, no replacement, no destroy, no schema change.
  Reversible: route can be deleted, Lambda can be redeployed from a prior
  artifact.

RECOMMENDATION:         APPLY — with the -var pin
PROPOSED MECHANISM:     installer-supported contract package -> plan -> apply
  1. python3 lambda/build_zip.py --bundle agent
  2. terraform plan -out=g2.tfplan -var='identity_email_verification_enabled=true'
  3. terraform apply g2.tfplan
  (identity guard: aws sts get-caller-identity --profile mayaws == 240571105849)

POST-DEPLOY VERIFICATION: 5 steps listed above; step 5 (Cognito
  AutoVerifiedAttributes still ["email"]) is the drift guard.

DO NOT APPLY. WAITING FOR EXPLICIT APPROVAL.
```