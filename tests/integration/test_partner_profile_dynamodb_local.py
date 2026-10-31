"""R07-A: partner-profile persistence against a real DynamoDB Local instance.

The whole module skips unless *both* conditions hold:

* ``RIS_TEST_DYNAMODB_ENDPOINT`` points at a loopback endpoint (see
  ``tests/integration/dynamodb_local_support.py``), and
* boto3/botocore and a reachable DynamoDB Local are available.

The tests create their own ``ris-r07g0-*`` table, never use AWS credentials
and delete only that table.  They are not run in R07-G0 because the toolchain
is missing; they are the executable R07-A plan.
"""

import sys
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.integration.dynamodb_local_support import (  # noqa: E402
    UnsafeTestConfiguration, build_local_dynamodb, new_test_table_name,
    require_local_endpoint, require_test_table_name,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile, CVDocument, CVSearchProfile, SearchConfiguration,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    IDEMPOTENCY_TTL_SECONDS, MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
    MAX_CVS_PER_USER, MAX_SEARCH_PROFILES_PER_CV,
    PartnerProfileConflictError, PartnerProfileRepository,
)

TENANT = "tenant-r07"
PARTNER_APP = "app-r07"
ISSUER = "https://issuer-r07.example"


def _skip_reason():
    try:
        require_local_endpoint()
    except UnsafeTestConfiguration as exc:
        return f"local DynamoDB not configured: {exc}"
    try:
        import boto3  # noqa: F401
        import botocore  # noqa: F401
    except ImportError:
        return "boto3/botocore not installed (see requirements.txt)"
    return None


SKIP_REASON = _skip_reason()


def _uid(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _identity(user):
    return {"user_id": user, "tenant_id": TENANT,
            "partner_app_id": PARTNER_APP, "issuer": ISSUER}


@unittest.skipIf(SKIP_REASON, SKIP_REASON or "")
class DynamoDbLocalBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dynamodb = build_local_dynamodb()
        cls.client = cls.dynamodb.meta.client
        try:
            cls.client.list_tables(Limit=1)
        except Exception as exc:  # pragma: no cover - environment dependent
            raise unittest.SkipTest(
                f"DynamoDB Local not reachable: {type(exc).__name__}") from exc
        cls.table_name = new_test_table_name()
        cls._create_table()
        cls.repo = PartnerProfileRepository(
            table_name=cls.table_name, dynamodb=cls.dynamodb)

    @classmethod
    def _create_table(cls):
        cls.dynamodb.create_table(
            TableName=cls.table_name,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "resourceId", "AttributeType": "S"},
                {"AttributeName": "userId", "AttributeType": "S"},
                {"AttributeName": "tenantId", "AttributeType": "S"},
                {"AttributeName": "resourceType", "AttributeType": "S"},
                {"AttributeName": "parentId", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "resourceId", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {"IndexName": "gsi-user",
                 "KeySchema": [
                     {"AttributeName": "userId", "KeyType": "HASH"},
                     {"AttributeName": "resourceType", "KeyType": "RANGE"}],
                 "Projection": {"ProjectionType": "ALL"}},
                {"IndexName": "gsi-parent",
                 "KeySchema": [
                     {"AttributeName": "parentId", "KeyType": "HASH"}],
                 "Projection": {"ProjectionType": "ALL"}},
            ],
        )
        cls.client.get_waiter("table_exists").wait(
            TableName=cls.table_name,
            WaiterConfig={"Delay": 1, "MaxAttempts": 30})

    @classmethod
    def tearDownClass(cls):
        # Guard again: only the dedicated test table may ever be dropped.
        require_test_table_name(cls.table_name)
        try:
            cls.client.delete_table(TableName=cls.table_name)
        except Exception:  # pragma: no cover - best effort cleanup
            pass

    # helpers ---------------------------------------------------------- #
    def _cv(self, user, cv_id=None):
        cv_id = cv_id or _uid("cv")
        obj = CVDocument(cv_id=cv_id, user_id=user, tenant_id=TENANT,
                         name="cv.pdf", content_type="application/pdf")
        self.repo.create(obj, **_identity(user))
        return cv_id

    def _sp(self, user, cv_id, sp_id=None):
        sp_id = sp_id or _uid("sp")
        obj = CVSearchProfile(
            search_profile_id=sp_id, cv_id=cv_id, user_id=user,
            tenant_id=TENANT, name="sp", origin="cv",
            search_config=SearchConfiguration(
                skills="AWS", target_roles=["Cloud Engineer"],
                city="Darmstadt", radius_km=50, work_modes=["remote"],
                employment_types=["full_time"]))
        self.repo.create(obj, **_identity(user))
        return sp_id

    def _ats(self, user, sp_id, cv_id, ats_id=None, key=None):
        ats_id = ats_id or _uid("ats")
        obj = ATSSearchProfile(
            ats_profile_id=ats_id, search_profile_id=sp_id, cv_id=cv_id,
            user_id=user, tenant_id=TENANT, name="ats",
            target_roles=["DevOps Engineer"], skills=["Terraform"])
        self.repo.create(obj, **_identity(user), idempotency_key=key)
        return ats_id

    def _counter(self, resource_type, parent_id):
        resp = self.dynamodb.Table(self.table_name).get_item(
            Key={"resourceId": f"capacity#{resource_type}#{parent_id}"},
            ConsistentRead=True)
        item = resp.get("Item")
        return None if item is None else int(item["count"])

    def _list(self, sp_id, user, **kwargs):
        return self.repo.list_by_parent(
            sp_id, user, TENANT, "ATSSearchProfile",
            partner_app_id=PARTNER_APP, issuer=ISSUER, **kwargs)

    def _eventually_get(self, resource_id, user):
        return _poll(lambda: self.repo.get(resource_id, **_identity(user)))

    def _eventually_none(self, resource_id, user):
        return _poll(lambda: self.repo.get(
            resource_id, **_identity(user)) is None)

    def _versioned_get(self, resource_id, user, version):
        def read():
            obj = self.repo.get(resource_id, **_identity(user))
            return obj if obj is not None and obj.version == version else None

        return _poll(read)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

class TestPersistence(DynamoDbLocalBase):
    def test_full_hierarchy_roundtrip(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        ats_id = self._ats(user, sp_id, cv_id)
        self.assertIsNotNone(self._eventually_get(cv_id, user))
        self.assertIsNotNone(self._eventually_get(sp_id, user))
        self.assertIsNotNone(self._eventually_get(ats_id, user))

    def test_fresh_repository_reads_stored_items(self):
        user = _uid("user")
        cv_id = self._cv(user)
        fresh = PartnerProfileRepository(
            table_name=self.table_name, dynamodb=self.dynamodb)
        obj = _poll(lambda: fresh.get(cv_id, **_identity(user)))
        self.assertIsNotNone(obj)
        self.assertEqual(cv_id, obj.cv_id)

    def test_update_increments_version(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        obj = self._eventually_get(sp_id, user)
        obj.name = "renamed"
        self.repo.update(obj, **_identity(user), expected_version=1)
        again = self._versioned_get(sp_id, user, 2)
        self.assertIsNotNone(again)
        self.assertEqual("renamed", again.name)

    def test_stale_update_is_rejected(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        obj = self.repo.get(sp_id, **_identity(user))
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.update(obj, **_identity(user), expected_version=99)

    def test_delete_removes_item(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        ats_id = self._ats(user, sp_id, cv_id)
        self.assertTrue(self.repo.delete(ats_id, **_identity(user)))
        self.assertTrue(self._eventually_none(ats_id, user))

    def test_stale_delete_is_rejected(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        ats_id = self._ats(user, sp_id, cv_id)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete(ats_id, **_identity(user), expected_version=99)

    def test_foreign_identity_cannot_read(self):
        user = _uid("user")
        cv_id = self._cv(user)
        self.assertIsNone(self.repo.get(cv_id, **_identity(_uid("other"))))


# --------------------------------------------------------------------------- #
# Capacity
# --------------------------------------------------------------------------- #

class TestCapacity(DynamoDbLocalBase):
    def test_ten_cvs_then_eleventh_rejected(self):
        user = _uid("user")
        for _ in range(MAX_CVS_PER_USER):
            self._cv(user)
        with self.assertRaises(PartnerProfileConflictError):
            self._cv(user)
        self.assertEqual(MAX_CVS_PER_USER, self._counter("CV", user))

    def test_two_search_profiles_then_third_rejected(self):
        user = _uid("user")
        cv_id = self._cv(user)
        for _ in range(MAX_SEARCH_PROFILES_PER_CV):
            self._sp(user, cv_id)
        with self.assertRaises(PartnerProfileConflictError):
            self._sp(user, cv_id)

    def test_five_ats_then_sixth_rejected(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        for _ in range(MAX_ATS_PROFILES_PER_SEARCH_PROFILE):
            self._ats(user, sp_id, cv_id)
        with self.assertRaises(PartnerProfileConflictError):
            self._ats(user, sp_id, cv_id)
        self.assertEqual(5, self._counter("ATS", sp_id))

    def test_concurrent_last_slot_has_one_winner(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        for _ in range(MAX_ATS_PROFILES_PER_SEARCH_PROFILE - 1):
            self._ats(user, sp_id, cv_id)

        outcome = []
        barrier = threading.Barrier(2)

        def attempt(i):
            barrier.wait()
            try:
                self._ats(user, sp_id, cv_id, ats_id=_uid(f"race{i}"))
                outcome.append("ok")
            except PartnerProfileConflictError:
                outcome.append("conflict")

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(attempt, range(2)))
        self.assertEqual(1, outcome.count("ok"), outcome)
        self.assertEqual(1, outcome.count("conflict"), outcome)
        self.assertEqual(5, self._counter("ATS", sp_id))

    def test_delete_frees_capacity(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        ids = [self._ats(user, sp_id, cv_id) for _ in range(5)]
        self.repo.delete(ids[0], **_identity(user))
        self._ats(user, sp_id, cv_id)
        self.assertEqual(5, self._counter("ATS", sp_id))

    def test_different_parents_do_not_share_counters(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp1 = self._sp(user, cv_id)
        sp2 = self._sp(user, cv_id)
        for _ in range(5):
            self._ats(user, sp1, cv_id)
        self._ats(user, sp2, cv_id)
        self.assertEqual(5, self._counter("ATS", sp1))
        self.assertEqual(1, self._counter("ATS", sp2))

    def test_parent_delete_with_children_is_refused(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        self._ats(user, sp_id, cv_id)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete(sp_id, **_identity(user),
                             child_type="ATSSearchProfile")
        self.assertIsNotNone(self.repo.get(sp_id, **_identity(user)))

    def test_delete_vs_create_leaves_no_orphan(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        outcome = []
        barrier = threading.Barrier(2)

        def create_child():
            barrier.wait()
            try:
                self._ats(user, sp_id, cv_id)
                outcome.append("child")
            except Exception:
                pass

        def delete_parent():
            barrier.wait()
            try:
                self.repo.delete(sp_id, **_identity(user),
                                 child_type="ATSSearchProfile")
                outcome.append("delete")
            except PartnerProfileConflictError:
                pass

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda fn: fn(),
                          (create_child, delete_parent)))
        self.assertEqual(1, len(outcome), outcome)
        if self.repo.get(sp_id, **_identity(user)) is None:
            self.assertTrue(_poll(lambda: not self._list(sp_id, user)[0]))


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #

class TestIdempotency(DynamoDbLocalBase):
    def test_same_key_same_payload_replays(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        first = self._ats(user, sp_id, cv_id, key="idem-1")
        replay = self._ats(user, sp_id, cv_id, key="idem-1")
        self.assertEqual(first, replay)
        self.assertEqual(1, self._counter("ATS", sp_id))

    def test_same_key_other_payload_conflicts(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        self._ats(user, sp_id, cv_id, key="idem-2")
        other = ATSSearchProfile(
            ats_profile_id=_uid("ats"), search_profile_id=sp_id,
            cv_id=cv_id, user_id=user, tenant_id=TENANT, name="different",
            target_roles=["SRE"], skills=["Linux"])
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(other, **_identity(user),
                             idempotency_key="idem-2")

    def test_timeout_retry_after_commit_replays(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        ats_id = self._ats(user, sp_id, cv_id, key="idem-3")
        # Client never saw the 201; it retries the same request.
        self.assertEqual(ats_id, self._ats(user, sp_id, cv_id, key="idem-3"))
        self.assertEqual(1, self._counter("ATS", sp_id))

    def test_expired_record_does_not_block_forever(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        first = self._ats(user, sp_id, cv_id, key="idem-4")
        idem_key = self.repo._idem_key(
            "ATSSearchProfile", user, TENANT, PARTNER_APP, ISSUER, "idem-4")
        self.dynamodb.Table(self.table_name).update_item(
            Key={"resourceId": idem_key},
            UpdateExpression="SET expiresAt = :past",
            ExpressionAttributeValues={":past": int(time.time()) - 1})
        second = self._ats(user, sp_id, cv_id, key="idem-4")
        self.assertNotEqual(first, second)

    def test_parallel_identical_retries_share_one_resource(self):
        """Strict contract; red here confirms blocker F-1 (consistency)."""
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        results = []
        barrier = threading.Barrier(2)

        def attempt(i):
            barrier.wait()
            try:
                results.append(("ok", self._ats(
                    user, sp_id, cv_id, ats_id="ats-parallel", key="idem-5")))
            except Exception as exc:  # noqa: BLE001 - surfaced in the assert
                results.append(("err", type(exc).__name__))

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(attempt, range(2)))
        self.assertEqual(2, sum(1 for kind, _ in results if kind == "ok"),
                         results)
        self.assertEqual(1, len({value for _, value in results}))
        self.assertEqual(1, self._counter("ATS", sp_id))


# --------------------------------------------------------------------------- #
# GSI / pagination
# --------------------------------------------------------------------------- #

class TestGsiPagination(DynamoDbLocalBase):
    def test_parent_list_is_eventually_consistent_and_paginates(self):
        user = _uid("user")
        cv_id = self._cv(user)
        sp_id = self._sp(user, cv_id)
        ids = {self._ats(user, sp_id, cv_id) for _ in range(3)}

        def all_visible():
            items, _ = self._list(sp_id, user, limit=50)
            return len(items) >= 3

        self.assertTrue(_poll(all_visible), "GSI did not converge")

        seen = []
        cursor = None
        for _ in range(10):
            page, cursor = self._list(sp_id, user, limit=1, cursor=cursor)
            seen.extend(item.ats_profile_id for item in page)
            if not cursor:
                break
        self.assertEqual(ids, set(seen))
        self.assertEqual(len(seen), len(set(seen)))

    def test_parent_list_does_not_leak_other_users(self):
        owner = _uid("user")
        other = _uid("user")
        cv_id = self._cv(owner)
        sp_id = self._sp(owner, cv_id)
        self._ats(owner, sp_id, cv_id)
        items, _ = self._list(sp_id, other)
        self.assertEqual([], items)

    def test_user_list_excludes_system_items(self):
        user = _uid("user")
        cv_id = self._cv(user)

        def visible():
            items, _ = self.repo.list_by_user(
                user, TENANT, "CVDocument", partner_app_id=PARTNER_APP,
                issuer=ISSUER, limit=50)
            return [item.cv_id for item in items] == [cv_id]

        self.assertTrue(_poll(visible))


def _poll(predicate, timeout=10.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


if __name__ == "__main__":
    unittest.main()
