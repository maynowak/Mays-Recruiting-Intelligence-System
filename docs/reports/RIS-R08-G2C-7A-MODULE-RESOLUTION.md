# RIS-R08-G2C-7A — Terraform Module Resolution

**Status:** GO / OFFLINE VERIFIED / NO AWS OR STATE ACCESS

## Root cause

Terraform must resolve a local module source during initialization even when
the module block has `count = 0`. `terraform/modules/mays_orders` is a generated
artifact and was absent from the checkout, so root validation stopped before
evaluating `orders_lifecycle=external|disabled`.

The pinned local builder already is the repository's authoritative generation
path. The additional failure was in
`installer.build_mays_orders_module.check_arn_id_contract`: it required the
obsolete direct assignment
`orders_table_name = module.mays_orders.dynamodb_table_name`. G2C-6 correctly
changed this to a conditional managed/external expression and indexed module
instance.

## Repair

The checker now:

- accepts the conditional lifecycle expression;
- normalizes only `module.mays_orders[0]` to inspect its managed branch;
- still requires every managed Orders output and RIS API/authorizer binding;
- retains the mixed RIS/Mays-Orders API safety check;
- does not create a stub, dummy ARN, remote module, or AWS resource.

The generated module remains a local build artifact and is not committed.

## Actual offline verification

1. `python -m installer.build_mays_orders_module --project-name ris-dev2`
   **PASS**. Pinned builder commit, generated contract, IAM SQS contract,
   `fmt`, module `init -backend=false`, and module `validate` all passed.
2. `terraform init -backend=false -input=false -no-color` **PASS**.
3. Root `terraform validate -no-color` **PASS**, with only existing provider
   deprecation warnings.
4. Root `terraform fmt -check` **PASS**.
5. G2C-6 static protection tests remain passing.

No Terraform plan was run. No backend was contacted. No Orders deployment or
AWS mutation occurred.

## Supported boundaries

- `managed`: generated module is required locally and retains its existing
  managed behavior.
- `external`: generated module is not instantiated (`count=0`), and supplied
  table/queue references feed only the RIS reader.
- `disabled`: generated module and reader/Orders monitoring are not instantiated.

Terraform source resolution still requires the local generated module directory
to exist for all root `init` invocations. The supported remedy is the pinned
offline builder step, not a hand-written substitute.
