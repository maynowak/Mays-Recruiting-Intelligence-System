# SOURCE-CONNECTIVITY-GATE-01 — Source Connectivity Framework

**Status**: FRAMEWORK DOCUMENTED

## Executive Summary

This document describes the source connectivity framework for the Mays-Orders-AWS installer. This framework provides the structure for checking source connectivity BEFORE any Terraform operations.

## Architecture

### Purpose

Prevent source connectivity failures that occur AFTER GitHub → AWS Source / CodeConnections → CodePipeline → CodeBuild during the DOWNLOAD_SOURCE step.

### Design Principles

1. **READ-ONLY** - No Terraform, no Apply, no state changes
2. **PREDICTIVE** - Check before deployment, not during
3. **DETERMINISTIC** - Same inputs produce same outputs
4. **NO SIDE EFFECTS** - Cannot corrupt or modify resources

## Framework Components

### 1. ConnectivityStatus Enum

```python
GREEN    = "GREEN"    # Check passed
YELLOW   = "YELLOW"   # Warning, proceed with caution
RED      = "RED"      # Critical failure, halt
NOT_PRESENT = "NOT_PRESENT"  # Resource doesn't exist
NOT_VERIFIED = "NOT_VERIFIED" # Cannot verify without AWS access
BLOCKED  = "BLOCKED"  # Permission denied
ERROR    = "ERROR"    # Unexpected error
```

### 2. ConnectivityCheck Dataclass

```python
@dataclass
class ConnectivityCheck:
    name: str                    # Check identifier
    status: ConnectivityStatus   # Result status
    message: Optional[str]       # Human-readable message
    details: Dict[str, Any]      # Additional details
    verification_source: Optional[str]  # Where verified
```

### 3. SourceConnectivityChecker ABC

Abstract base for implementing connectivity checks.

### 4. MaysOrdersConnectivityChecker

Implementation stub for Mays-Orders-AWS installer.

## Required Checks

| Check | Description | IAM Permissions |
|-------|-------------|-----------------|
| `aws_identity` | AWS credentials and identity available | `sts:GetCallerIdentity` |
| `aws_account_region` | Correct AWS account and region | - |
| `github_source_config` | GitHub source repository accessible | `codestarconnections:ListConnections`, `codestarconnections:DescribeConnection` |
| `codeconnections_status` | AWS CodeConnections connection valid | `codestarconnections:ListConnections`, `codestarconnections:DescribeConnection` |
| `codepipeline_source` | CodePipeline source stage configured | `codepipeline:GetPipeline`, `codepipeline:GetPipelineState`, `codepipeline:ListPipelines` |
| `codebuild_project` | CodeBuild project exists and configured | `codebuild:BatchGetProjects`, `codebuild:DescribeProjects` |
| `download_source_auth` | DOWNLOAD_SOURCE step can authenticate | `codebuild:BatchGetBuilds`, `codebuild:BatchGetBuildBatches` |

## Implementation Plan

### Phase 1: Framework (COMPLETE)

- ✅ Define data structures
- ✅ Define check requirements
- ✅ Create abstract checker
- ✅ Create stub implementation
- ✅ Create tests
- ✅ Create documentation

### Phase 2: Shell Integration

To be implemented in Mays-Orders-AWS installer:

```
Mays-Orders-AWS Installer
  ├── Identity
  ├── Validate
  ├── Source Connectivity   ← NEW
  │   ├── Check AWS Identity
  │   ├── Check Account/Region
  │   ├── Check GitHub Connection
  │   ├── Check CodeConnections
  │   ├── Check CodePipeline Source
  │   └── Check CodeBuild DOWNLOAD
  ├── Plan
  ├── Plan Destroy
  ├── State
  ├── Reports
  ├── Configuration
  └── Security Status
```

### Phase 3: AWS Integration

Implementation requires:

1. **AWS SDK** (boto3) access
2. **Appropriate IAM permissions** (see above)
3. **AWS credentials** configured

## Test Fixtures

Current implementation uses dry-run mode that returns `NOT_VERIFIED` for all checks:

| Check | Dry-Run Result |
|-------|----------------|
| aws_identity | NOT_VERIFIED |
| aws_account_region | NOT_VERIFIED |
| github_source_config | NOT_VERIFIED |
| codeconnections_status | NOT_VERIFIED |
| codepipeline_source | NOT_VERIFY |
| codebuild_project | NOT_VERIFIED |
| download_source_auth | NOT_VERIFIED |

## Integration with Dependency Checker

The source connectivity checker complements the dependency checker:

| Aspect | Dependency Checker | Source Connectivity |
|--------|-------------------|---------------------|
| Purpose | Contract/config changes | AWS connectivity |
| When | Every commit | Before deployment |
| AWS calls | No | Yes (when implemented) |
| CI integration | Pre-validate | Preflight |

## Current State

**IMPORTANT**: This is a framework-only implementation. The actual AWS API checks have NOT been implemented.

To implement actual checks, the Mays-Orders-AWS repository needs to:

1. Integrate `MaysOrdersConnectivityChecker` into installer
2. Implement each check using boto3
3. Add appropriate IAM permissions
4. Test with actual AWS resources

## Files

| File | Purpose |
|------|---------|
| `agents/source_connectivity.py` | Framework implementation |
| `tests/unit/agents/test_source_connectivity.py` | Unit tests (19 tests) |

## Limitations

1. **No AWS Integration** - Actual checks require boto3
2. **No IAM Permissions** - Dependencies defined but not used
3. **No Real Testing** - Dry-run mode only
4. **External Repository** - This is in Mays-Recruiting-Intelligence-System, not Mays-Orders-AWS

## Next Steps

1. **SOURCE-CONNECTIVITY-02** - Implement actual AWS checks in Mays-Orders-AWS
2. **SHELL-INTEGRATION-01** - Add to installer UI
3. **PERMISSION-ANALYSIS-01** - Verify IAM permissions work correctly

---

## Hard Stop

**STATUS**: YELLOW (Framework Ready)

- ✅ Framework designed (no code duplication)
- ✅ All checks documented
- ✅ Tests passing (19 tests)
- ✅ Ready for AWS implementation
- ❌ NO AWS MUTATIONS (0)
- ❌ NO TERRAFORM CHANGES (0)
- ❌ NO DEPLOYMENTS (0)