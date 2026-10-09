# RIS Consolidation Gate 02 Synthesis

## Research Findings Summary

R1 Privacy/Retention/Deletion
CURRENT_STATE: No dedicated retention/deletion implementation found. Documents mention documents bucket with presigned URLs, no PII in keys. No automated data deletion jobs.
EVIDENCE: SYSTEM-ARCHITECTURE.md mentions documents bucket keys tenant/{t}/users/{sub}/documents/{uuid}, presigned URLs only.
GAP: No retention policy enforcement, no user data deletion endpoint, no audit trail for deletion.
IMPLEMENTATION_REQUIRED: YES

R2 Event-driven Health Plane
CURRENT_STATE: Static /health liveness only. No health events emitted.
EVIDENCE: lambda/handler.py _handle_health dependency-free, tests/test_p20_health_contract.py
GAP: No health events, no health aggregation, no /health/runtime.
IMPLEMENTATION_REQUIRED: YES

R3 OpenAPI/API Contract Governance
CURRENT_STATE: API-STANDARD.md exists, contract tests exist.
EVIDENCE: tests/test_p20_api_contract_consistency.py
GAP: No machine-verified OpenAPI spec, drift detection limited.
IMPLEMENTATION_REQUIRED: YES

R4 WorkItem-AgentRun-Event-Orders Traceability
CURRENT_STATE: workId propagated, but correlation to AgentRun and Orders not fully documented.
EVIDENCE: agents/runtime/pipeline.py, lambda/handler.py
GAP: Missing explicit trace headers in events, Orders adapter correlation weak.
IMPLEMENTATION_REQUIRED: YES

R5 Remaining Warning Root-Cause
CURRENT_STATE: 255 warnings remain after utcnow migration, many from tests.
EVIDENCE: pytest output
GAP: Test deprecation warnings, unittest warnings.
IMPLEMENTATION_REQUIRED: PARTIAL

## Dependency Matrix
- R2 Health Plane overlaps with R4 Traceability via event metadata
- R1 Privacy overlaps with R3 OpenAPI for deletion endpoint contract
- R5 Warnings independent
