"""R07-G0: partner-profile integration readiness harness.

These tests are pure Python and never touch AWS.  They cover three things:

1. the local DynamoDB endpoint/table guards that make an accidental AWS call
   impossible;
2. static assertions that Terraform, IAM and the repository still match the
   assumptions R01-R06 were built on (keys, GSIs, TTL, routes, no scans);
3. behavioural checks of the *transaction shape* produced by the repository,
   using the existing in-memory fake.  Real DynamoDB semantics (conditional
   writes, GSI consistency, concurrency) are R07-A and live in
   ``tests/integration/test_partner_profile_dynamodb_local.py``.
"""

import base64
import json
import os
import re
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lambda"))

import handler as h  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    FakeDynamo, USER, TENANT, ISSUER, PARTNER_APP,
)
from tests.integration.dynamodb_local_support import (  # noqa: E402
    ENDPOINT_ENV, TABLE_PREFIX, UnsafeTestConfiguration, build_local_dynamodb,
    new_test_table_name, poll_until, require_local_endpoint,
    require_test_table_name,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile, CVDocument, CVSearchProfile, ManualSearchProfile,
    SearchConfiguration,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    CAPACITY_RULES, IDEMPOTENCY_TTL_SECONDS, PartnerProfileConflictError,
    PartnerProfileRepository,
)

IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}


def _read(*parts):
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _action_key(action):
    for kind in ("Put", "Update", "Delete", "ConditionCheck"):
        if kind in action:
            body = action[kind]
            if kind == "Put":
                return body["Item"]["resourceId"]["S"]
            return body["Key"]["resourceId"]["S"]
    raise AssertionError(f"unknown transaction action: {action!r}")


def _search_config():
    return SearchConfiguration(
        skills="AWS", target_roles=["Cloud Engineer"], city="Darmstadt",
        radius_km=50, work_modes=["remote"], employment_types=["full_time"])


def _cv(cv_id="cv-r07"):
    return CVDocument(cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                      name="cv.pdf", content_type="application/pdf")


def _cvsp(cv_id="cv-r07", sp_id="sp-r07"):
    return CVSearchProfile(search_profile_id=sp_id, cv_id=cv_id,
                           user_id=USER, tenant_id=TENANT, name="sp",
                           origin="cv", search_config=_search_config())


def _ats(sp_id="sp-r07", ats_id="ats-r07", cv_id="cv-r07"):
    return ATSSearchProfile(ats_profile_id=ats_id, search_profile_id=sp_id,
                            cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                            name="ats", target_roles=["DevOps Engineer"],
                            skills=["Terraform"])


# --------------------------------------------------------------------------- #
# 1. Endpoint / table guards
# --------------------------------------------------------------------------- #

class TestEndpointGuard(unittest.TestCase):
    def test_accepts_loopback_variants(self):
        self.assertEqual("http://127.0.0.1:8000",
                         require_local_endpoint("http://127.0.0.1:8000"))
        self.assertEqual("http://localhost:8001",
                         require_local_endpoint("  http://localhost:8001  "))
        self.assertEqual("http://[::1]:8002",
                         require_local_endpoint("http://[::1]:8002"))

    def test_rejects_unset_endpoint(self):
        with self.assertRaises(UnsafeTestConfiguration):
            require_local_endpoint("")
        old = os.environ.pop(ENDPOINT_ENV, None)
        try:
            with self.assertRaises(UnsafeTestConfiguration):
                require_local_endpoint()
        finally:
            if old is not None:
                os.environ[ENDPOINT_ENV] = old

    def test_rejects_aws_and_remote_hosts(self):
        for raw in (
            "https://dynamodb.eu-central-1.amazonaws.com",
            "http://dynamodb.us-east-1.amazonaws.com:8000",
            "http://10.0.0.5:8000",
            "http://192.168.1.10:8000",
            "http://prod.example.com:8000",
            "http://127.0.0.1.nip.io:8000",
            "http://localhost.evil.example:8000",
        ):
            with self.assertRaises(UnsafeTestConfiguration, msg=raw):
                require_local_endpoint(raw)

    def test_rejects_ambiguous_endpoint_shapes(self):
        for raw in (
            "ftp://127.0.0.1:8000",
            "http://user:pass@127.0.0.1:8000",
            "http://127.0.0.1",
            "http://127.0.0.1:8000/table",
            "http://127.0.0.1:8000?x=1",
            "http://127.0.0.1:0",
            "http://127.0.0.1:99999",
            "",
        ):
            with self.assertRaises(UnsafeTestConfiguration, msg=raw):
                require_local_endpoint(raw)

    def test_boto3_absent_is_a_clear_blocker(self):
        """No boto3 -> UnsafeTestConfiguration, never an implicit AWS client."""
        try:
            import boto3  # noqa: F401
        except ImportError:
            with self.assertRaises(UnsafeTestConfiguration):
                build_local_dynamodb("http://127.0.0.1:8000")
        else:  # pragma: no cover - only when boto3 is installed
            resource = build_local_dynamodb("http://127.0.0.1:8000")
            self.assertEqual("http://127.0.0.1:8000",
                             resource.meta.client.meta.endpoint_url)


class TestTableIsolation(unittest.TestCase):
    def test_generated_name_is_namespaced(self):
        name = new_test_table_name()
        self.assertTrue(name.startswith(TABLE_PREFIX))
        self.assertEqual(name, require_test_table_name(name))

    def test_rejects_production_and_foreign_tables(self):
        for name in (
            "ris-dev-dev-partner-profiles",
            "mays-ris-dev-partner-profiles",
            "partner-profiles",
            "mays-orders",
            "ris-r07g0-prod",
            "ris-r07g0-",
            "ris-r07g0-UPPER",
            "",
        ):
            with self.assertRaises(UnsafeTestConfiguration, msg=name):
                require_test_table_name(name)

    def test_rejects_configured_production_table(self):
        old = os.environ.get("PARTNER_PROFILE_TABLE")
        os.environ["PARTNER_PROFILE_TABLE"] = "ris-r07g0-localbox"
        try:
            with self.assertRaises(UnsafeTestConfiguration):
                require_test_table_name("ris-r07g0-localbox")
        finally:
            if old is None:
                os.environ.pop("PARTNER_PROFILE_TABLE", None)
            else:
                os.environ["PARTNER_PROFILE_TABLE"] = old


# --------------------------------------------------------------------------- #
# 2. Static infrastructure assertions
# --------------------------------------------------------------------------- #

def _table_block():
    src = _read("terraform", "modules", "dynamodb", "main.tf")
    start = src.index('resource "aws_dynamodb_table" "partner_profiles"')
    rest = src[start + 10:]
    end = rest.find('\nresource "')
    return rest if end == -1 else rest[:end]


class TestTerraformSchema(unittest.TestCase):
    def test_partner_profile_table_shape(self):
        block = _table_block()
        self.assertIn('hash_key     = "resourceId"', block)
        self.assertIn('billing_mode = "PAY_PER_REQUEST"', block)
        self.assertNotIn("range_key", block.split("global_secondary_index")[0])

    def test_user_and_parent_gsis(self):
        block = _table_block()
        self.assertEqual(2, block.count("global_secondary_index {"))
        user = block.split('name            = "gsi-user"')[1].split("}")[0]
        self.assertIn('hash_key        = "userId"', user)
        self.assertIn('range_key       = "resourceType"', user)
        parent = block.split('name            = "gsi-parent"')[1].split("}")[0]
        self.assertIn('hash_key        = "parentId"', parent)
        self.assertIn('projection_type = "ALL"', parent)

    def test_ttl_is_on_expires_at(self):
        block = _table_block()
        self.assertIn('attribute_name = "expiresAt"', block)
        self.assertIn("enabled        = true", block)

    def test_every_attribute_definition_is_used_by_a_key(self):
        # DynamoDB rejects AttributeDefinitions that no key schema uses.
        block = _table_block()
        attrs = set(re.findall(r'attribute \{\s*name = "([^"]+)"', block))
        keys = set(re.findall(r'(?:hash_key|range_key)\s*=\s*"([^"]+)"',
                              block))
        self.assertEqual(keys, attrs)

    def test_iam_covers_every_repository_action(self):
        src = _read("terraform", "modules", "lambda", "main.tf")
        policy = src.split(
            'resource "aws_iam_role_policy" "lambda_dynamodb_partner_profiles"')[1]
        policy = policy.split('\nresource "')[0]
        for action in ("PutItem", "GetItem", "Query", "DeleteItem",
                       "UpdateItem", "TransactWriteItems"):
            self.assertIn(f'"dynamodb:{action}"', policy)
        self.assertIn("/index/*", policy)
        self.assertNotIn('"dynamodb:Scan"', policy)


class TestApiRoutes(unittest.TestCase):
    EXPECTED = (
        "GET /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles",
        "POST /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles",
        "GET /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/"
        "{atsSearchProfileId}",
        "PUT /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/"
        "{atsSearchProfileId}",
        "DELETE /v1/partner/me/search-profiles/{searchProfileId}/ats-profiles/"
        "{atsSearchProfileId}",
    )

    def test_five_ats_routes_are_explicit(self):
        src = _read("terraform", "modules", "api", "main.tf")
        for route in self.EXPECTED:
            self.assertIn(f'route_key          = "{route}"', src)
        self.assertEqual(5, src.count("/ats-profiles"))

    def test_no_wildcard_proxy_for_partner_routes(self):
        src = _read("terraform", "modules", "api", "main.tf")
        self.assertNotIn("{proxy+}", src)
        self.assertNotIn("ANY /v1/partner", src)

    def test_handler_uses_single_route_dispatcher(self):
        src = _read("lambda", "handler.py")
        self.assertIn("_ATS_PARENT_PREFIX = '/v1/partner/me/search-profiles/'",
                      src)
        # Exactly one dispatcher: its definition plus the single guarded call.
        self.assertEqual(2, src.count("_handle_partner_ats_routes"))
        self.assertEqual(1, src.count(
            "_partner_storage_guard(\n            _handle_partner_ats_routes"))


class TestRepositoryStatic(unittest.TestCase):
    def test_repository_never_scans(self):
        src = _read("jobsearch", "partner_profile_repository.py")
        self.assertNotIn(".scan(", src)

    def test_repository_uses_both_gsis(self):
        src = _read("jobsearch", "partner_profile_repository.py")
        self.assertIn('"IndexName": "gsi-user"', src)
        self.assertIn('"IndexName": "gsi-parent"', src)

    def test_idempotency_ttl_is_24h_and_conditionally_expiring(self):
        self.assertEqual(86400, IDEMPOTENCY_TTL_SECONDS)
        src = _read("jobsearch", "partner_profile_repository.py")
        self.assertIn("expiresAt < :now", src)
        self.assertIn("attribute_not_exists(resourceId) OR expiresAt < :now",
                      src)

    def test_capacity_limits_match_contract(self):
        self.assertEqual({"CVDocument": 10, "CVSearchProfile": 2,
                          "ATSSearchProfile": 5}, CAPACITY_RULES)

    def test_lifecycle_guard_and_child_counter_conditions_exist(self):
        src = _read("jobsearch", "partner_profile_repository.py")
        self.assertIn("attribute_not_exists(resourceId) OR #s = :gactive",
                      src)
        self.assertIn(
            "attribute_not_exists(resourceId) OR #c = :zero", src)
        self.assertIn("#s = :deleting", src)
        self.assertIn('"#c": "count"', src)
        self.assertIn('"#s": "state"', src)

    def test_s3_versioning_and_delete_marker_report(self):
        tf = _read("terraform", "modules", "documents", "main.tf")
        self.assertIn('status = "Enabled"', tf)
        self.assertIn('sse_algorithm = "AES256"', tf)
        docs = _read("lambda", "documents.py")
        self.assertIn("delete_object", docs)
        self.assertIn('"physicalPurge": False', docs)


# --------------------------------------------------------------------------- #
# 3. Behavioural transaction shape (in-memory fake)
# --------------------------------------------------------------------------- #

class TestTransactionShape(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDynamo()
        self.repo = PartnerProfileRepository(table_name="ris-r07g0-unittest")
        self.repo._table = self.fake
        self.repo._client = self.fake

    def _assert_one_action_per_item(self):
        self.assertTrue(self.fake.calls)
        for call in self.fake.calls:
            keys = [_action_key(a) for a in call]
            self.assertEqual(len(keys), len(set(keys)),
                             f"duplicate item in transaction: {keys}")

    def test_every_create_transaction_touches_an_item_once(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        self.repo.create(_ats(), **IDENTITY)
        self._assert_one_action_per_item()

    def test_ats_create_has_counter_parent_guard_and_resource(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        self.fake.calls.clear()
        self.repo.create(_ats(), **IDENTITY)
        keys = [_action_key(a) for a in self.fake.calls[-1]]
        self.assertIn("capacity#ATS#sp-r07", keys)
        self.assertIn("sp-r07", keys)
        self.assertIn("lifecycle#CVSearchProfile#sp-r07", keys)
        self.assertIn("ats-r07", keys)
        counter = next(a["Update"] for a in self.fake.calls[-1]
                       if "Update" in a and "#c" in a["Update"].get(
                           "UpdateExpression", ""))
        self.assertEqual("#c < :max", counter["ConditionExpression"])
        self.assertEqual({"#c": "count"},
                         counter["ExpressionAttributeNames"])
        self.assertEqual("5", counter["ExpressionAttributeValues"][":max"]["N"])

    def test_idempotency_item_carries_epoch_ttl(self):
        before = int(time.time())
        self.repo.create(
            ManualSearchProfile(manual_profile_id="m-1", user_id=USER,
                                tenant_id=TENANT, name="m"),
            **IDENTITY, idempotency_key="key-1")
        call = self.fake.calls[-1]
        put = next(a["Put"] for a in call
                   if a["Put"]["Item"].get("resourceType", {}).get("S")
                   == "IdempotencyRecord")
        item = put["Item"]
        expires = int(item["expiresAt"]["N"])
        self.assertGreaterEqual(expires, before + IDEMPOTENCY_TTL_SECONDS)
        self.assertLessEqual(expires, int(time.time())
                             + IDEMPOTENCY_TTL_SECONDS)
        self.assertEqual("attribute_not_exists(resourceId) OR expiresAt < :now",
                         put["ConditionExpression"])
        self.assertIn(":now", put["ExpressionAttributeValues"])

    def test_live_key_replays_original_resource(self):
        first = ManualSearchProfile(manual_profile_id="m-1", user_id=USER,
                                    tenant_id=TENANT, name="m")
        second = ManualSearchProfile(manual_profile_id="m-2", user_id=USER,
                                     tenant_id=TENANT, name="m")
        rid = self.repo.create(first, **IDENTITY, idempotency_key="same")
        replay = self.repo.create(second, **IDENTITY, idempotency_key="same")
        self.assertEqual(rid, replay)
        self.assertIsNone(self.repo.get("m-2", **IDENTITY))

    def test_live_key_with_other_payload_conflicts(self):
        self.repo.create(
            ManualSearchProfile(manual_profile_id="m-1", user_id=USER,
                                tenant_id=TENANT, name="one"),
            **IDENTITY, idempotency_key="same")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(
                ManualSearchProfile(manual_profile_id="m-2", user_id=USER,
                                    tenant_id=TENANT, name="two"),
                **IDENTITY, idempotency_key="same")

    def test_expired_key_is_logically_reusable(self):
        rid = self.repo.create(
            ManualSearchProfile(manual_profile_id="m-1", user_id=USER,
                                tenant_id=TENANT, name="m"),
            **IDENTITY, idempotency_key="expiring")
        idem_key = next(k for k, v in self.fake.resources.items()
                        if v.get("resourceType") == "IdempotencyRecord")
        # DynamoDB TTL would remove this item *later* (asynchronously). The
        # repository must already honour the 24h contract.
        self.fake.resources[idem_key]["expiresAt"] = int(time.time()) - 1
        new_rid = self.repo.create(
            ManualSearchProfile(manual_profile_id="m-2", user_id=USER,
                                tenant_id=TENANT, name="m"),
            **IDENTITY, idempotency_key="expiring")
        self.assertNotEqual(rid, new_rid)
        self.assertIsNotNone(self.repo.get("m-2", **IDENTITY))

    def test_parent_guard_blocks_create_while_deleting(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        self.repo.reserve_parent_delete(
            "sp-r07", **IDENTITY, child_type="ATSSearchProfile")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(_ats(), **IDENTITY)

    def test_parent_delete_refused_with_children(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        self.repo.create(_ats(), **IDENTITY)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete("sp-r07", **IDENTITY,
                             child_type="ATSSearchProfile")

    def test_delete_reserve_and_finalize_transactions_touch_items_once(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        self.repo.create(_ats(), **IDENTITY)
        # Refused reservation (child counter > 0) still has a well-formed body.
        self.fake.calls.clear()
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.reserve_parent_delete(
                "sp-r07", **IDENTITY, child_type="ATSSearchProfile")
        keys = [_action_key(a) for a in self.fake.calls[-1]]
        self.assertEqual(len(keys), len(set(keys)), keys)
        # A real reservation + finalize pair.
        self.repo.delete("ats-r07", **IDENTITY)
        self.fake.calls.clear()
        reservation = self.repo.reserve_parent_delete(
            "sp-r07", **IDENTITY, child_type="ATSSearchProfile")
        keys = [_action_key(a) for a in self.fake.calls[-1]]
        self.assertEqual(len(keys), len(set(keys)), keys)
        self.fake.calls.clear()
        self.assertTrue(self.repo.finalize_parent_delete(
            reservation, **IDENTITY, expected_version=1))
        keys = [_action_key(a) for a in self.fake.calls[-1]]
        self.assertEqual(len(keys), len(set(keys)), keys)

    def test_parent_gsi_pagination_returns_cursor(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        for i in range(3):
            self.repo.create(_ats(ats_id=f"ats-{i}"), **IDENTITY)
        first, cursor = self.repo.list_by_parent(
            "sp-r07", USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER, limit=1)
        self.assertEqual(1, len(first))
        self.assertIsNotNone(cursor)
        rest, _ = self.repo.list_by_parent(
            "sp-r07", USER, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER, limit=10,
            cursor=cursor)
        self.assertEqual(2, len(rest))

    def test_gsi_list_does_not_leak_other_identity(self):
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_cvsp(), **IDENTITY)
        self.repo.create(_ats(), **IDENTITY)
        items, _ = self.repo.list_by_parent(
            "sp-r07", "user-2", TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER)
        self.assertEqual([], items)


class TestCursorEncoding(unittest.TestCase):
    """R07-G0 characterization of the existing cursor (finding C-1)."""

    def test_cursor_roundtrips(self):
        cursor = {"resourceId": "ats-1", "parentId": "sp-1"}
        self.assertEqual(cursor, h._decode_cursor(h._encode_cursor(cursor)))
        self.assertEqual("invalid", h._decode_cursor("not-base64-!!"))

    def test_cursor_is_encoded_but_not_encrypted(self):
        raw = {"resourceId": "internal-key"}
        encoded = h._encode_cursor(raw)
        self.assertNotIn("internal-key", encoded)
        decoded = json.loads(base64.urlsafe_b64decode(encoded.encode()))
        self.assertEqual(raw, decoded)


class TestPollingHelper(unittest.TestCase):
    def test_poll_returns_last_value_on_timeout(self):
        calls = []

        def predicate():
            calls.append(1)
            return None

        self.assertIsNone(poll_until(predicate, timeout=0.12, interval=0.02))
        self.assertGreaterEqual(len(calls), 2)

    def test_poll_stops_on_truthy(self):
        state = {"n": 0}

        def predicate():
            state["n"] += 1
            return "ok" if state["n"] >= 3 else None

        self.assertEqual("ok", poll_until(predicate, timeout=1, interval=0.01))


if __name__ == "__main__":
    unittest.main()
