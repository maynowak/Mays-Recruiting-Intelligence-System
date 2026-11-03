# RIS-APPLICATION-E2E-06C — DEV2 Data Access Preflight

**Decision:** **DEV2 DATA TEST BLOCKED**

This phase was read-only. No application item, partner record, credential,
Cognito object, Terraform state or other resource was mutated. No application
table item contents were read.

## 1. Account and state guard

| Check | Result |
|---|---|
| AWS profile | `default` |
| STS account | `262370457690` — PASS |
| Region | `eu-central-1` — PASS |
| Terraform workspace | `ris-dev2` — PASS |
| State serial | `24` — PASS |
| State lineage | `a0bd361d-5cd1-a207-a8c0-e6888f0be082` — PASS |
| Terraform plan/apply/refresh | Not executed |

## 2. ApplicationV1 resource guard

The exact installed target is:

```text
Table: ris-dev2-dev-applications
ARN: arn:aws:dynamodb:eu-central-1:262370457690:table/ris-dev2-dev-applications
Status: ACTIVE
```

The table has the expected primary key:

```text
applicationId (HASH), entityKey (RANGE)
```

The expected `gsi-owner` is present and `ACTIVE` with:

```text
ownerKey (HASH), updatedAt (RANGE), ProjectionType=ALL
```

The similarly named `ris-dev2-applications` table does not exist. The target
was identified from the exact table name and ARN; no scan, query or item read
was issued.

## 3. Principal and IAM boundary

The actual read-only discovery principal was:

```text
arn:aws:iam::262370457690:user/devnemo
```

Read-only IAM metadata showed the AWS-managed `AdministratorAccess` policy and
`IAMUserChangePassword`; no inline user policies were present. This proves the
principal can technically perform broad operations, but it does **not** provide
the required narrow authorization for this test. The installed permissions are
not bounded to the ApplicationV1 table, and no separate approval for live test
mutations was supplied.

Required actions for a future repository-backed live test would include the
table-scoped equivalents of `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`,
`Query`, and the transaction operations used by the repository. They are not
treated as authorized merely because the current principal has broad IAM
rights.

## 4. Live data safety

- No existing application records were read.
- No test prefix or correlation was written because mutation approval is absent.
- No existing records can be proven safe for overwrite without a future
  approved, deterministic allocation/conditional-write procedure.
- Future cleanup must use only repository-owned synthetic records and must not
  scan or globally clear the table.
- No retention, backup or protected-resource setting was changed.

## 5. Decision

| Gate | Result | Reason |
|---|---|---|
| Account/profile/region | PASS | Exact expected Foundation account and region |
| Workspace/state guard | PASS | `ris-dev2`, serial `24`, expected lineage |
| Table/GSI guard | PASS | Exact ApplicationV1 table and active `gsi-owner` |
| IAM narrow-scope guard | **BLOCKED** | Principal has broad AdministratorAccess, not table-scoped proof |
| Live mutation approval | **BLOCKED** | Separate explicit 06D approval not supplied |
| DEV2 data test | **BLOCKED** | No live write/read test may start |

```text
DEV2 DATA TEST BLOCKED
```

06D must not run until a separate approval names the exact table, synthetic
correlation strategy, allowed repository operations, cleanup owner and
time-bounded mutation window. This preflight does not authorize that work.
