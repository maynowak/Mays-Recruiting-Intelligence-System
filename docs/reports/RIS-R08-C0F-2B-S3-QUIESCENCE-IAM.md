# RIS-R08-C0F-2B — S3 ERASURE QUIESCENCE & IAM READINESS

**Status:** LOCAL QUIESCENCE VERIFIED / PRODUCTION BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `80f84b0e66738d0c10c35390cdde3b3353dcabb4`
- RIS only; no AWS calls, Terraform changes, deployment or real S3 delete
- Receipt journal and productive erasure persistence remain disabled
- 39 original untracked files preserved

## Quiescence contract

`S3QuiescenceCoordinator` requires all of the following before a local
exclusive lease can be acquired:

- active USER/CV freeze;
- ticket creation blocked;
- every issued ticket has known expiry and is expired;
- zero known active upload/S3 actions;
- complete inventory and an empty version/delete-marker result;
- no Object Lock blocker or unknown Object Lock state.

Unknown ticket expiry, open actions, late uploads, incomplete pagination,
remaining objects, retention/legal hold and unknown lock state are all
`BLOCKED`. No ticket TTL or retention period is invented by this gate. The
existing upload URL implementation currently computes a 900-second expiry in
the response but does not persist a server-side ticket record; therefore a
real erasure run cannot prove historical ticket expiry from the current
contract and remains blocked.

The local lease store is exclusive and thread-safe. A stale worker or replaced
attempt fails the lease check. Completion requires the lease to remain current
and a final empty inventory proof. This models the required execution order;
it does not claim cross-service atomicity.

## Race and upload analysis

The DynamoDB freeze/operation check, lease check and subsequent S3 API request
are separate systems. A worker may lose authorization after its final local
check but before S3 receives the request. The lease and adapter callback reduce
the window and final re-inventory detects many late writes, but neither can
revoke an already-issued presigned URL or atomically fence S3 with a DynamoDB
token. This race remains explicitly open and prevents production activation.

## IAM read-only review and patch proposal

Current `terraform/modules/lambda/main.tf` grants the document Lambda:

- `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on
  `${documents_bucket_arn}/tenant/*`;
- `s3:ListBucket` on the bucket.

It does not explicitly grant:

- `s3:ListBucketVersions` on the bucket;
- `s3:DeleteObjectVersion` on `${documents_bucket_arn}/tenant/*`.

Proposed future least-privilege patch (not applied):

```hcl
Action   = ["s3:ListBucketVersions"]
Resource = [var.documents_bucket_arn]

Action   = ["s3:DeleteObjectVersion"]
Resource = ["${var.documents_bucket_arn}/tenant/*"]
```

The patch must be reviewed with any bucket-policy Deny conditions, object
ownership, versioning and Object Lock configuration. No
`s3:BypassGovernanceRetention` permission is proposed. Governance/legal holds,
compliance retention or unknown lock state remain hard blockers.

## Verification

| Check | Result |
|---|---|
| Local S3 adapter/quiescence tests | **12 passed** |
| C0B–C0F-2A regression | **300 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| Real S3/AWS calls | **None** |
| DynamoDB Local | Not available; transaction fakes used |

Covered cases include tickets before/after expiry, unknown expiry, late
uploads, open actions, stale/concurrent leases, freeze loss, incomplete
pagination, version/delete-marker inventory, S3 failures, retry/resume and
final re-inventory.

## Gate decisions

- **R08-C0F-2B local:** **GO** — quiescence and exclusive local lease behavior
  are verified with fakes.
- **R08-C1 local:** **BLOCKED** — ticket persistence/invalidity proof and
  cross-service fencing are not available in the current contracts.
- **Production:** **BLOCKED** — no real S3 fencing guarantee, missing explicit
  versioned-delete IAM permissions, and no Object Lock/bucket-policy
  verification or activation approval.
