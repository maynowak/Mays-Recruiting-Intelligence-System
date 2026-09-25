"""
Tests for Source Connectivity Framework

Tests for agents/source_connectivity.py

These tests exercise the read-only framework for source connectivity
checking in the Mays-Orders-AWS installer context.

CRITICAL: NO AWS CALLS, NO NETWORK, NO FILE SYSTEM CHANGES
"""

import pytest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.source_connectivity import (
    ConnectivityStatus,
    ConnectivityCheck,
    SourceConnectivityReport,
    SourceConnectivityChecker,
    MaysOrdersConnectivityChecker,
    format_report_simple,
    format_report_json,
    CONTINUITY_REQUIREMENTS,
)


class TestConnectivityStatus:
    """Tests for connectivity status enum."""

    def test_all_statuses_exist(self):
        """All expected statuses are defined."""
        assert ConnectivityStatus.GREEN.value == "GREEN"
        assert ConnectivityStatus.YELLOW.value == "YELLOW"
        assert ConnectivityStatus.RED.value == "RED"
        assert ConnectivityStatus.NOT_PRESENT.value == "NOT_PRESENT"
        assert ConnectivityStatus.NOT_VERIFIED.value == "NOT_VERIFIED"
        assert ConnectivityStatus.BLOCKED.value == "BLOCKED"
        assert ConnectivityStatus.ERROR.value == "ERROR"

    def test_status_ordering(self):
        """Status ordering for importance."""
        # GREEN should indicate success
        # RED should indicate failure
        assert ConnectivityStatus.GREEN not in [
            ConnectivityStatus.RED,
            ConnectivityStatus.NOT_PRESENT,
            ConnectivityStatus.ERROR,
        ]


class TestConnectivityCheck:
    """Tests for ConnectivityCheck dataclass."""

    def test_create_check(self):
        """Create a connectivity check."""
        check = ConnectivityCheck(
            name="test_check",
            status=ConnectivityStatus.GREEN,
            message="Test passed",
        )
        assert check.name == "test_check"
        assert check.status == ConnectivityStatus.GREEN

    def test_check_defaults(self):
        """Check with minimal info."""
        check = ConnectivityCheck(name="minimal", status=ConnectivityStatus.GREEN)
        # Status is required, meaning required fields are name and status
        assert check.name == "minimal"


class TestSourceConnectivityReport:
    """Tests for SourceConnectivityReport."""

    def test_empty_report(self):
        """Create empty report."""
        report = SourceConnectivityReport()
        assert report.checks == []
        assert report.overall_status == ConnectivityStatus.YELLOW

    def test_report_with_checks(self):
        """Report with checks."""
        report = SourceConnectivityReport(
            checks=[
                ConnectivityCheck(name="check1", status=ConnectivityStatus.GREEN),
                ConnectivityCheck(name="check2", status=ConnectivityStatus.GREEN),
            ]
        )
        assert report.all_passed is True

    def test_report_mixed_status(self):
        """Report with mixed statuses."""
        report = SourceConnectivityReport(
            checks=[
                ConnectivityCheck(name="check1", status=ConnectivityStatus.GREEN),
                ConnectivityCheck(name="check2", status=ConnectivityStatus.RED),
            ]
        )
        assert report.all_passed is False


class TestMaysOrdersConnectivityChecker:
    """Tests for Mays-Orders-AWS connectivity checker."""

    def test_dry_run_by_default(self):
        """Dry run is default."""
        checker = MaysOrdersConnectivityChecker()
        assert checker.dry_run is True

    def test_dry_run_returns_not_verified(self):
        """Dry run returns NOT_VERIFIED for all checks."""
        checker = MaysOrdersConnectivityChecker(dry_run=True)
        report = checker.check_all()

        for check in report.checks:
            assert check.status == ConnectivityStatus.NOT_VERIFIED

    def test_checker_has_required_checks(self):
        """Checker defines required checks."""
        checker = MaysOrdersConnectivityChecker()

        expected_checks = [
            "aws_identity",
            "aws_account_region",
            "github_source_config",
            "codeconnections_status",
            "codepipeline_source",
            "codebuild_project",
            "download_source_auth",
        ]

        for check_name in expected_checks:
            assert check_name in checker.REQUIRED_CHECKS

    def test_report_format_json(self):
        """JSON report is serializable."""
        checker = MaysOrdersConnectivityChecker(dry_run=True)
        report = checker.check_all()

        json_report = format_report_json(report)

        assert "report_type" in json_report
        assert "checks" in json_report
        assert "overall_status" in json_report

        # Should be JSON serializable
        json_str = json.dumps(json_report)
        assert json_str is not None


class TestFormatReportSimple:
    """Tests for simple text report formatting."""

    def test_format_contains_status(self):
        """Formatted report contains status."""
        report = SourceConnectivityReport(
            checks=[
                ConnectivityCheck(name="test", status=ConnectivityStatus.GREEN)
            ]
        )

        text = format_report_simple(report)
        assert "SOURCE CONNECTIVITY CHECK REPORT" in text

    def test_format_contains_check_name(self):
        """Formatted report contains check names."""
        report = SourceConnectivityReport(
            checks=[
                ConnectivityCheck(name="aws_identity", status=ConnectivityStatus.GREEN)
            ]
        )

        text = format_report_simple(report)
        assert "aws_identity" in text


class TestConnectivityRequirements:
    """Tests for connectivity requirements structure."""

    def test_requirements_has_all_checks(self):
        """Requirements define all checks."""
        expected = [
            "aws_identity",
            "aws_account_region",
            "github_source_config",
            "codeconnections_status",
            "codepipeline_source",
            "codebuild_project",
            "download_source_auth",
        ]

        for check in expected:
            assert check in CONTINUITY_REQUIREMENTS

    def test_requirements_have_descriptions(self):
        """Each requirement has description."""
        for check_name, req in CONTINUITY_REQUIREMENTS.items():
            assert "description" in req
            assert req["description"] is not None

    def test_requirements_have_iam_permissions(self):
        """Some requirements have IAM permissions."""
        has_permissions = False
        for req in CONTINUITY_REQUIREMENTS.values():
            if "iam_permissions" in req:
                has_permissions = True
                break

        assert has_permissions


class TestNoAwsDependencies:
    """Verify no AWS dependencies exist in tests."""

    def test_no_aws_imports(self):
        """No boto3 or aws SDK imports."""
        import sys
        aws_modules = [m for m in sys.modules if m.startswith('boto') or 'aws' in m.lower()]
        # Should not have aws modules loaded
        assert len(aws_modules) == 0 or all(m in ['agents.source_connectivity'] for m in aws_modules)


class TestDeterminism:
    """Tests for deterministic behavior."""

    def test_same_input_same_output(self):
        """Same inputs produce same outputs."""
        checker1 = MaysOrdersConnectivityChecker(dry_run=True)
        checker2 = MaysOrdersConnectivityChecker(dry_run=True)

        report1 = checker1.check_all()
        report2 = checker2.check_all()

        assert len(report1.checks) == len(report2.checks)
        for c1, c2 in zip(report1.checks, report2.checks):
            assert c1.name == c2.name
            assert c1.status == c2.status


class TestNoSideEffects:
    """Tests to verify no side effects."""

    def test_checker_is_pure(self):
        """Checker doesn't modify state."""
        checker = MaysOrdersConnectivityChecker(dry_run=True)

        # Run multiple times
        for _ in range(5):
            checker.check_all()

        # Should produce same result
        report1 = checker.check_all()
        report2 = checker.check_all()

        assert report1.checks == report2.checks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])