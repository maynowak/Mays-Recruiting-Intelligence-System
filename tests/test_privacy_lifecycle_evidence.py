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
ERASURE = os.path.join(REPO, "agents", "ecosystem", "privacy_erasure.py")


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
                      source.index("def _handle_me_erasure")]
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

    def test_credentials_have_owner_index(self):
        """D2 (approved, implemented): owner lookup is now indexed.

        Was `{'gsi-digest'}` only, forcing a full scan for the erasure
        path. The index exists now, so erasure never scans.
        """
        gsis = self._gsi_names("credentials")
        self.assertEqual({"gsi-digest", "gsi-owner"}, gsis,
                         "credential index set changed again; re-review "
                         "whether the erasure path still avoids scans")
        self.assertIn("ownerUserId", _table_block("credentials"))

    def test_credential_owner_lookup_uses_the_index(self):
        """The scan fallback must not come back."""
        source = _read(CREDENTIALS)
        body = source[source.index("class DynamoDBCredentialStore"):]
        method = body[body.index("def list_by_owner"):]
        method = method[:method.index("def list_by_profile")]
        self.assertIn("IndexName=self._owner_index", method)
        self.assertNotIn(".scan(", method)

    def test_owner_attribute_is_written_at_runtime(self):
        self.assertIn('"ownerUserId": owner', _read(CREDENTIALS))

    def test_entitlements_are_reachable_by_user(self):
        self.assertIn("gsi-user", self._gsi_names("entitlements"))

    def test_jobsearches_are_reachable_by_user(self):
        self.assertIn("gsi-user", self._gsi_names("jobsearches"))

    def test_api_profiles_are_reachable_by_owner(self):
        self.assertIn("gsi-owner", self._gsi_names("api_profiles"))

    def test_work_items_have_user_index(self):
        """D2 (approved, implemented): per-user work lookup is indexed.

        Was `{'gsi-status'}` only. Range key is `status` so erasure can
        target non-terminal work without reading terminal history.
        """
        gsis = self._gsi_names("work_items")
        self.assertEqual({"gsi-status", "gsi-user"}, gsis,
                         "work-item index set changed again; re-review the "
                         "erasure path")
        block = _table_block("work_items")
        self.assertIn("userId", block)
        index = block[block.index('name            = "gsi-user"'):]
        self.assertIn('hash_key        = "userId"', index)
        self.assertIn('range_key       = "status"', index)

    def test_worker_registration_persists_the_user(self):
        """A sparse GSI only helps if the attribute is actually written.

        `_register_processing` used to omit the user entirely, so work
        registered by the worker was invisible to any per-user lookup.
        """
        source = _read(PIPELINE)
        block = source[source.index("def _register_processing"):
                       source.index("def _to_dynamo")]
        self.assertIn('"userId": user_id', block)
        self.assertIn('"requestedBy": user_id', block)
        self.assertIn('work.get("requestedBy")', block)


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
        """Still true: erasure REVOKES profiles, it does not delete them."""
        source = _read(API_PROFILES)
        self.assertIn("deletion only via explicit admin cleanup", source)
        self.assertNotIn("def delete_profile", source)

    def test_erasure_revokes_profiles_rather_than_deleting(self):
        """Scoped to the profile step: the module does delete the profile ROW."""
        source = _read(ERASURE)
        step = source[source.index("def _revoke_profiles"):
                      source.index("def _cancel_work")]
        self.assertIn("REVOKED_PROFILE_STATUS", step)
        self.assertNotIn("delete_item", step,
                         "API profiles are revoked, never deleted")

    def test_entitlements_self_expire_via_ttl(self):
        block = _table_block("entitlements")
        self.assertIn("ttl", block)
        self.assertIn('attribute_name = "expiresAt"', block)

    def test_erasure_retains_entitlements(self):
        """Entitlements are never a collaborator of the erasure workflow."""
        source = _read(ERASURE)
        self.assertNotIn("ENTITLEMENTS_TABLE", source,
                         "entitlements are retained; they must not be "
                         "reachable from the erasure path at all")
        self.assertIn("Entitlements are **retained**", source)

    def test_erasure_cancels_rather_than_deletes_work(self):
        """D3: non-terminal work is cancelled; nothing deletes work rows."""
        source = _read(ERASURE)
        self.assertIn("cancel", source)
        work_step = source[source.index("def _cancel_work"):
                           source.index("def _delete_documents")]
        self.assertNotIn("delete_item", work_step)
        self.assertIn("attribute_exists(workId)", work_step)

    def test_runtime_still_never_deletes_work_items(self):
        pipeline = _read(PIPELINE)
        self.assertNotIn(
            "delete_item", pipeline,
            "the runtime must not delete work items; cancellation is the "
            "only lifecycle it owns")

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
        """SUPERSEDED premise, intentionally inverted by the implementation.

        This test previously asserted that NO erasure endpoint may appear in
        the contract, guarding against documenting a capability that did not
        exist. Gate-05 implemented it, so the premise is now the opposite
        and equally important: the advertised erasure contract must match
        what the implementation actually guarantees.
        """
        import yaml
        with open(os.path.join(REPO, "docs", "api", "openapi-platform.yaml"),
                  encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
        self.assertIn("/me/erasure", spec["paths"],
                      "erasure is implemented; it must be documented")

    def test_advertised_erasure_matches_implementation(self):
        """The new invariant: no overclaiming in either direction."""
        import yaml
        with open(os.path.join(REPO, "docs", "api", "openapi-platform.yaml"),
                  encoding="utf-8") as fh:
            spec = yaml.safe_load(fh)
        op = spec["paths"]["/me/erasure"]["post"]

        # Partial failure must be representable, and documented.
        self.assertIn("207", op["responses"],
                      "a partial erasure must not be reported as 200")
        self.assertIn("200", op["responses"])
        self.assertTrue(op.get("x-is-account-erasure"))
        self.assertTrue(op.get("x-terminal-work-retained"))

        # Scope is always the caller: no user/tenant parameter anywhere.
        self.assertNotIn("requestBody", op,
                         "no target parameter: identity comes from the JWT")
        params = [p.get("$ref", p.get("name")) for p in op.get("parameters", [])]
        self.assertEqual([], params)

        # The ordering claim must match the implementation's first step.
        source = _read(ERASURE)
        first_step = re.search(r"# 1\..*?_(\w+)\(result\)", source, re.S)
        self.assertIsNotNone(first_step)
        self.assertEqual("revoke_credentials", first_step.group(1),
                         "documented ordering must match code ordering")

    def test_erasure_documents_what_is_retained(self):
        source = _read(ERASURE)
        self.assertIn("Entitlements are **retained**", source)
        self.assertIn("Orders are **untouched**", source)


if __name__ == "__main__":
    unittest.main()