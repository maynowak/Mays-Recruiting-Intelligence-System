# RIS-DEV2-AUTH-06A — Fix Baseline

## Result

```text
PASS — COMMITTED DISPATCHER FIX VERIFIED
```

- Repository: `C:\Users\DCI-Student\AppData\Local\Temp\opencode\ris-application-persistence-v1`
- Branch: `feature/ris-application-persistence-v1`
- Starting commit: `f876c26dbb84be38b8c9604a46e48b8489f4f422`
- Working tree: clean before packaging
- No foreign or pre-existing working-tree changes were overwritten.

## Code verification

The ApplicationV1 dispatch branch in `lambda/handler.py` calls:

```python
_application_routes(event, context, method, path)
```

The function exists with the matching four-argument signature. It enters
`_application_ctx()`, which reuses `_partner_profile_context()` before
constructing `ApplicationContext` or opening `ApplicationRepository`.

The committed boundary also rejects malformed credentials before store
construction, while preserving 503 for unavailable stores and the existing
401/403 credential, registry and tenant mappings. No fallback identity or
tenant was added. The handler continues to expose `lambda_handler = handler`
for the Terraform-configured entry point.

## Existing packaging/deployment contract

The repository's official procedure is:

```text
python lambda/build_zip.py --bundle all
```

The agent bundle is `terraform/lambda.zip`; Terraform's Lambda module uses
`filename` plus `filebase64sha256(filename)`, with default handler
`handler.lambda_handler` and runtime `python3.14`. The Lambda code is therefore
Terraform-managed; a direct code update would create drift unless separately
authorized.

No packaging or AWS write operation is itself a deployment. This phase stops
before any Lambda update, alias change, Terraform apply or rollback.
