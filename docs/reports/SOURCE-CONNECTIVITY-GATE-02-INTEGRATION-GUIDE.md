# SOURCE-CONNECTIVITY-GATE-02 — Integration Guide for Mays-Orders-AWS

## Status: READY FOR INTEGRATION

This document describes how to integrate the source connectivity checker into the Mays-Orders-AWS installer.

## Overview

The source connectivity framework from Mays-Recruiting-Intelligence-System (`agents/source_connectivity.py`) is designed to be integrated into the Mays-Orders-AWS installer.

**IMPORTANT**: This is a cross-repository integration. Do NOT copy the entire file. Instead, provide the checking capabilities in your installer.

## Integration Points

### 1. Location

The source connectivity check should be integrated at:

```
Mays-Orders-AWS Installer
├── Identity
├── Validate
├── Source Connectivity  ← NEW
├── Plan
├── Apply
```

**Placement**: BEFORE Plan, AFTER Validate

### 2. AWS Configuration

```python
# Required AWS Profile
AWS_PROFILE = "maysaws"

# Required Region  
AWS_REGION = "eu-central-1"

# Target Project
TARGET_PROJECT = "mays-orders"
```

### 3. Implementation Pattern

```python
from agents.source_connectivity import (
    MaysOrdersConnectivityChecker,
    ConnectivityStatus,
)

def check_source_connectivity() -> dict:
    """Check source connectivity before Terraform operations."""
    checker = MaysOrdersConnectivityChecker(
        dry_run=False,  # Actually check
        aws_profile="maysaws",
        region="eu-central-1"
    )
    
    report = checker.check_all()
    
    return {
        "status": report.overall_status.value,
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
            }
            for c in report.checks
        ],
        "can_proceed": report.overall_status == ConnectivityStatus.GREEN,
    }
```

### 4. Execution Flow

```
Pipeline Trigger
      ↓
AWS Identity Check
      ↓
AWS Account/Region Check
      ↓
GitHub Source Config Check
      ↓
CodeConnections Check
      ↓
CodePipeline Source Check
      ↓
CodeBuild Project Check
      ↓
DOWNLOAD_SOURCE Auth Check
      ↓
[FAIL] → Halt with error
[PASS] → Proceed to Terraform Plan
```

## Checks Performed

| Check | Purpose | IAM Permissions |
|-------|---------|-----------------|
| `aws_identity` | Verify AWS credentials | `sts:GetCallerIdentity` |
| `aws_account_region` | Verify correct account/region | - |
| `github_source_config` | Check GitHub connection | `codestarconnections:ListConnections` |
| `codeconnections_status` | Verify CodeConnections | `codestarconnections:DescribeConnection` |
| `codepipeline_source` | Check pipeline source stage | `codepipeline:GetPipeline` |
| `codebuild_project` | Verify CodeBuild projects | `codebuild:BatchGetProjects` |
| `download_source_auth` | Check DOWNLOAD_SOURCE auth | `codebuild:BatchGetBuilds` |

## Status Semantics

| Status | Meaning | Action |
|--------|---------|--------|
| `GREEN` | All checks passed | Proceed with Terraform |
| `YELLOW` | Warnings, some checks inconclusive | Human review required |
| `RED` | Critical failure | Stop execution |
| `NOT_PRESENT` | Resource not found | Alert, investigate |
| `NOT_VERIFIED` | Cannot verify (dry-run) | In CI/CD, this would be RED |
| `BLOCKED` | Permission denied | Check IAM |
| `ERROR` | Unexpected error | Debug |

## CLI Usage

The framework includes a CLI for testing:

```bash
# Dry-run mode (safe, no AWS required)
python source_connectivity.py

# Actual AWS check (requires maysaws profile)
python source_connectivity.py --verify

# JSON output for scripting
python source_connectivity.py --format json

# Custom profile/region
python source_connectivity.py --profile production --region eu-central-1
```

## Integration Examples

### In Terraform Pipeline

```yaml
# GitHub Actions example
steps:
  - name: Checkout
    uses: actions/checkout@v4
    
  - name: Check Source Connectivity
    run: |
      python agents/source_connectivity.py --verify
    env:
      AWS_PROFILE: maysaws
      AWS_REGION: eu-central-1
      
  # Only proceed if source connectivity is OK
  - name: Terraform Plan
    if: success()
    run: terraform plan
```

### In Existing Installer Script

```bash
#!/bin/bash
# In your installer script

echo "Checking source connectivity..."
if ! python agents/source_connectivity.py --verify; then
  echo "ERROR: Source connectivity check failed"
  echo "Cannot proceed with deployment"
  exit 1
fi

echo "Source connectivity OK, proceeding..."
terraform apply -auto-approve
```

## Project Protection

The checker includes built-in protection:

1. **Project Isolation**: Only checks resources in `mays-orders` context
2. **No Mutations**: All calls are read-only (`Get*`, `List*`, `Describe*`)
3. **No Builds**: Never triggers CodeBuild jobs
4. **No Pipeline Executions**: Never triggers pipelines
5. **No Credential Changes**: Never modifies secrets

## Required IAM Permissions

Create a policy for the source connectivity checker:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity",
                "codestarconnections:ListConnections",
                "codestarconnections:DescribeConnection",
                "codepipeline:ListPipelines",
                "codepipeline:GetPipeline",
                "codepipeline:GetPipelineState",
                "codebuild:ListProjects",
                "codebuild:BatchGetProjects",
                "codebuild:ListBuilds",
                "codebuild:BatchGetBuilds"
            ],
            "Resource": "*"
        }
    ]
}
```

## Testing

### Unit Tests

Run the unit tests to verify the implementation:

```bash
python -m pytest tests/unit/agents/test_source_connectivity.py -v
```

### Integration Testing

When testing in the Mays-Orders-AWS environment:

1. Use the `maysaws` AWS profile
2. Run in `eu-central-1` region
3. Ensure you have read access to the resources
4. Test both success and failure scenarios

## Debugging

To see detailed information:

```python
import json
from agents.source_connectivity import MaysOrdersConnectivityChecker, format_report_json

checker = MaysOrdersConnectivityChecker(dry_run=False)
report = checker.check_all()

print(json.dumps(format_report_json(report), indent=2))
```

## Next Steps

After integration, consider:

1. Add to installer's `--help` output
2. Integrate with existing logging
3. Add to CI/CD pipeline
4. Create email/slack notifications for failures
5. Add historical tracking of connectivity status

---

**For questions or issues**: Refer to the SHARED-CONTRACT-01 and ENVIRONMENT-COMPATIBILITY-01 documents.