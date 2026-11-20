# RIS Analysis Parser Artifact (internal Node Lambda)

**Status:** prepared; the Lambda is Terraform-gated
(`enable_analysis_runtime=false`). No apply.
**Source:** jobsearch `c40bf78` · **Reference build:** 412 files,
17 937 176 bytes, SHA-256
`fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a`

## Build

```powershell
# 1. pin the host/CI dependencies from the jobsearch lockfile
#    (adds @napi-rs/canvas + platform package)
npm ci

# 2. fetch the Linux arm64 native canvas package pinned in package-lock.json
npm pack @napi-rs/canvas-linux-arm64-gnu@1.0.6 --pack-destination <tmp>
tar -xzf <tmp>/napi-rs-canvas-linux-arm64-gnu-1.0.6.tgz -C <tmp>

# 3. build the deterministic artifact
python tools/build_analysis_parser_artifact.py `
  --jobsearch-root <jobsearch> --expected-commit c40bf78 `
  --canvas-platform-dir "@napi-rs/canvas-linux-arm64-gnu=<tmp>/package" `
  --out lambda/dist/analysis-parser.zip
```

The sidecar `analysis-parser.manifest.json` records SHA-256, size, file count,
source commit and the included canvas platform. Rebuilding the same inputs is
byte-identical.

## Closure

| Included | Excluded |
|---|---|
| `lambda/ris_parser_handler.mjs` | `node_modules/pdfjs-dist/web/**` |
| `scripts/ris-parser-cli.mjs` | source maps, tests, `__tests__` |
| `api/_lib/**` | site/UI code, other node_modules |
| `node_modules/pdfjs-dist/**` | |
| `node_modules/@napi-rs/canvas` + `canvas-linux-arm64-gnu` | other platform binaries |

`@napi-rs/canvas` is pdfjs-dist's optional native dependency; without it the
legacy Node build fails with `DOMMatrix is not defined`. The Lambda is
`linux-arm64`, so only that native package is shipped.

## Verify without deploying

```powershell
python tools/verify_analysis_parser_artifact.py `
  --artifact lambda/dist/analysis-parser.zip `
  --pdf tests/fixtures/analysis/synthetic-canary-cv.pdf `
  --host-canvas-dir <jobsearch>/node_modules/@napi-rs/canvas-win32-x64-msvc `
  --expected-sha fb741fb25e7cd29232a43a63137a6e2a8ca0e948cc2efdf6764b8779119f301a
```

The verifier checks the SHA, required closure, forbidden entries, exactly one
`linux-arm64` native binary, then extracts the artifact and runs the real Node
handler. On a non-Linux host the matching canvas package is added only to the
extracted staging copy; the artifact itself is unchanged.

Observed smoke result: job `stableId` 64 chars, 6 job tags, CV `stableId` 64
chars with skills `Python, AWS, Terraform, Docker, Linux, SQL`, 2 ATS tags,
`invalid_input` for an empty job and `unsupported_capability` for an unknown
capability.

## Limits and IAM

- Runtime `nodejs22.x`, `arm64`, 512 MB, 15 s (60 s maximum), log group 14 days.
- Adapter limits: 100 000-char payload, 15 s timeout, `ParserInputError` for
  invalid input and `ParserUnavailable` for runtime failures.
- Parser role: logs only. The analysis role gets `lambda:InvokeFunction` on this
  function only. No SQS, Secrets Manager, DynamoDB or other shared policy.
- No API Gateway route, function URL, CloudFront distribution or public HTTP
  endpoint.
