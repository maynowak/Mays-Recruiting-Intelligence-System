"""P19: APIProfile management HTTP (productive wiring tests).

The domain logic is NOT reimplemented or re-tested here. These tests
cover only the P19 HTTP layer: dispatch, request parsing, role mapping,
neutral error mapping and store wiring on top of the existing
agents.ecosystem.api_profiles contract.
"""
import json
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (str(REPO_ROOT / "lambda"), str(REPO_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

os.environ.setdefault("API_PROFILES_TABLE", "mays-ris-dev-api-profiles")
os.environ.setdefault("AWS_REGION", "eu-central-1")

from agents.ecosystem import api_profiles as ap  # noqa: E402
import handler as h  # noqa: E402


OWNER_SUB = "11111111-1111-1111-1111-111111111111"
OTHER_SUB = "22222222-2222-2222-2222-222222222222"
TENANT = "tenant-p19"
OTHER_TENANT = "tenant-other"


def ev(path, method, sub=OWNER_SUB, groups=(), tenant=TENANT, body=None,
       query=None):
    event = {
        "httpMethod": method,
        "path": path,
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": sub,
                        "email": "synthetic@example.invalid",
                        "custom:tenant_id": tenant,
                        "cognito:groups": list(groups),
                    }
                }
            },
            "requestId": "p19-test",
        },
    }
    if body is not None:
        event["body"] = json.dumps(body)
    if query is not None:
        event["queryStringParameters"] = query
    return event


class Store:
    """In-memory store injected into the handler (same interface as DDB)."""

    def __init__(self):
        self.items = {}
        self.puts = 0

    def put_profile(self, item):
        if item["apiProfileId"] in self.items:
            raise ap.ProfileConflict("apiProfileId exists")
        self.items[item["apiProfileId"]] = dict(item)
        self.puts += 1

    def get_profile(self, pid):
        item = self.items.get(pid)
        return dict(item) if item else None

    def list_by_owner(self, owner):
        return [dict(i) for i in self.items.values()
                if i.get("ownerUserId") == owner]

    def update_profile(self, pid, item):
        if pid not in self.items:
            raise ap.ProfileNotFound(pid)
        self.items[pid] = dict(item)


class CredStore:
    """Minimal credential store stub (routing assertion only)."""

    def list_by_profile(self, api_profile_id):
        return []


class P19Harness(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self._orig = h._aprof_store
        h._aprof_store = lambda: self.store

    def tearDown(self):
        h._aprof_store = self._orig

    def call(self, path, method, **kw):
        resp = h.handler(ev(path, method, **kw), None)
        raw = resp.get("body")
        try:
            body = json.loads(raw) if raw else None
        except (ValueError, TypeError):
            body = raw
        return resp["statusCode"], body


class TestCreate(P19Harness):
    def test_01_post_create_returns_201_pending(self):
        code, body = self.call(
            "/v1/apiprofiles", "POST", body={"name": "alpha"})
        self.assertEqual(code, 201)
        self.assertEqual(body["status"], ap.STATUS_PENDING)
        self.assertEqual(body["ownerUserId"], OWNER_SUB)
        self.assertEqual(body["tenantId"], TENANT)
        self.assertTrue(body["apiProfileId"].startswith("aprof_"))
        self.assertEqual(body["createdBy"]["role"], "owner")

    def test_02_never_active_on_create(self):
        code, body = self.call(
            "/v1/apiprofiles", "POST", body={"name": "beta"})
        self.assertEqual(code, 201)
        self.assertNotEqual(body["status"], ap.STATUS_ACTIVE)

    def test_03_owner_cannot_set_owner_user_id(self):
        code, _ = self.call("/v1/apiprofiles", "POST", body={
            "name": "spoof", "ownerUserId": OTHER_SUB})
        self.assertEqual(code, 400)

    def test_04_client_ref_and_expires_at_not_settable_by_owner(self):
        code, body = self.call("/v1/apiprofiles", "POST", body={
            "name": "gamma", "clientRef": "c1", "expiresAt": "2030-01-01"})
        self.assertEqual(code, 400)
        self.assertEqual(self.store.puts, 0)

    def test_03b_duplicate_name_same_owner_returns_409(self):
        self.call("/v1/apiprofiles", "POST", body={"name": "dup"})
        code, _ = self.call("/v1/apiprofiles", "POST", body={"name": "DUP"})
        self.assertEqual(code, 409)

    def test_04b_same_name_other_owner_allowed(self):
        self.call("/v1/apiprofiles", "POST", body={"name": "shared"})
        code, _ = self.call("/v1/apiprofiles", "POST", sub=OTHER_SUB,
                            body={"name": "shared"})
        self.assertEqual(code, 201)

    def test_05_missing_name_returns_400(self):
        code, _ = self.call("/v1/apiprofiles", "POST", body={})
        self.assertEqual(code, 400)

    def test_06_no_secret_and_no_credential_side_effect(self):
        code, body = self.call("/v1/apiprofiles", "POST",
                               body={"name": "clean"})
        self.assertEqual(code, 201)
        blob = json.dumps(body).lower()
        for forbidden in ("secret", "token", "password", "credential",
                          "bearer", "apikey"):
            self.assertNotIn(forbidden, blob)


class TestRead(P19Harness):
    def _one(self, **kw):
        code, body = self.call("/v1/apiprofiles", "POST",
                               body={"name": "readable"}, **kw)
        self.assertEqual(code, 201)
        return body["apiProfileId"]

    def test_07_get_own_profile(self):
        pid = self._one()
        code, body = self.call(f"/v1/apiprofiles/{pid}", "GET")
        self.assertEqual(code, 200)
        self.assertEqual(body["apiProfileId"], pid)

    def test_08_list_own_profiles(self):
        self._one()
        code, body = self.call("/v1/apiprofiles", "GET")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["items"]), 1)

    def test_09_foreign_profile_neutral_404(self):
        pid = self._one()
        code, body = self.call(f"/v1/apiprofiles/{pid}", "GET", sub=OTHER_SUB)
        self.assertEqual(code, 404)
        self.assertEqual(body, {"error": "Not found"})

    def test_10_unknown_profile_404_identical_to_foreign(self):
        pid = self._one()
        foreign = self.call(f"/v1/apiprofiles/{pid}", "GET", sub=OTHER_SUB)
        missing = self.call("/v1/apiprofiles/aprof_missing", "GET",
                            sub=OTHER_SUB)
        self.assertEqual(foreign, missing)

    def test_11_list_is_tenant_scoped(self):
        self._one()
        code, body = self.call("/v1/apiprofiles", "GET", tenant=OTHER_TENANT)
        self.assertEqual(code, 200)
        self.assertEqual(body["items"], [])

    def test_12_missing_tenant_returns_403(self):
        code, _ = self.call("/v1/apiprofiles", "GET", tenant=None)
        self.assertEqual(code, 403)


class TestUpdate(P19Harness):
    def _one(self, **kw):
        code, body = self.call("/v1/apiprofiles", "POST",
                               body={"name": "upd", "description": "d0"},
                               **kw)
        self.assertEqual(code, 201)
        return body["apiProfileId"]

    def test_13_patch_name_and_description(self):
        pid = self._one()
        code, body = self.call(f"/v1/apiprofiles/{pid}", "PATCH", body={
            "name": "renamed", "description": "d1"})
        self.assertEqual(code, 200)
        self.assertEqual(body["name"], "renamed")
        self.assertEqual(body["description"], "d1")
        self.assertEqual(body["updatedBy"]["role"], "owner")

    def test_14_immutable_fields_rejected(self):
        pid = self._one()
        before = self.store.get_profile(pid)
        for field, value in (("ownerUserId", OTHER_SUB),
                             ("apiProfileId", "aprof_hijack"),
                             ("createdAt", "1999-01-01T00:00:00Z"),
                             ("createdBy", {"actor": "x", "role": "admin"}),
                             ("status", ap.STATUS_ACTIVE),
                             ("tenantId", OTHER_TENANT)):
            code, _ = self.call(f"/v1/apiprofiles/{pid}", "PATCH",
                                body={field: value})
            self.assertEqual(code, 400, field)
        self.assertEqual(self.store.get_profile(pid), before)

    def test_15_patch_foreign_profile_denied(self):
        pid = self._one()
        code, _ = self.call(f"/v1/apiprofiles/{pid}", "PATCH", sub=OTHER_SUB,
                            body={"name": "hijack"})
        self.assertEqual(code, 404)

    def test_16_patch_duplicate_name_conflict(self):
        self.call("/v1/apiprofiles", "POST", body={"name": "taken"})
        pid = self._one()
        code, _ = self.call(f"/v1/apiprofiles/{pid}", "PATCH",
                            body={"name": "taken"})
        self.assertEqual(code, 409)


class TestRoles(P19Harness):
    def test_17_staff_cannot_create(self):
        code, _ = self.call("/v1/apiprofiles", "POST", groups=("Staff",),
                            body={"name": "staff-try"})
        self.assertIn(code, (403, 404))
        self.assertEqual(self.store.puts, 0)

    def test_18_admin_can_create_for_target_user(self):
        code, body = self.call("/v1/apiprofiles", "POST",
                               groups=("admins",),
                               body={"name": "for-other",
                                     "targetOwner": OTHER_SUB})
        self.assertEqual(code, 201)
        self.assertEqual(body["ownerUserId"], OTHER_SUB)
        self.assertEqual(body["tenantId"], TENANT)
        self.assertEqual(body["createdBy"]["role"], "admin")

    def test_19_owner_cannot_create_for_other(self):
        code, _ = self.call("/v1/apiprofiles", "POST", body={
            "name": "nope", "targetOwner": OTHER_SUB})
        self.assertEqual(code, 400)
        self.assertEqual(self.store.puts, 0)

    def test_20_staff_list_requires_reason_and_stays_empty(self):
        code, body = self.call("/v1/apiprofiles", "GET", groups=("Staff",),
                               query={"reason": "support-case-1"})
        self.assertEqual(code, 200)
        self.assertEqual(body["items"], [])


class TestLifecycle(P19Harness):
    def _pending(self, groups=()):
        code, body = self.call("/v1/apiprofiles", "POST", groups=groups,
                               body={"name": f"lc-{len(self.store.items)}"})
        self.assertEqual(code, 201)
        self.assertEqual(body["status"], ap.STATUS_PENDING)
        return body["apiProfileId"]

    def test_21_owner_cannot_activate_pending(self):
        pid = self._pending()
        code, _ = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                            body={"status": ap.STATUS_ACTIVE})
        self.assertIn(code, (403, 404))
        self.assertEqual(self.store.get_profile(pid)["status"],
                         ap.STATUS_PENDING)

    def test_22_admin_can_activate_pending(self):
        pid = self._pending()
        code, body = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                               groups=("admins",),
                               body={"status": ap.STATUS_ACTIVE})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], ap.STATUS_ACTIVE)

    def test_23_owner_disable_requires_reason(self):
        pid = self._pending()
        self.call(f"/v1/apiprofiles/{pid}/status", "POST", groups=("admins",),
                  body={"status": ap.STATUS_ACTIVE})
        code, _ = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                            body={"status": ap.STATUS_DISABLED})
        self.assertEqual(code, 400)
        code, body = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                               body={"status": ap.STATUS_DISABLED,
                                     "reason": "p19 test disable"})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], ap.STATUS_DISABLED)

    def test_24_owner_can_reenable_own_disable(self):
        pid = self._pending()
        self.call(f"/v1/apiprofiles/{pid}/status", "POST", groups=("admins",),
                  body={"status": ap.STATUS_ACTIVE})
        self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                  body={"status": ap.STATUS_DISABLED, "reason": "r"})
        code, body = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                               body={"status": ap.STATUS_ACTIVE})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], ap.STATUS_ACTIVE)

    def test_25_expired_is_not_a_target(self):
        pid = self._pending()
        code, _ = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                            groups=("admins",),
                            body={"status": ap.STATUS_EXPIRED})
        self.assertEqual(code, 400)

    def test_26_unknown_status_rejected(self):
        pid = self._pending()
        code, _ = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                            groups=("admins",), body={"status": "BOGUS"})
        self.assertEqual(code, 400)

    def test_27_revoke_is_admin_only(self):
        pid = self._pending()
        code, _ = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                            body={"status": ap.STATUS_REVOKED,
                                  "reason": "r"})
        self.assertIn(code, (403, 404))

    def test_28_revoked_is_terminal(self):
        pid = self._pending()
        code, body = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                               groups=("admins",),
                               body={"status": ap.STATUS_REVOKED,
                                     "reason": "p19 terminal test"})
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], ap.STATUS_REVOKED)
        for target in (ap.STATUS_ACTIVE, ap.STATUS_DISABLED):
            code, _ = self.call(f"/v1/apiprofiles/{pid}/status", "POST",
                                groups=("admins",),
                                body={"status": target, "reason": "r"})
            self.assertEqual(code, 409, target)
        self.assertEqual(self.store.get_profile(pid)["status"],
                         ap.STATUS_REVOKED)


class TestAuthAndAudit(P19Harness):
    def test_29_missing_jwt_401(self):
        event = {"httpMethod": "GET", "path": "/v1/apiprofiles",
                 "requestContext": {"authorizer": {"jwt": {"claims": {}}}}}
        resp = h.handler(event, None)
        self.assertEqual(resp["statusCode"], 401)

    def test_30_credential_paths_still_reach_credential_handler(self):
        """P19 must not steal the P15/P16 credential routes.

        Both handlers live under /v1/apiprofiles. The credential branch
        is asserted by its own success shape (200 + {"items": []}),
        not by the apiprofile handler (which would 404 this path).
        """
        os.environ["CREDENTIALS_TABLE"] = "mays-ris-dev-credentials"
        orig_sources = h._cred_sources
        h._cred_sources = lambda: {"credentials": CredStore(),
                                   "profiles": self.store}
        try:
            code, body = self.call("/v1/apiprofiles/aprof_x/credentials",
                                   "GET")
        finally:
            h._cred_sources = orig_sources
            os.environ.pop("CREDENTIALS_TABLE", None)
        self.assertEqual(code, 200)
        self.assertEqual(body, {"items": []})

    def test_31_audit_lines_emitted(self):
        import logging

        records = []

        class Cap(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("agents.ecosystem.api_profiles")
        handler_obj = Cap()
        logger.addHandler(handler_obj)
        prev = logger.level
        logger.setLevel(logging.WARNING)
        try:
            self.call("/v1/apiprofiles", "POST", body={"name": "audited"})
        finally:
            logger.removeHandler(handler_obj)
            logger.setLevel(prev)
        blob = "\n".join(records)
        self.assertIn("apiprofile-audit", blob)
        self.assertIn("action=profile-create", blob)
        self.assertIn("outcome=success", blob)

    def test_32_method_not_allowed_paths_404(self):
        for method in ("DELETE", "PUT"):
            code, _ = self.call("/v1/apiprofiles/aprof_x", method)
            self.assertEqual(code, 404, method)
        code, _ = self.call("/v1/apiprofiles", "DELETE")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
