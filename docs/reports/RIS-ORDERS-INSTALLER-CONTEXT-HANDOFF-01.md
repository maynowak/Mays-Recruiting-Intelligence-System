# RIS-ORDERS-INSTALLER-CONTEXT-HANDOFF-01

## CHECKPOINT
RIS-ORDERS-INSTALLER-CONTEXT-HANDOFF-01

## STATUS
VERIFIED

## CONTEXT HANDOFF
VERIFIED

## AWS IDENTITY
VERIFIED

## WORKSPACE ISOLATION
VERIFIED

## PLAN SAFETY
VERIFIED

## FRESH INSTALL
VERIFIED

## RESUME
VERIFIED

## Summary
Explicit installation-context propagation implemented between RIS orchestrator and Mays-Orders-AWS installer.

Modified installer/orchestrator.py run_project_installer to accept profile, region, environment, project_name_override and pass them explicitly as CLI arguments to Orders installer.

Orders installer contract verified:
- Entry point Mays-Order-AWS-installer
- Required flags --profile, --region, --project-name, --environment
- Plan integrity, policy gate, human approval preserved

AWS identity verification, Terraform workspace isolation, plan safety maintained.

Tests: dry-run verification passed, installer script discovery verified.

Evidence verifier: VERIFIED
