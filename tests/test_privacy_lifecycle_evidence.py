"""
Verified privacy-lifecycle FACTS for G5-PRIVACY-ERASURE-LIFECYCLE-01.

These tests do NOT implement erasure. They pin the premises the erasure
decision depends on, so that nobody can later assume a capability the
architecture does not have.

Each test asserts something that was verified by direct evidence while
assessing G5. If one of these facts stops being true, the erasure decision
must be revisited rather than silently inherited.

The most important of them:

    Deleting the USER_PROFILE_TABLE row does NOT revoke machine
    credentials and does NOT affect authentication.

Credential verification reads `API_PROFILES_TABLE` and the credentials
table; `USER_PROFILE_TABLE` appears nowhere in that path. Cognito is the
sole identity provider. So a user who calls DELETE /me/profile retains a
fully working `ris_...` credential and can still authenticate.
"""

import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "lambda"))

from agents.ecosystem.credentials import CredentialStatus

HANDLER = os.path.join(REPO, "lambda", "handler.py")
CREDENTIALS = os.path.join(REPO, "agents", "ecosystem", "credentials.py")
API_PROFILES = os.path.join(REPO, "agents", "ecosystem", "api_profiles.py")
DYNAMODB_TF = os.path.join(REPO, "terraform", "modules", "dynamodb", "main.tf")
PIPELINE = os.path.join(REPO, "agents", "runtime", "pipeline.py")
DOCUMENTS = os.path.join(REPO, "lambda", "documents.py")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _table_block(name):
    text = _read(DYNAMODB_TF)
    match = re.search(
        r'resource "aws_dynamodb_table" "%s" \{(.*?)\n\}\n' % name, text, re.S)
    assert match, "table %s not found" % name
    return match.group(1)


class TestProfileDeletionLeavesAuthorizationIntact(unittest.TestCase):
    """The security premise behind the erasure decision."""

    def test_credential_verification_never_reads_user_profile_table(self):
        source = _read(CREDENTIALS)
        self.assertNotIn(
            "USER_PROFILE_TABLE", source,
            "if the credential path ever starts reading USER_PROFILE_TABLE, "
            "this erasure premise changes and must be re-reviewed")

    def test_credential_verification_reads_api_profiles_store(self):
        handler = _read(HANDLER)
        self.assertIn(
            'profile_store=sources["profile_store"]', handler)
        self.assertIn('DynamoDBApiProfileStore(', handler)
        self.assertIn('table_name=os.environ.get("API_PROFILES_TABLE")', handler)

    def test_profile_usability_is_an_api_profile_concern(self):
        """`_profile_usable` asks the API profile, not the user profile."""
        source = _read(CREDENTIALS)
        body = source[source.index("def _profile_usable"):
                      source.index("def _persist_new_credential")]
        self.assertIn("api_profiles.effective_status", body)
        self.assertNotIn("USER_PROFILE_TABLE", body)

    def test_delete_handler_touches_only_the_profile_table(self):
        source = _read(HANDLER)
        body = source[source.index("def _handle_me_profile_delete"):
                      source.index("def _documents_context")]
        self.assertIn('os.environ.get(\'USER_PROFILE_TABLE\')', body)
        for other in ("CREDENTIALS_TABLE", "API_PROFILES_TABLE",
                      "ENTITLEMENTS_TABLE", "WORK_ITEMS_TABLE"):
            self.assertNotIn(other, body,
                             "profile deletion must not reach into %s"
                             % other)

    def test_cognito_is_the_sole_identity_provider(self):
        """Profile rows are application data, never an authz input."""
        api = _read(os.path.join(REPO, "terraform", "modules", "api", "main.tf"))
        jwt_routes = re.findall(
            r'route_key\s*=\s*"([^"]+)"\s*\n\s*target[^=]*=\s*"[^"]*"'
            r'\s*\n\s*authorization_type\s*=\s*"JWT"', api)
        self.assertGreater(len(jwt_routes), 20,
                           "human API surface is Cognito-JWT protected")
        self.assertIn("authorizer_id", api)


class TestErasureTargetability(unittest.TestCase):
    """Which domains can even be *found* for a given user."""

    def _gsi_names(self, table):
        block = _table_block(table)
        names = re.findall(r'global_secondary_index\s*\{\s*\n\s*name\s*=\s*"([^"]+)"',
                           block)
        return set(names)

    def test_credentials_have_no_owner_index(self):
        """HARD BLOCKER for bulk credential revocation.

        `ownerUserId` is written on every credential row, but the only
        index is `gsi-digest` (on the secret digest). There is no query
        path to "all credentials owned by user X" -- only a scan.
        """
        gsis = self._gsi_names("credentials")
        self.assertEqual({"gsi-digest"}, gsis,
                         "credential index set changed; re-evaluate whether "
                         "bulk revocation by owner is now possible")
        self.assertNotIn("gsi-owner", gsis)
        self.assertNotIn("ownerUserId", _table_block("credentials"))

    def test_owner_attribute_is_written_at_runtime(self):
        self.assertIn('"ownerUserId": owner', _read(CREDENTIALS),
                      "the attribute exists but is not indexed -- that gap "
                      "is the blocker, not the field")

    def test_entitlements_are_reachable_by_user(self):
        self.assertIn("gsi-user", self._gsi_names("entitlements"))

    def test_jobsearches_are_reachable_by_user(self):
        self.assertIn("gsi-user", self._gsi_names("jobsearches"))

    def test_api_profiles_are_reachable_by_owner(self):
        self.assertIn("gsi-owner", self._gsi_names("api_profiles"))

    def test_work_items_have_no_user_index(self):
        """HARD BLOCKER for targeted erasure of work items.

        `requestedBy` stores the user, but only `gsi-status`
        (tenantId + status) exists. There is no query path to "all work
        items requested by user X" -- only a full table scan.
        """
        gsis = self._gsi_names("work_items")
        self.assertEqual({"gsi-status"}, gsis,
                         "work-item index set changed; re-evaluate whether "
                         "targeted erasure is now possible")
        block = _table_block("work_items")
        self.assertNotIn("userId", block)
        self.assertNotIn("requestedBy", block)
        # The attribute IS written at runtime, just not indexed.
        self.assertIn("'requestedBy': user_id", _read(HANDLER))


class TestOwnershipBoundaries(unittest.TestCase):
    """Mays-RIS must not delete what another system owns."""

    def test_orders_are_not_user_linked_in_ris(self):
        """Orders live in Mays-Orders; RIS holds no userId on them."""
        for path in ("lambda/orders_reader.py", "lambda/handler.py"):
            source = _read(os.path.join(REPO, path))
            order_handlers = [
                chunk for chunk in source.split("def ")
                if chunk.startswith(("_handle_jobsearch", "_handle_offer",
                                    "_handle_me", "_handle_api"))]
            self.assertNotIn(
                "orderId.userId", source,
                "%s must not fabricate user linkage on orders" % path)
        self.assertNotIn("userId", _read(
            os.path.join(REPO, "lambda", "orders_reader.py")))

    def test_documents_are_owned_by_ris_and_user_scoped(self):
        documents = _read(DOCUMENTS)
        self.assertIn(
            'return f"tenant/{tenant}/users/{user_id}/documents/{doc_id}"',
            documents,
            "document keys are tenant+user scoped, so they are RIS-owned "
            "and deletable by user erasure")

    def test_documents_module_can_delete(self):
        self.assertIn("def delete", _read(DOCUMENTS))


class TestExistingLifecycleOperations(unittest.TestCase):
    """What the architecture can already do."""

    def test_credentials_have_a_revoked_state(self):
        self.assertIn("REVOKED", [s.value for s in CredentialStatus])
        self.assertIn("ACTIVE", [s.value for s in CredentialStatus])

    def test_api_profiles_have_no_delete_operation(self):
        """Documented gap: profile deletion is deferred by design."""
        source = _read(API_PROFILES)
        self.assertIn("deletion only via explicit admin cleanup", source)
        self.assertNotIn("def delete_profile", source)

    def test_entitlements_self_expire_via_ttl(self):
        block = _table_block("entitlements")
        self.assertIn("ttl", block)
        self.assertIn('attribute_name = "expiresAt"', block)

    def test_no_code_deletes_work_items(self):
        """Nothing removes work items today.

        Scoped deliberately: the handler DOES delete -- but only the user
        profile row. What must not exist is any delete aimed at the work
        item table.
        """
        pipeline = _read(PIPELINE)
        self.assertNotIn(
            "delete_item", pipeline,
            "the runtime must not delete work items; erasure semantics are "
            "undefined for in-flight work")
        handler = _read(HANDLER)
        self.assertEqual(
            1, handler.count("delete_item"),
            "the handler has exactly one delete_item (the profile row); a "
            "new one must be accompanied by an explicit erasure decision")
        self.assertNotIn("WORK_ITEMS_TABLE", handler[handler.index(
            "delete_item") - 600:handler.index("delete_item") + 600])

    def test_work_item_has_a_cancelled_state_available(self):
        source = _read(os.path.join(REPO, "agents", "base.py"))
        self.assertIn("CANCELLED = 'CANCELLED'", source)
        self.assertIn("EXPIRED = 'EXPIRED'", source)


class TestNoFalseErasureClaim(unittest.TestCase):
    """The public contract must not overclaim."""

    def test_openapi_disclaims_account_erasure(self):
        import yaml
        with open(os.path.join(REPO, "docs", "api", "openapi-platform.yaml"),
                  encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
        op = spec["paths"]["/me/profile"]["delete"]
        self.assertFalse(op.get("x-is-account-erasure", True))
        self.assertEqual("USER_PROFILE_TABLE-row-only",
                         op.get("x-deletion-scope"))
        self.assertNotIn("requestBody", op)

    def test_no_erasure_endpoint_is_advertised(self):
        """No cascade/erasure operation may exist without implementation."""
        import yaml
        with open(os.path.join(REPO, "docs", "api", "openapi-platform.yaml"),
                  encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
        routes = {"%s %s" % (m.upper(), p)
                  for p, item in spec["paths"].items()
                  for m in item if m in ("get", "post", "put", "patch", "delete")}
        leaked = sorted(r for r in routes
                        if "erasure" in r.lower() or "account" in r.lower())
        self.assertEqual([], leaked,
                         "an erasure endpoint must not be documented unless "
                         "implemented: %s" % leaked)


if __name__ == "__main__":
    unittest.main()