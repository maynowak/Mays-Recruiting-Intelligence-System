"""Tests for the agent installation orchestrator (contract/status only)."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from installer import agent_install  # noqa: E402


MANIFEST = """schemaVersion: "1.0"
package:
  name: demo-agent
  version: "1.0.0"
agent:
  agentId: demo-agent
  capability: demo.run
source:
  sha: 0123456789abcdef0123456789abcdef01234567
versions:
  transport: "1"
  resultBody: "2.0"
compatibility:
  ordersPin: 016cdfd6ac62565dcec9a2fee78cb898fb919e59
privacy:
  contractVersion: RIS-CAPABILITY-PRIVACY/1
  contractPath: contracts/privacy.json
  sourcePaths:
    - agents/ecosystem/privacy_contract.py
  testPaths:
    - tests/test_ecosystem_privacy_contract.py
"""


class OrchestratorTest(unittest.TestCase):
    def make_package(self, root: Path, manifest: str = MANIFEST):
        pkg = root / "demo-agent"
        (pkg / "contracts").mkdir(parents=True)
        (pkg / "tests").mkdir()
        (pkg / "manifest.yaml").write_text(manifest, encoding="utf-8")
        (pkg / "contracts" / "privacy.json").write_text(json.dumps({
            "capability": "demo.run", "processing_purpose": "synthetic-test",
            "technical_inputs": ["value"], "business_inputs": [],
            "allowed_input_fields": ["value"],
            "input_field_types": [["value", "string"]],
            "prohibited_inline_categories": ["personal-data"],
            "actor_identity": "verified-runtime", "requester_identity": "verified-test",
            "tenant_identity": "verified-test-tenant",
            "authorization_requirements": ["test-only"],
            "storage_locations": ["none"], "external_recipients": [],
            "result_categories": ["number"], "order_result_disposition": "forbidden",
            "allowed_result_fields": ["number"],
            "allowed_order_result_fields": [],
            "result_field_types": [["number", "integer"]],
            "lifecycle_phases": ["execution"], "cleanup_mechanism": "no-storage",
        }), encoding="utf-8")
        (pkg / "risks.md").write_text("Stop conditions: none in test.\n",
                                      encoding="utf-8")
        (pkg / "operations.md").write_text("ops\n", encoding="utf-8")
        (pkg / "handoff.md").write_text("handoff\n", encoding="utf-8")
        (pkg / "lifecycle.yaml").write_text(
            "agentId: demo-agent\nsharedResources:\n  - q\n"
            "exclusiveResources: []\npartnerBindings:\n  - type: entitlement\n"
            "    scope: agent\nuninstall:\n  retain: true\n"
            "retention:\n  orders: retain\n  workItems: retain\n"
            "  results: retain\n", encoding="utf-8")
        (pkg / "uninstall.md").write_text("uninstall\n", encoding="utf-8")
        (pkg / "partner-bindings.md").write_text("bindings\n", encoding="utf-8")
        (pkg / "retention.md").write_text("retention\n", encoding="utf-8")
        return pkg

    def test_real_packages_are_discoverable_and_valid(self):
        packages = agent_install.discover(agent_install.DEFAULT_ROOT)
        names = {p.name for p in packages}
        self.assertEqual(
            {"ats-agent", "addition-agent", "cv-parser-agent",
             "job-parser-agent", "analysis-agent"}, names)
        for package in packages:
            info = agent_install.analyze(package)
            if package.name == "addition-agent":
                self.assertTrue(agent_install.validate(package, info)["validated"])
            else:
                with self.assertRaises(agent_install.AgentInstallError):
                    agent_install.validate(package, info)

    def test_template_is_not_discovered_as_an_agent(self):
        packages = agent_install.discover(agent_install.DEFAULT_ROOT)
        self.assertNotIn("_template", {p.name for p in packages})

    def test_stages_are_idempotent_and_resumable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(root)
            status = root / "status.json"
            first = agent_install.run_stage("validate", pkg, status)
            self.assertEqual("PASSED", first["status"])
            again = agent_install.run_stage("validate", pkg, status)
            self.assertEqual("SKIPPED", again["status"])
            data = json.loads(status.read_text(encoding="utf-8"))
            self.assertEqual("demo-agent", data["agentId"])
            self.assertIn("validate", data["stages"])

    def test_changed_package_invalidates_cached_passed_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(root)
            status = root / "status.json"
            first = agent_install.run_stage("validate", pkg, status)
            self.assertEqual("PASSED", first["status"])
            (pkg / "contracts" / "privacy.json").write_text(
                (pkg / "contracts" / "privacy.json").read_text(encoding="utf-8")
                .replace("synthetic-test", "changed-purpose"), encoding="utf-8")
            changed = agent_install.run_stage("validate", pkg, status)
            self.assertEqual("PASSED", changed["status"])
            self.assertNotEqual(first["inputFingerprint"], changed["inputFingerprint"])

    def test_apply_requires_the_separate_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(root)
            status = root / "status.json"
            with self.assertRaises(agent_install.AgentInstallError):
                agent_install.run_stage("apply", pkg, status)
            self.assertFalse(status.exists())

    def test_missing_manifest_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(root, MANIFEST.replace("capability: demo.run\n", ""))
            with self.assertRaises(agent_install.AgentInstallError):
                agent_install.analyze(pkg)

    def test_incomplete_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(root)
            (pkg / "operations.md").unlink()
            with self.assertRaises(agent_install.AgentInstallError):
                agent_install.package_check(pkg)

    def test_missing_lifecycle_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(root)
            (pkg / "retention.md").unlink()
            with self.assertRaises(agent_install.AgentInstallError):
                agent_install.package_check(pkg)

    def test_template_package_is_refused_by_run_stage(self):
        status = Path(tempfile.gettempdir()) / "template-status.json"
        self.addCleanup(lambda: status.exists() and status.unlink())
        with self.assertRaises(agent_install.AgentInstallError):
            agent_install.run_stage(
                "validate", agent_install.DEFAULT_ROOT / "_template", status)

    def test_placeholder_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = self.make_package(
                root, MANIFEST.replace(
                    "0123456789abcdef0123456789abcdef01234567",
                    "<RIS_SOURCE_SHA>"))
            info = agent_install.analyze(pkg)
            with self.assertRaises(agent_install.AgentInstallError):
                agent_install.validate(pkg, info)


if __name__ == "__main__":
    unittest.main()
