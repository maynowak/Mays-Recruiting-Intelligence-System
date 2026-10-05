"""Tests Gate B4: persistenter Agent Catalog Writer.

Deckt ab (Gate §10 A): Writer Unit Tests + Read-Back ueber den
BESTEHENDEN Read Path.

Alle Tests laufen gegen einen InMemory-DDB-Fake — kein AWS, keine
Mutation. Status-Entscheidungen nutzen die ZENTRALE Normalisierung
(agents.ecosystem.agent_status), nie eine zweite Testlogik.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.ecosystem.agent_status import (  # noqa: E402
    is_executable_status,
    normalize_agent_status,
)
from agents.ecosystem.catalog_adapter import (  # noqa: E402
    CatalogAdapter,
    populate_registry_from_catalog,
)
from agents.ecosystem.catalog_writer import (  # noqa: E402
    CatalogEntryInvalid,
    CatalogWriter,
    catalog_item_from_descriptor,
    validate_catalog_item,
)
from agents.ecosystem.registry import (  # noqa: E402
    AgentDescriptor,
    AgentRegistry,
    AgentStatus,
    ExecutionProfile,
)

TABLE = "test-agent-catalog"

READ_PATH_FIELDS = ("agentId", "status", "name", "version", "description",
                    "capabilities", "supported_bodies", "supported_runtimes",
                    "risk_level", "metadata")


class FakeTable:
    """Minimal in-memory stand-in for a boto3 DynamoDB Table resource.

    Supports exactly what writer/adapter use: put_item, get_item,
    delete_item, scan. Unknown operations and kwargs raise, so a test
    cannot pass against a fake that silently tolerates something new.
    """

    def __init__(self, items=None):
        self.items = {k: dict(v) for k, v in (items or {}).items()}
        self.put_calls = 0
        self.delete_calls = 0
        self.scan_calls = 0

    def put_item(self, Item=None, **kwargs):
        if kwargs:
            raise AssertionError(f"unexpected put_item kwargs: {kwargs}")
        self.put_calls += 1
        self.items[Item["agentId"]] = dict(Item)
        return {}

    def get_item(self, Key=None, **kwargs):
        if kwargs:
            raise AssertionError(f"unexpected get_item kwargs: {kwargs}")
        item = self.items.get(Key["agentId"])
        return {"Item": dict(item)} if item else {}

    def delete_item(self, Key=None, **kwargs):
        if kwargs:
            raise AssertionError(f"unexpected delete_item kwargs: {kwargs}")
        self.delete_calls += 1
        self.items.pop(Key["agentId"], None)
        return {}

    def scan(self, **kwargs):
        self.scan_calls += 1
        unknown = set(kwargs) - {"ProjectionExpression"}
        if unknown:
            raise AssertionError(f"unexpected scan kwargs: {unknown}")
        projection = kwargs.get("ProjectionExpression")
        items = list(self.items.values())
        if projection:
            assert projection == "agentId", projection
            items = [{"agentId": i["agentId"]} for i in items]
        return {"Items": [dict(i) for i in items]}


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, name):
        assert name == TABLE, name
        return self._table


def fake_db(table=None):
    t = table or FakeTable()
    return FakeResource(t), t


def descriptor(status=AgentStatus.ACTIVE, agent_id="reference_agent"):
    return AgentDescriptor(
        agent_id=agent_id,
        name=agent_id,
        version="1.0.0",
        status=status,
        capabilities=["reference.echo"],
        supported_bodies=["1.0.0"],
        supported_runtimes=["python3.14"],
        execution_profile=ExecutionProfile.LAMBDA,
        risk_level="low",
        description="Technischer Nachweis-Agent (Echo, keine Domain-Logik)",
    )


class TestWriterUnit(unittest.TestCase):
    def test_writer_persists_item(self):
        db, table = fake_db()
        writer = CatalogWriter(TABLE, dynamodb=db)
        written = writer.put_agent(catalog_item_from_descriptor(descriptor()))
        self.assertEqual(table.put_calls, 1)
        self.assertEqual(table.items["reference_agent"]["status"], "ACTIVE")
        self.assertEqual(written["agentId"], "reference_agent")

    def test_item_shape_matches_existing_read_path(self):
        item = catalog_item_from_descriptor(descriptor())
        self.assertEqual(sorted(item), sorted(READ_PATH_FIELDS))

    def test_no_expires_at_written(self):
        """TTL is enabled on expiresAt; writing it would expire the seed."""
        self.assertNotIn("expiresAt", catalog_item_from_descriptor(descriptor()))

    def test_status_uses_existing_normaliser(self):
        item = catalog_item_from_descriptor(descriptor())
        self.assertEqual(item["status"],
                         normalize_agent_status(item["status"]).value)

    def test_unknown_status_rejected_and_nothing_written(self):
        bad = descriptor()
        bad.status = "NOT_A_STATUS"
        with self.assertRaises(CatalogEntryInvalid):
            catalog_item_from_descriptor(bad)
        db, table = fake_db()
        with self.assertRaises(CatalogEntryInvalid):
            CatalogWriter(TABLE, dynamodb=db).put_agent(
                {"agentId": "x", "status": "NOT_A_STATUS"})
        self.assertEqual(table.put_calls, 0)

    def test_blocked_status_is_persistable_but_not_executable(self):
        """Fail-closed is preserved: a non-ACTIVE row may exist, but the
        existing read path then refuses it for execution."""
        item = catalog_item_from_descriptor(descriptor(AgentStatus.INACTIVE))
        self.assertEqual(item["status"], "INACTIVE")
        self.assertFalse(is_executable_status(item["status"]))
        db, _ = fake_db()
        written = CatalogWriter(TABLE, dynamodb=db).put_agent(item)
        found = CatalogAdapter(TABLE, dynamodb=db).get_all_agents().get(
            "reference_agent")
        self.assertEqual(found["status"], written["status"])

    def test_unknown_attribute_rejected(self):
        db, table = fake_db()
        with self.assertRaises(CatalogEntryInvalid):
            CatalogWriter(TABLE, dynamodb=db).put_agent(
                {"agentId": "x", "status": "ACTIVE", "secretToken": "leak"})
        self.assertEqual(table.put_calls, 0)

    def test_missing_required_field_rejected(self):
        db, table = fake_db()
        with self.assertRaises(CatalogEntryInvalid):
            CatalogWriter(TABLE, dynamodb=db).put_agent({"status": "ACTIVE"})
        self.assertEqual(table.put_calls, 0)

    def test_non_string_capability_rejected(self):
        db, _ = fake_db()
        with self.assertRaises(CatalogEntryInvalid):
            validate_catalog_item({"agentId": "x", "status": "ACTIVE",
                                   "capabilities": [1, 2]})

    def test_store_failure_is_raised_not_swallowed(self):
        class Boom(FakeTable):
            def put_item(self, Item=None, **kwargs):
                raise RuntimeError("simulated store outage")

        db, _ = fake_db(Boom())
        with self.assertRaises(Exception) as ctx:
            CatalogWriter(TABLE, dynamodb=db).put_agent(
                catalog_item_from_descriptor(descriptor()))
        self.assertIn("simulated store outage", str(ctx.exception))

    def test_writer_does_not_touch_runtime_registry(self):
        db, _ = fake_db()
        registry = AgentRegistry()
        writer = CatalogWriter(TABLE, dynamodb=db)
        writer.put_agent(catalog_item_from_descriptor(descriptor()))
        self.assertEqual(registry.list_all(), [])

    def test_writer_without_table_name_raises(self):
        with self.assertRaises(Exception):
            CatalogWriter(dynamodb=fake_db()[0]).put_agent(
                catalog_item_from_descriptor(descriptor()))


class TestCatalogReadBack(unittest.TestCase):
    """§10 C: Read-back through the EXISTING read path, not the write
    result."""

    def test_existing_read_path_finds_written_entry(self):
        db, _ = fake_db()
        CatalogWriter(TABLE, dynamodb=db).put_agent(
            catalog_item_from_descriptor(descriptor()))
        agents = CatalogAdapter(TABLE, dynamodb=db).get_all_agents()
        self.assertIn("reference_agent", agents)
        self.assertEqual(agents["reference_agent"]["status"], "ACTIVE")

    def test_existing_registry_population_registers_it(self):
        db, _ = fake_db()
        CatalogWriter(TABLE, dynamodb=db).put_agent(
            catalog_item_from_descriptor(descriptor()))
        registry = AgentRegistry()
        count = populate_registry_from_catalog(registry, TABLE, dynamodb=db)
        self.assertEqual(count, 1)
        self.assertTrue(registry.is_registered("reference_agent"))
        entry = registry.get("reference_agent")
        self.assertEqual(entry.status, AgentStatus.ACTIVE)
        self.assertEqual(entry.capabilities, ["reference.echo"])

    def test_existing_read_path_still_fail_closed_on_bad_status(self):
        db, _ = fake_db(FakeTable({
            "reference_agent": {"agentId": "reference_agent",
                                "status": "WEIRD"}}))
        registry = AgentRegistry()
        self.assertEqual(
            populate_registry_from_catalog(registry, TABLE, dynamodb=db), 0)
        self.assertFalse(registry.is_registered("reference_agent"))

    def test_scan_all_agent_ids_finds_written_entry(self):
        db, _ = fake_db()
        CatalogWriter(TABLE, dynamodb=db).put_agent(
            catalog_item_from_descriptor(descriptor()))
        self.assertEqual(
            CatalogAdapter(TABLE, dynamodb=db).scan_all_agent_ids(),
            ["reference_agent"])


if __name__ == "__main__":
    unittest.main()
