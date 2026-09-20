#!/usr/bin/env python3
"""
Dependency & Contract Change Checker

Detects and analyzes contract/dependency changes, identifies affected
consumers, and produces impact reports.

Usage:
    python dependency_check.py [--base REF] [--format text|json] [--changed-only]
"""

import json
import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class ImpactLevel(Enum):
    NONE = "NONE"
    LOW = "LOW"
    REVIEW = "REVIEW"
    BREAKING = "BREAKING"
    UNKNOWN = "UNKNOWN"


@dataclass
class ContractMetadata:
    """Metadata for a shared contract."""
    contract_id: str
    version: str
    owner: str
    producer: str
    consumers: List[str]
    repository: str
    path: str
    type: str
    compatibility: str


SYSTEM_CONTRACTS = [
    ContractMetadata(
        contract_id="canonical.job",
        version="1.0.0",
        owner="jobsearch",
        producer="jobsearch/models.py:Job",
        consumers=["agent/orders"],
        repository="Mays-Recruiting-Intelligence-System",
        path="jobsearch/models.py",
        type="DOMAIN",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="agent.descriptor",
        version="1.0.0",
        owner="agents.ecosystem",
        producer="agents/ecosystem/registry.py:AgentDescriptor",
        consumers=["agents/ecosystem/discovery.py", "lambda/handler.py"],
        repository="Mays-Recruiting-Intelligence-System",
        path="agents/ecosystem/registry.py",
        type="DOMAIN",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="jobsearch.api",
        version="1.0.0",
        owner="lambda",
        producer="lambda/handler.py",
        consumers=["frontend"],
        repository="Mays-Recruiting-Intelligence-System",
        path="lambda/handler.py",
        type="HTTP",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="work.item",
        version="1.0.0",
        owner="lambda",
        producer="lambda/handler.py:_create_work",
        consumers=["sqs.worker"],
        repository="Mays-Recruiting-Intelligent-System",
        path="lambda/handler.py",
        type="WORK",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="user.context",
        version="1.0.0",
        owner="lambda",
        producer="lambda/handler.py:_extract_user_context",
        consumers=["all handlers"],
        repository="Mays-Recruiting-Intelligence-System",
        path="lambda/handler.py",
        type="DOMAIN",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="jobsearch.domain",
        version="1.0.0",
        owner="jobsearch.domain_models",
        producer="jobsearch/domain_models.py:JobSearch",
        consumers=["jobsearch/repository.py", "lambda/handler.py"],
        repository="Mays-Recruiting-Intelligence-System",
        path="jobsearch/domain_models.py",
        type="DOMAIN",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="ats.search.profile",
        version="1.0.0",
        owner="jobsearch.domain_models",
        producer="jobsearch/domain_models.py:ATSSearchProfile",
        consumers=["jobsearch/repository.py"],
        repository="Mays-Recruiting-Intelligence-System",
        path="jobsearch/domain_models.py",
        type="DOMAIN",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="search.configuration",
        version="1.0.0",
        owner="jobsearch.domain_models",
        producer="jobsearch/domain_models.py:SearchConfiguration",
        consumers=["jobsearch/repository.py"],
        repository="Mays-Recruiting-Intelligence-System",
        path="jobsearch/domain_models.py",
        type="DOMAIN",
        compatibility="stable"
    ),
    ContractMetadata(
        contract_id="ats.registry",
        version="1.0.0",
        owner="agents.ats_agent",
        producer="agents/ats_agent/registry.py",
        consumers=["lambda/handler.py"],
        repository="Mays-Recruiting-Intelligence-System",
        path="agents/ats_agent/registry.py",
        type="DOMAIN",
        compatibility="stable"
    )
]


class ChangeDetector:
    """Detects git changes in the repository."""

    def __init__(self, repository_path: Path = None):
        self.repo_path = repository_path or Path(__file__).parent.parent

    def get_changed_files(self, base_ref: str = None) -> Dict[str, List[str]]:
        """Get changed files categorized by change type."""
        result = {"modified": [], "added": [], "deleted": [], "untracked": []}

        try:
            # Get git status
            status_output = subprocess.run(
                ["git", "status", "--short"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )

            for line in status_output.stdout.strip().split("\n"):
                if not line:
                    continue
                status, file = line.split(" ", 1)
                if status == " M":
                    result["modified"].append(file)
                elif status == "A  ":
                    result["added"].append(file)
                elif status == "D ":
                    result["deleted"].append(file)
                elif status.startswith("??"):
                    result["untracked"].append(file)

            # Get staged changes
            staged_output = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )

            for file in staged_output.stdout.strip().split("\n"):
                if file and file not in result["modified"]:
                    result["modified"].append(file)

        except Exception as e:
            print(f"Error detecting changes: {e}", file=sys.stderr)

        return result


class ContractChangeIdentifier:
    """Identifies which contracts are affected by changed files."""

    def __init__(self, contracts: List[ContractMetadata]):
        self.contracts = {c.path: c for c in contracts}

    def identify_changes(self, changed_files: List[str]) -> List[Dict[str, Any]]:
        """Identify which contracts are affected by the changes."""
        changes = []

        for file in changed_files:
            if file in self.contracts:
                contract = self.contracts[file]
                changes.append({
                    "contract": contract,
                    "changedFile": file,
                    "impact": ImpactLevel.REVIEW,
                    "reason": "File is a contract source"
                })

        return changes


class ConsumerResolver:
    """Resolves consumers for affected contracts."""

    def get_consumers(self, contract: ContractMetadata) -> List[str]:
        """Get all consumers of a contract."""
        return contract.consumers


class DependencyChecker:
    """Checks for dependency changes in the repository."""

    def __init__(self, repository_path: Path = None):
        self.repo_path = repository_path or Path(__file__).parent.parent
        self.requirements_files = [
            "requirements.txt",
            "pyproject.toml",
            "setup.py"
        ]

    def check_dependencies(self, changed_files: List[str]) -> List[Dict[str, Any]]:
        """Check for dependency-related changes."""
        changes = []

        for req_file in self.requirements_files:
            req_path = self.repo_path / req_file
            if any(req_file in f for f in changed_files):
                changes.append({
                    "type": "dependency",
                    "file": str(req_path),
                    "impact": ImpactLevel.REVIEW,
                    "reason": "Dependency manifest changed"
                })

        return changes


class ImpactAnalyzer:
    """Analyzes impact of contract changes."""

    def analyze(self, contract_changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze impact of contract changes."""
        for change in contract_changes:
            contract = change["contract"]
            change["affectedConsumers"] = contract.consumers
            change["impact"] = ImpactLevel.REVIEW

        return contract_changes


class ImpactReporter:
    """Generates impact reports."""

    def report_text(self, changes: List[Dict[str, Any]], deps: List[Dict[str, Any]],
                   repository: str) -> str:
        """Generate text report."""
        lines = [
            "DEPENDENCY CHECK",
            "----------------",
            "",
            f"Repository: {repository}",
            ""
        ]

        if not changes and not deps:
            lines.append("No contract or dependency changes detected.")
            return "\n".join(lines)

        if changes:
            lines.append("Contract impact:")
            for change in changes:
                lines.append(f"")
                lines.append(f"  {change['contract'].contract_id}")
                lines.append(f"    Changed: {change['changedFile']}")
                lines.append(f"    Consumers: {', '.join(change.get('affectedConsumers', []))}")
                lines.append(f"    Impact: {change['impact'].value}")
                lines.append(f"    Reason: {change['reason']}")

        if deps:
            lines.append("")
            lines.append("Dependency impact:")
            for dep in deps:
                lines.append(f"")
                lines.append(f"  {dep['file']}")
                lines.append(f"    Impact: {dep['impact'].value}")
                lines.append(f"    Reason: {dep['reason']}")

        lines.append("")
        lines.append("Overall: REVIEW")

        return "\n".join(lines)

    def report_json(self, changes: List[Dict[str, Any]], deps: List[Dict[str, Any]],
                   repository: str) -> str:
        """Generate JSON report."""
        result = {
            "repository": repository,
            "changedFiles": [],
            "contractChanges": [],
            "dependencyChanges": deps,
            "consumerImpacts": [],
            "overallStatus": "REVIEW"
        }

        for change in changes:
            result["changedFiles"].append(change["changedFile"])
            result["contractChanges"].append({
                "contract": change["contract"].contract_id,
                "changedFile": change["changedFile"],
                "affectedConsumers": change.get("affectedConsumers", []),
                "impact": change["impact"].value,
                "reason": change["reason"]
            })
            result["consumerImpacts"].append({
                "contract": change["contract"].contract_id,
                "consumers": change.get("affectedConsumers", [])
            })

        if changes or deps:
            result["overallStatus"] = "REVIEW"

        return json.dumps(result, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Check for dependency and contract changes"
    )
    parser.add_argument(
        "--base", "-b",
        help="Base ref to compare against (default: current state)"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Only show changed contracts"
    )
    parser.add_argument(
        "--repo", "-r",
        help="Repository path (default: current directory)"
    )

    args = parser.parse_args()

    repo_path = Path(args.repo) if args.repo else Path(__file__).parent.parent

    # Detect changes
    detector = ChangeDetector(repo_path)
    changes = detector.get_changed_files(args.base)

    all_changed = (
        changes["modified"] + 
        changes["added"] + 
        changes["deleted"]
    )

    # Identify contract changes
    identifier = ContractChangeIdentifier(SYSTEM_CONTRACTS)
    contract_changes = identifier.identify_changes(all_changed)

    # Check dependencies
    dep_checker = DependencyChecker(repo_path)
    dep_changes = dep_checker.check_dependencies(all_changed)

    # Analyze impact
    analyzer = ImpactAnalyzer()
    analyzed_changes = analyzer.analyze(contract_changes)

    # Generate report
    reporter = ImpactReporter()

    if args.format == "json":
        print(reporter.report_json(
            analyzed_changes, dep_changes, str(repo_path.name)
        ))
    else:
        print(reporter.report_text(
            analyzed_changes, dep_changes, str(repo_path.name)
        ))

    # Exit codes
    if any(c["impact"] == ImpactLevel.BREAKING for c in analyzed_changes):
        return 2
    elif any(c["impact"] == ImpactLevel.REVIEW for c in analyzed_changes):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())