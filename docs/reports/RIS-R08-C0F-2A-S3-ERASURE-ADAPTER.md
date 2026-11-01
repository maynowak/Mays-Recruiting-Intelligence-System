# RIS-R08-C0F-2A — S3 ERASURE ADAPTER & LOCAL VERIFICATION

**Status:** LOCAL ADAPTER VERIFIED / PRODUCTION DISABLED / C0F-2B BLOCKED

## Baseline and scope

- Branch: `feature/ris-partner-profile-persistence-v1`
- Parent HEAD: `1a9544108ebab3f4e5660e9768c90e913d365096`
- RIS only; no AWS calls, deployment, Terraform changes or real S3 deletes
- Receipt journal and productive erasure persistence remain disabled
- 39 original untracked files preserved

## Adapter

`FencedS3VersionedAdapter` connects the C0F-1 orchestrator to an injected
S3-shaped client only. It:

- inventories `Versions` and `DeleteMarkers` via `list_object_versions`;
- consumes `KeyMarker`/`VersionIdMarker` pagination completely;
- restricts every object to the server-provided authorized prefix;
- deletes only with an explicit `VersionId` (never an unversioned delete);
- invokes the trusted fencing callback immediately before every inventory and
  delete call;
- rejects stale attempts before reaching the client.

The adapter has no boto3 construction path. Local tests provide the client and
the fencing callback. The existing C0F-1 phase ledger still performs atomic
operation/freeze/attempt checks before each phase record, while the adapter
rechecks the attempt immediately before each S3 action.

## Upload-ticket and completion handling

Previously issued presigned upload URLs are not assumed revoked. The adapter
always performs a new full inventory after deletion. Late uploads, remaining
versions or delete markers prevent `COMPLETED` and result in a retry boundary.
No ticket TTL, retention period or upload-ticket behavior was invented or
changed in this gate. Existing CV upload-complete metadata guards remain
unchanged.

## Race-condition analysis

There remains a non-atomic interval between the final DynamoDB fencing check/
callback and the subsequent S3 API request. S3 has no conditional operation
that accepts the DynamoDB attempt token, so this adapter does **not** claim
complete cross-service fencing. A worker losing authorization after the
callback but before S3 receives the request is an unresolved race. The final
inventory detects many consequences, but cannot prove that a stale request was
not accepted. Production execution therefore remains disabled.

Unknown S3 results are never treated as successful. Retry/resume requires a
new attempt and the phase ledger's compare-and-swap version. No public
checkpoint contains keys, version IDs, pagination URLs or presigned URLs.

## IAM review (read-only)

The existing Lambda document policy grants `s3:PutObject`, `s3:GetObject`,
`s3:DeleteObject` and `s3:ListBucket` under the tenant prefix. It does not
explicitly grant `s3:DeleteObjectVersion`; no IAM or Terraform change was made.
This is an additional production-activation blocker, not a reason to broaden
permissions in C0F-2A.

## Verification

| Check | Result |
|---|---|
| Local S3 adapter/fencing tests | **8 passed** |
| C0B–C0F-1 regression | **296 passed, 252 subtests** |
| `py_compile` | **PASS** |
| `git diff --check` | **PASS** |
| Real S3/AWS calls | **None** |
| DynamoDB Local | Not available; transaction fakes used |

Covered cases include version/delete-marker inventory, pagination, explicit
VersionId deletion, stale workers, freeze/transaction conflicts, unknown S3
results, resume/retry boundaries and final re-inventory.

## Gate decision

- **R08-C0F-2A:** PASS for the locally verified, fake-only adapter.
- **R08-C0F-2B:** **BLOCKED** — the DynamoDB-to-S3 race remains uneliminated,
  `DeleteObjectVersion` IAM is not explicitly granted, and no production
  fencing/activation has been approved.
