# RIS-R08-ORCH-PR-03B — Security Review

## Result: BLOCKED by active-path findings

| Finding | Severity | Datei/Zeile | Szenario | Evidence | Empfehlung | Merge-Blocker |
|---|---|---|---|---|---|---|
| Missing universal cache header | MEDIUM | `lambda/handler.py:3753-3792,1553-1558` | Application auth/dependency errors bypass `_application_response()` | Reviewer inspection | Apply `no-store, private` to every ApplicationV1 response path | Yes |
| Reduced completion scope callable | HIGH | `privacy_document_erasure.py:320-327` | Caller can omit required categories | Reviewer inspection | Make reduced scope private/local or require canonical categories | Yes |
| Active runtime erasure fence incomplete | CRITICAL/HIGH | `agents/runtime/pipeline.py:226-236,373-398` | Missing work row can be re-registered after erasure; running worker has no final freeze check | Messaging review | Add durable subject-level fence before registration and before execution | Yes |

Positive evidence: verified partner context binds user/tenant/partner/issuer;
metrics responses use `no-store, private`; local ledger reconciliation rejects
foreign scope and does not auto-delete. No secrets or production credentials
were found. No AWS access was performed.
