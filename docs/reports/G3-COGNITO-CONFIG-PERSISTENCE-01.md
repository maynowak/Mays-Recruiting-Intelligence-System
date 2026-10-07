# G3-COGNITO-CONFIG-PERSISTENCE-01

Mission: eliminate the temporary `-var='identity_email_verification_enabled=true'`
deployment pin so an ordinary supported deployment no longer plans
`AutoVerifiedAttributes ["email"] → []`.

Base: `8e406e0` · **Status: GREEN** · **AWS mutation: NONE**

---

## W1 — CONFIGURATION SOURCE OF TRUTH

Full trace of `identity_email_verification_enabled`:

```
terraform/variables.tf:38          variable, bool, default false   ← the defect
        │
        └── terraform/main.tf:48   email_verification_enabled = var.identity_email_verification_enabled
                    │
                    └── terraform/modules/cognito/main.tf:27
                                auto_verified_attributes = var.email_verification_enabled ? ["email"] : []
```

**The RIS installer has no tfvars mechanism.** Verified by search: the only
`.tfvars` handling in the repository is inside `installer/projects/mays_orders/`,
which is the *separate* Mays-Orders project, not Mays-RIS.

The RIS installer's sole variable channel is CLI:

```
installer/ris.py:393   --var KEY=VALUE
        → parse_var_args()  (line 420)
        → RisInstallContext.extra_vars
        → terraform_vars()   (line 94)  — identity wins fail-closed
        → terraform plan -var k=v
```

Verified directly:

```
RisInstallContext(project_name='mays-ris', environment='dev').terraform_vars()
  → {'environment': 'dev', 'project_name': 'mays-ris'}
```

So there is **no committed environment configuration file** that could carry
this value, and the only durable, machine-readable configuration in this
repository is the Terraform variable default itself.

### Decision: options considered

| Option | Verdict |
|---|---|
| Create `terraform.tfvars` | **Rejected** — the mission explicitly warns against creating one merely because none exists. It would also be an untracked, environment-specific artifact with no installation contract behind it. |
| Pass a default via the installer | **Rejected** — fixes only the installer path. Direct `terraform plan` (used by every gate in this repo's history) would still propose the change. Two sources of truth. |
| Change the root variable default | **Selected** — the default *is* the repository's persistent configuration layer. It governs both the installer path and direct Terraform use, so one change converges both. |

### Prior-art evidence that this was known and never fixed

The pin appears in at least eight prior gate reports, each recording it as a
harmless "variable default artifact":

- `docs/reports/RIS-GATEWAY-ACTIVATION-P16-P13-01.md:37,39,136`
- `docs/reports/RIS-APIPROFILE-TESTDATA-REVOKE-05.md:244` — *"Das ist keine Drift und nicht von mir verursacht"*
- `docs/reports/RIS-GATEWAY-ROUTE-ACTIVATION-17C.md:35`
- `docs/reports/RIS-B3-B4-COGNITO-AND-AGENT-ENTRYPOINT-DISCOVERY-07-EXECUTION_LOG.md:75`
- `docs/reports/RIS-P17-CREDENTIAL-LIFECYCLE-E2P-06-EXECUTION_LOG.md:55,62`
- `docs/reports/RIS-P20-API-CONTRACT-AND-HEALTH-01-EXECUTION_LOG.md:41`
- `docs/reports/RIS-P17-CREDENTIAL-LIFECYCLE-E2P-01-EXECUTION_LOG.md:38`
- `docs/reports/RIS-LEGACY-GATEWAY-SQS-DRIFT-ANALYSIS-17A-EXECUTION_LOG.md:47`

`RIS-GATEWAY-ACTIVATION-P16-P13-01.md:136` states it outright: *"jeder Plan ohne
explizites `-var=true` schlägt eine unbeabsichtigte Cognito-Änderung vor … Korrektur
nicht in diesem Gate."* Every gate deferred it. This one fixes it.

## W2 — INSTALLER / DEPLOYMENT CONTRACT

The invariant required: *a fresh supported dev installation and a later
ordinary apply must agree on Cognito email verification.*

With the root default corrected, both paths resolve from the same source:

| Path | How the flag is resolved | Result |
|---|---|---|
| `installer.ris install` | no `--var` → Terraform substitutes root default | `true` |
| `installer.ris plan/apply` | same | `true` |
| direct `terraform plan/apply` | same | `true` |
| explicit `-var=...=false` | CLI override still honoured | `false` (rollback possible) |

Verified by executing the installer's own code path, not by reading it.

No behavioural flag is added to the installer, so no architecture is
duplicated and identity override protection is untouched (existing
fail-closed test still passes).

## W3 — TERRAFORM / LIVE EVIDENCE

```
live AutoVerifiedAttributes : ["email"]
tf state auto_verified_attributes : ["email"]
repository default         : false        ← divergent
```

## BEFORE

```
repository value : default = false
live value       : ["email"]
unpinned plan    : Plan: 0 to add, 1 to change, 0 to destroy
                   # module.cognito.aws_cognito_user_pool.users will be updated in-place
                       ~ auto_verified_attributes = [ - "email" ]
```

Negative control reproduced before any change.

## IMPLEMENTATION

One behavioural line, plus explanatory comments.

`terraform/variables.tf`:

```hcl
variable "identity_email_verification_enabled" {
  description = "E-Mail-Verifikation bei Registrierung (Cognito-managed Versand)."
  type        = bool
  default     = true          # was: false — pre-Gate-11 state
}
```

`terraform/modules/cognito/main.tf` — comment only, no logic change:

```hcl
auto_verified_attributes = var.email_verification_enabled ? ["email"] : []
```

`default = false` was the *pre-Gate-11* behaviour. The delivered dev pool was
deliberately provisioned with verification ON. Aligning the default with the
delivered state is what makes repository configuration converge to the
already-correct live value — no apply required, and nothing is mutated.

## INSTALLER

**No change required, and none made.** Verified: a fresh `dev` install supplies
only `{project_name, environment}` and relies on the corrected root default.
Adding a behavioural flag to the installer would have created a second source
of truth and left direct `terraform plan` still wrong.

## AFTER

```
resolved value          : true
unpinned plan           : No changes. Your infrastructure matches the configuration.
Cognito planned changes : NONE
pinned plan (back-compat): No changes.   ← existing scripts keep working
live Cognito            : ["email"]  (unchanged, no apply performed)
```

## TARGETED TESTS

`tests/test_cognito_email_verification_config.py` — **9 tests, all passing**:

| Test | Pins |
|---|---|
| `test_email_verification_default_is_enabled` | root default is `true` |
| `test_default_is_not_reintroduced_as_false` | explicit guard against regression to `false` |
| `test_no_tfvars_file_is_required` | fix must not depend on an untracked tfvars |
| `test_root_passes_variable_to_cognito_module` | forwarding exists |
| `test_cognito_derives_auto_verified_attributes_from_the_flag` | derivation is flag-driven |
| `test_cognito_receives_enabled_flag_from_root` | end-to-end resolution without evaluating Terraform |
| `test_fresh_dev_install_relies_on_the_configured_default` | installer supplies identity only |
| `test_identity_cannot_be_overridden_by_var` | existing fail-closed guarantee survives |
| `test_explicit_var_still_overrides_for_rollback` | change remains reversible |

### Negative control

Reverting the default to `false` and re-running:

```
3 failed, 6 passed
```

The tests detect the defect rather than merely describing the fixed state.

## FULL REGRESSION

```
collected 1120   passed 1112   failed 0   skipped 8   warnings 236
```

Baseline moved 1111 → 1120 collected (+9, all new). No test weakened or
disabled. Skips remain the 8 AWS-gated ones.

## AWS MUTATION

**NONE.** No apply was run. The live pool was read-only throughout and remains
`["email"]`. The fix is repository-side only, which is the intended outcome:
configuration converges to the already-correct live state.

## EVIDENCE VERIFIER: VERIFIED

| Claim | Verified |
|---|---|
| account | `240571105849` |
| region | `eu-central-1` |
| live Cognito | `email` |
| root default | `= true` |
| tfvars files | 0 |
| unpinned plan | `No changes.` |
| pinned plan | `No changes.` (back-compat) |
| targeted tests | 9 passed; 3 fail on revert |
| full regression | 1112 passed, 0 failed |
| HEAD at verification | `8e406e0` |

## GIT ISOLATION

Both modified files were already in the pre-existing whitespace-only set
(`terraform/variables.tf`, `terraform/modules/cognito/main.tf`). The semantic
change was isolated and confirmed with `git diff -w`, which shows only the
default flip and two comment lines — no whitespace churn from the earlier
edits is attributed to this package. The remaining pre-existing whitespace
files (`main.tf`, `monitoring`, `orders_reader`, `sqs`) are untouched.

## ACCEPTANCE CRITERIA

| # | Criterion | |
|---|---|---|
| 1 | Live intended behaviour represented in source-controlled config | ✓ |
| 2 | Fresh install receives the same intended configuration | ✓ |
| 3 | Ordinary future apply preserves it | ✓ `No changes.` |
| 4 | No CLI `-var` required | ✓ |
| 5 | No secrets introduced | ✓ behavioural bool only |
| 6 | No unrelated Terraform changes | ✓ `git diff -w` reviewed |
| 7 | No architecture duplication | ✓ installer untouched |
| 8 | Key acceptance: unpinned plan shows no Cognito change | ✓ |

## NEXT PACKAGE RECOMMENDATION

**Platform OpenAPI (OPEN-1).** It is the largest remaining documented gap:
`jobsearch/openapi.yaml` describes an external service and covers none of the
33 platform routes, so no machine-readable contract exists for the API whose
governance this gate just tightened. It also has a natural dependency
resolved by G3 — the route inventory is now stable at 33 Terraform-managed
routes including `DELETE /me/profile`.

Two caveats to carry forward:

- The remaining six OPEN-3 `documents` routes are live but unmanaged by
  Terraform; a complete OpenAPI must represent them explicitly as such
  rather than silently omitting them.
- Two different error envelopes exist (agent string vs orders-reader object,
  OPEN-2). The spec must reflect reality, which means documenting both, not
  pretending they are unified.

Priority order after that: privacy cascade/erasure, timestamp serialization
contract (gates 43 `utcnow()` sites), health event sink.