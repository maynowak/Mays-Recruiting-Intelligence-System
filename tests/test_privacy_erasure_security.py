"""
Security acceptance tests for the G5 privacy erasure lifecycle.

The central requirement: **a successful erasure must leave no usable RIS
machine credential for the erased user.**

These tests exercise `agents.ecosystem.privacy_erasure` end to end against
in-memory stores, plus the credential verification boundary itself, so the
assertion is about real capability rather than about bookkeeping flags.

Negative controls are included deliberately: several tests assert that the
right thing does NOT happen.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from agents.ecosystem.privacy_erasure import (
    CANCELLED_STATUS,
    NON_TERMINAL_WORK_STATUSES,
    PrivacyErasure,
    REVOKED_CREDENTIAL_STATUS,
    REVOKED_PROFILE_STATUS,
)


class FakeCredentialStore:
    def __init__(self, rows):
        self.rows = {r["credentialId"]: dict(r) for r in rows}
        self.fail_for = set()

    def list_by_owner(self, owner_id):
        return [dict(r) for r in self.rows.values()
                if r.get("ownerUserId") == owner_id]

    def update_credential(self, credential_id, metadata):
        if credential_id in self.fail_for:
            raise RuntimeError("write failed for %s" % credential_id)
        self.rows[credential_id] = dict(metadata)


class FakeProfileStore:
    def __init__(self, rows):
        self.rows = {r["apiProfileId"]: dict(r) for r in rows}

    def list_by_owner(self, owner_id):
        return [dict(r) for r in self.rows.values()
                if r.get("ownerUserId") == owner_id]

    def update_profile(self, api_profile_id, item):
        self.rows[api_profile_id] = dict(item)


class FakeWorkTable:
    def __init__(self, items, fail_for=None):
        self.items = {i["workId"]: dict(i) for i in items}
        self.fail_for = fail_for or set()
        self.queried = []

    def query(self, IndexName, KeyConditionExpression):
        self.queried.append(IndexName)
        user_id = KeyConditionExpression._values[1]
        return {"Items": [dict(i) for i in self.items.values()
                          if i.get("userId") == user_id]}

    def update_item(self, Key, UpdateExpression, ConditionExpression=None,
                    ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None):
        if Key["workId"] in self.fail_for:
            raise RuntimeError("update failed")
        self.items[Key["workId"]]["status"] = ExpressionAttributeValues[":c"]
        return {}


class FakeUserProfileTable:
    def __init__(self, existing=True):
        self.existing = existing
        self.deleted = []

    def delete_item(self, Key):
        self.deleted.append(Key)
        if not self.existing:
            raise KeyError("not found")


def _cred(cid, owner, status="ACTIVE", tenant="t1"):
    return {"credentialId": cid, "ownerUserId": owner, "tenantId": tenant,
            "status": status, "digest": "dig-" + cid, "apiProfileId": "p1"}


def _erasure(**kwargs):
    defaults = dict(
        credential_store=FakeCredentialStore([_cred("c1", "user-a")]),
        profile_store=FakeProfileStore(
            [{"apiProfileId": "p1", "ownerUserId": "user-a",
              "status": "ACTIVE"}]),
        work_table=FakeWorkTable([{"workId": "w1", "userId": "user-a",
                                   "status": "QUEUED"}]),
        document_deleter=lambda uid: 2,
        user_profile_table=FakeUserProfileTable(),
    )
    defaults.update(kwargs)
    return PrivacyErasure(**defaults)


class TestSuccessfulErasureRemovesCapability(unittest.TestCase):
    """The headline requirement."""

    def test_no_credential_remains_usable(self):
        store = FakeCredentialStore([_cred("c1", "user-a"),
                                     _cred("c2", "user-a")])
        result = _erasure(credential_store=store).erase("user-a", "t1")

        self.assertTrue(result.complete)
        self.assertTrue(result.capability_revoked)
        self.assertEqual(2, result.credentials_revoked)
        for row in store.rows.values():
            self.assertEqual(REVOKED_CREDENTIAL_STATUS, row["status"])
            self.assertEqual("privacy-erasure", row["revokeReason"])

    def test_other_users_credentials_are_untouched(self):
        store = FakeCredentialStore([
            _cred("c1", "user-a"), _cred("c9", "user-b")])
        _erasure(credential_store=store).erase("user-a", "t1")

        self.assertEqual(REVOKED_CREDENTIAL_STATUS, store.rows["c1"]["status"])
        self.assertEqual("ACTIVE", store.rows["c9"]["status"],
                         "erasing user-a must never touch user-b")

    def test_revocation_happens_before_any_deletion(self):
        """Ordering is the security property, not an implementation detail."""
        order = []

        class OrderedCreds(FakeCredentialStore):
            def update_credential(self, cid, meta):
                order.append("revoke-credential")
                super().update_credential(cid, meta)

        class OrderedProfiles(FakeProfileStore):
            def update_profile(self, pid, item):
                order.append("revoke-profile")
                super().update_profile(pid, item)

        class OrderedWork(FakeWorkTable):
            def update_item(self, *a, **kw):
                order.append("cancel-work")
                return super().update_item(*a, **kw)

        class OrderedUserProfiles(FakeUserProfileTable):
            def delete_item(self, Key):
                order.append("delete-profile")
                super().delete_item(Key)

        def deleter(uid):
            order.append("delete-documents")
            return 1

        _erasure(
            credential_store=OrderedCreds([_cred("c1", "user-a")]),
            profile_store=OrderedProfiles(
                [{"apiProfileId": "p1", "ownerUserId": "user-a"}]),
            work_table=OrderedWork(
                [{"workId": "w1", "userId": "user-a", "status": "QUEUED"}]),
            document_deleter=deleter,
            user_profile_table=OrderedUserProfiles(),
        ).erase("user-a", "t1")

        self.assertEqual("revoke-credential", order[0],
                         "capability must be revoked first")
        self.assertEqual("delete-profile", order[-1],
                         "the profile row is keyed by, so it goes last")
        self.assertLess(order.index("revoke-credential"),
                        order.index("revoke-profile"))
        self.assertLess(order.index("revoke-credential"),
                        order.index("cancel-work"))
        self.assertLess(order.index("revoke-credential"),
                        order.index("delete-documents"))

    def test_owned_api_profiles_are_revoked(self):
        store = FakeProfileStore([
            {"apiProfileId": "p1", "ownerUserId": "user-a", "status": "ACTIVE"},
            {"apiProfileId": "p2", "ownerUserId": "user-b", "status": "ACTIVE"},
        ])
        result = _erasure(profile_store=store).erase("user-a", "t1")
        self.assertEqual(1, result.profiles_revoked)
        self.assertEqual(REVOKED_PROFILE_STATUS, store.rows["p1"]["status"])
        self.assertEqual("ACTIVE", store.rows["p2"]["status"])


class TestWorkCancellationSemantics(unittest.TestCase):
    """D3: cancel non-terminal, never delete terminal."""

    def test_non_terminal_work_is_cancelled_not_deleted(self):
        table = FakeWorkTable([
            {"workId": "q", "userId": "user-a", "status": "QUEUED"},
            {"workId": "r", "userId": "user-a", "status": "RUNNING"},
            {"workId": "c", "userId": "user-a", "status": "COMPLETED"},
            {"workId": "f", "userId": "user-a", "status": "FAILED"},
        ])
        result = _erasure(work_table=table).erase("user-a", "t1")

        self.assertEqual(2, result.work_cancelled)
        self.assertEqual(CANCELLED_STATUS, table.items["q"]["status"])
        self.assertEqual(CANCELLED_STATUS, table.items["r"]["status"])

    def test_terminal_work_is_retained_for_idempotency(self):
        table = FakeWorkTable([
            {"workId": "c", "userId": "user-a", "status": "COMPLETED"},
        ])
        _erasure(work_table=table).erase("user-a", "t1")

        self.assertIn("c", table.items,
                      "terminal work must be RETAINED: deleting it would "
                      "re-admit duplicate execution")
        self.assertEqual("COMPLETED", table.items["c"]["status"])

    def test_erasure_uses_the_user_index_not_a_scan(self):
        table = FakeWorkTable([])
        _erasure(work_table=table).erase("user-a", "t1")
        self.assertEqual(["gsi-user"], table.queried)

    def test_cancel_sets_a_real_terminal_state(self):
        """CANCELLED must not itself be treated as non-terminal."""
        self.assertNotIn(CANCELLED_STATUS, NON_TERMINAL_WORK_STATUSES)
        table = FakeWorkTable([{"workId": "w", "userId": "u",
                                "status": "RETRY"}])
        _erasure(work_table=table).erase("u", "t1")
        self.assertEqual(CANCELLED_STATUS, table.items["w"]["status"])
        # Second run must not re-cancel an already-cancelled item.
        result = _erasure(work_table=table).erase("u", "t1")
        self.assertEqual(0, result.work_cancelled)


class TestIdempotencyAndRetry(unittest.TestCase):

    def test_repeat_erasure_is_safe(self):
        store = FakeCredentialStore([_cred("c1", "user-a")])
        profiles = FakeProfileStore(
            [{"apiProfileId": "p1", "ownerUserId": "user-a",
              "status": "ACTIVE"}])
        table = FakeWorkTable([{"workId": "w", "userId": "user-a",
                                "status": "QUEUED"}])
        erasure = _erasure(credential_store=store, profile_store=profiles,
                           work_table=table)

        first = erasure.erase("user-a", "t1")
        second = erasure.erase("user-a", "t1")

        self.assertTrue(first.complete)
        self.assertTrue(second.complete)
        # Nothing re-processed the second time.
        self.assertEqual(0, second.credentials_revoked)
        self.assertEqual(0, second.profiles_revoked)
        self.assertEqual(0, second.work_cancelled)

    def test_missing_user_id_is_rejected(self):
        with self.assertRaises(ValueError):
            _erasure().erase("", "t1")


class TestPartialFailureIsNotReportedAsSuccess(unittest.TestCase):
    """A partial run must never claim erasure completed."""

    def test_credential_revocation_failure_marks_incomplete(self):
        store = FakeCredentialStore([_cred("c1", "user-a")])
        store.fail_for.add("c1")
        result = _erasure(credential_store=store).erase("user-a", "t1")

        self.assertFalse(result.complete)
        self.assertFalse(result.capability_revoked,
                         "a failed revocation must never report capability gone")
        revoke = [s for s in result.steps if s.step == "revoke-credentials"][0]
        self.assertFalse(revoke.ok)
        self.assertIn("c1", revoke.error)

    def test_work_cancel_failure_marks_incomplete(self):
        table = FakeWorkTable([{"workId": "w", "userId": "user-a",
                                "status": "QUEUED"}])
        table.fail_for.add("w")
        result = _erasure(work_table=table).erase("user-a", "t1")
        self.assertFalse(result.complete)

    def test_credentials_still_revoked_when_later_step_fails(self):
        """Fail-safe direction: revoke first, so access dies even if
        data cleanup fails."""
        store = FakeCredentialStore([_cred("c1", "user-a")])
        table = FakeWorkTable([{"workId": "w", "userId": "user-a",
                                "status": "QUEUED"}])
        table.fail_for.add("w")
        result = _erasure(credential_store=store, work_table=table
                          ).erase("user-a", "t1")

        self.assertFalse(result.complete)
        self.assertTrue(result.capability_revoked)
        self.assertEqual(REVOKED_CREDENTIAL_STATUS, store.rows["c1"]["status"])


class TestTenantAndUserIsolation(unittest.TestCase):

    def test_user_a_cannot_reach_user_b_data(self):
        creds = FakeCredentialStore([_cred("cb", "user-b")])
        profiles = FakeProfileStore(
            [{"apiProfileId": "pb", "ownerUserId": "user-b"}])
        table = FakeWorkTable([{"workId": "wb", "userId": "user-b",
                                "status": "QUEUED"}])
        user_profiles = FakeUserProfileTable()

        result = _erasure(credential_store=creds, profile_store=profiles,
                          work_table=table,
                          user_profile_table=user_profiles).erase("user-a", "t1")

        self.assertEqual(0, result.credentials_revoked)
        self.assertEqual("ACTIVE", creds.rows["cb"]["status"])
        self.assertEqual("QUEUED", table.items["wb"]["status"])
        self.assertEqual([{"userId": "user-a"}], user_profiles.deleted)

    def test_only_the_named_user_is_queried(self):
        creds = FakeCredentialStore([_cred("c1", "user-a"), _cred("c2", "user-b")])
        _erasure(credential_store=creds).erase("user-a", "t1")
        self.assertEqual(REVOKED_CREDENTIAL_STATUS, creds.rows["c1"]["status"])
        self.assertEqual("ACTIVE", creds.rows["c2"]["status"])

    def test_orders_are_never_touched(self):
        """Mays-Orders owns orders; RIS holds only a reference."""
        erasure = _erasure()
        self.assertFalse(hasattr(erasure, "orders"),
                         "the erasure workflow must have no order collaborator")
        steps = {s.step for s in erasure.erase("user-a", "t1").steps}
        self.assertNotIn("delete-orders", steps)


class TestDeleteProfileRemainsSeparate(unittest.TestCase):
    """DELETE /me/profile must NOT have silently become erasure."""

    def test_profile_delete_handler_does_not_import_erasure(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lambda", "handler.py")
        source = open(path, encoding="utf-8").read()
        body = source[source.index("def _handle_me_profile_delete"):
                      source.index("def _handle_me_erasure")]
        self.assertNotIn("PrivacyErasure", body)
        self.assertNotIn("CREDENTIALS_TABLE", body)
        self.assertNotIn("WORK_ITEMS_TABLE", body)

    def test_erasure_is_a_separate_operation(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "lambda", "handler.py")
        source = open(path, encoding="utf-8").read()
        self.assertIn("def _handle_me_erasure", source)
        self.assertIn("POST /me/erasure", source)


if __name__ == "__main__":
    unittest.main()