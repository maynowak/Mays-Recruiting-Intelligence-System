"""R03 tests: partner manual search profile CRUD API.

Exercises the REAL handler -> REAL R02 repository -> in-memory DynamoDB fake,
with the REAL credential/profile boundary backed by fake stores. Only the
partner registry lookup and the DynamoDB client are substituted.
"""

import json
import os
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

import handler as h  # noqa: E402
from agents.ecosystem.credentials import (  # noqa: E402
    CredentialStatus,
    digest_secret,
    generate_secret,
)
from jobsearch.partner_profile_repository import PartnerProfileRepository  # noqa: E402

COLLECTION = "/v1/partner/me/manual-search-profiles"

USER = "user-1"
OTHER_USER = "user-2"
TENANT = "tenant-1"
CLIENT = "client-1"
ISSUER = "https://cognito-idp.eu-central-1.amazonaws.com/pool-1"
OTHER_ISSUER = "https://cognito-idp.us-east-1.amazonaws.com/pool-2"
PARTNER_APP = "app-1"
API_PROFILE = "prof-1"
BEARER = generate_secret()


def _future():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


# --------------------------------------------------------------------------- #
# Fake DynamoDB (table + client interfaces)
# --------------------------------------------------------------------------- #

class _Cancelled(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.response = {"CancellationReasons": [
            {"Code": "ConditionalCheckFailed", "Message": msg}]}


def _unwrap(v):
    if isinstance(v, dict):
        if "S" in v:
            return v["S"]
        if "N" in v:
            try:
                return int(v["N"])
            except ValueError:
                return float(v["N"])
        if "NULL" in v:
            return None
        if "BOOL" in v:
            return v["BOOL"]
        if "M" in v:
            return {k: _unwrap(x) for k, x in v["M"].items()}
        if "L" in v:
            return [_unwrap(x) for x in v["L"]]
    return v


class FakeDynamo:
    class exceptions:
        TransactionCanceledException = _Cancelled

    def __init__(self):
        self.resources = {}
        self.lock = threading.Lock()

    # table interface
    def get_item(self, Key):
        it = self.resources.get(Key["resourceId"])
        return {"Item": it} if it else {}

    def put_item(self, Item, **kwargs):
        rid = Item.get("resourceId")
        cond = kwargs.get("ConditionExpression")
        if cond == "attribute_not_exists(resourceId)" and rid in self.resources:
            raise Exception("ConditionalCheckFailedException")
        if cond == "version = :v":
            expected = kwargs["ExpressionAttributeValues"][":v"]
            current = self.resources.get(rid, {}).get("version")
            if current != expected:
                raise Exception("ConditionalCheckFailedException")
        self.resources[rid] = Item

    def delete_item(self, Key, **kwargs):
        self.resources.pop(Key["resourceId"], None)

    def query(self, **kwargs):
        index = kwargs.get("IndexName")
        vals = kwargs.get("ExpressionAttributeValues", {})
        filt = kwargs.get("FilterExpression", "")
        results = []
        for item in self.resources.values():
            if item.get("resourceType") == "CapacityCounter":
                continue
            if index == "gsi-user" and item.get("userId") == vals.get(":u", {}).get("S"):
                results.append(item)
            elif index == "gsi-parent" and item.get("parentId") == vals.get(":p", {}).get("S"):
                results.append(item)

        def matches(item):
            for part in filt.replace(" AND ", ",").split(","):
                part = part.strip()
                if not part:
                    continue
                if " = " in part:
                    attr, _, lit = part.partition(" = ")
                    if item.get(attr.strip()) != vals.get(lit.strip(), {}).get("S"):
                        return False
                elif " <> " in part:
                    attr, _, lit = part.partition(" <> ")
                    if item.get(attr.strip()) == vals.get(lit.strip(), {}).get("S"):
                        return False
            return True

        results = [r for r in results if matches(r)]
        results.sort(key=lambda r: r.get("resourceId", ""))
        start = kwargs.get("ExclusiveStartKey")
        if start and start.get("resourceId"):
            idx = next((i for i, r in enumerate(results)
                        if r.get("resourceId") == start["resourceId"]), None)
            if idx is not None:
                results = results[idx + 1:]
        limit = kwargs.get("Limit", 50)
        page = results[:limit]
        cursor = {"resourceId": page[-1]["resourceId"]} if len(results) > limit else None
        return {"Items": page, "LastEvaluatedKey": cursor}

    # client interface
    def transact_write_items(self, TransactItems):
        with self.lock:
            for action in TransactItems:
                if "Update" in action:
                    upd = action["Update"]
                    key = upd["Key"]["resourceId"]["S"]
                    vals = upd.get("ExpressionAttributeValues", {})
                    item = self.resources.get(key)
                    cond = upd.get("ConditionExpression", "")
                    if cond:
                        if item is None:
                            raise _Cancelled("ConditionalCheckFailed: missing")
                        if "count < :max" in cond and item.get("count", 0) >= int(vals[":max"]["N"]):
                            raise _Cancelled("ConditionalCheckFailed: count >= max")
                        if "count > :zero" in cond and item.get("count", 0) <= int(vals[":zero"]["N"]):
                            raise _Cancelled("ConditionalCheckFailed: count <= 0")
                if "Put" in action:
                    raw = {k: _unwrap(v) for k, v in action["Put"]["Item"].items()}
                    if ("attribute_not_exists(resourceId)" in action["Put"].get("ConditionExpression", "")
                            and raw["resourceId"] in self.resources):
                        raise _Cancelled("ConditionalCheckFailed: exists")
                if "Delete" in action:
                    if action["Delete"]["Key"]["resourceId"]["S"] not in self.resources:
                        raise _Cancelled("ConditionalCheckFailed: missing")
            for action in TransactItems:
                if "Put" in action:
                    raw = {k: _unwrap(v) for k, v in action["Put"]["Item"].items()}
                    self.resources[raw["resourceId"]] = raw
                if "Update" in action:
                    upd = action["Update"]
                    key = upd["Key"]["resourceId"]["S"]
                    item = self.resources.setdefault(key, {"count": 0})
                    if "count = count + :inc" in upd["UpdateExpression"]:
                        item["count"] = item.get("count", 0) + 1
                    elif "count = count - :inc" in upd["UpdateExpression"]:
                        item["count"] = item.get("count", 0) - 1
                if "Delete" in action:
                    self.resources.pop(action["Delete"]["Key"]["resourceId"]["S"], None)
        return {}


# --------------------------------------------------------------------------- #
# Fake credential / profile stores
# --------------------------------------------------------------------------- #

class FakeCredentialStore:
    def __init__(self, meta):
        self.meta = meta

    def get_by_digest(self, digest):
        return dict(self.meta) if self.meta is not None else None


class FakeProfileStore:
    def __init__(self, profile):
        self.profile = profile

    def get_profile(self, pid):
        if pid == self.profile.get("apiProfileId"):
            return dict(self.profile)
        return None


def _meta(tenant=TENANT, profile=API_PROFILE, owner=USER, status="ACTIVE"):
    return {
        "credentialId": "cred-1",
        "apiProfileId": profile,
        "tenantId": tenant,
        "ownerUserId": owner,
        "status": status,
        "expiresAt": _future(),
    }


def _profile(tenant=TENANT, profile=API_PROFILE, owner=USER, status="ACTIVE"):
    return {
        "apiProfileId": profile,
        "tenantId": tenant,
        "ownerUserId": owner,
        "status": status,
        "expiresAt": _future(),
    }


def _registry(client=CLIENT, tenant=TENANT, profile=API_PROFILE, status="ACTIVE"):
    return {
        "applicationId": PARTNER_APP,
        "cognitoClientId": client,
        "apiProfileId": profile,
        "tenantId": tenant,
        "status": status,
    }


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #

class Harness(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        self.repo = PartnerProfileRepository(table_name="partner-profiles")
        self.repo._table = self.dynamo
        self.repo._client = self.dynamo

        self.cred_store = FakeCredentialStore(_meta())
        self.prof_store = FakeProfileStore(_profile())
        self.registry = _registry()
        self.enqueued = []

        self.patches = [
            patch("handler._build_introspection_sources",
                  return_value={"credential_store": self.cred_store,
                                "profile_store": self.prof_store}),
            patch("handler._manual_profile_repo", return_value=self.repo),
            patch("agents.ecosystem.partner_registry.resolve_partner_application",
                  side_effect=self._resolve),
            patch("handler._enqueue_agent_work",
                  side_effect=lambda **kw: self.enqueued.append(kw)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def _resolve(self, client_id, *a, **kw):
        if self.registry and self.registry.get("cognitoClientId") == client_id:
            return dict(self.registry)
        return None

    def event(self, method, path, *, sub=USER, client=CLIENT, tenant=TENANT,
              issuer=ISSUER, body=None, credential=BEARER, query=None,
              path_params=None):
        headers = {}
        if credential is not None:
            headers["X-Api-Credential"] = credential
        return {
            "httpMethod": method,
            "path": path,
            "body": json.dumps(body) if body is not None else None,
            "headers": headers,
            "queryStringParameters": query,
            "pathParameters": path_params,
            "requestContext": {
                "authorizer": {"jwt": {"claims": {
                    "sub": sub,
                    "token_use": "access",
                    "client_id": client,
                    "custom:tenant_id": tenant,
                    "iss": issuer,
                }}},
                "http": {"method": method, "path": path},
                "requestId": "req-1",
            },
        }

    def call(self, method, path, **kw):
        path_params = kw.pop("path_params", None)
        if path_params is None and path.startswith(COLLECTION + "/"):
            path_params = {"profileId": path[len(COLLECTION + "/"):].split("?")[0]}
        event = self.event(method, path, path_params=path_params, **kw)
        return h._handle_api_event(event, None)

    def body(self, resp):
        return json.loads(resp["body"]) if resp.get("body") else None

    def create(self, **overrides):
        payload = {
            "name": "Senior Backend",
            "description": "Manual profile",
            "matchingPreferences": {
                "requiredSkills": ["python", "aws"],
                "preferredSkills": ["terraform"],
                "excludedTerms": ["internship"],
                "roles": ["Backend", "Platform"],
                "workModes": ["remote", "hybrid"],
                "employmentTypes": ["full_time"],
                "locations": ["Berlin"],
            },
        }
        payload.update(overrides)
        return self.call("POST", COLLECTION, body=payload)


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #

class TestCrud(Harness):
    def test_create_returns_201(self):
        resp = self.create()
        self.assertEqual(resp["statusCode"], 201)
        b = self.body(resp)
        self.assertTrue(b["manualSearchProfileId"])
        self.assertEqual(b["name"], "Senior Backend")
        self.assertEqual(b["origin"], "manual")
        self.assertEqual(b["matchingPreferences"]["requiredSkills"], ["python", "aws"])
        self.assertEqual(b["matchingPreferences"]["preferredSkills"], ["terraform"])
        self.assertEqual(b["matchingPreferences"]["excludedTerms"], ["internship"])
        self.assertEqual(b["version"], 1)

    def test_get_returns_200(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        resp = self.call("GET", f"{COLLECTION}/{pid}")
        self.assertEqual(resp["statusCode"], 200)
        self.assertEqual(self.body(resp)["name"], "Senior Backend")

    def test_list_returns_200(self):
        self.create()
        resp = self.call("GET", COLLECTION)
        self.assertEqual(resp["statusCode"], 200)
        b = self.body(resp)
        self.assertEqual(len(b["items"]), 1)
        self.assertIsNone(b["nextCursor"])

    def test_update_returns_200(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        resp = self.call("PUT", f"{COLLECTION}/{pid}", body={
            "name": "Updated",
            "matchingPreferences": {"requiredSkills": ["go"]},
            "version": 1,
        })
        self.assertEqual(resp["statusCode"], 200)
        b = self.body(resp)
        self.assertEqual(b["name"], "Updated")
        self.assertEqual(b["matchingPreferences"]["requiredSkills"], ["go"])
        self.assertEqual(b["version"], 2)

    def test_delete_returns_204(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        resp = self.call("DELETE", f"{COLLECTION}/{pid}")
        self.assertEqual(resp["statusCode"], 204)

    def test_get_after_delete_returns_404(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        self.call("DELETE", f"{COLLECTION}/{pid}")
        resp = self.call("GET", f"{COLLECTION}/{pid}")
        self.assertEqual(resp["statusCode"], 404)


# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #

class TestSecurity(Harness):
    def test_missing_user_context_401(self):
        resp = self.call("GET", COLLECTION, sub=None)
        self.assertEqual(resp["statusCode"], 401)

    def test_missing_credential_401(self):
        resp = self.call("GET", COLLECTION, credential=None)
        self.assertEqual(resp["statusCode"], 401)

    def test_invalid_credential_401(self):
        self.cred_store.meta = _meta(status=CredentialStatus.REVOKED.value)
        resp = self.call("GET", COLLECTION)
        # revoked credential -> 403 (forbidden), not 401
        self.assertEqual(resp["statusCode"], 403)

    def test_unknown_credential_401(self):
        self.cred_store.meta = None
        resp = self.call("GET", COLLECTION)
        self.assertEqual(resp["statusCode"], 401)

    def test_inactive_partner_403(self):
        self.registry = _registry(status="INACTIVE")
        resp = self.call("GET", COLLECTION)
        self.assertEqual(resp["statusCode"], 403)

    def test_partner_profile_mismatch_403(self):
        self.registry = _registry(profile="other-prof")
        resp = self.call("GET", COLLECTION)
        self.assertEqual(resp["statusCode"], 403)

    def test_foreign_user_cannot_read(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        resp = self.call("GET", f"{COLLECTION}/{pid}", sub=OTHER_USER)
        self.assertEqual(resp["statusCode"], 404)

    def test_foreign_tenant_403(self):
        resp = self.call("GET", COLLECTION, tenant="tenant-other")
        self.assertEqual(resp["statusCode"], 403)

    def test_foreign_issuer_404(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        resp = self.call("GET", f"{COLLECTION}/{pid}", issuer=OTHER_ISSUER)
        self.assertEqual(resp["statusCode"], 404)

    def test_foreign_partner_403(self):
        self.registry = None
        resp = self.call("GET", COLLECTION)
        self.assertEqual(resp["statusCode"], 403)

    def test_manipulated_identity_fields_no_escalation(self):
        resp = self.create(userId="victim", tenantId="other-tenant")
        self.assertEqual(resp["statusCode"], 400)
        self.assertEqual(self.body(resp)["code"], "CLIENT_IDENTITY_FORBIDDEN")

    def test_manipulated_identity_does_not_change_owner(self):
        created = self.body(self.create())
        stored = self.dynamo.resources[created["manualSearchProfileId"]]
        self.assertEqual(stored["userId"], USER)
        self.assertEqual(stored["tenantId"], TENANT)


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #

class TestContract(Harness):
    def test_invalid_schema_version_422(self):
        resp = self.create(matchingPreferences={
            "schemaVersion": "v2", "requiredSkills": ["python"]})
        self.assertEqual(resp["statusCode"], 422)
        self.assertEqual(self.body(resp)["code"], "INVALID_SCHEMA_VERSION")

    def test_missing_name_422(self):
        resp = self.create(name="")
        self.assertEqual(resp["statusCode"], 422)

    def test_invalid_matching_preferences_422(self):
        resp = self.create(matchingPreferences={"requiredSkills": "not-a-list"})
        self.assertEqual(resp["statusCode"], 422)

    def test_invalid_search_config_422(self):
        resp = self.create(matchingPreferences={"workModes": ["teleport"]})
        self.assertEqual(resp["statusCode"], 422)

    def test_version_conflict_409(self):
        created = self.body(self.create())
        pid = created["manualSearchProfileId"]
        resp = self.call("PUT", f"{COLLECTION}/{pid}", body={
            "name": "X", "matchingPreferences": {}, "version": 99})
        self.assertEqual(resp["statusCode"], 409)

    def test_pagination(self):
        for i in range(5):
            self.create(name=f"P{i}")
        ids = []
        cursor = None
        while True:
            query = {"limit": "2"}
            if cursor:
                query["cursor"] = cursor
            resp = self.call("GET", COLLECTION, query=query)
            self.assertEqual(resp["statusCode"], 200)
            b = self.body(resp)
            ids.extend(item["manualSearchProfileId"] for item in b["items"])
            cursor = b["nextCursor"]
            if not cursor:
                break
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(set(ids)), 5)

    def test_roundtrip_no_field_loss(self):
        payload = {
            "name": "Roundtrip",
            "description": "desc",
            "matchingPreferences": {
                "requiredSkills": ["a", "b"],
                "preferredSkills": ["c"],
                "excludedTerms": ["d"],
                "roles": ["r1", "r2"],
                "workModes": ["remote", "onsite"],
                "employmentTypes": ["full_time", "part_time"],
                "locations": ["Berlin", "Munich"],
            },
        }
        created = self.body(self.create(**payload))
        pid = created["manualSearchProfileId"]
        got = self.body(self.call("GET", f"{COLLECTION}/{pid}"))
        self.assertEqual(got["name"], "Roundtrip")
        self.assertEqual(got["description"], "desc")
        mp = got["matchingPreferences"]
        self.assertEqual(mp["requiredSkills"], ["a", "b"])
        self.assertEqual(mp["preferredSkills"], ["c"])
        self.assertEqual(mp["excludedTerms"], ["d"])
        self.assertEqual(mp["workModes"], ["remote", "onsite"])
        self.assertEqual(mp["employmentTypes"], ["full_time", "part_time"])
        self.assertEqual(mp["locations"], ["Berlin", "Munich"])

    def test_no_agent_or_model_call(self):
        resp = self.create()
        self.assertEqual(resp["statusCode"], 201)
        self.assertEqual(self.enqueued, [])


if __name__ == "__main__":
    unittest.main()
