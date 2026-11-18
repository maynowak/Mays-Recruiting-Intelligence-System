"""Lifecycle contract tests (local state/inventory only)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from installer import agent_lifecycle as lifecycle  # noqa: E402


def inventory():
    return {
        "agents": {"ats-agent": {"catalog": "ACTIVE",
                                 "allowlist": ["ats-agent"],
                                 "entitlement": "present"},
                   "addition_agent": {"catalog": "ACTIVE",
                                      "allowlist": [],
                                      "entitlement": "present"}},
        "partnerBindings": [
            {"agentId": "ats-agent", "type": "entitlement", "id": "ent-ats",
             "managedBy": "ris"},
            {"agentId": "ats-agent", "type": "api-profile", "id": "prof-ats",
             "managedBy": "ris"},
            {"agentId": "ats-agent", "type": "partner-application",
             "id": "app-ats", "managedBy": "ris"},
            {"agentId": "ats-agent", "type": "external-ui", "id": "ui-ats",
             "managedBy": "external"},
            {"agentId": "addition_agent", "type": "entitlement",
             "id": "ent-add", "managedBy": "ris"},
            {"agentId": "other-agent", "type": "entitlement", "id": "ent-other",
             "managedBy": "ris"},
        ],
        "openOrders": [],
        "openResults": [],
        "sharedResources": ["dispatch", "results", "consumer"],
        "retailOrders": 3,
        "secret": "ris_do_not_leak",
        "ownerKey": "do-not-leak",
    }


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.inv = self.root / "inventory.json"
        self.inv.write_text(json.dumps(inventory()), encoding="utf-8")
        self.state = self.root / "ats-state.json"
        self.audit = self.root / "audit.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def run_action(self, agent, action, execute=False, confirm=None):
        return lifecycle.run(
            action, lifecycle.DEFAULT_ROOT / agent, execute=execute,
            inventory_path=self.inv, state_path=self.state,
            audit_path=self.audit, purge_confirm=confirm)

    def test_addition_uninstall_does_not_affect_ats(self):
        result = self.run_action("addition-agent", "uninstall", execute=True)
        self.assertEqual("APPLIED", result["status"])
        self.assertEqual(1, len(result["impact"]["bindingsToRemove"]))
        self.assertEqual("ent-add",
                         result["impact"]["bindingsToRemove"][0]["id"])
        self.assertNotIn("dispatch", result["impact"]["bindingsToRemove"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual("uninstalled", state["status"])
        self.assertFalse(state["catalog"])

    def test_ats_disable_keeps_retail_and_shared(self):
        result = self.run_action("ats-agent", "disable", execute=True)
        self.assertEqual("APPLIED", result["status"])
        self.assertFalse(result["impact"]["catalogAfter"])
        self.assertFalse(result["impact"]["retailOrdersAffected"])
        self.assertIn("ris-dev2-dev-agent-dispatch",
                      result["impact"]["sharedResourcesRetained"])
        self.assertEqual("disabled",
                         json.loads(self.state.read_text())["status"])

    def test_detach_removes_only_agent_binding_and_marks_external_pending(self):
        result = self.run_action("ats-agent", "detach-partner", execute=True)
        self.assertEqual(["ent-ats"],
                         [b["id"] for b in result["impact"]["bindingsToRemove"]])
        self.assertEqual(["ui-ats"],
                         [b["id"] for b in
                          result["impact"]["externalPartnerPending"]])
        self.assertNotIn("prof-ats",
                         [b["id"] for b in result["impact"]["bindingsToRemove"]])

    def test_open_orders_block_uninstall(self):
        data = inventory()
        data["openOrders"] = [{"orderId": "ord_open", "agentId": "ats-agent",
                               "status": "PENDING"}]
        self.inv.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_action("ats-agent", "uninstall", execute=True)
        self.assertEqual("BLOCKED", result["status"])
        self.assertIn("open_orders_must_drain_or_cancel", result["blockers"])
        self.assertFalse(self.state.exists())

    def test_no_secret_or_owner_leak_in_evidence(self):
        self.run_action("ats-agent", "status", execute=True)
        result = json.loads(Path(
            self.state.with_suffix(".result.json")).read_text(encoding="utf-8"))
        audit = self.audit.read_text(encoding="utf-8")
        for blob in (json.dumps(result), audit):
            self.assertNotIn("ris_", blob)
            self.assertNotIn("do-not-leak", blob)
            self.assertNotIn("ownerKey", blob)

    def test_disable_enable_detach_install_uninstall_install_recovery(self):
        self.run_action("ats-agent", "disable", execute=True)
        enabled = self.run_action("ats-agent", "enable", execute=True)
        self.assertTrue(enabled["impact"]["catalogAfter"])
        self.run_action("ats-agent", "detach-partner", execute=True)
        installed = self.run_action("ats-agent", "install", execute=True)
        self.assertEqual("installed",
                         json.loads(self.state.read_text())["status"])
        self.assertTrue(installed["impact"]["catalogAfter"])
        self.run_action("ats-agent", "uninstall", execute=True)
        again = self.run_action("ats-agent", "uninstall", execute=True)
        self.assertEqual("APPLIED", again["status"])

    def test_purge_requires_confirmation_and_uninstall(self):
        blocked = self.run_action("ats-agent", "purge", execute=True)
        self.assertEqual("BLOCKED", blocked["status"])
        self.assertIn("purge_confirmation_required", blocked["blockers"])
        self.run_action("ats-agent", "uninstall", execute=True)
        purged = self.run_action("ats-agent", "purge", execute=True,
                                 confirm="ats-agent")
        self.assertEqual("APPLIED", purged["status"])
        self.assertEqual("purged",
                         json.loads(self.state.read_text())["status"])

    def test_purge_grace_window_blocks_immediate_purge(self):
        self.run_action("ats-agent", "uninstall", execute=True)
        blocked = lifecycle.run(
            "purge", lifecycle.DEFAULT_ROOT / "ats-agent", execute=True,
            inventory_path=self.inv, state_path=self.state,
            audit_path=self.audit, purge_confirm="ats-agent",
            purge_grace_days=30)
        self.assertEqual("BLOCKED", blocked["status"])
        self.assertIn("purge_grace_window_not_elapsed", blocked["blockers"])

    def test_destructive_action_requires_inventory(self):
        for action in ("disable", "detach-partner", "uninstall"):
            result = lifecycle.run(
                action, lifecycle.DEFAULT_ROOT / "ats-agent", execute=True,
                state_path=self.state, audit_path=self.audit)
            self.assertEqual("BLOCKED", result["status"], action)
            self.assertIn("inventory_required_for_impact", result["blockers"])
        self.assertFalse(self.state.exists())

    def test_second_uninstall_is_idempotent_and_keeps_grace_anchor(self):
        first = self.run_action("ats-agent", "uninstall", execute=True)
        self.assertEqual("APPLIED", first["status"])
        anchor = json.loads(self.state.read_text())["uninstalledAt"]
        second = self.run_action("ats-agent", "uninstall", execute=True)
        self.assertEqual("already_uninstalled", second["result"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(anchor, json.loads(self.state.read_text())["uninstalledAt"])

    def test_package_identity_mismatch_is_rejected(self):
        package = self.root / "fake-agent"
        (package).mkdir()
        (package / "manifest.yaml").write_text(
            "agentId: ats-agent\n", encoding="utf-8")
        (package / "lifecycle.yaml").write_text(
            "agentId: addition_agent\nsharedResources:\n  - x\n"
            "exclusiveResources: []\npartnerBindings:\n  - type: entitlement\n"
            "uninstall:\n  retain: true\nretention:\n  orders: retain\n",
            encoding="utf-8")
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.run("status", package, inventory_path=self.inv,
                          state_path=self.state, audit_path=self.audit)

    def test_template_package_is_not_deployable(self):
        with self.assertRaises(lifecycle.LifecycleError):
            lifecycle.run("install", lifecycle.DEFAULT_ROOT / "_template",
                          inventory_path=self.inv, state_path=self.state,
                          audit_path=self.audit)

    def test_audit_records_actor_and_approval(self):
        lifecycle.run("disable", lifecycle.DEFAULT_ROOT / "ats-agent",
                      execute=True, inventory_path=self.inv,
                      state_path=self.state, audit_path=self.audit,
                      actor="op@example", approval="CHG-1",
                      reason="pilot off")
        entry = json.loads(self.audit.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual("op@example", entry["actor"])
        self.assertEqual("CHG-1", entry["approval"])
        self.assertEqual("pilot off", entry["reason"])
        self.assertTrue(entry["inventoryProvided"])
        self.assertEqual(64, len(entry["inventoryDigest"]))

    def test_verify_reports_catalog_and_pending(self):
        self.run_action("ats-agent", "disable", execute=True)
        result = self.run_action("ats-agent", "verify")
        self.assertEqual("REPORTED", result["status"])
        self.assertFalse(result["impact"]["catalogBefore"])
        self.assertEqual(["ui-ats"],
                         [b["id"] for b in
                          result["impact"]["externalPartnerPending"]])

    def test_inventory_with_utf8_bom_is_accepted(self):
        self.inv.write_bytes(b"\xef\xbb\xbf" + self.inv.read_bytes())
        result = self.run_action("ats-agent", "status")
        self.assertEqual("REPORTED", result["status"])
        self.assertEqual("ats-agent", result["agentId"])

    def test_orchestrator_action_passthrough(self):
        from installer import agent_install

        code = agent_install.main([
            "--root", str(lifecycle.DEFAULT_ROOT),
            "--agent", "addition-agent",
            "--action", "uninstall",
            "--inventory", str(self.inv),
            "--lifecycle-state", str(self.state),
            "--lifecycle-audit", str(self.audit),
        ])
        self.assertEqual(0, code)
        # dry-run: no state file, only a result manifest
        self.assertFalse(self.state.exists())
        manifest = json.loads(
            self.state.with_suffix(".result.json").read_text(encoding="utf-8"))
        self.assertEqual("DRY_RUN", manifest["plan"]["status"])

    def test_orchestrator_blocks_purge_without_confirmation(self):
        from installer import agent_install

        code = agent_install.main([
            "--root", str(lifecycle.DEFAULT_ROOT),
            "--agent", "ats-agent",
            "--action", "purge",
            "--execute",
            "--inventory", str(self.inv),
            "--lifecycle-state", str(self.state),
            "--lifecycle-audit", str(self.audit),
        ])
        self.assertEqual(2, code)

    # --- LIFECYCLE-12: shared infrastructure and partner impact ----------

    def test_catalog_only_disable_is_documented_as_non_blocking(self):
        result = self.run_action("ats-agent", "disable")
        self.assertIn("catalog_is_not_a_worker_execution_gate",
                      result["warnings"])
        self.assertIn("entitlement_withdraw_required_to_stop_dispatch",
                      result["warnings"])
        gates = result["impact"]["executionGates"]
        self.assertFalse(gates["catalogAloneBlocksExecution"])
        self.assertEqual("entitlement+registry", gates["worker"])
        self.assertEqual("entitlement+registry", gates["orderDispatch"])

    def test_disable_removes_no_binding_and_keeps_shared(self):
        result = self.run_action("ats-agent", "disable", execute=True)
        self.assertEqual([], result["impact"]["bindingsToRemove"])
        self.assertEqual([{"id": "ent-ats"}],
                         result["impact"]["entitlementsToWithdraw"])
        self.assertTrue(result["impact"]["entitlementWithdrawRequired"])
        self.assertIn("ris-dev2-dev-agent-dispatch",
                      result["impact"]["sharedResourcesRetained"])
        self.assertFalse(result["impact"]["retailOrdersAffected"])

    def test_detach_keeps_partner_application_and_notifies_partner(self):
        result = self.run_action("ats-agent", "detach-partner", execute=True)
        self.assertEqual(["ent-ats"],
                         [b["id"] for b in result["impact"]["bindingsToRemove"]])
        self.assertEqual(["app-ats"],
                         [a["id"] for a in
                          result["impact"]["partnerApplicationsAffected"]])
        self.assertEqual("retained",
                         result["impact"]["partnerApplicationsAffected"][0]["action"])
        impact = result["removalImpact"]
        self.assertIn("partner-team", impact["notifications"])
        self.assertIn("security-privacy", impact["notifications"])
        self.assertEqual(["ui-ats"],
                         [p["id"] for p in impact["pendingExternalChanges"]])
        self.assertTrue(all(p["status"] == "PENDING"
                            for p in impact["pendingExternalChanges"]))

    def test_removal_impact_reports_orders_results_allowlist(self):
        data = inventory()
        data["openOrders"] = [{"orderId": "ord_open", "agentId": "ats-agent",
                               "status": "PENDING"}]
        data["openResults"] = [{"orderId": "ord_open", "agentId": "ats-agent",
                                "status": "PENDING"}]
        self.inv.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_action("ats-agent", "status")
        impact = result["removalImpact"]
        self.assertEqual(["ord_open"], [o["orderId"] for o in impact["openOrders"]])
        self.assertEqual(["ord_open"], [o["orderId"] for o in impact["openResults"]])
        self.assertEqual(["ats-agent"], impact["agentAllowlist"]["entries"])
        self.assertEqual("present", impact["entitlementStatus"])
        self.assertIn("operations", impact["notifications"])

    def test_repeated_disable_is_idempotent(self):
        first = self.run_action("ats-agent", "disable", execute=True)
        second = self.run_action("ats-agent", "disable", execute=True)
        self.assertEqual(first["status"], second["status"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual("disabled", state["status"])
        self.assertFalse(state["catalog"])
        self.assertEqual(2, len(state["history"]))
        self.assertTrue(state["history"][0]["action"] == "DISABLE")

    def test_uninstall_keeps_history_and_retail(self):
        result = self.run_action("addition-agent", "uninstall", execute=True)
        self.assertTrue(result["impact"]["historyRetained"])
        self.assertFalse(result["impact"]["retailOrdersAffected"])
        self.assertFalse(result["impact"]["secretValueRead"])
        self.assertIn("ris-dev2-mays-orders",
                      result["impact"]["sharedResourcesRetained"])
        self.assertIn("security-privacy",
                      result["removalImpact"]["notifications"])


if __name__ == "__main__":
    unittest.main()
