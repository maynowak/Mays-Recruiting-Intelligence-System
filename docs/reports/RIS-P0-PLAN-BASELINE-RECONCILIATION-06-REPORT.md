# RIS-P0-PLAN-BASELINE-RECONCILIATION-06 — MAYS ORDERS MODULE VALIDATION

**Status: BLOCKED — MAYS ORDERS MODULE FAILURE**

- RIS branch: `feature/ris-p0-plan-baseline-reconciliation-06`
- RIS base: `ddd7660` (Gate-05 integration)
- Mays-Orders AWS canonical checkout: `/home/dci-student/projects/Mays-Orders-AWS`
- Mays-Orders remote HEAD: `8830da2`
- RIS builder pin: `016cdfd6ac62565dcec9a2fee78cb898fb919e59`
- RIS historical clone pin: `5cf50a0a8e4221348c264c59432ff4c8dc580c8b`
- Reviewed live baseline: `1dbb0cb4e6cc019bc5b03f92e5ffb368a7bdb88d`
- No Terraform plan/apply, no AWS mutation, no deployment and no main merge.

## 1. Result

A reproducible failure was found in the **original Mays-Orders module** at
the commit used by the RIS builder pin:

```
Mays-Orders 016cdfd
module_builder.tests.test_module_builder.TestModuleSelectionB1
  .test_full_custom_selection_equivalent_to_complete
FAILED
```

Reproduction from a clean detached worktree:

```bash
git -C /home/dci-student/projects/Mays-Orders-AWS \
  worktree add --detach /tmp/opencode/orders-pin-016cdfd 016cdfd
cd /tmp/opencode/orders-pin-016cdfd
python3 -m unittest \
  module_builder.tests.test_module_builder.TestModuleSelectionB1.test_full_custom_selection_equivalent_to_complete -v
```

Result:

```
AssertionError: Items in the second set but not the first:
'ris_result_producer_role_arns'
'lambda_execution_boundary'
'enable_agent_transport' : Mengen weichen ab: variables.tf
```

The same test passes at `1dbb0cb`. It is therefore a module-version
regression, not an RIS-only failure.

## 2. Module comparison

| Item | `1dbb0cb` | `016cdfd` |
| --- | --- | --- |
| Role | reviewed live baseline | current RIS builder pin |
| Merge base | `9627eb2` | `9627eb2` |
| Divergence | 10 commits unique | 21 commits unique |
| Ancestor relationship | neither is ancestor of the other | neither is ancestor of the other |
| Original Lambda tests | 76 PASS | 225 PASS |
| Original installer tests | 129 PASS | 129 PASS |
| Original module-builder tests | 90 PASS | 91 tests, **1 FAIL** |
| `terraform fmt -check` | **FAIL** (`terraform/main.tf`) | PASS |
| `terraform init -backend=false` / `validate` | PASS | PASS |
| `orders-service` preset build + validate | PASS | PASS |
| RIS transport-output injection + validate | **FAIL** (no `agent_transport` module) | PASS |

`016cdfd` is **not** a superset of `1dbb0cb`. Unique to `1dbb0cb` are the
wildcard-SQS-policy removal `a2fb385` and the IAM portability fixes
`f3e78d0`, `a46b189`, `ccf22a3`. Unique to `016cdfd` is the agent result
transport and order-result consumer work. A straight pin increase therefore
mixes two independent lines.

### Current RIS module state

`terraform/modules/mays_orders/` contains only `variables.tf`; the generated
module tree is incomplete. Root `terraform validate` therefore fails at
`module.mays_orders[0].iam_handler_role_name`.

## 3. Original Mays-Orders tests

Commands were run in isolated `/tmp` worktrees; the original checkout was not
modified.

### `1dbb0cb`

| Suite | Result |
| --- | --- |
| Lambda compile + unit tests | **76 PASS** |
| Installer tests | **129 PASS** |
| Module-builder tests | **90 PASS** |
| Terraform fmt | **FAIL** (`main.tf`) |
| Terraform init/validate | PASS |
| Generated `orders-service` build + validate | PASS |

### `016cdfd`

| Suite | Result |
| --- | --- |
| Lambda compile + unit tests | **225 PASS** |
| Installer tests | **129 PASS** |
| Module-builder tests | **91 tests / 1 FAIL** |
| Terraform fmt | PASS |
| Terraform init/validate | PASS |
| Generated `orders-service` build + validate | PASS |

### Current Mays-Orders main `8830da2`

Additional check of the current original repository HEAD:

| Suite | Result |
| --- | --- |
| Lambda unit tests | **456 PASS** |
| Module-builder tests | **129 PASS** |
| Generated `orders-service` build + validate | **FAIL** |

The `orders-service` preset at main fails Terraform validation with:

```
outputs.tf:129: value = var.deployment_version  (undeclared)
main.tf:108:   var.sqs_max_receive_count        (undeclared)
```

This is a second original-module failure. The module-builder unit tests pass,
but the actual generated `orders-service` preset does not validate.

## 4. Error classification

| ID | Category | Finding |
| --- | --- | --- |
| A1 | **A — original module** | `016cdfd` module-builder test `test_full_custom_selection_equivalent_to_complete` fails; custom selection and complete preset diverge. |
| A2 | **A — original module** | Current main `8830da2` generates an `orders-service` module that fails Terraform validation (`deployment_version`, `sqs_max_receive_count` undeclared). |
| B1 | **B — RIS integration** | `installer/build_mays_orders_module.py` is Windows-only on Linux: `_terraform_exe()` calls `where` and raises `FileNotFoundError`; `run()` hardcodes `C:\Program Files\Git\bin\git.exe`. The official RIS builder cannot run in this workspace. |
| B2 | **B — RIS integration** | The RIS target module is incomplete (only `variables.tf`); root validate cannot succeed. |
| C1 | **C — contract incompatibility** | `1dbb0cb` does not contain `agent_transport`; RIS injects `module.agent_transport[0]` outputs and the generated module then fails Terraform validate. |
| C2 | **C — contract incompatibility** | `016cdfd` is a divergent branch that lacks `1dbb0cb` fixes (`a2fb385`, IAM portability). It is not a safe direct replacement for the reviewed baseline. |
| D1 | **D — IAM/Terraform regression** | Live `ris-dev-mays-orders-orders-queue` has a wildcard-principal queue policy. `1dbb0cb` has no queue-policy resource (plan would delete it); `016cdfd` has an account-root policy (plan would update it). Both need explicit plan review. |
| E1 | **E — existing baseline** | RIS full suite: 3393 PASS / 129 skipped / 18 known environmental failures; no new RIS failure introduced by this analysis. |

## 5. RIS integration tests

| Check | Result |
| --- | --- |
| `tests/test_build_mays_orders_transport_outputs.py` | PASS (within 79 focused tests) |
| `tests/test_composite_lifecycle.py` | 3 known failures (pre-existing) |
| RIS full suite | 3393 PASS / 129 skipped / 18 baseline failures |
| Root `terraform fmt -check` | PASS |
| Root `terraform validate` | FAIL — `mays_orders[0].iam_handler_role_name` (module incomplete) |
| Generated `016cdfd` + RIS transport injection + Terraform validate | PASS |
| Generated `1dbb0cb` + RIS transport injection + Terraform validate | FAIL — no `agent_transport` module |

Manual RIS contract injection at `016cdfd` produces 23 outputs and validates.
This proves the RIS transport contract itself is compatible with `016cdfd`,
but the original module test failure and the missing pin reconciliation remain.

## 6. Compatibility assessment

- **`016cdfd` cannot be declared clean**: the original module builder test
  fails. The pin is not a superset of the reviewed baseline and lacks the
  wildcard-SQS/IAM-portability fixes.
- **`1dbb0cb` cannot be used with current RIS transport injection**: the
  generated module lacks `agent_transport`, so Terraform validation fails.
- **Current Mays-Orders main `8830da2` cannot be used as a replacement**: the
  `orders-service` preset fails Terraform validation.
- The reviewed live SQS queue policy is wildcard-principal; a plan from either
  pin changes it. That change is security-relevant and must be reviewed, not
  treated as a no-op.
- No pin migration was performed.

## 7. Stop gate

A reproducible original Mays-Orders module failure exists. Per the stop gate:

1. Failure documented.
2. Module versions/commits recorded (`016cdfd`, main `8830da2`).
3. Reproduction command and tests recorded.
4. RIS impact: builder pin cannot be accepted; plan remains blocked.
5. Orchestrator informed here.
6. No change was made to the original Mays-Orders repository.

**BLOCKED — MAYS ORDERS MODULE FAILURE**

Secondary RIS integration failures also remain:
**BLOCKED — RIS ORDERS INTEGRATION FAILURE** (Windows-only builder; incomplete
generated module).

## 8. Required next steps

1. Original Mays-Orders owner fixes the `016cdfd` module-selection regression
   and the main `orders-service` undeclared-variable failure.
2. Reconcile the result-transport branch (`016cdfd`) with the reviewed
   baseline fixes (`a2fb385`, `f3e78d0`, `a46b189`, `ccf22a3`) on a new,
   test-green Mays-Orders commit.
3. Re-run both original test suites at the new commit.
4. Make the RIS builder portable or run it on its supported host; rebuild
   `terraform/modules/mays_orders` and pass root validate.
5. Review the live SQS queue-policy change explicitly (wildcard → account
   root, or removal, depending on the chosen pin).
6. Only then update the RIS builder pin and produce a Terraform plan.

## 9. Branch / reports

- RIS branch: `feature/ris-p0-plan-baseline-reconciliation-06`
- Base: `ddd7660`
- Report: `docs/reports/RIS-P0-PLAN-BASELINE-RECONCILIATION-06-REPORT.md`
- No AWS mutation, Terraform plan/apply, deployment or main merge.
