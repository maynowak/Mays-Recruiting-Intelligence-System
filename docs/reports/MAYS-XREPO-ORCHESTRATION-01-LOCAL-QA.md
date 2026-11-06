# MAYS-XREPO-ORCHESTRATION-01 — Local QA Report

## Result

`LOCAL QA PASS — GREEN` for the contract, validator, sender, receiver, and
state-machine tests. **Live E2E was not executed.**

- Repository: `maynowak/Mays-Recruiting-Intelligence-System`
- Branch: `feature/mays-xrepo-orchestration-01`
- HEAD at QA start: `1e9f80a (working tree included the marker hardening)`
- Run date: 2026-11-06 (Europe/Berlin)
- Runner: `scripts/xrepo/run_local_qa.sh`

## Commands actually executed

```bash
./scripts/xrepo/run_local_qa.sh
```

The runner performs:

```bash
python3 -m py_compile scripts/xrepo/{validate_event,apply_event,build_event,test_validate_event,test_apply_event,test_build_event}.py
python3 -m unittest discover -s scripts/xrepo -p 'test_*.py' -v
python3 - <<'PY'  # parse every docs/xrepo JSON file
...
PY
python3 - <<'PY'  # parse xrepo-*.yml with PyYAML
...
PY
git diff --check
```

Actual result: **54/54 tests PASS**, all schema/fixtures JSON parse, both
workflow YAML files parse, `git diff --check` clean, `LOCAL QA PASS`.

## Reproducible test matrix

| Case | Test(s) | Result |
| --- | --- | --- |
| valid event | `test_valid_event`, `test_fixtures`, `test_cli_valid` | PASS |
| invalid schema | `test_missing_field`, `test_extra_field`, `test_wrong_protocol`, `test_invalid_status`, `test_invalid_event_id`, `test_sequence_must_be_positive_integer`, `test_issue_must_be_positive_integer`, `test_too_many_evidence_items`, `test_payload_too_large`, `test_duplicate_json_key_rejected` | PASS |
| spoofed source | `test_spoofed_source_with_expected_source`, `test_spoofed_evidence_repository` | PASS |
| unauthorized repository | `test_unauthorized_source` | PASS |
| wrong target | `test_wrong_target_with_expected_target`, `test_same_source_and_destination` | PASS |
| stale sequence | `test_older_sequence_is_stale`, `test_retry_cycle` | PASS |
| duplicate event | `test_duplicate_event_id_is_ignored`, `test_retry_cycle` | PASS |
| evidence absent | `test_evidence_absent_for_implementation_ready`, `invalid-evidence-absent.json` | PASS |
| retry cycle | `test_retry_cycle` | PASS |
| A→B→A status sequence | `test_a_to_b_to_a_status_sequence_is_monotonic` | PASS (local state machine) |
| source issue/commit verification | `test_verify_source_accepts_issue_and_commit`, `test_verify_source_rejects_pull_request`, `test_verify_source_rejects_missing_commit` | PASS (mocked API) |
| no shell interpolation | `test_post_comment_uses_json_file_not_shell_arguments` | PASS |
| untrusted issue comment marker | `test_untrusted_comment_markers_are_ignored` | PASS |
| missing app credentials | `test_missing_source_token_is_blocked_for_live` | PASS (`BLOCKED FOR LIVE`) |
| live `repository_dispatch` | not executed | **E2E PENDING** |

## Limits / honest status

- The A→B→A row verifies the receiver state machine and status sequence locally;
  it is **not** a live cross-repository dispatch.
- Live dispatch requires both workflows on the default branches and an approved
  GitHub App installation with `XREPO_APP_ID` / `XREPO_APP_PRIVATE_KEY`.
- No full frontend/API suite was run because no product code, product API, or
  existing workflow was changed. The focused xrepo suite is the relevant gate.
- No Terraform/AWS/Cognito/CloudFront/Vercel/Mays-Orders action was executed.

## Security audit

- Payload is validated before use; allowlist and expected source/target are enforced.
- Only comments authored by `github-actions[bot]` can define sequence/event markers; user-injected markers are ignored.
- Evidence URLs are bound to the source repository and, for commits, to the exact SHA.
- Issue comments are HTML-escaped; no payload value is passed as a shell argument.
- `GITHUB_TOKEN` is used only for the destination issue; the app token is scoped
  to source reads or target dispatch.
- No secrets, tokens, PII, or candidate data are present in events or reports.

## Resume point

Gate 05 local QA complete. Next: Gate 06 PR readiness and review.
