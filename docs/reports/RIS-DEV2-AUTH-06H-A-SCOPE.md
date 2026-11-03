# RIS-DEV2-AUTH-06H-A — Terraform Scope Boundary

## Result

```text
PASS — MAYS-ORDERS BUILDER CLONE IS OUTSIDE THE ACTIVE RIS TERRAFORM ROOT
```

## Repository checkpoint

- branch: `feature/ris-application-persistence-v1`;
- HEAD: `f0a233302393b46a936dda3ee962414399304df2`;
- working tree: clean before this report change.

## Active RIS root

The active RIS Terraform root is:

```text
terraform/
```

Its root configuration is `terraform/main.tf`. All root module sources are
relative local paths under `terraform/modules/`, including:

```text
./modules/cognito
./modules/sqs
./modules/dynamodb
./modules/iam
./modules/api
./modules/lambda
./modules/orders_reader
./modules/mays_orders
./modules/monitoring
./modules/cloudtrail
./modules/documents
./modules/health_public
./modules/health_plane
```

No RIS root or local module source references
`installer/projects/mays_order_builder/terraform/main.tf`.

## Mays-Orders boundary

`terraform/modules/mays_orders/` is the generated local Terraform module used
by the RIS root. Its manifest identifies the builder repository as provenance,
but its generated files are the actual Terraform source consumed by the root.
The builder clone at `installer/projects/mays_order_builder/` is ignored by
`.gitignore` and is not itself a Terraform module source in the active root.

The saved deployment plan uses `orders_lifecycle = "disabled"`, so the
`module.mays_orders` instance has count zero for this deployment. In either
case, the external builder file is not read as an active module source during
the RIS plan.

## Independence conclusion

The failing file
`installer/projects/mays_order_builder/terraform/main.tf` is an independent,
ignored builder-clone file. Its formatting failure is not a formatting failure
of the active RIS root or any local module actually consumed by the RIS plan.
No foreign Terraform file was changed.
