"""Tests for the partner profile DynamoDB repository (R02 / R02-R).

Covers:
- Create / Get / List / Update / Delete
- User / Tenant / Partner / Issuer isolation
- Parent relationships and independent manual profiles
- Capacity limits 10 / 2 / 5 (atomic, concurrency-simulated)
- Version conflicts and pagination
- Round-trip without field loss
- Negative contract tests
"""

import sys
import os
import threading
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from jobsearch.partner_profile_contract import (
    SCHEMA_VERSION,
    ProfileContractError,
    CVDocument,
    CVSearchProfile,
    ATSSearchProfile,
    ManualSearchProfile,
    MatchingPreferences,
    SearchConfiguration,
    MAX_CVS_PER_USER,
    MAX_SEARCH_PROFILES_PER_CV,
    MAX_ATS_PROFILES_PER_SEARCH_PROFILE,
)
from jobsearch.partner_profile_repository import (
    PartnerProfileRepository,
    PartnerProfileConflictError,
)

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _cv(cv_id="cv1", user_id="u1", tenant_id="t1", name="r.pdf", size=10):
    return CVDocument(cv_id=cv_id, user_id=user_id, tenant_id=tenant_id, name=name, size=size)


def _sp(sp_id="sp1", cv_id="cv1", user_id="u1", tenant_id="t1", name="sp"):
    return CVSearchProfile(search_profile_id=sp_id, cv_id=cv_id, user_id=user_id, tenant_id=tenant_id, name=name)


def _ats(ats_id="ats1", sp_id="sp1", cv_id="cv1", user_id="u1", tenant_id="t1", name="a"):
    return ATSSearchProfile(ats_profile_id=ats_id, search_profile_id=sp_id, cv_id=cv_id,
                            user_id=user_id, tenant_id=tenant_id, name=name)


def _manual(mp_id="m1", user_id="u1", tenant_id="t1", name="m"):
    return ManualSearchProfile(manual_profile_id=mp_id, user_id=user_id, tenant_id=tenant_id, name=name,
                               matching_preferences=MatchingPreferences(roles=["Dev"]))


def _unwrap_value(v):
    """Unwrap a DynamoDB serialized value to a plain Python value."""
    if isinstance(v, dict):
        if "S" in v:
            return v["S"]
        if "N" in v:
            n = v["N"]
            try:
                return int(n)
            except ValueError:
                return float(n)
        if "NULL" in v:
            return None
        if "BOOL" in v:
            return v["BOOL"]
        if "M" in v:
            return {k: _unwrap_value(x) for k, x in v["M"].items()}
        if "L" in v:
            return [_unwrap_value(x) for x in v["L"]]
    return v


def _unwrap_item(item):
    return {k: _unwrap_value(v) for k, v in item.items()}


# --------------------------------------------------------------------------- #
# fake client: simulates transact_write_items serially with a lock
# --------------------------------------------------------------------------- #

def _eval_term(term, item, vals):
    term = term.strip()
    if term == "attribute_not_exists(resourceId)":
        return item is None or "resourceId" not in item
    if term == "attribute_exists(resourceId)":
        return item is not None and "resourceId" in item
    if " IN " in term:
        attr, _, rhs = term.partition(" IN ")
        expected = [_unwrap_value(vals[c.strip()]) for c in rhs.strip().strip("()").split(",")]
        return item is not None and item.get(attr.strip()) in expected
    if " < " in term:
        attr, _, lit = term.partition(" < ")
        exp = _unwrap_value(vals[lit.strip()])
        cur = item.get(attr.strip()) if item else None
        return cur is not None and exp is not None and cur < exp
    if " > " in term:
        attr, _, lit = term.partition(" > ")
        exp = _unwrap_value(vals[lit.strip()])
        cur = item.get(attr.strip()) if item else None
        return cur is not None and exp is not None and cur > exp
    if " = " in term:
        attr, _, lit = term.partition(" = ")
        exp = _unwrap_value(vals[lit.strip()])
        return item is not None and item.get(attr.strip()) == exp
    return False


def _eval_and(expr, item, vals):
    for part in expr.split(" AND "):
        if part.strip() and not _eval_term(part, item, vals):
            return False
    return True


def _eval_condition(expr, item, vals):
    if not expr:
        return True
    return any(_eval_and(part, item, vals) for part in expr.split(" OR "))


def _apply_update(item, expr, vals):
    if "count = count + :inc" in expr:
        item["count"] = item.get("count", 0) + 1
    elif "count = count - :inc" in expr:
        item["count"] = item.get("count", 0) - 1
    if "SET state = :active" in expr:
        item["state"] = _unwrap_value(vals[":active"])
    elif "SET state = :deleting" in expr:
        item["state"] = _unwrap_value(vals[":deleting"])
    if ":now" in vals:
        item["updatedAt"] = _unwrap_value(vals[":now"])


class _FakeTransactClient:
    class exceptions:
        class TransactionCanceledException(Exception):
            pass

    def __init__(self, resources=None):
        self.lock = threading.Lock()
        self.calls = []
        self.resources = dict(resources or {})  # rid -> raw python dict

    def transact_write_items(self, TransactItems):
        self.calls.append(list(TransactItems))
        with self.lock:
            for idx, action in enumerate(TransactItems):
                if "ConditionCheck" in action:
                    cc = action["ConditionCheck"]
                    if not _eval_condition(cc["ConditionExpression"],
                                           self.resources.get(cc["Key"]["resourceId"]["S"]),
                                           cc.get("ExpressionAttributeValues", {})):
                        raise self._cancelled(TransactItems, idx, "check")
                if "Put" in action:
                    raw = _unwrap_item(action["Put"]["Item"])
                    cond = action["Put"].get("ConditionExpression", "")
                    if cond and not _eval_condition(
                            cond, self.resources.get(raw["resourceId"]),
                            action["Put"].get("ExpressionAttributeValues", {})):
                        raise self._cancelled(TransactItems, idx, "put")
                if "Update" in action:
                    upd = action["Update"]
                    cond = upd.get("ConditionExpression", "")
                    if cond and not _eval_condition(
                            cond, self.resources.get(upd["Key"]["resourceId"]["S"]),
                            upd.get("ExpressionAttributeValues", {})):
                        raise self._cancelled(TransactItems, idx, "update")
                if "Delete" in action:
                    dele = action["Delete"]
                    cond = dele.get("ConditionExpression", "")
                    if cond and not _eval_condition(
                            cond, self.resources.get(dele["Key"]["resourceId"]["S"]),
                            dele.get("ExpressionAttributeValues", {})):
                        raise self._cancelled(TransactItems, idx, "delete")
            for action in TransactItems:
                if "Put" in action:
                    raw = _unwrap_item(action["Put"]["Item"])
                    self.resources[raw["resourceId"]] = raw
                if "Update" in action:
                    upd = action["Update"]
                    key = upd["Key"]["resourceId"]["S"]
                    item = self.resources.setdefault(key, {"resourceId": key})
                    _apply_update(item, upd["UpdateExpression"],
                                  upd.get("ExpressionAttributeValues", {}))
                if "Delete" in action:
                    self.resources.pop(action["Delete"]["Key"]["resourceId"]["S"], None)
        return {}

    def _cancelled(self, items, idx, kind):
        reasons = [{"Code": "None"} for _ in items]
        reasons[idx] = {"Code": "ConditionalCheckFailed", "Message": f"{kind} failed"}
        exc = self.exceptions.TransactionCanceledException("transaction cancelled")
        exc.response = {"CancellationReasons": reasons}
        return exc


# --------------------------------------------------------------------------- #
# base test case with a fake table + fake client
# --------------------------------------------------------------------------- #

class BaseRepo(unittest.TestCase):
    def setUp(self):
        self.client = _FakeTransactClient()
        self.table = MagicMock()
        self.table.get_item.side_effect = self._get_item
        self.table.query.side_effect = self._query
        self.table.put_item.side_effect = self._put_item
        self.table.delete_item.side_effect = self._delete_item
        self.repo = PartnerProfileRepository(table_name="test-table")
        self.repo._table = self.table
        self.repo._client = self.client

    # -- fake table backing store (raw python dicts) --------------------- #
    def _get_item(self, Key, ConsistentRead=False):
        rid = Key["resourceId"]
        item = self.client.resources.get(rid)
        return {"Item": item} if item else {}

    def _query(self, **kwargs):
        index = kwargs.get("IndexName")
        vals = kwargs.get("ExpressionAttributeValues", {})
        filt = kwargs.get("FilterExpression", "")
        results = []
        for item in self.client.resources.values():
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
                    expected = vals.get(lit.strip(), {}).get("S")
                    if item.get(attr.strip()) != expected:
                        return False
                elif " <> " in part:
                    attr, _, lit = part.partition(" <> ")
                    expected = vals.get(lit.strip(), {}).get("S")
                    if item.get(attr.strip()) == expected:
                        return False
            return True

        results = [r for r in results if matches(r)]
        results.sort(key=lambda r: r.get("resourceId", ""))
        start_key = kwargs.get("ExclusiveStartKey")
        if start_key and start_key.get("resourceId"):
            rid = start_key["resourceId"]
            idx = next((i for i, r in enumerate(results) if r.get("resourceId") == rid), None)
            if idx is not None:
                results = results[idx + 1:]
        limit = kwargs.get("Limit", 50)
        page = results[:limit]
        cursor = {"resourceId": page[-1]["resourceId"]} if len(results) > limit else None
        return {"Items": page, "LastEvaluatedKey": cursor}

    def _put_item(self, Item, **kwargs):
        cond = kwargs.get("ConditionExpression")
        rid = Item.get("resourceId")
        if cond == "attribute_not_exists(resourceId)" and rid in self.client.resources:
            e = Exception("ConditionalCheckFailedException")
            raise e
        self.client.resources[rid] = Item

    def _delete_item(self, Key, **kwargs):
        self.client.resources.pop(Key["resourceId"], None)


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #

class TestCreateGetListUpdateDelete(BaseRepo):
    def test_create_roundtrip(self):
        cv = _cv()
        rid = self.repo.create(cv, user_id="u1", tenant_id="t1")
        self.assertEqual(rid, "cv1")
        got = self.repo.get("cv1", "u1", "t1")
        self.assertIsInstance(got, CVDocument)
        self.assertEqual(got.cv_id, "cv1")
        self.assertEqual(got.size, 10)
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], 1)

    def test_create_duplicate_conflict(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(_cv(), user_id="u1", tenant_id="t1")

    def test_get_missing_returns_none(self):
        self.assertIsNone(self.repo.get("nope", "u1", "t1"))

    def test_update_success(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        cv = _cv(name="new.pdf", size=20)
        self.assertTrue(self.repo.update(cv, user_id="u1", tenant_id="t1", expected_version=1))
        got = self.repo.get("cv1", "u1", "t1")
        self.assertEqual(got.name, "new.pdf")
        self.assertEqual(got.size, 20)

    def test_update_version_conflict(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        cv = _cv(name="x.pdf", size=1)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.update(cv, user_id="u1", tenant_id="t1", expected_version=99)

    def test_delete_success(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        self.assertTrue(self.repo.delete("cv1", "u1", "t1"))
        self.assertIsNone(self.repo.get("cv1", "u1", "t1"))
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], 0)

    def test_delete_missing_returns_false(self):
        self.assertFalse(self.repo.delete("nope", "u1", "t1"))


# --------------------------------------------------------------------------- #
# Isolation
# --------------------------------------------------------------------------- #

class TestIsolation(BaseRepo):
    def test_cross_user_isolation(self):
        self.repo.create(_cv(cv_id="cv1", user_id="u1"), user_id="u1", tenant_id="t1")
        self.assertIsNone(self.repo.get("cv1", "u2", "t1"))

    def test_cross_tenant_isolation(self):
        self.repo.create(_cv(cv_id="cv1", tenant_id="t1"), user_id="u1", tenant_id="t1")
        self.assertIsNone(self.repo.get("cv1", "u1", "t2"))

    def test_cross_partner_isolation(self):
        self.repo.create(_cv(cv_id="cv1"), user_id="u1", tenant_id="t1", partner_app_id="p1")
        self.assertIsNone(self.repo.get("cv1", "u1", "t1", partner_app_id="p2"))

    def test_cross_issuer_isolation(self):
        self.repo.create(_cv(cv_id="cv1"), user_id="u1", tenant_id="t1", issuer="iss1")
        self.assertIsNone(self.repo.get("cv1", "u1", "t1", issuer="iss2"))

    def test_list_by_user_filters_tenant_and_type(self):
        self.repo.create(_cv(cv_id="cv1", user_id="u1", tenant_id="t1"), user_id="u1", tenant_id="t1")
        self.repo.create(_cv(cv_id="cv2", user_id="u1", tenant_id="t2"), user_id="u1", tenant_id="t2")
        items, _ = self.repo.list_by_user("u1", "t1", resource_type="CVDocument")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].cv_id, "cv1")

    def test_no_table_scans_uses_gsi(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        self.repo.list_by_user("u1", "t1", resource_type="CVDocument")
        self.table.query.assert_called()
        call_kwargs = self.table.query.call_args.kwargs
        self.assertEqual(call_kwargs["IndexName"], "gsi-user")
        self.assertNotIn("TableName", call_kwargs)


# --------------------------------------------------------------------------- #
# Hierarchy and capacity (atomic)
# --------------------------------------------------------------------------- #

class TestHierarchy(BaseRepo):
    def test_create_cv_search_profile_requires_parent(self):
        with self.assertRaises(ProfileContractError):
            self.repo.create(_sp(), user_id="u1", tenant_id="t1")

    def test_create_ats_requires_parent_search_profile(self):
        with self.assertRaises(ProfileContractError):
            self.repo.create(_ats(), user_id="u1", tenant_id="t1")

    def test_create_ats_valid_assignment(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        self.repo.create(_sp(), user_id="u1", tenant_id="t1")
        rid = self.repo.create(_ats(), user_id="u1", tenant_id="t1")
        self.assertEqual(rid, "ats1")
        self.assertEqual(self.client.resources["capacity#ATS#sp1"]["count"], 1)

    def test_manual_profile_no_parent(self):
        rid = self.repo.create(_manual(), user_id="u1", tenant_id="t1")
        self.assertEqual(rid, "m1")
        self.assertEqual(self.client.resources.get("capacity#CV#u1", {}).get("count", 0), 0)


class TestAtomicCapacity(BaseRepo):
    def _seed_cvs(self, count):
        for i in range(count):
            self.repo.create(_cv(cv_id=f"cv{i}", user_id="u1"), user_id="u1", tenant_id="t1")

    def test_two_concurrent_creates_last_cv_slot(self):
        """Only one of two concurrent creates on the last free CV slot succeeds."""
        self._seed_cvs(MAX_CVS_PER_USER - 1)  # 9 CVs, 1 slot left
        results = []
        errors = []

        def create_one(suffix):
            try:
                rid = self.repo.create(_cv(cv_id=f"last-{suffix}", user_id="u1"), user_id="u1", tenant_id="t1")
                results.append(rid)
            except PartnerProfileConflictError as e:
                errors.append(str(e))

        t1 = threading.Thread(target=create_one, args=("a",))
        t2 = threading.Thread(target=create_one, args=("b",))
        t1.start(); t2.start(); t1.join(); t2.join()

        self.assertEqual(len(results), 1, f"expected exactly 1 success, got {results}")
        self.assertEqual(len(errors), 1)
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], MAX_CVS_PER_USER)

    def test_two_concurrent_creates_last_sp_slot(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        self.repo.create(_sp(sp_id="sp1"), user_id="u1", tenant_id="t1")  # 1 of 2 used
        results = []

        def create_one(suffix):
            try:
                self.repo.create(_sp(sp_id=f"sp-last-{suffix}", cv_id="cv1"), user_id="u1", tenant_id="t1")
                results.append(suffix)
            except PartnerProfileConflictError:
                pass

        t1 = threading.Thread(target=create_one, args=("a",))
        t2 = threading.Thread(target=create_one, args=("b",))
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(len(results), 1)

    def test_two_concurrent_creates_last_ats_slot(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        self.repo.create(_sp(sp_id="sp1"), user_id="u1", tenant_id="t1")
        for i in range(MAX_ATS_PROFILES_PER_SEARCH_PROFILE - 1):  # 4 of 5 used
            self.repo.create(_ats(ats_id=f"ats{i}", sp_id="sp1"), user_id="u1", tenant_id="t1")
        results = []

        def create_one(suffix):
            try:
                self.repo.create(_ats(ats_id=f"ats-last-{suffix}", sp_id="sp1"), user_id="u1", tenant_id="t1")
                results.append(suffix)
            except PartnerProfileConflictError:
                pass

        t1 = threading.Thread(target=create_one, args=("a",))
        t2 = threading.Thread(target=create_one, args=("b",))
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(len(results), 1)
        self.assertEqual(self.client.resources["capacity#ATS#sp1"]["count"], MAX_ATS_PROFILES_PER_SEARCH_PROFILE)

    def test_delete_and_recreate_no_capacity_drift(self):
        self._seed_cvs(MAX_CVS_PER_USER)  # 10 CVs, full
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(_cv(cv_id="cv-extra", user_id="u1"), user_id="u1", tenant_id="t1")
        self.assertTrue(self.repo.delete("cv0", "u1", "t1"))
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], MAX_CVS_PER_USER - 1)
        self.repo.create(_cv(cv_id="cv0", user_id="u1"), user_id="u1", tenant_id="t1")
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], MAX_CVS_PER_USER)

    def test_failed_transaction_changes_no_capacity(self):
        self._seed_cvs(MAX_CVS_PER_USER - 1)  # 9 CVs
        before = self.client.resources["capacity#CV#u1"]["count"]
        results = []

        def create_one(suffix):
            try:
                self.repo.create(_cv(cv_id=f"race-{suffix}", user_id="u1"), user_id="u1", tenant_id="t1")
                results.append(suffix)
            except PartnerProfileConflictError:
                pass

        t1 = threading.Thread(target=create_one, args=("a",))
        t2 = threading.Thread(target=create_one, args=("b",))
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(len(results), 1)
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], MAX_CVS_PER_USER)
        self.assertEqual(self.client.resources["capacity#CV#u1"]["count"], before + 1)


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #

class TestPagination(BaseRepo):
    def test_pagination_no_lost_or_foreign_resources(self):
        for i in range(7):
            self.repo.create(_cv(cv_id=f"cv{i}", user_id="u1"), user_id="u1", tenant_id="t1")
        self.repo.create(_cv(cv_id="foreign", user_id="u2"), user_id="u2", tenant_id="t1")
        all_ids = []
        cursor = None
        while True:
            items, cursor = self.repo.list_by_user("u1", "t1", resource_type="CVDocument", limit=3, cursor=cursor)
            all_ids.extend([c.cv_id for c in items])
            if not cursor:
                break
        self.assertEqual(sorted(all_ids), sorted([f"cv{i}" for i in range(7)]))
        self.assertNotIn("foreign", all_ids)


# --------------------------------------------------------------------------- #
# Version conflicts and negative contract
# --------------------------------------------------------------------------- #

class TestConflictsAndNegatives(BaseRepo):
    def test_version_conflict_on_update(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        cv = _cv(name="x.pdf", size=1)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.update(cv, user_id="u1", tenant_id="t1", expected_version=5)

    def test_version_conflict_on_delete(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.delete("cv1", "u1", "t1", expected_version=99)

    def test_unknown_id_get_returns_none(self):
        self.assertIsNone(self.repo.get("does-not-exist", "u1", "t1"))

    def test_reserved_id_prefix_rejected(self):
        with self.assertRaises(ValueError):
            self.repo.create(_cv(cv_id="capacity#CV#u1"), user_id="u1", tenant_id="t1")


# --------------------------------------------------------------------------- #
# Transaction structure (AWS DynamoDB compatibility)
# --------------------------------------------------------------------------- #

class TestTransactionStructure(BaseRepo):
    def _last_transact(self):
        self.assertTrue(self.client.calls, "no transaction was issued")
        return self.client.calls[-1]

    def _action_key(self, action):
        for kind in ("ConditionCheck", "Put", "Update", "Delete"):
            if kind in action:
                body = action[kind]
                key = body.get("Key", {}).get("resourceId", {}).get("S")
                if key is None and kind == "Put":
                    key = body.get("Item", {}).get("resourceId", {}).get("S")
                return kind, key
        return None, None

    def test_no_two_actions_target_same_item(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        items = self._last_transact()
        seen = set()
        for action in items:
            kind, key = self._action_key(action)
            self.assertIsNotNone(key)
            pair = (key, "item")
            self.assertNotIn(pair, seen, f"duplicate action on item {key}: {kind}")
            seen.add(pair)

    def test_capacity_condition_is_on_counter_update(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        items = self._last_transact()
        # exactly one Update on the counter and no separate ConditionCheck there
        updates = [a["Update"] for a in items if "Update" in a]
        self.assertEqual(len(updates), 1)
        upd = updates[0]
        self.assertIn("count < :max", upd["ConditionExpression"])
        self.assertIn("count = count + :inc", upd["UpdateExpression"])
        self.assertIn(":max", upd["ExpressionAttributeValues"])
        # no ConditionCheck action at all for the counter
        checks = [a for a in items if "ConditionCheck" in a]
        self.assertEqual(checks, [])

    def test_create_transaction_targets_distinct_items(self):
        # CV: counter + resource, distinct keys
        self.repo.create(_cv(cv_id="cv1"), user_id="u1", tenant_id="t1")
        items = self._last_transact()
        keys = [self._action_key(a)[1] for a in items]
        self.assertEqual(len(keys), len(set(keys)))

    def test_delete_transaction_condition_on_counter_update(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        self.repo.delete("cv1", "u1", "t1")
        items = self._last_transact()
        updates = [a["Update"] for a in items if "Update" in a]
        self.assertEqual(len(updates), 1)
        self.assertIn("count > :zero", updates[0]["ConditionExpression"])

    def test_all_actions_have_low_level_types(self):
        self.repo.create(_cv(), user_id="u1", tenant_id="t1")
        items = self._last_transact()
        valid_types = {"S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"}
        for action in items:
            body = action.get("Put") or action.get("Update") or action.get("ConditionCheck") or action.get("Delete")
            # Check expression values are typed
            for val in (body.get("ExpressionAttributeValues") or {}).values():
                self.assertTrue(set(val.keys()) & valid_types, f"untyped value: {val}")
            if "Put" in action:
                for val in action["Put"]["Item"].values():
                    self.assertTrue(set(val.keys()) & valid_types, f"untyped item value: {val}")


# --------------------------------------------------------------------------- #
# Round-trip / field loss
# --------------------------------------------------------------------------- #

class TestRoundTrip(BaseRepo):
    def test_full_roundtrip_no_field_loss(self):
        sc = SearchConfiguration(
            skills='AWS, "Cloud Architecture"',
            target_roles=["Dev", "Lead"],
            city="Berlin",
            radius_km=50,
            work_modes=["remote", "hybrid"],
            employment_types=["full_time"],
        )
        mp = MatchingPreferences(required_skills=["AWS"], preferred_skills=["Terraform"],
                                 excluded_terms=["Schichtarbeit"])
        m = _manual(mp_id="m1")
        m.search_config = sc
        m.matching_preferences = mp
        self.repo.create(m, user_id="u1", tenant_id="t1")
        got = self.repo.get("m1", "u1", "t1")
        self.assertIsInstance(got, ManualSearchProfile)
        self.assertEqual(got.search_config.skills, 'AWS, "Cloud Architecture"')
        self.assertEqual(got.search_config.target_roles, ["Dev", "Lead"])
        self.assertEqual(got.search_config.city, "Berlin")
        self.assertEqual(got.search_config.radius_km, 50)
        self.assertEqual(got.search_config.work_modes, ["remote", "hybrid"])
        self.assertEqual(got.matching_preferences.required_skills, ["AWS"])
        self.assertEqual(got.matching_preferences.excluded_terms, ["Schichtarbeit"])


if __name__ == "__main__":
    unittest.main()
