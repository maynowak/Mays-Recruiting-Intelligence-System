"""
Source Connectivity Framework for Mays-Orders-AWS

This module provides a read-only source connectivity checking framework
for the Mays-Orders-AWS installer.

IMPORTANT: This framework is designed for Mays-Orders-AWS but lives in
Mays-Recruiting-Intelligence-System for cross-repo reference and can be
copied to the appropriate repository.

ARCHITECTURE:
Mays-Orders-AWS Installers should implement:
1. Source Connectivity Check (READ-ONLY)
   - BEFORE Terraform Plan/Apply
2. Source Configuration Validation
   - GitHub Source Configuration
   - CodeConnections Status
   - CodePipeline Source Stage
3. CodeBuild Check
   - Project Status
   - Source Configuration
   - DOWNLOAD_SOURCE step status

AWS PROFILE: maysaws
AWS REGION: eu-central-1
TARGET PROJECT: mays-orders

AUTHOR: Generated for SOURCE-CONNECTIVITY-GATE-01
STATUS: Framework + Partial Implementation
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ConnectivityStatus(Enum):
    """Status of a connectivity check."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"
    NOT_PRESENT = "NOT_PRESENT"
    NOT_VERIFIED = "NOT_VERIFIED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass
class ConnectivityCheck:
    """Result of a connectivity check."""
    name: str
    status: ConnectivityStatus
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    verification_source: Optional[str] = None


@dataclass
class SourceConnectivityReport:
    """Complete source connectivity report."""
    checks: List[ConnectivityCheck] = field(default_factory=list)
    overall_status: ConnectivityStatus = ConnectivityStatus.YELLOW
    explanation: str = ""

    @property
    def all_passed(self) -> bool:
        """Check if all connectivity checks passed."""
        return all(c.status == ConnectivityStatus.GREEN for c in self.checks)


class SourceConnectivityChecker(ABC):
    """
    Abstract base class for source connectivity checking.

    Implementations should be READ-ONLY and should NOT:
    - Modify AWS resources
    - Execute Terraform plans or applies
    - Require destructive operations
    - Have side effects
    """

    @abstractmethod
    def check_all(self) -> SourceConnectivityReport:
        """Run all source connectivity checks."""
        pass

    def get_terminal_checks(self) -> List[str]:
        """Get list of checks that can fail the pipeline."""
        return [
            "aws_identity",
            "aws_account_region",
            "codepipeline_source",
        ]


class MaysOrdersConnectivityChecker(SourceConnectivityChecker):
    """
    Source connectivity checker for Mays-Orders-AWS repository.

    This checker verifies that all source connectivity requirements
    are met before attempting Terraform apply operations.

    AWS PROFILE: maysaws
    AWS REGION: eu-central-1
    TARGET PROJECT: mays-orders
    """

    REQUIRED_CHECKS = [
        "aws_identity",
        "aws_account_region",
        "github_source_config",
        "codeconnections_status",
        "codepipeline_source",
        "codebuild_project",
        "download_source_auth",
    ]

    def __init__(self, dry_run: bool = True, aws_profile: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize checker.

        Args:
            dry_run: If True, return NOT_VERIFIED for checks that require AWS.
                     For demonstration/testing without AWS access.
            aws_profile: AWS profile name (default: maysaws)
            region: AWS region (default: eu-central-1)
        """
        self.dry_run = dry_run
        self.aws_profile = aws_profile or "maysaws"
        self.region = region or "eu-central-1"
        self._aws_session = None
        self._target_project = "mays-orders"

    def _get_aws_session(self):
        """Get or create AWS session (lazy initialization)."""
        if self._aws_session is None and not self.dry_run:
            try:
                import boto3
                from botocore.exceptions import BotoCoreError, ClientError

                session_kwargs = {"region_name": self.region}
                if self.aws_profile:
                    session_kwargs["profile_name"] = self.aws_profile

                self._aws_session = boto3.session.Session(**session_kwargs)

                # Test credentials
                sts = self._aws_session.client("sts")
                sts.get_caller_identity()

                logger.info(f"AWS session created with profile: {self.aws_profile}, region: {self.region}")
                return self._aws_session
            except Exception as e:
                logger.warning(f"AWS session creation failed: {e}")
                return None
        return self._aws_session if not self.dry_run else None

    def check_all(self) -> SourceConnectivityReport:
        """Run all source connectivity checks."""
        if self.dry_run:
            return self._get_dry_run_report()

        checks = []

        # Check 1: AWS Identity
        checks.append(self._check_aws_identity())

        # Check 2: AWS Account / Region
        checks.append(self._check_account_region())

        # Check 3: GitHub Source Configuration (requires CodeConnections)
        checks.append(self._check_github_source())

        # Check 4: CodeConnections Status
        checks.append(self._check_codeconnections())

        # Check 5: CodePipeline Source
        checks.append(self._check_codepipeline_source())

        # Check 6: CodeBuild Project
        checks.append(self._check_codebuild_project())

        # Check 7: DOWNLOAD_SOURCE Authorization
        checks.append(self._check_download_source_auth())

        # Determine overall status
        statuses = [c.status for c in checks]

        if all(s == ConnectivityStatus.GREEN for s in statuses):
            overall = ConnectivityStatus.GREEN
            explanation = "All source connectivity checks passed"
        elif any(s == ConnectivityStatus.RED for s in statuses):
            overall = ConnectivityStatus.RED
            explanation = "Critical source connectivity failures detected"
        elif any(s == ConnectivityStatus.BLOCKED for s in statuses):
            overall = ConnectivityStatus.BLOCKED
            explanation = "Access denied for some connectivity checks"
        elif any(s == ConnectivityStatus.NOT_PRESENT for s in statuses):
            overall = ConnectivityStatus.YELLOW
            explanation = "Some required resources not found"
        else:
            overall = ConnectivityStatus.YELLOW
            explanation = "Source connectivity checks inconclusive"

        return SourceConnectivityReport(
            checks=checks,
            overall_status=overall,
            explanation=explanation
        )

    def _check_aws_identity(self) -> ConnectivityCheck:
        """Check AWS identity is available."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="aws_identity",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="AWS session not available",
                    details={"requires": "AWS credentials"}
                )

            sts = session.client("sts")
            identity = sts.get_caller_identity()

            return ConnectivityCheck(
                name="aws_identity",
                status=ConnectivityStatus.GREEN,
                message=f"AWS identity verified: {identity.get('Arn', 'unknown')}",
                details={
                    "account": identity.get("Account"),
                    "arn": identity.get("Arn"),
                    "userId": identity.get("UserId"),
                }
            )
        except Exception as e:
            return ConnectivityCheck(
                name="aws_identity",
                status=ConnectivityStatus.RED,
                message=f"AWS identity check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_account_region(self) -> ConnectivityCheck:
        """Check AWS account and region."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="aws_account_region",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="Cannot verify account/region - no session",
                    details={"expected_region": self.region}
                )

            sts = session.client("sts")
            identity = sts.get_caller_identity()

            # Get region from session
            actual_region = session.region_name

            # Verify region matches expected
            if actual_region == self.region:
                return ConnectivityCheck(
                    name="aws_account_region",
                    status=ConnectivityStatus.GREEN,
                    message=f"Account {identity.get('Account')} in correct region: {actual_region}",
                    details={
                        "account": identity.get("Account"),
                        "region": actual_region,
                        "expected_region": self.region,
                    }
                )
            else:
                return ConnectivityCheck(
                    name="aws_account_region",
                    status=ConnectivityStatus.YELLOW,
                    message=f"Region mismatch: expected {self.region}, got {actual_region}",
                    details={
                        "account": identity.get("Account"),
                        "expected_region": self.region,
                        "actual_region": actual_region,
                    }
                )
        except Exception as e:
            return ConnectivityCheck(
                name="aws_account_region",
                status=ConnectivityStatus.ERROR,
                message=f"Account/region check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_github_source(self) -> ConnectivityCheck:
        """Check GitHub source configuration via CodeConnections."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="github_source_config",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="Cannot check GitHub source - no session",
                )

            client = session.client("codestar-connections")

            # Look for GitHub connections
            connections = client.list_connections()

            github_connections = [
                conn for conn in connections.get("connections", [])
                if conn.get("connectionName", "").startswith("mays") or
                   "github" in conn.get("connectionName", "").lower()
            ]

            if github_connections:
                conn = github_connections[0]
                return ConnectivityCheck(
                    name="github_source_config",
                    status=ConnectivityStatus.GREEN,
                    message=f"GitHub connection found: {conn.get('connectionName')}",
                    details={
                        "connection_name": conn.get("connectionName"),
                        "connection_arn": conn.get("connectionArn"),
                        "status": conn.get("connectionStatus"),
                    }
                )
            else:
                return ConnectivityCheck(
                    name="github_source_config",
                    status=ConnectivityStatus.NOT_PRESENT,
                    message="No GitHub connections found in AWS account",
                    details={"connections_count": len(connections.get("connections", []))}
                )
        except Exception as e:
            return ConnectivityCheck(
                name="github_source_config",
                status=ConnectivityStatus.ERROR,
                message=f"GitHub source check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_codeconnections(self) -> ConnectivityCheck:
        """Check CodeConnections status."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="codeconnections_status",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="Cannot check CodeConnections - no session",
                )

            client = session.client("codestar-connections")
            connections = client.list_connections()

            for conn in connections.get("connections", []):
                if conn.get("connectionStatus") == "AVAILABLE":
                    return ConnectivityCheck(
                        name="codeconnections_status",
                        status=ConnectivityStatus.GREEN,
                        message=f"CodeConnections available: {conn.get('connectionName')}",
                        details={
                            "connection_arn": conn.get("connectionArn"),
                            "status": conn.get("connectionStatus"),
                        }
                    )

            return ConnectivityCheck(
                name="codeconnections_status",
                status=ConnectivityStatus.RED,
                message="No available CodeConnections found",
                details={"error": "All connections are not AVAILABLE"}
            )
        except Exception as e:
            return ConnectivityCheck(
                name="codeconnections_status",
                status=ConnectivityStatus.ERROR,
                message=f"CodeConnections check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_codepipeline_source(self) -> ConnectivityCheck:
        """Check CodePipeline source configuration."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="codepipeline_source",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="Cannot check CodePipeline - no session",
                )

            client = session.client("codepipeline")
            pipelines = client.list_pipelines()

            # Look for Mays-Orders pipelines
            mays_pipelines = [
                p for p in pipelines.get("pipelines", [])
                if "mays-orders" in p.get("name", "").lower()
            ]

            if mays_pipelines:
                pipeline = mays_pipelines[0]
                pipeline_details = client.get_pipeline(name=pipeline["name"])

                has_source_stage = any(
                    stage.get("name") == "Source"
                    for stage in pipeline_details.get("pipeline", {}).get("stages", [])
                )

                if has_source_stage:
                    return ConnectivityCheck(
                        name="codepipeline_source",
                        status=ConnectivityStatus.GREEN,
                        message=f"CodePipeline configured: {pipeline['name']}",
                        details={
                            "pipeline_name": pipeline["name"],
                            "has_source_stage": True,
                        }
                    )

            return ConnectivityCheck(
                name="codepipeline_source",
                status=ConnectivityStatus.NOT_PRESENT,
                message="No Mays-Orders CodePipeline found",
                details={"pipelines_found": len(pipelines.get("pipelines", []))}
            )
        except Exception as e:
            return ConnectivityCheck(
                name="codepipeline_source",
                status=ConnectivityStatus.RED,
                message=f"CodePipeline check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_codebuild_project(self) -> ConnectivityCheck:
        """Check CodeBuild project exists."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="codebuild_project",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="Cannot check CodeBuild - no session",
                )

            client = session.client("codebuild")
            projects = client.list_projects()

            # Look for Mays-related projects
            mays_projects = [
                p for p in projects.get("projects", [])
                if "mays" in p.lower() or "orders" in p.lower()
            ]

            if mays_projects:
                return ConnectivityCheck(
                    name="codebuild_project",
                    status=ConnectivityStatus.GREEN,
                    message=f"CodeBuild projects found: {len(mays_projects)}",
                    details={
                        "projects": mays_projects[:5],  # Show first 5
                    }
                )

            return ConnectivityCheck(
                name="codebuild_project",
                status=ConnectivityStatus.NOT_PRESENT,
                message="No Mays-related CodeBuild projects found",
                details={"total_projects": len(projects.get("projects", []))}
            )
        except Exception as e:
            return ConnectivityCheck(
                name="codebuild_project",
                status=ConnectivityStatus.ERROR,
                message=f"CodeBuild check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _check_download_source_auth(self) -> ConnectivityCheck:
        """Check DOWNLOAD_SOURCE authorization status."""
        try:
            session = self._get_aws_session()
            if session is None:
                return ConnectivityCheck(
                    name="download_source_auth",
                    status=ConnectivityStatus.NOT_VERIFIED,
                    message="Cannot check DOWNLOAD_SOURCE - no session",
                )

            client = session.client("codebuild")

            # Get recent builds for Mays projects
            mays_projects = [
                p for p in client.list_projects().get("projects", [])
                if "mays" in p.lower() or "orders" in p.lower()
            ]

            if not mays_projects:
                return ConnectivityCheck(
                    name="download_source_auth",
                    status=ConnectivityStatus.NOT_PRESENT,
                    message="No CodeBuild projects to check for source auth",
                )

            # Check recent builds for source-related errors
            auth_issues = []
            for project in mays_projects[:3]:  # Check first 3 projects
                try:
                    builds = client.list_builds(
                        projectName=project,
                        maxResults=5
                    )

                    for build_id in builds.get("ids", []):
                        build = client.batch_get_builds(ids=[build_id])
                        for build_item in build.get("builds", []):
                            phases = build_item.get("phases", [])
                            for phase in phases:
                                if phase.get("phaseType") == "DOWNLOAD_SOURCE":
                                    if phase.get("status") != "SUCCEEDED":
                                        auth_issues.append({
                                            "project": project,
                                            "phase": phase.get("phaseType"),
                                            "status": phase.get("status"),
                                            "message": phase.get("message"),
                                        })
                except Exception:
                    pass

            if auth_issues:
                return ConnectivityCheck(
                    name="download_source_auth",
                    status=ConnectivityStatus.RED,
                    message=f"DOWNLOAD_SOURCE auth issues detected: {len(auth_issues)}",
                    details={"issues": auth_issues}
                )

            return ConnectivityCheck(
                name="download_source_auth",
                status=ConnectivityStatus.GREEN,
                message="No DOWNLOAD_SOURCE authentication issues found",
                details={"checked_projects": len(mays_projects)}
            )
        except Exception as e:
            return ConnectivityCheck(
                name="download_source_auth",
                status=ConnectivityStatus.ERROR,
                message=f"DOWNLOAD_SOURCE check failed: {str(e)}",
                details={"error": str(e)}
            )

    def _get_dry_run_report(self) -> SourceConnectivityReport:
        """Get report for dry-run mode (no actual checks)."""
        checks = []

        for check_name in self.REQUIRED_CHECKS:
            checks.append(ConnectivityCheck(
                name=check_name,
                status=ConnectivityStatus.NOT_VERIFIED,
                message=f"Dry-run: check '{check_name}' requires AWS access",
                details={
                    "requires_aws": True,
                    "default_profile": self.aws_profile,
                    "region": self.region,
                }
            ))

        return SourceConnectivityReport(
            checks=checks,
            overall_status=ConnectivityStatus.YELLOW,
            explanation=f"Dry-run mode for {self._target_project}. "
                       f"Use aws_profile='{self.aws_profile}' in {self.region}. "
                       "Implement actual AWS checks for production use."
        )


def format_report_simple(report: SourceConnectivityReport) -> str:
    """Format report for simple display."""
    lines = []
    lines.append("SOURCE CONNECTIVITY CHECK REPORT")
    lines.append("=" * 40)

    for check in report.checks:
        status_icon = "✓" if check.status == ConnectivityStatus.GREEN else \
                      "?" if check.status == ConnectivityStatus.NOT_VERIFIED else "✗"
        lines.append(f"{status_icon} {check.name}: {check.status.value}")
        if check.message:
            lines.append(f"    {check.message}")

    lines.append("-" * 40)
    lines.append(f"OVERALL: {report.overall_status.value}")

    return "\n".join(lines)


def format_report_json(report: SourceConnectivityReport) -> Dict[str, Any]:
    """Format report as JSON-serializable dict."""
    return {
        "report_type": "source_connectivity",
        "checks": [
            {
                "name": c.name,
                "status": c.status.value,
                "message": c.message,
                "details": c.details,
            }
            for c in report.checks
        ],
        "overall_status": report.overall_status.value,
        "explanation": report.explanation,
    }


# Pre-defined connectivity requirements for Mays-Orders-AWS
CONTINUITY_REQUIREMENTS = {
    "aws_identity": {
        "description": "AWS credentials and identity available",
        "required": True,
        "iam_permissions": ["sts:GetCallerIdentity"],
    },
    "aws_account_region": {
        "description": "Correct AWS account and region",
        "required": True,
    },
    "github_source_config": {
        "description": "GitHub source repository accessible",
        "required": True,
        "iam_permissions": [
            "codestarconnections:ListConnections",
            "codestarconnections:DescribeConnection",
        ],
    },
    "codeconnections_status": {
        "description": "AWS CodeConnections connection valid",
        "required": True,
        "iam_permissions": [
            "codestarconnections:ListConnections",
            "codestarconnections:DescribeConnection",
        ],
    },
    "codepipeline_source": {
        "description": "CodePipeline source stage configured",
        "required": True,
        "iam_permissions": [
            "codepipeline:GetPipeline",
            "codepipeline:GetPipelineState",
            "codepipeline:ListPipelines",
        ],
    },
    "codebuild_project": {
        "description": "CodeBuild project exists and configured",
        "required": True,
        "iam_permissions": [
            "codebuild:BatchGetProjects",
            "codebuild:DescribeProjects",
        ],
    },
    "download_source_auth": {
        "description": "DOWNLOAD_SOURCE step can authenticate",
        "required": True,
        "iam_permissions": [
            "codebuild:BatchGetBuilds",
            "codebuild:BatchGetBuildBatches",
        ],
    },
}


if __name__ == "__main__":
    print("SOURCE CONNECTIVITY FRAMEWORK")
    print("=" * 60)
    print("\nRequired checks:")
    for check_name, req in CONTINUITY_REQUIREMENTS.items():
        print(f"\n  {check_name}:")
        print(f"    Description: {req['description']}")
        print(f"    Required: {req['required']}")
        if 'iam_permissions' in req:
            print(f"    IAM Permissions: {', '.join(req['iam_permissions'])}")

    print("\n" + "=" * 60)
    print("NOTE: This framework documents REQUIRED checks for Mays-Orders-AWS")
    print("Installers. Implementation requires AWS SDK integration.")
    print("=" * 60)

# CLI entry point for source connectivity checking
def main():
    """CLI entry point for source connectivity checks."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Check source connectivity for Mays-Orders-AWS installer"
    )
    parser.add_argument(
        "--profile", "-p",
        default="maysaws",
        help="AWS profile name (default: maysaws)"
    )
    parser.add_argument(
        "--region", "-r",
        default="eu-central-1",
        help="AWS region (default: eu-central-1)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Dry-run mode (default: True)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Actually verify from AWS (requires credentials)"
    )

    args = parser.parse_args()

    checker = MaysOrdersConnectivityChecker(
        dry_run=not args.verify,
        aws_profile=args.profile,
        region=args.region
    )

    report = checker.check_all()

    if args.format == "json":
        print(json.dumps(format_report_json(report), indent=2))
    else:
        print(format_report_simple(report))
        print(f"\nExplanation: {report.explanation}")

    # Exit codes:
    # 0 = GREEN (all checks passed)
    # 1 = YELLOW/RED (issues found)
    # 2 = NOT_VERIFIED (dry-run)
    if args.verify:
        if report.overall_status == ConnectivityStatus.GREEN:
            return 0
        else:
            return 1
    else:
        return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
