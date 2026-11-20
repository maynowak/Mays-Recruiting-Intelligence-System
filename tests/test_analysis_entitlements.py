"""RIS-ANALYSIS-READINESS-09 STEP C — entitlements, catalog and privacy gates.

Static checks only: the configuration must stay approval-gated, the purpose must
stay DRAFT and no consent/entitlement/activation may be granted implicitly.
"""

import os
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "agent-installations", "analysis-agent")


def load(name):
    with open(os.path.join(PACKAGE, name), encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def read(relative):
    with open(os.path.join(ROOT, relative), encoding="utf-8") as handle:
        return handle.read()


class EntitlementConfigTest(unittest.TestCase):
    def setUp(self):
        self.config = load("entitlements.yaml")

    def test_partner_and_agent_identity(self):
        self.assertEqual("analysis-agent", self.config["agentId"])
        self.assertEqual("ris-internal", self.config["partner"]["partnerId"])
        self.assertEqual("ris-internal-analysis",
                         self.config["partner"]["applicationId"])
        self.assertEqual("analysis-agent", self.config["partner"]["agentId"])

    def test_nothing_is_granted_or_activated(self):
        self.assertEqual("PENDING_APPROVAL", self.config["status"])
        self.assertFalse(self.config["activation"])
        grants = self.config["entitlements"]
        self.assertEqual("explicit-approval-only", grants["grantPolicy"])
        self.assertFalse(grants["autoGrant"])
        self.assertFalse(grants["inheritExistingConsents"])
        self.assertEqual([], grants["grants"])

    def test_all_analysis_capabilities_are_declared(self):
        ids = {entry["id"] for entry in
               self.config["entitlements"]["capabilities"]}
        self.assertEqual({"parse.cv", "parse.job", "analyze.job",
                          "compare.tags"}, ids)
        for entry in self.config["entitlements"]["capabilities"]:
            self.assertEqual("analysis-processing", entry["consentPurpose"])
            self.assertEqual("1.0", entry["consentVersion"])

    def test_consent_stays_draft(self):
        consent = self.config["consent"]
        self.assertEqual("analysis-processing", consent["purpose"])
        self.assertEqual("1.0", consent["version"])
        self.assertEqual("DRAFT", consent["state"])
        self.assertFalse(consent["grantable"])
        self.assertEqual("", consent["legalApprovalRef"])
        self.assertFalse(consent["extendExistingPurposes"])

    def test_all_approvals_are_pending(self):
        approvals = {item["id"]: item
                     for item in self.config["approvalsRequired"]}
        self.assertEqual({
            "legal-notice-approval", "operator-entitlement-approval",
            "terraform-apply-approval", "catalog-seed-approval"}, set(approvals))
        for item in approvals.values():
            self.assertEqual("PENDING", item["status"])
            self.assertTrue(item["evidence"])

    def test_catalog_and_public_endpoint_are_off(self):
        self.assertEqual("ABSENT", self.config["catalog"]["visibility"])
        self.assertIsNone(self.config["catalog"]["seed"])
        self.assertFalse(self.config["runtime"]["publicEndpoint"])
        self.assertFalse(self.config["runtime"]["sharedTransportPolicy"])


class InstallManifestGateTest(unittest.TestCase):
    def test_manifest_is_not_active(self):
        manifest = load("manifest.yaml")
        self.assertEqual("pending-approval", manifest["package"]["status"])
        self.assertFalse(manifest["runtime"]["publicEndpoint"])
        self.assertFalse(manifest["runtime"]["sharedTransportPolicy"])
        self.assertEqual("agents/parsers/lambda_adapter.py",
                         manifest["runtime"]["modes"]["lambda"])

    def test_lifecycle_is_activation_gated(self):
        lifecycle = load("lifecycle.yaml")
        activation = lifecycle["lifecycle"]
        self.assertEqual("PENDING_APPROVAL", activation["activation"])
        self.assertEqual("ABSENT", lifecycle["discovery"]["visibility"])
        self.assertIn("catalog-seed-approval",
                      activation["approvalsRequired"])

    def test_installer_still_discovers_and_validates_the_package(self):
        import installer.agent_install as agent_install

        packages = {p.name: p for p in
                    agent_install.discover(agent_install.DEFAULT_ROOT)}
        package = packages["analysis-agent"]
        info = agent_install.analyze(package)
        self.assertTrue(agent_install.validate(package, info)["validated"])


class PrivacyContractTest(unittest.TestCase):
    def test_purpose_registry_stays_draft(self):
        from jobsearch.consent_contract import (
            CONSENT_PURPOSES,
            NOTICE_DRAFT,
            NOTICE_REGISTRY,
            NOTICE_ACTIVE,
            NOTICE_APPROVED,
        )

        self.assertEqual({"1.0"}, set(CONSENT_PURPOSES["analysis-processing"]))
        entry = NOTICE_REGISTRY["analysis-processing"]["1.0"]
        self.assertEqual(NOTICE_DRAFT, entry.state)
        self.assertNotIn(entry.state, (NOTICE_APPROVED, NOTICE_ACTIVE))
        self.assertEqual("", entry.legal_approval_ref)
        # Existing purposes do not authorize analysis.
        for purpose in ("application-storage", "cv-storage",
                        "search-profile-storage"):
            self.assertNotIn("analysis-processing",
                             CONSENT_PURPOSES[purpose])

    def test_draft_notice_and_pack_mark_legal_review(self):
        notice = read("docs/privacy/ANALYSIS-PROCESSING-NOTICE-DRAFT.md")
        pack = read("docs/privacy/ANALYSIS-PROCESSING-APPROVAL-PACK.md")
        for body in (notice, pack):
            self.assertIn("DRAFT", body)
            self.assertIn("REVIEW REQUIRED", body)
            self.assertIn("withdraw", body.lower())
            self.assertIn("erasure", body.lower())
        self.assertIn("PENDING", pack)
        self.assertIn("legal_approval_ref", pack)

    def test_no_silent_consent_grant_in_runtime(self):
        agent = read("agents/analysis_agent/agent.py")
        self.assertIn('config.get("consent_notice_approved", False)', agent)
        self.assertIn('config.get("consent", False)', agent)
        orchestrator = read("agents/analysis/orchestrator.py")
        self.assertIn("require_capabilities", orchestrator)


if __name__ == "__main__":
    unittest.main()
