# G2-AWS-DEPLOY-VERIFY-01

Execution + verification of the deployment approved in
`G2-AWS-DEPLOYMENT-RECONCILIATION-01`.

**Result: GREEN.** The Gate-02 AWS branch is closed.

Canonical input: branch `main`, HEAD `eb4a7ba`
Deployment: account `240571105849`, profile `mayaws`, region `eu-central-1`

---

## STEP 0 — PRE-FLIGHT

| Check | Expected | Actual | |
|---|---|---|---|
| HEAD | `eb4a7ba` | `eb4a7bae951bd8f15dcb402890853cb8656e4606` | ✓ |
| account | `240571105849` | `240571105849` | ✓ |
| region | `eu-central-1` | `eu-central-1` | ✓ |
| worktree | pre-existing tf changes unstaged | 6 whitespace-only files unstaged | ✓ |
| canonical artifact | `XEzSImDF…AGE=` | rebuilt from scratch → identical | ✓ |

Artifact rebuilt from scratch (`rm terraform/lambda.zip` then
`python3 lambda/build_zip.py --bundle agent`), 53 files,
base64 `XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=` — matches the
approved value. Determinism confirmed a second time.

## STEP 1 — FRESH PLAN (old plan file discarded)

```
rm -f /tmp/opencode/g2.tfplan
terraform plan -out=/tmp/opencode/g2.tfplan -var='identity_email_verification_enabled=true'
```

```
Plan: 1 to add, 1 to change, 0 to destroy.
  # module.api.aws_apigatewayv2_route.profile_delete will be created
  # module.lambda.aws_lambda_function.agent will be updated in-place
```

Invariant check — no forbidden resource present:

```
grep -E "cognito|dynamodb|sqs|monitoring|orders_reader|iam|
          apigatewayv2_api|apigatewayv2_integration|apigatewayv2_authorizer"
→ empty    PASS
```

Matched the approved invariant exactly. Proceeded.

## STEP 2 — APPLY

Final identity guard immediately before mutation:
`account=240571105849` → GUARD PASS.

```
terraform apply /tmp/opencode/g2.tfplan
```

| Planned | Result |
|---|---|
| `+ module.api.aws_apigatewayv2_route.profile_delete` | created |
| `~ module.lambda.aws_lambda_function.agent` | updated in-place |
| 0 replace / 0 destroy | as planned |

## STEP 3 — PARALLEL VERIFICATION

### W1 — API ROUTE

```
DELETE /me/profile   Auth: JWT   AuthorizerId: 9ghezn   Target: integrations/ewy9u57
```

`/me/profile` now exposes all four verbs (`GET`, `POST`, `PUT`, `DELETE`).
Authorizer and integration match the intended configuration — the **existing**
JWT authorizer and the **existing** Lambda integration, no new ones created.
`DELETE /me/profile` is the first `DELETE` route on this API.

### W2 — LAMBDA ARTIFACT

```
live CodeSha256 : XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=
expected        : XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=
LastModified    : 2026-10-07T16:51:07Z   (was 2026-10-06T18:55:31Z)
CodeSize        : 136168
DRIFT: CLOSED
```

### W3 — COGNITO DRIFT GUARD

```
AutoVerifiedAttributes = ["email"]     GUARD PASS
```

Email auto-verification preserved. The `-var` pin held — no
`["email"] → []` change was applied.

### W4 — AWS LIVE TESTS

**First run: 12 passed, 1 FAILED.** `test_e_noop_live_hash_matches` still
failed even though W2 proved the live hash equals the canonical artifact.
That contradiction was investigated rather than accepted.

#### Root cause: a test defect, not a deployment defect

```
canonical (AGENT_FILES + AGENT_DIRS)  : 5c4cd222...   53 files
live-test  (hardcoded list)           : 503bc209...   52 files
```

`test_e_noop_live_hash_matches` rebuilt its own bundle from a hardcoded list:

```python
["lambda/handler.py", "agents", "jobsearch"]     # omits lambda/documents.py
```

`build_zip.AGENT_FILES` is `["lambda/handler.py", "lambda/documents.py"]`,
so the deployed artifact contains 53 files and the test rebuilt 52. The test
was comparing **two different artifacts** and could never match. The failure
had been misread — in Gate-01 and again in the reconciliation package — as
deployment drift.

The reader test was always correct: it calls `build_reader_bundle()`, the
canonical builder. The agent test bypassed the canonical builder with a
hardcoded list, and that asymmetry is exactly what hid the defect.

#### Fix

The test now builds via `build_zip.AGENT_FILES + build_zip.AGENT_DIRS` with
the same arcname rule as `build_agent_bundle`, so it verifies what is actually
deployed. No assertion was weakened — the comparison against live is still
exact and still fails on any real difference.

#### Negative control

A passing hash test is worthless if it cannot fail. Verified:

```
inject '\n# drift-probe\n' into agents/base.py
  → 1 failed, 1 passed        (drift detected)
restore agents/base.py
  → 2 passed                 (correct state passes)
```

#### Result after fix

```
8 / 8 AWS live tests PASS   (6 observability + 2 packaging)
13 passed, 14 warnings in 8.95s
```

### Full local regression

```
1111 collected / 1103 passed / 0 failed / 8 skipped / 236 warnings
```

## STEP 4 — EVIDENCE VERIFIER: VERIFIED

Independent re-read of every claim, not inference from `apply` output:

| Claim | Verified value |
|---|---|
| account | `240571105849` |
| region | `eu-central-1` |
| `DELETE /me/profile` route | present, JWT, `integrations/ewy9u57` |
| Lambda `CodeSha256` | `XEzSImDF+yYNw5g+xzPXFGX+8YebvW9iVBsh0svvAGE=` |
| Cognito `AutoVerifiedAttributes` | `email` |
| AWS live tests | 8/8 PASS |
| Full regression | 1103 passed, 0 failed |
| Terraform apply | 1 added, 1 changed, 0 destroyed |

## FILES CHANGED

- `tests/test_lambda_packaging.py` — live hash test uses the canonical
  builder instead of a hardcoded file list

No production code, no Terraform, no infrastructure definition changed by
this package.

## COMMITS

| SHA | Content |
|---|---|
| `a3e2e8f` | docs: record G2 deployment execution + verification evidence |

## GIT

```
branch:   main
HEAD:     a3e2e8f
worktree: 6 pre-existing whitespace-only Terraform modifications, unstaged
          and uncommitted; NOT included in this commit
```

## GATE-02 AWS BRANCH: GREEN

All six conditions met:

- [x] API DELETE route LIVE
- [x] Lambda hash canonical
- [x] Cognito email verification preserved
- [x] 8/8 AWS tests PASS
- [x] full regression 0 failures
- [x] Evidence Verifier VERIFIED

### Three defects closed across the AWS branch

1. **Deployment drift** — live artifact matched no commit in 281 rebuilds.
   Closed by deploying the canonical build.
2. **Unreachable endpoint** — `DELETE /me/profile` shipped with no gateway
   route. Closed by the Terraform route.
3. **Vacuous hash test** — the packaging live test compared two different
   artifacts, so it could never pass and its failure was misdiagnosed twice.
   Closed by using the canonical builder; negative control confirms it still
   detects real drift.

### Residual observation (not a defect)

The live API reports 36 routes; Terraform declares 33. The difference is the
three OPEN-3 `documents` routes, which exist live but in no `.tf` file and are
therefore not managed by `terraform apply`. Pre-existing, documented, and
untouched by this deployment.

## NEXT GOVERNANCE PACKAGES

| Package | Status | Note |
|---|---|---|
| Cognito persistent configuration | OPEN | `identity_email_verification_enabled` is still a CLI var. The live value is `true`; the committed default is `false`. Next apply without the pin will disable email verification again. Needs a committed tfvars or installer default. |
| Platform OpenAPI | OPEN (OPEN-1) | `jobsearch/openapi.yaml` covers an external service only. |
| Privacy cascade / erasure | OPEN | `DELETE /me/profile` is profile deletion only. |
| Timestamp serialization contract | OPEN | gates 43 `utcnow()` sites. |
| Health event sink / consumer | OPEN | events are emitted and returned, not transported. |