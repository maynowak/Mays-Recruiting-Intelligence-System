# RIS-R08-DEV2-11B — Health Artifact Drift

## Affected resources

- `module.health_plane.aws_lambda_function.health_writer`
- `module.health_plane.aws_lambda_function.health_publisher`

Both use `filebase64sha256()` over the configured ZIP. The historical plan
reported path/filename changes, not a proven semantic R08 change.

## Read-only artifact evidence

The live packages were downloaded through the read-only Lambda code endpoint
into a temporary directory solely for hash comparison:

| Function | Live size | ZIP SHA-256 | Live `CodeSha256` |
|---|---:|---|---|
| health-writer | 11889 bytes | `47bc136e9f6af2025ed14f9cecf138e9ca74f81c9caff4b29d72e568c43115a7` | `R7wTbp9q8gJe0U+c7PE46cp0+Bycr/SynXLlaMQxFac=` |
| health-publisher | 12079 bytes | `91aaf50f7cbb17d018496147ee2b94c2f8701f5305a77459c1c504e071e9e097` | `kar1D3y7F9AYSWFH7iuUwvhwH1MFp3RZwcUE4HHp4Jc=` |

The writer hash matches the historical canonical package. The publisher hash
differs from the older locally documented package, but matches the current
live Lambda package exactly. The repository currently does not contain the
Health ZIPs and `build_zip.py --bundle all` builds only the agent and reader
bundles.

## Resolution for the R08 plan

The downloaded live baseline packages were placed temporarily at the exact
forward-slash paths recorded in the Terraform state. With those byte-identical
baseline files, the controlled plan contains **zero Health Lambda actions**.
The earlier four-action plan therefore combined the real R08 agent/IAM/route
changes with filename/path identity drift. No `ignore_changes`, state edit,
hash substitution, or Lambda deployment was used.

The Health Lambdas remain outside the R08 approval scope. Any future
repackaging requires a separate deterministic build, package-content review,
and Health-specific approval.
