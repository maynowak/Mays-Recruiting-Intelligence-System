"""G04 — verified APIProfile propagation (M2M entry -> WorkItem -> worker).

Local only: no AWS, no network. All stores are fakes; the handler entry point
and the real pipeline are exercised.
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lambda"))

import handler as h  # noqa: E402

from agents.agent_body import AgentBody  # noqa: E402
from agents.ecosystem import api_profiles as ap  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    InMemoryCredentialStore,
    issue_credential,
)
from agents.ecosystem.registry import AgentRegistry  # noqa: E402
from agents.runtime.pipeline import process_record  # noqa: E402

AGENT = "addition_agent"
CAPABILITY = "math.add"
PAYLOAD = {"left": 17, "right": 25}


def _ts(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _claims(tenant="tenant-a", client_id="client-a"):
    return {"sub": "user-a", "token_use": "access",
            "custom:tenant_id": tenant, "client_id": client_id}


def _event(credential, agent=AGENT):
    return {
        "httpMethod": "POST",
        "path": "/v1/m2m/agents/%s/execute" % agent,
        "headers": {"X-Api-Credential": credential},
        "body": json.dumps({"capability": CAPABILITY, "payload": PAYLOAD,
                            "idempotencyKey": "idem-g04"}),
        "requestContext": {
            "requestId": "req-g04",
            "http": {"method": "POST",
                     "path": "/v1/m2m/agents/%s/execute" % agent},
            "authorizer": {"jwt": {"claims": _claims()}},
        },
    }


class _Resolver:
    def __init__(self, rows):
        self.rows = list(rows)

    def find_entitlements(self, user_id):
        return [dict(r) for r in self.rows if r.get("userId") == user_id]


def _entitlement(agent=AGENT, profile=None, days=30):
    row = {"entitlementId": "ent-g04", "userId": "user-a",
           "tenantId": "tenant-a", "agentId": agent,
           "validFrom": _ts(-1), "validUntil": _ts(days)}
    if profile is not None:
        row["apiProfileId"] = profile
    return row


# ---------------------------------------------------------------------------
# M2M entry point: does it hand the verified profile to the enqueue contract?
# ---------------------------------------------------------------------------
class MachineEntryHarness(unittest.TestCase):
    def setUp(self):
        self.profiles = ap.InMemoryApiProfileStore()
        self.credentials = InMemoryCredentialStore()
        self.pid = ap.create_profile(
            self.profiles,
            {"userId": "user-a", "tenantId": "tenant-a", "groups": []},
            "g04 profile")["apiProfileId"]
        ap.transition_status(
            self.profiles,
            {"userId": "admin", "tenantId": "tenant-a", "groups": ["admins"]},
            self.pid, "ACTIVE")
        issued = issue_credential(
            self.credentials, self.profiles, self.pid, _ts(30),
            "admin", "admin", label="g04")
        self.secret = issued["secret"]
        self.catalog = {AGENT: "ACTIVE"}
        self.registry_profile = self.pid

    def call(self, event, resolver=None):
        captured = []

        def _enq(**kwargs):
            captured.append(kwargs)
            return {"workId": "w-g04", "status": "QUEUED",
                    "requestId": "rq-g04", "workItem": kwargs}

        sources = {
            "profile_store": self.profiles,
            "credential_store": self.credentials,
            "entitlement_resolver": resolver or _Resolver([_entitlement()]),
            "catalog": self.catalog,
        }

        def registry_stub(client_id):
            return {"applicationId": "app-a", "cognitoClientId": client_id,
                    "apiProfileId": self.registry_profile,
                    "tenantId": "tenant-a", "status": "ACTIVE"}

        with patch.object(h, "_build_introspection_sources",
                          return_value=sources), \
             patch.object(h, "_enqueue_agent_work", side_effect=_enq), \
             patch("agents.ecosystem.partner_registry."
                   "resolve_partner_application", side_effect=registry_stub):
            out = h.handler(event, None)
        return out["statusCode"], json.loads(out["body"]), captured


class TestMachineEntryPropagation(MachineEntryHarness):
    def test_verified_profile_reaches_the_enqueue_contract(self):
        code, _body, captured = self.call(_event(self.secret))
        self.assertEqual(202, code)
        self.assertEqual(1, len(captured))
        self.assertEqual(self.pid, captured[0]["api_profile_id"])

    def test_verified_profile_is_the_credential_profile_not_a_claim(self):
        code, _body, captured = self.call(_event(self.secret))
        self.assertEqual(202, code)
        # The value comes from verify_api_credential's context, which derives
        # it from the credential's profile; the body carries no profile at all.
        self.assertNotIn("apiProfileId", json.loads(
            _event(self.secret)["body"]))
        self.assertEqual(self.pid, captured[0]["api_profile_id"])

    def test_foreign_profile_binding_is_denied_and_nothing_is_enqueued(self):
        self.registry_profile = "profile-foreign"
        code, _body, captured = self.call(_event(self.secret))
        self.assertEqual(403, code)
        self.assertEqual([], captured)

    def test_denied_request_never_carries_a_profile(self):
        code, _body, captured = self.call(
            _event("ris_" + "z" * 47))
        self.assertEqual(401, code)
        self.assertEqual([], captured)


# ---------------------------------------------------------------------------
# Persistence + SQS must carry the same verified profile
# ---------------------------------------------------------------------------
class _CapturingClient:
    def __init__(self):
        self.transact_calls = []

    def transact_write_items(self, TransactItems):
        self.transact_calls.append(TransactItems)


class _CapturingSqs:
    def __init__(self):
        self.messages = []

    def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": "m-1"}


class _FakeTable:
    def __init__(self):
        self.name = "work-items"
        self.meta = type("Meta", (), {"client": _CapturingClient()})()


def _plain(value):
    """Unmarshal the low-level DynamoDB attribute format used by the handler."""
    if isinstance(value, dict) and len(value) == 1:
        kind, raw = next(iter(value.items()))
        if kind == "S":
            return raw
        if kind == "N":
            return int(raw) if str(raw).lstrip("-").isdigit() else float(raw)
        if kind == "BOOL":
            return bool(raw)
        if kind == "NULL":
            return None
        if kind == "M":
            return {k: _plain(v) for k, v in raw.items()}
        if kind == "L":
            return [_plain(v) for v in raw]
    return {k: _plain(v) for k, v in value.items()}


class TestEnqueueCarriesSameProfile(unittest.TestCase):
    def setUp(self):
        self.table = _FakeTable()
        self.sqs = _CapturingSqs()
        resource = type("R", (), {"Table": staticmethod(lambda name: self.table)})
        self.env = patch.dict(os.environ, {
            "WORK_ITEMS_TABLE": "work-items",
            "WORK_QUEUE_URL": "https://sqs.local/work",
        })
        self.env.start()
        self.patches = [
            patch.object(h, "_get_dynamodb", return_value=resource()),
            patch.object(h, "_get_sqs", return_value=self.sqs),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.env.stop()

    def test_persisted_item_and_sqs_message_share_the_profile(self):
        out = h._enqueue_agent_work(
            agent_id=AGENT, capability=CAPABILITY, payload=PAYLOAD,
            tenant_id="tenant-a", user_id="user-a",
            idempotency_key="idem-g04",
            partner_application_id="app-a", issuer="https://issuer.example",
            api_profile_id="profile-a")

        self.assertEqual("QUEUED", out["status"])

        body = json.loads(self.sqs.messages[0]["MessageBody"])
        self.assertEqual("profile-a", body["apiProfileId"])
        self.assertEqual("app-a", body["partnerApplicationId"])
        self.assertEqual("https://issuer.example", body["issuer"])
        self.assertEqual(out["workId"], body["workId"])

        items = self.table.meta.client.transact_calls[0]
        put = [i["Put"] for i in items if "Put" in i][0]
        persisted = _plain(put["Item"])
        self.assertEqual("profile-a", persisted["apiProfileId"])
        self.assertEqual("app-a", persisted["partnerApplicationId"])
        self.assertEqual(body, persisted)

    def test_missing_profile_becomes_empty_not_invented(self):
        h._enqueue_agent_work(
            agent_id=AGENT, capability=CAPABILITY, payload=PAYLOAD,
            tenant_id="tenant-a", user_id="user-a",
            idempotency_key="idem-g04b")
        body = json.loads(self.sqs.messages[0]["MessageBody"])
        self.assertEqual("", body["apiProfileId"])

    def test_no_secret_is_persisted_or_sent(self):
        h._enqueue_agent_work(
            agent_id=AGENT, capability=CAPABILITY, payload=PAYLOAD,
            tenant_id="tenant-a", user_id="user-a",
            idempotency_key="idem-g04c",
            api_profile_id="profile-a")
        serialized = json.dumps(self.sqs.messages)
        self.assertNotIn("ris_", serialized)
        self.assertNotIn("X-Api-Credential", serialized)


# ---------------------------------------------------------------------------
# Worker: does the pipeline actually receive and enforce the profile?
# ---------------------------------------------------------------------------
class _ConditionalFailed(Exception):
    @property
    def response(self):
        return {"Error": {"Code": "ConditionalCheckFailedException"}}


class WorkerTable:
    def __init__(self):
        self.items = {}

    def put_item(self, Item, ConditionExpression=None):
        if (ConditionExpression == "attribute_not_exists(workId)"
                and Item["workId"] in self.items):
            raise _ConditionalFailed()
        self.items[Item["workId"]] = dict(Item)

    def get_item(self, Key):
        item = self.items.get(Key["workId"])
        return {"Item": dict(item)} if item else {}

    def update_item(self, Key, UpdateExpression,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None,
                    ConditionExpression=None):
        item = self.items[Key["workId"]]
        names = ExpressionAttributeNames or {}
        values = ExpressionAttributeValues or {}
        set_part = UpdateExpression.split("REMOVE")[0].strip()
        if set_part.startswith("SET "):
            set_part = set_part[4:]
        for assign in set_part.split(","):
            left, right = [s.strip() for s in assign.split("=", 1)]
            item[names.get(left, left)] = values[right]


def _work(profile="profile-a", partner="app-a"):
    return {
        "workId": "w-g04-worker",
        "type": "agent_%s" % AGENT,
        "tenantId": "tenant-a",
        "userId": "user-a",
        "requestedBy": "user-a",
        "agentId": AGENT,
        "capability": CAPABILITY,
        "idempotencyKey": "idem-worker",
        "payload": PAYLOAD,
        "apiProfileId": profile,
        "partnerApplicationId": partner,
        "issuer": "https://issuer.example",
    }


def _run(work, resolver):
    record = {"messageId": "msg-g04", "body": json.dumps(work)}
    return process_record(record, table=WorkerTable(),
                          registry=AgentRegistry(), body=AgentBody(),
                          entitlement_resolver=resolver)


class TestWorkerUsesVerifiedProfile(unittest.TestCase):
    def test_profile_bound_entitlement_authorises_and_executes(self):
        out = _run(_work(), _Resolver([_entitlement(profile="profile-a")]))
        self.assertNotIn("denied", out)
        self.assertEqual("COMPLETED", out["status"])
        # The pipeline persists the agent result verbatim: {success, data, ...}
        self.assertEqual(42, out["result"]["data"]["sum"])

    def test_foreign_profile_is_denied_by_the_worker(self):
        out = _run(_work(profile="profile-b"),
                   _Resolver([_entitlement(profile="profile-a")]))
        self.assertTrue(out.get("denied"))
        self.assertEqual("DEAD_LETTER", out["status"])
        self.assertEqual("profile-mismatch", out["reason"])

    def test_partner_scoped_work_without_profile_is_denied(self):
        # Even a user-wide row that would otherwise authorise must not apply.
        out = _run(_work(profile=""), _Resolver([_entitlement()]))
        self.assertTrue(out.get("denied"))
        self.assertEqual("api-profile-binding-missing", out["reason"])
        self.assertEqual("DEAD_LETTER", out["status"])

    def test_user_wide_semantics_are_preserved(self):
        out = _run(_work(profile="", partner=""), _Resolver([_entitlement()]))
        self.assertNotIn("denied", out)
        self.assertEqual("COMPLETED", out["status"])

    def test_entitlement_revoked_between_enqueue_and_execution_is_denied(self):
        out = _run(_work(), _Resolver([]))
        self.assertTrue(out.get("denied"))
        self.assertEqual("DEAD_LETTER", out["status"])
        # no execution happened
        self.assertNotIn("result", out)

    def test_unrelated_profile_row_does_not_authorise(self):
        row = _entitlement(profile="profile-a")
        row["agentId"] = "reference_agent"
        out = _run(_work(), _Resolver([row]))
        self.assertTrue(out.get("denied"))


class TestPipelinePassesProfileToEntitlement(unittest.TestCase):
    def test_check_worker_entitlement_receives_the_work_item_profile(self):
        seen = {}
        real = __import__(
            "agents.ecosystem.worker_authorization", fromlist=["x"]
        ).check_worker_entitlement

        def spy(**kwargs):
            seen.update(kwargs)
            return real(**kwargs)

        with patch("agents.ecosystem.worker_authorization."
                   "check_worker_entitlement", side_effect=spy):
            _run(_work(), _Resolver([_entitlement(profile="profile-a")]))

        self.assertEqual("profile-a", seen.get("api_profile_id"))
        self.assertEqual("user-a", seen.get("user_id"))
        self.assertEqual("tenant-a", seen.get("tenant_id"))


if __name__ == "__main__":
    unittest.main()
