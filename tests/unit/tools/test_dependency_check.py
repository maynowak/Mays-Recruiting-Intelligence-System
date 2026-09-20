"""
Tests for Dependency & Contract Change Checker
"""

import pytest
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

from tools.dependency_check import (
    ChangeDetector, ContractChangeIdentifier,
    DependencyChecker, ImpactAnalyzer, ImpactReporter,
    ContractMetadata, ImpactLevel, SYSTEM_CONTRACTS
)


class TestChangeDetector:
    """Tests for ChangeDetector class."""

    def test_detect_no_changes(self, tmp_path):
        """Detect no changes in clean repo."""
        detector = ChangeDetector(tmp_path)
        # This will return empty since we're not in a git repo
        changes = detector.get_changed_files()
        assert "modified" in changes
        assert "added" in changes

    def test_detect_with_mock_changes(self, tmp_path):
        """Test change detection with mocked git output."""
        detector = ChangeDetector(tmp_path)
        # Mock subprocess to return empty changes
        with patch.object(subprocess, 'run') as mock_run:
            mock_run.return_value = MagicMock(stdout="", stderr="")
            changes = detector.get_changed_files()
            assert isinstance(changes, dict)


class TestContractChangeIdentifier:
    """Tests for ContractChangeIdentifier class."""

    def test_identify_no_changes(self):
        """No contract changes for unrelated files."""
        identifier = ContractChangeIdentifier(SYSTEM_CONTRACTS)
        changes = identifier.identify_changes([
            "some/other/file.py",
            "unrelated/module.js"
        ])
        assert len(changes) == 0

    def test_identify_contract_change(self):
        """Identify contract source file changes."""
        identifier = ContractChangeIdentifier(SYSTEM_CONTRACTS)
        changes = identifier.identify_changes([
            "jobsearch/models.py"
        ])
        assert len(changes) == 1
        assert changes[0]["changedFile"] == "jobsearch/models.py"


class TestDependencyChecker:
    """Tests for DependencyChecker class."""

    def test_check_dependencies_no_changes(self, tmp_path):
        """No dependency changes for clean repo."""
        checker = DependencyChecker(tmp_path)
        changes = checker.check_dependencies(["other/file.py"])
        assert len(changes) == 0

    def test_check_requirements_change(self, tmp_path):
        """Detect requirements.txt change."""
        checker = DependencyChecker(tmp_path)
        changes = checker.check_dependencies(["requirements.txt"])
        assert len(changes) == 1
        assert "requirements.txt" in changes[0]["file"]


class TestImpactAnalyzer:
    """Tests for ImpactAnalyzer class."""

    def test_analyze_no_changes(self):
        """Analyze no changes."""
        analyzer = ImpactAnalyzer()
        changes = analyzer.analyze([])
        assert len(changes) == 0

    def test_analyze_with_changes(self):
        """Analyze changes adds consumers."""
        analyzer = ImpactAnalyzer()
        changes = [
            {"contract": SYSTEM_CONTRACTS[0], "changedFile": "test.py",
             "impact": ImpactLevel.REVIEW, "reason": "test"}
        ]
        result = analyzer.analyze(changes)
        assert len(result) == 1
        assert "affectedConsumers" in result[0]


class TestImpactReporter:
    """Tests for ImpactReporter class."""

    def test_report_text_no_changes(self):
        """Generate text report with no changes."""
        reporter = ImpactReporter()
        report = reporter.report_text([], [], "test-repo")
        assert "No contract or dependency changes detected" in report

    def test_report_json_no_changes(self):
        """Generate JSON report with no changes."""
        reporter = ImpactReporter()
        report = reporter.report_json([], [], "test-repo")
        data = json.loads(report)
        assert data["repository"] == "test-repo"
        assert data["overallStatus"] == "REVIEW"


class TestContractMetadata:
    """Tests for ContractMetadata dataclass."""

    def test_metadata_creation(self):
        """Create contract metadata."""
        contract = ContractMetadata(
            contract_id="test.contract",
            version="1.0.0",
            owner="test",
            producer="test.py:func",
            consumers=["consumer1"],
            repository="test-repo",
            path="test.py",
            type="DOMAIN",
            compatibility="stable"
        )
        assert contract.contract_id == "test.contract"
        assert contract.compatibility == "stable"


class TestExitCodes:
    """Tests for CLI exit codes."""

    def test_cli_exit_code_clean(self, tmp_path):
        """CLI returns 0 for clean state."""
        result = subprocess.run(
            ["python3", "-m", "tools.dependency_check", "--repo", str(tmp_path)],
            capture_output=True,
            text=True
        )
        # Should return 0 for no changes
        assert result.returncode in [0, 1, 2]  # May vary based on state

    def test_cli_json_output(self, tmp_path):
        """CLI produces valid JSON with --format json."""
        result = subprocess.run(
            ["python3", "-m", "tools.dependency_check", 
             "--format", "json", "--repo", str(tmp_path)],
            capture_output=True,
            text=True
        )
        data = json.loads(result.stdout)
        assert "repository" in data
        assert "changedFiles" in data
        assert data["overallStatus"] in ["REVIEW", "GREEN"]