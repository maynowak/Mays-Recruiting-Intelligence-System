"""Tests fuer Gate-5-Pipeline: Worker -> Agent Body -> Ecosystem (Gate 5).

Belegt mit Fake-Tabelle (Conditional-Write-Semantik) und echten
Registry-/Discovery-/Eligibility-/Router-/Engine-Klassen:
- Happy Path ueber Ecosystem-Auswahl (kein hartcodierter Agent)
- Duplikat -> kein zweiter fachlicher Run
- Retry -> neuer Attempt desselben Processings
- Ungueltig/kein Agent -> keine Registrierung, keine Ausfuehrung
"""

import sys
import os
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.agent_body import AgentBody
from agents.ecosystem.registry import AgentRegistry
from agents.runtime.pipeline import process_record
from agents.runtime.subject_fence import SubjectFenceBlocked, fence_item


def work_item(work_id="work-1", capability="reference.echo", agent_id="reference_agent",
              work_type="agent_reference_agent", tenant="tenant-test"):
    return {
        "workId": work_id,
        "type": work_type,
        "tenantId": tenant,
        "idempotencyKey": f"key-{work_id}",
        "agentId": agent_id,
        "capability": capability,
        "payload": {"message": "hello"},
    }


def record(work, message_id="msg-1"):
    import json
    return {"messageId": message_id, "body": json.dumps(work)}


class FakeTable:
    """DDB-Tabelle mit Conditional-Write-Semantik."""

    class ConditionalFailed(Exception):
        @property
        def response(self):
            return {"Error": {"Code": "ConditionalCheckFailedException"}}

    def __init__(self):
        self.items = {}
        self.puts = 0
        self.update_conditions = []

    def put_item(self, Item, ConditionExpression=None):
        if ConditionExpression == "attribute_not_exists(workId)" and Item["workId"] in self.items:
            raise FakeTable.ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)
        self.puts += 1

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, ConditionExpression=None):
        self.update_conditions.append(ConditionExpression)
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        if ConditionExpression == "#status = :queued":
            if item.get(names.get("#status", "#status")) != values[":queued"]:
                raise FakeTable.ConditionalFailed()
        if ConditionExpression == "#status = :failed AND attempt_no = :expectedAttempt":
            if (item.get(names.get("#status", "#status")) != values[":failed"]
                    or item.get("attempt_no") != values[":expectedAttempt"]):
                raise FakeTable.ConditionalFailed()
        if ConditionExpression == "#status = :running AND attempt_no = :attempt":
            if (item.get(names.get("#status", "#status")) != values[":running"]
                    or item.get("attempt_no") != values[":attempt"]):
                raise FakeTable.ConditionalFailed()
        # minimaler Parser fuer die in pipeline.py verwendeten SET/REMOVE-Ausdruecke
        expr = UpdateExpression.split("REMOVE")[0].strip()
        set_part = expr[len("SET "):] if expr.startswith("SET ") else expr
        for assign in set_part.split(","):
            left, right = [s.strip() for s in assign.split("=", 1)]
            field = names.get(left, left)
            item[field] = values[right]
        if "REMOVE" in UpdateExpression:
            item.pop("error", None)


class TransactionalFenceTable(FakeTable):
    """Small low-level-DynamoDB seam for the production admission contract."""

    class _Meta:
        def __init__(self, client):
            self.client = client

    class Client:
        def __init__(self, table):
            self.table = table

        def transact_write_items(self, TransactItems):
            check = TransactItems[0]["ConditionCheck"]
            key = check["Key"]["workId"]["S"]
            put = TransactItems[1].get("Put")
            update = TransactItems[1].get("Update")
            work_id = (put["Item"]["workId"]["S"] if put
                       else update["Key"]["workId"]["S"])
            if key in self.table.items:
                raise FakeTable.ConditionalFailed()
            if work_id in self.table.items and not update:
                raise FakeTable.ConditionalFailed()
            if put:
                from boto3.dynamodb.types import TypeDeserializer
                deserialize = TypeDeserializer()
                self.table.items[work_id] = {
                    name: deserialize.deserialize(value)
                    for name, value in put["Item"].items()
                }
            else:
                from boto3.dynamodb.types import TypeDeserializer
                deserialize = TypeDeserializer()
                item = self.table.items[work_id]
                item["updatedAt"] = deserialize.deserialize(
                    update["ExpressionAttributeValues"][":updated"])

    def __init__(self):
        super().__init__()
        self.name = "work-items"
        self.meta = self._Meta(self.Client(self))


def fresh_wiring():
    return AgentRegistry(), AgentBody()


class TestWorkerPipeline(unittest.TestCase):
    def test_existing_queued_item_claim_executes_without_retry_claim(self):
        """An ingress-created QUEUED row gets one initial claim, then runs."""
        table = FakeTable()
        registry, body = fresh_wiring()
        calls = []

        def execute(work):
            calls.append(work["workId"])
            return {"success": True, "data": {"executed": True}}

        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        registry.register("worker-test-agent", AgentDescriptor(
            agent_id="worker-test-agent", name="worker-test-agent",
            version="1.0.0", status=AgentStatus.ACTIVE,
            capabilities=["worker.test"],
        ))
        body.register_agent(capability="worker.test", handler=execute)
        body.register_agent(agent_id="worker-test-agent", handler=execute)
        item = work_item("work-prequeued", capability="worker.test",
                         agent_id="worker-test-agent")
        item.update({"status": "QUEUED", "attempt_no": 0})
        table.items[item["workId"]] = dict(item)

        out = process_record(record(item), table=table,
                             registry=registry, body=body)

        self.assertEqual("#status = :queued", table.update_conditions[0])
        self.assertNotIn(
            "#status = :failed AND attempt_no = :expectedAttempt",
            table.update_conditions,
        )
        self.assertEqual(["work-prequeued"], calls)
        self.assertFalse(out["duplicate"])
        self.assertEqual("COMPLETED", out["status"])
        self.assertEqual(1, out["attempt_no"])
        self.assertEqual("COMPLETED", table.items["work-prequeued"]["status"])

    def test_lost_initial_claim_suppresses_execution(self):
        class CompetingInitialClaimTable(FakeTable):
            def update_item(self, Key, UpdateExpression,
                            ExpressionAttributeNames=None,
                            ExpressionAttributeValues=None,
                            ConditionExpression=None):
                if ConditionExpression == "#status = :queued":
                    item = self.items[Key["workId"]]
                    item.update({"status": "RUNNING", "attempt_no": 1})
                    self.update_conditions.append(ConditionExpression)
                    raise FakeTable.ConditionalFailed()
                return super().update_item(
                    Key, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues, ConditionExpression)

        table = CompetingInitialClaimTable()
        registry, body = fresh_wiring()
        calls = []
        item = work_item("work-initial-race", "worker.test", "worker-test-agent")
        item.update({"status": "QUEUED", "attempt_no": 0})
        table.items[item["workId"]] = dict(item)
        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        registry.register("worker-test-agent", AgentDescriptor(
            agent_id="worker-test-agent", name="worker-test-agent",
            version="1.0.0", status=AgentStatus.ACTIVE,
            capabilities=["worker.test"],
        ))
        body.register_agent(capability="worker.test",
                            handler=lambda work: calls.append(work["workId"]))
        body.register_agent(agent_id="worker-test-agent",
                            handler=lambda work: calls.append(work["workId"]))

        out = process_record(record(item), table=table,
                             registry=registry, body=body)

        self.assertTrue(out["duplicate"])
        self.assertTrue(out["suppressed"])
        self.assertEqual("RUNNING", out["status"])
        self.assertEqual([], calls)

    def test_preexisting_running_item_remains_suppressed(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        calls = []
        item = work_item("work-running", "worker.test", "worker-test-agent")
        item.update({"status": "RUNNING", "attempt_no": 1})
        table.items[item["workId"]] = dict(item)
        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        registry.register("worker-test-agent", AgentDescriptor(
            agent_id="worker-test-agent", name="worker-test-agent",
            version="1.0.0", status=AgentStatus.ACTIVE,
            capabilities=["worker.test"],
        ))
        body.register_agent(capability="worker.test",
                            handler=lambda work: calls.append(work["workId"]))
        body.register_agent(agent_id="worker-test-agent",
                            handler=lambda work: calls.append(work["workId"]))

        out = process_record(record(item), table=table,
                             registry=registry, body=body)

        self.assertTrue(out["duplicate"])
        self.assertTrue(out["suppressed"])
        self.assertEqual("RUNNING", out["status"])
        self.assertEqual([], calls)
        self.assertEqual("RUNNING", table.items[item["workId"]]["status"])

    def test_retry_claim_lost_does_not_execute_agent(self):
        class CompetingRetryClaimTable(FakeTable):
            def update_item(self, Key, UpdateExpression,
                            ExpressionAttributeNames=None,
                            ExpressionAttributeValues=None,
                            ConditionExpression=None):
                if ConditionExpression == "#status = :failed AND attempt_no = :expectedAttempt":
                    self.update_conditions.append(ConditionExpression)
                    raise FakeTable.ConditionalFailed()
                return super().update_item(
                    Key, UpdateExpression, ExpressionAttributeNames,
                    ExpressionAttributeValues, ConditionExpression)

        table = CompetingRetryClaimTable()
        registry, body = fresh_wiring()
        calls = []
        item = work_item("work-retry-race", "worker.test", "worker-test-agent")
        item.update({"status": "FAILED", "attempt_no": 1,
                     "error": {"type": "Transient", "message": "retry"}})
        table.items[item["workId"]] = dict(item)
        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        registry.register("worker-test-agent", AgentDescriptor(
            agent_id="worker-test-agent", name="worker-test-agent",
            version="1.0.0", status=AgentStatus.ACTIVE,
            capabilities=["worker.test"],
        ))
        body.register_agent(capability="worker.test",
                            handler=lambda work: calls.append(work["workId"]))
        body.register_agent(agent_id="worker-test-agent",
                            handler=lambda work: calls.append(work["workId"]))

        out = process_record(record(item), table=table,
                             registry=registry, body=body)

        self.assertTrue(out["duplicate"])
        self.assertTrue(out["suppressed"])
        self.assertEqual([], calls)
        self.assertEqual("FAILED", table.items[item["workId"]]["status"])

    def test_two_concurrent_retry_claims_have_one_winner(self):
        class AtomicRetryTable(FakeTable):
            def __init__(self):
                super().__init__()
                self.lock = threading.Lock()

            def update_item(self, Key, UpdateExpression,
                            ExpressionAttributeNames=None,
                            ExpressionAttributeValues=None,
                            ConditionExpression=None):
                with self.lock:
                    return super().update_item(
                        Key, UpdateExpression, ExpressionAttributeNames,
                        ExpressionAttributeValues, ConditionExpression)

        from concurrent.futures import ThreadPoolExecutor
        from agents.runtime.pipeline import _RetryClaimLost, _start_retry_attempt

        table = AtomicRetryTable()
        failed = {"workId": "work-retry-concurrent", "status": "FAILED",
                  "attempt_no": 1, "processing_id": "proc-retry"}
        table.items[failed["workId"]] = dict(failed)

        def claim():
            try:
                return _start_retry_attempt(table, dict(failed))
            except _RetryClaimLost:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: claim(), range(2)))

        self.assertEqual(1, sum(result is not None for result in results))
        self.assertEqual("RUNNING", table.items[failed["workId"]]["status"])
        self.assertEqual(2, table.items[failed["workId"]]["attempt_no"])

    def test_production_admission_blocks_replay_after_fence_and_missing_row(self):
        table = TransactionalFenceTable()
        registry, body = fresh_wiring()
        calls = []
        body.register_agent(capability="reference.echo",
                            handler=lambda work: calls.append(work))
        item = work_item("work-erased")
        item["userId"] = "user-erased"
        table.items[fence_item(user_id="user-erased", tenant_id="tenant-test")
                   ["workId"]] = fence_item(
                       user_id="user-erased", tenant_id="tenant-test")

        with self.assertRaises(SubjectFenceBlocked) as caught:
            process_record(record(item), table=table, registry=registry,
                           body=body, subject_fence_table=table,
                           require_subject_fence=True)

        self.assertIn("fenced", str(caught.exception))
        self.assertNotIn("work-erased", table.items)
        self.assertEqual([], calls)

    def test_production_admission_blocks_existing_inflight_row_after_fence(self):
        table = TransactionalFenceTable()
        registry, body = fresh_wiring()
        item = work_item("work-inflight")
        item["userId"] = "user-inflight"
        table.items["work-inflight"] = {
            "workId": "work-inflight", "userId": "user-inflight",
            "tenantId": "tenant-test", "status": "RUNNING", "attempt_no": 1,
        }
        fenced = fence_item(user_id="user-inflight", tenant_id="tenant-test")
        table.items[fenced["workId"]] = fenced

        with self.assertRaises(SubjectFenceBlocked):
            process_record(record(item), table=table, registry=registry,
                           body=body, subject_fence_table=table,
                           require_subject_fence=True)

    def test_production_admission_uses_atomic_fence_transaction_for_create(self):
        table = TransactionalFenceTable()
        registry, body = fresh_wiring()
        item = work_item("work-new")
        item["userId"] = "user-new"
        out = process_record(record(item), table=table, registry=registry,
                             body=body, subject_fence_table=table,
                             require_subject_fence=True)
        self.assertEqual("COMPLETED", out["status"])
        self.assertEqual("COMPLETED", table.items["work-new"]["status"])
    def test_terminal_dead_letter_is_suppressed(self):
        table = FakeTable()
        table.items["work-dead"] = {
            "workId": "work-dead", "status": "DEAD_LETTER", "attempt_no": 1,
        }
        registry, body = fresh_wiring()
        called = []
        body.register_agent(capability="reference.echo",
                            handler=lambda work: called.append(work))
        out = process_record(record(work_item("work-dead")), table=table,
                             registry=registry, body=body)
        self.assertTrue(out["duplicate"])
        self.assertEqual(out["status"], "DEAD_LETTER")
        self.assertFalse(called)

    def test_permanent_agent_error_is_terminal_and_not_retried(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        calls = []
        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        registry.register("permanent", AgentDescriptor(
            agent_id="permanent", name="permanent", version="1.0.0",
            status=AgentStatus.ACTIVE, capabilities=["permanent.cap"]))

        def permanent(work):
            calls.append(work["workId"])
            return {"success": False, "error": {"type": "CONFLICT", "message": "no"}}

        body.register_agent(capability="permanent.cap", handler=permanent)
        body.register_agent(agent_id="permanent", handler=permanent)
        item = work_item("work-permanent", capability="permanent.cap", agent_id="permanent")
        first = process_record(record(item), table=table, registry=registry, body=body)
        second = process_record(record(item, message_id="msg-2"), table=table,
                                registry=registry, body=body)
        self.assertEqual("DEAD_LETTER", first["status"])
        self.assertEqual("DEAD_LETTER", second["status"])
        self.assertEqual(["work-permanent"], calls)

    def test_execution_fence_can_suppress_after_admission(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        called = []
        body.register_agent(capability="reference.echo",
                            handler=lambda work: called.append(work))

        def fence(work, phase):
            if phase == "before_execution":
                raise RuntimeError("ERASURE_FREEZE_ACTIVE")

        with self.assertRaises(RuntimeError):
            process_record(record(work_item("work-fenced")), table=table,
                           registry=registry, body=body,
                           erasure_admission=fence)
        self.assertFalse(called)

    def test_happy_path_selects_reference_agent_via_ecosystem(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        out = process_record(record(work_item()), table=table, registry=registry, body=body)
        self.assertEqual(out["status"], "COMPLETED")
        self.assertFalse(out["duplicate"])
        self.assertEqual(out["agent_id"], "reference_agent")
        self.assertEqual(out["attempt_no"], 1)
        self.assertIn("processing_id", out)
        item = table.items["work-1"]
        self.assertEqual(item["status"], "COMPLETED")
        self.assertEqual(item["attempt_no"], 1)
        self.assertEqual(item["sequence_no"], 1)
        self.assertTrue(item["processing_id"])
        self.assertTrue(item["execution_id"])
        self.assertTrue(item["result_reference"].startswith("work:work-1:attempt:1"))
        self.assertTrue(out["result"]["success"])
        echoed = out["result"]["data"]["echoed"]
        self.assertEqual(echoed["workId"], "work-1")
        self.assertEqual(echoed["payload"], {"message": "hello"})

    def test_selection_by_capability_not_hardcoded(self):
        """Zweiter Agent mit anderer Capability -> Auswahl folgt Capability."""
        from agents.ecosystem.registry import AgentDescriptor, AgentStatus
        table = FakeTable()
        registry, body = fresh_wiring()
        registry.register("other_agent", AgentDescriptor(
            agent_id="other_agent", name="other", version="1.0.0",
            status=AgentStatus.ACTIVE, capabilities=["other.cap"],
        ))
        calls = []

        def other_handler(work):
            calls.append(work["workId"])
            return {"success": True, "data": {"via": "other"}}

        body.register_agent(capability="other.cap", handler=other_handler)
        out = process_record(
            record(work_item("work-9", capability="other.cap", agent_id=None)),
            table=table, registry=registry, body=body,
        )
        self.assertEqual(out["agent_id"], "other_agent")
        self.assertEqual(calls, ["work-9"])

    def test_duplicate_delivery_no_second_run(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        first = process_record(record(work_item()), table=table, registry=registry, body=body)
        self.assertFalse(first["duplicate"])
        puts_after_first = table.puts
        second = process_record(record(work_item(), message_id="msg-2"),
                                table=table, registry=registry, body=body)
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["status"], "COMPLETED")
        self.assertEqual(second["attempt_no"], 1)
        # kein neuer Put, kein neuer Run: Zustand unveraendert
        self.assertEqual(table.puts, puts_after_first)
        self.assertEqual(table.items["work-1"]["attempt_no"], 1)

    def test_retry_after_failure_is_new_attempt(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        attempts = []

        from agents.ecosystem.registry import AgentDescriptor, AgentStatus

        registry.register("flaky", AgentDescriptor(
            agent_id="flaky", name="flaky", version="1.0.0",
            status=AgentStatus.ACTIVE, capabilities=["flaky.cap"],
        ))

        def flaky(work):
            attempts.append(work["workId"])
            if len(attempts) == 1:
                raise RuntimeError("transient boom")
            return {"success": True, "data": {"recovered": True}}

        body.register_agent(capability="flaky.cap", handler=flaky)
        body.register_agent(agent_id="flaky", handler=flaky)
        rec = record(work_item("work-r", capability="flaky.cap", agent_id="flaky"))

        with self.assertRaises(RuntimeError):
            process_record(rec, table=table, registry=registry, body=body)
        self.assertEqual(table.items["work-r"]["status"], "FAILED")
        self.assertEqual(table.items["work-r"]["attempt_no"], 1)

        out = process_record(rec, table=table, registry=registry, body=body)
        self.assertEqual(out["status"], "COMPLETED")
        self.assertFalse(out["duplicate"])
        self.assertEqual(out["attempt_no"], 2)
        self.assertEqual(attempts, ["work-r", "work-r"])
        self.assertNotIn("error", table.items["work-r"])

    def test_invalid_work_item_no_registration(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        bad = {"workId": "work-bad"}  # Pflichtfelder fehlen
        with self.assertRaises(ValueError):
            process_record(record(bad), table=table, registry=registry, body=body)
        self.assertEqual(table.items, {})

    def test_no_eligible_agent_no_registration(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        orphan = work_item("work-o", capability="unknown.cap", agent_id="ghost")
        with self.assertRaises(ValueError):
            process_record(record(orphan), table=table, registry=registry, body=body)
        self.assertEqual(table.items, {})

    def test_float_results_persisted_ddb_safe(self):
        """Executor-Metriken (durationMs float) duerfen Persistenz nicht brechen."""
        from decimal import Decimal

        class StrictTable(FakeTable):
            def _reject_floats(self, value):
                if isinstance(value, float):
                    raise TypeError("Float types are not supported")
                if isinstance(value, dict):
                    for v in value.values():
                        self._reject_floats(v)
                if isinstance(value, list):
                    for v in value:
                        self._reject_floats(v)

            def put_item(self, Item, ConditionExpression=None):
                self._reject_floats(Item)
                super().put_item(Item, ConditionExpression)

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        # Regression-Waechter: reservierte DDB-Woerter duerfen nur via
        # ExpressionAttributeNames (#-Platzhalter) vorkommen (live belegt:
        # error, result, status).
        import re
        bare = re.sub(r"#[A-Za-z_]+", "#x", UpdateExpression)
        for word in ("error", "result", "status"):
            assert word not in re.sub(r"#x", "", bare).split(), \
                f"reserviertes Wort '{word}' ohne Platzhalter: {UpdateExpression}"
        self._reject_floats(ExpressionAttributeValues)
        super().update_item(Key, UpdateExpression, ExpressionAttributeNames,
                            ExpressionAttributeValues)

        table = StrictTable()
        registry, body = fresh_wiring()
        out = process_record(record(work_item()), table=table, registry=registry, body=body)
        self.assertEqual(out["status"], "COMPLETED")
        stored = table.items["work-1"]["result"]
        self.assertIsInstance(stored["metrics"]["durationMs"], Decimal)


class TestOrderResultForwarding(unittest.TestCase):
    """ORDER_RESULT is derived from the persisted row, not a second contract."""

    def _wiring(self):
        from agents.addition_agent import register_addition_agent

        registry, body = AgentRegistry(), AgentBody()
        register_addition_agent(registry, body)
        return registry, body

    def _work(self, work_id="work-order-1"):
        item = work_item(work_id, capability="math.add",
                         agent_id="addition_agent",
                         work_type="agent_addition_agent")
        item.update({
            "orderId": "ord_abc123",
            "correlationId": "corr-1",
            "apiProfileId": "profile-a",
            "issuer": "issuer-a",
            "partnerApplicationId": "app-a",
        })
        item["payload"] = {"left": 17, "right": 25}
        return item

    def test_correlation_is_persisted_on_the_row(self):
        table = FakeTable()
        registry, body = self._wiring()
        process_record(record(self._work()), table=table,
                       registry=registry, body=body)
        row = table.items["work-order-1"]
        self.assertEqual(row["orderId"], "ord_abc123")
        self.assertEqual(row["correlationId"], "corr-1")
        self.assertEqual(row["apiProfileId"], "profile-a")

    def test_completed_order_work_forwards_one_order_result(self):
        table = FakeTable()
        registry, body = self._wiring()
        sent = []
        process_record(record(self._work()), table=table, registry=registry,
                       body=body, result_sender=sent.append)
        self.assertEqual(len(sent), 1)
        envelope = sent[0]
        self.assertEqual(envelope["messageType"], "ORDER_RESULT")
        self.assertEqual(envelope["orderId"], "ord_abc123")
        self.assertEqual(envelope["correlationId"], "corr-1")
        self.assertEqual(envelope["execution"],
                         {"workId": "work-order-1", "attempt": 1})
        self.assertEqual(envelope["payload"],
                         {"left": 17, "right": 25, "sum": 42})
        self.assertNotIn("success", envelope["payload"])
        # COMPLETED alone does not prove delivery; the marker does.
        row = table.items["work-order-1"]
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["orderResultDelivery"]["status"], "SENT")
        self.assertEqual(row["orderResultDelivery"]["messageId"],
                         envelope["messageId"])

    def test_non_order_work_is_not_forwarded(self):
        table = FakeTable()
        registry, body = fresh_wiring()
        sent = []
        process_record(record(work_item()), table=table, registry=registry,
                       body=body, result_sender=sent.append)
        self.assertEqual(sent, [])

    def test_missing_correlation_is_skipped(self):
        table = FakeTable()
        registry, body = self._wiring()
        work = self._work()
        work.pop("correlationId")
        sent = []
        process_record(record(work), table=table, registry=registry,
                       body=body, result_sender=sent.append)
        self.assertEqual(sent, [])
        marker = table.items["work-order-1"]["orderResultDelivery"]
        self.assertEqual(marker["status"], "SKIPPED")
        self.assertEqual(marker["code"], "missing_correlation")

    def test_no_result_transport_configuration_skips(self):
        table = FakeTable()
        registry, body = self._wiring()
        with patch.dict(os.environ, {
            "ORDER_RESULT_QUEUE_URL": "",
            "ORDER_RESULT_SECRET_ARN": "",
        }):
            process_record(record(self._work()), table=table, registry=registry,
                           body=body)
        row = table.items["work-order-1"]
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["orderResultDelivery"]["status"],
                         "NOT_CONFIGURED")

    def test_sender_failure_keeps_row_completed_and_raises(self):
        table = FakeTable()
        registry, body = self._wiring()

        def failing_sender(_envelope):
            raise RuntimeError("send failed")

        with self.assertRaises(RuntimeError):
            process_record(record(self._work()), table=table, registry=registry,
                           body=body, result_sender=failing_sender)
        row = table.items["work-order-1"]
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["orderResultDelivery"]["status"], "RETRYING")

    def test_duplicate_delivery_reemits_the_same_result(self):
        table = FakeTable()
        registry, body = self._wiring()
        sent = []
        process_record(record(self._work()), table=table, registry=registry,
                       body=body, result_sender=sent.append)
        process_record(record(self._work(), message_id="msg-2"), table=table,
                       registry=registry, body=body, result_sender=sent.append)
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["idempotencyKey"], sent[1]["idempotencyKey"])
        self.assertEqual(sent[0]["messageId"], sent[1]["messageId"])
        self.assertEqual(
            table.items["work-order-1"]["orderResultDelivery"]["status"],
            "SENT")


if __name__ == "__main__":
    unittest.main()
