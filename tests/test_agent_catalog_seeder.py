"""Tests Gate B4: Agent-Catalog-Seeder (Idempotenz, Read-Back) und die
Aufloesung des synthetischen Catalog-Agent durch verify_api_credential.

Deckt ab (Gate §10 B + E).

Kein AWS, keine Mutation: der Seeder bekommt denselben InMemory-Fake
wie der Writer-Test. Es wird KEIN echtes opaque Credential erzeugt —
getestet wird ausschliesslich, ob der Catalog-Agent als
Operation-Target aufloesbar ist (die Voraussetzung, die B3 braucht).
"""

import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.agent_status import is_executable_status  # noqa: E402
from agents.ecosystem.catalog_adapter import CatalogAdapter  # noqa: E402
from tests.test_agent_catalog_writer import (  # noqa: E402
    TABLE,
    FakeTable,
    fake_db,
)

SEED_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "installer", "scripts", "seed_agent_catalog.py")


def load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_agent_catalog",
                                                  SEED_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed_mod = load_seed_module()


class TestSeedDescriptor(unittest.TestCase):
    def test_seed_agent_is_the_existing_reference_agent(self):
        d = seed_mod.build_seed_descriptor()
        self.assertEqual(d.agent_id, "reference_agent")

    def test_seed_descriptor_taken_from_runtime_pipeline(self):
        """No second hardcoded definition: the seeder reads the canonical
        constants of agents.runtime.pipeline."""
        from agents.runtime.pipeline import (
            BODY_VERSION,
            REFERENCE_CAPABILITY,
            REFERENCE_AGENT_ID,
            RUNTIME_LAMBDA,
        )
        d = seed_mod.build_seed_descriptor()
        self.assertEqual(d.agent_id, REFERENCE_AGENT_ID)
        self.assertEqual(d.capabilities, [REFERENCE_CAPABILITY])
        self.assertEqual(d.supported_bodies, [BODY_VERSION])
        self.assertEqual(d.supported_runtimes, [RUNTIME_LAMBDA])

    def test_seed_descriptor_is_executable(self):
        self.assertTrue(is_executable_status(seed_mod.build_seed_descriptor().status))

    def test_seed_item_is_synthetic(self):
        """No personal data, no secrets, no credentials, no tokens."""
        from agents.ecosystem.catalog_writer import catalog_item_from_descriptor
        item = catalog_item_from_descriptor(seed_mod.build_seed_descriptor())
        blob = " ".join(str(v) for v in item.values()).lower()
        for needle in ("secret", "token", "password", "credential",
                       "@", "bearer", "key"):
            self.assertNotIn(needle, blob, f"seed item mentions {needle!r}")
        self.assertEqual(item["metadata"], {})


class TestSeedIdempotency(unittest.TestCase):
    def test_first_run_writes_and_reads_back(self):
        db, table = fake_db()
        result = seed_mod.seed(TABLE, dynamodb=db)
        self.assertEqual(result["outcome"], "written")
        self.assertEqual(table.put_calls, 1)
        self.assertTrue(result["readback_found"])
        self.assertEqual(result["readback_status"], "ACTIVE")

    def test_second_run_does_not_duplicate(self):
        db, table = fake_db()
        seed_mod.seed(TABLE, dynamodb=db)
        seed_mod.seed(TABLE, dynamodb=db)
        seed_mod.seed(TABLE, dynamodb=db)
        self.assertEqual(len(table.items), 1)
        self.assertEqual(table.put_calls, 3)
        self.assertEqual(
            CatalogAdapter(TABLE, dynamodb=db).scan_all_agent_ids(),
            ["reference_agent"])

    def test_skip_existing_leaves_row_untouched(self):
        db, table = fake_db()
        seed_mod.seed(TABLE, dynamodb=db)
        table.items["reference_agent"]["status"] = "INACTIVE"
        result = seed_mod.seed(TABLE, skip_existing=True, dynamodb=db)
        self.assertEqual(result["outcome"], "skipped")
        self.assertEqual(table.items["reference_agent"]["status"], "INACTIVE")

    def test_rerun_is_deterministic(self):
        db1, _ = fake_db()
        db2, _ = fake_db()
        a = seed_mod.seed(TABLE, dynamodb=db1)["readback_status"]
        b = seed_mod.seed(TABLE, dynamodb=db2)["readback_status"]
        self.assertEqual(a, b)
        db3, t3 = fake_db()
        seed_mod.seed(TABLE, dynamodb=db3)
        db4, t4 = fake_db()
        seed_mod.seed(TABLE, dynamodb=db4)
        self.assertEqual(t3.items, t4.items)

    def test_dry_run_writes_nothing(self):
        db, table = fake_db()
        result = seed_mod.seed(TABLE, dry_run=True, dynamodb=db)
        self.assertEqual(result["outcome"], "dry-run")
        self.assertEqual(table.put_calls, 0)
        self.assertEqual(table.items, {})

    def test_seed_propagates_store_error(self):
        class Boom(FakeTable):
            def put_item(self, Item=None, **kwargs):
                raise RuntimeError("simulated outage")

        db, _ = fake_db(Boom())
        with self.assertRaises(Exception) as ctx:
            seed_mod.seed(TABLE, dynamodb=db)
        self.assertIn("simulated outage", str(ctx.exception))

    def test_unseed_removes_only_seed_entries(self):
        db, table = fake_db(FakeTable({
            "someone-elses-agent": {"agentId": "someone-elses-agent",
                                    "status": "ACTIVE"}}))
        seed_mod.seed(TABLE, dynamodb=db)
        self.assertEqual(len(table.items), 2)
        unseed = load_unseed_module()
        out = unseed.unseed(TABLE, dynamodb=db)
        self.assertEqual(sorted(table.items), ["someone-elses-agent"])
        self.assertEqual(out["remaining"], ["someone-elses-agent"])


def load_unseed_module():
    script = os.path.join(os.path.dirname(SEED_SCRIPT), "unseed_agent_catalog.py")
    spec = importlib.util.spec_from_file_location("unseed_agent_catalog", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestVerifyApiCredentialCatalogResolution(unittest.TestCase):
    """§10 E: verify_api_credential resolves the seeded catalog agent.

    No opaque credential is created here. The check is exactly the
    B4 precondition B3 needs: the catalog lookup in step 14 of
    verify_api_credential can resolve an agent that really exists.
    """

    def test_catalog_map_resolves_seeded_agent(self):
        db, _ = fake_db()
        seed_mod.seed(TABLE, dynamodb=db)
        items = CatalogAdapter(TABLE, dynamodb=db).get_all_agents()
        # Same projection the production introspection sources build.
        catalog = {aid: item.get("status") for aid, item in items.items()}
        self.assertEqual(catalog, {"reference_agent": "ACTIVE"})
        raw = catalog.get("reference_agent")
        self.assertTrue(is_executable_status(raw))

    def test_verify_step14_would_authorize_catalog_status(self):
        from agents.ecosystem.agent_status import is_executable_status
        db, _ = fake_db()
        seed_mod.seed(TABLE, dynamodb=db)
        items = CatalogAdapter(TABLE, dynamodb=db).get_all_agents()
        for agent_id, item in items.items():
            # Mirrors credentials.verify_api_credential step 14 exactly.
            raw_status = item.get("status")
            self.assertTrue(is_executable_status(raw_status),
                            f"step 14 would deny {agent_id}")

    def test_absent_catalog_entry_blocks_execution(self):
        """Negative counterpart: the empty catalog denies — this is why
        B4 was a blocker for B3."""
        self.assertFalse(is_executable_status(None))
        self.assertFalse(is_executable_status(""))

    def test_verify_api_credential_still_has_no_productive_caller(self):
        """B3 stays blocked: this gate must not accidentally wire it."""
        import subprocess
        out = subprocess.run(
            ["grep", "-rn", "verify_api_credential",
             "lambda/", "agents/"],
            capture_output=True, text=True).stdout
        calls = [l for l in out.splitlines()
                 if "def verify_api_credential" not in l
                 and '"verify_api_credential"' not in l]
        self.assertEqual(calls, [], f"unexpected new callers: {calls}")


if __name__ == "__main__":
    unittest.main()
