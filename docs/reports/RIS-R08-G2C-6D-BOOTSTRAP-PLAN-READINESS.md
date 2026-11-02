# RIS-R08-G2C-6D — RIS-DEV2 Bootstrap and Plan Readiness

**Status:** CONSTRUCTION READY / OFFLINE VERIFIED / AWS READ-ONLY VERIFIED /
STATE-BOOTSTRAP BLOCKED / PLAN NOT AUTHORIZED / APPLY NOT AUTHORIZED

## Read-only evidence

The explicit `default` profile guard passed for account `262370457690` and
region `eu-central-1`. Read-only checks confirmed:

- state bucket `ris-dev2-tf-state-dev` and key
  `env:/ris-dev2/dev/terraform.tfstate` are readable;
- current object has a version ID and the version listing contains 17 historical
  state versions, with no delete marker;
- lock table `ris-dev2-tf-lock` is `ACTIVE` with two items;
- no state body was written and no version was restored.

The current State remains serial 17 with zero resources as established by
G2C-5. No live `ris-dev2` Cognito/CloudFront/API/Lambda/Orders runtime baseline
was identified. Therefore current external Jobsearch identity references remain
`UNKNOWN`; they must be supplied and independently verified before a plan.

## Bootstrap contract

The safe future bootstrap tuple is explicit and immutable:

```text
profile=default
account=262370457690
region=eu-central-1
project=ris-dev2
environment=dev
workspace=ris-dev2
bucket=ris-dev2-tf-state-dev
lock_table=ris-dev2-tf-lock
key=env:/ris-dev2/dev/terraform.tfstate
```

No new workspace, backend object, state migration, import, state push or lock
mutation is authorized by this phase. Because the existing state is empty and
historical ownership is unresolved, the bootstrap gate is **BLOCKED** until a
separate ownership decision authorizes either authoritative state recovery or a
new isolated project/state tuple. A name-only reuse of `ris-dev2` is not safe.

## Intended installation sequence after approval

1. Repeat profile/account/region and project/state guards.
2. Verify supplied external pool/clients/issuer and external Orders ARNs live,
   without changing them.
3. Build the generated Orders artifact only if `orders_lifecycle=managed`;
   external and disabled modes must not build or deploy that component.
4. Build Lambda bundles and run offline format/validation/regression gates.
5. Obtain explicit state/bootstrap and protected-resource ownership approval.
6. Run one saved Terraform plan against the approved isolated state contract.
7. Review creates, updates, deletes, replacements, IAM and cost impact; require
   zero protected-resource changes.
8. Obtain a separate written Apply approval; this task provides none.

## Plan checklist

- [ ] External identity values are complete, live and independently verified.
- [ ] No Cognito, user, client, OAuth, CloudFront, DNS or ACM resource is in
      RIS ownership.
- [ ] Orders lifecycle is explicitly `managed`, `external` or `disabled`.
- [ ] No foreign project/workspace/backend values occur.
- [ ] No state import/recovery workaround is used.
- [ ] Exact plan artifact and hash are stored outside Git.
- [ ] All privacy/erasure/cutover execution flags remain false.
- [ ] Apply authorization is recorded separately.

## Final gate classification

| Gate | Status |
|---|---|
| Construction | READY |
| Offline verification | VERIFIED with documented installer/build blockers |
| AWS read-only | VERIFIED |
| State/bootstrap | BLOCKED |
| Terraform plan | NOT AUTHORIZED / NOT RUN |
| Apply | NOT AUTHORIZED |
