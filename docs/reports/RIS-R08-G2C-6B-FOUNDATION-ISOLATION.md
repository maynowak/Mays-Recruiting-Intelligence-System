# RIS-R08-G2C-6B — Foundation and Orders Lifecycle Isolation

**Status:** IMPLEMENTED / OFFLINE VERIFIED / PLAN NOT RUN

## Orders lifecycle

The root now exposes `orders_lifecycle`:

| Mode | Managed module | RIS Orders Reader | Orders monitoring |
|---|---:|---:|---:|
| `managed` (default) | enabled | enabled | enabled |
| `external` | disabled | enabled with explicit table/queue references | disabled |
| `disabled` | disabled | disabled | disabled |

External mode requires explicit, region-shaped table and queue references. The
reader IAM policy is limited to the supplied DynamoDB table/table indexes and
SQS `SendMessage`; it does not gain access to the external Orders module's
administrative resources. Disabled mode uses no dummy ARNs and declares no
Orders reader or Orders monitoring resources.

The generated `mays_orders` module remains a managed-only build artifact and is
not imported, altered or reconstructed by this change. Existing managed
installations remain compatible because `managed` is the default.

## Installer behavior

Project overlays and explicit `extra_vars` may set the lifecycle. The installer
validates the value and only runs the separate Mays-Orders component preflight,
plan and handoff when the lifecycle is `managed`. External and disabled modes
therefore cannot silently trigger a managed Orders deployment.

## State and IAM boundaries

RIS owns only its own API, reader Lambda/role and foundation resources. External
identity and Orders references are values, not Terraform resource addresses.
No import, state recovery, backend change or state write was performed. The
existing tracked deletion of `terraform/modules/mays_orders/variables.tf` was
preserved and not overwritten.

## Verification

| Check | Result |
|---|---|
| G2C-6 mode/protection tests | 6 passed |
| Terraform fmt check on changed files | PASS |
| Installer `py_compile` | PASS |
| Terraform validate | BLOCKED: generated `mays_orders` module absent |
| AWS mutation | NOT PERFORMED |

The validation blocker is a packaging/build-artifact prerequisite, not a
request to restore or commit the generated Orders module.
