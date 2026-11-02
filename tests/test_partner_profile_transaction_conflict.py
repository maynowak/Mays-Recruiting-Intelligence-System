"""R07-FIX-02: DynamoDB transaction conflict classification and bounded retry.

Deterministic injection via controlled client doubles; no AWS access.
"""

import json
import os
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lambda"))

from tests.test_partner_ats_profiles_api import AtsHarness  # noqa: E402
from tests.test_partner_manual_profiles_api import (  # noqa: E402
    FakeDynamo, USER, TENANT, ISSUER, PARTNER_APP,
)
from jobsearch.partner_profile_contract import (  # noqa: E402
    ATSSearchProfile, CVDocument, CVSearchProfile,
)
from jobsearch.partner_profile_repository import (  # noqa: E402
    PartnerProfileConflictError, PartnerProfileIndeterminateError,
    PartnerProfileRepository, PartnerProfileTransientError,
    TRANSACTION_MAX_ATTEMPTS, classify_transaction_error,
)

IDENTITY = {
    "user_id": USER, "tenant_id": TENANT,
    "partner_app_id": PARTNER_APP, "issuer": ISSUER,
}


class TxError(Exception):
    def __init__(self, reasons=None, code="TransactionCanceledException"):
        self.response = {"Error": {"Code": code, "Message": "test"}}
        if reasons is not None:
            self.response["CancellationReasons"] = reasons


class TransactionInProgressException(Exception):
    def __init__(self):
        self.response = {"Error": {
            "Code": "TransactionInProgressException", "Message": "test"}}


class TransactionConflictException(Exception):
    def __init__(self):
        self.response = {"Error": {
            "Code": "TransactionConflictException", "Message": "test"}}


class EndpointConnectionError(Exception):
    pass


def _reasons(*codes):
    return [{"Code": code} for code in codes]


class SequenceClient:
    """Delegates to the fake, raising scripted errors first."""

    def __init__(self, inner, errors):
        self.inner = inner
        self.errors = list(errors)
        self.calls = 0

    def transact_write_items(self, TransactItems):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return self.inner.transact_write_items(TransactItems)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _cv(cv_id="cv-1"):
    return CVDocument(cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                      name="cv.pdf", content_type="application/pdf")


def _sp(sp_id="sp-1", cv_id="cv-1"):
    return CVSearchProfile(search_profile_id=sp_id, cv_id=cv_id,
                           user_id=USER, tenant_id=TENANT, name="sp",
                           origin="cv")


def _ats(ats_id="ats-1", sp_id="sp-1", cv_id="cv-1"):
    return ATSSearchProfile(ats_profile_id=ats_id, search_profile_id=sp_id,
                            cv_id=cv_id, user_id=USER, tenant_id=TENANT,
                            name="ats", target_roles=["DevOps"],
                            skills=["Terraform"])


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #

class TestClassification(unittest.TestCase):
    def test_pure_transaction_conflict_is_transient(self):
        kind, failed = classify_transaction_error(
            TxError(_reasons("None", "TransactionConflict")))
        self.assertEqual("transient", kind)
        self.assertEqual({}, failed)

    def test_conditional_check_is_business(self):
        kind, failed = classify_transaction_error(
            TxError(_reasons("ConditionalCheckFailed", "None")))
        self.assertEqual("business", kind)
        self.assertEqual({0: "ConditionalCheckFailed"}, failed)

    def test_mixed_business_and_transient_is_not_retried(self):
        kind, failed = classify_transaction_error(
            TxError(_reasons("ConditionalCheckFailed", "TransactionConflict")))
        self.assertEqual("business", kind)
        self.assertEqual({0: "ConditionalCheckFailed"}, failed)

    def test_missing_reasons_is_indeterminate(self):
        kind, _ = classify_transaction_error(TxError([]))
        self.assertEqual("indeterminate", kind)

    def test_only_none_reasons_is_indeterminate(self):
        kind, _ = classify_transaction_error(TxError(_reasons("None", "None")))
        self.assertEqual("indeterminate", kind)

    def test_unknown_reason_is_indeterminate(self):
        kind, _ = classify_transaction_error(
            TxError(_reasons("SomethingNew", "TransactionConflict")))
        self.assertEqual("indeterminate", kind)

    def test_validation_reason_is_fatal(self):
        kind, _ = classify_transaction_error(TxError(_reasons("ValidationError")))
        self.assertEqual("fatal", kind)

    def test_transaction_in_progress_is_indeterminate(self):
        kind, _ = classify_transaction_error(TransactionInProgressException())
        self.assertEqual("indeterminate", kind)

    def test_top_level_conflict_is_transient(self):
        kind, _ = classify_transaction_error(TransactionConflictException())
        self.assertEqual("transient", kind)

    def test_network_error_is_indeterminate(self):
        kind, _ = classify_transaction_error(EndpointConnectionError())
        self.assertEqual("indeterminate", kind)

    def test_arbitrary_exception_is_fatal(self):
        kind, _ = classify_transaction_error(RuntimeError("boom"))
        self.assertEqual("fatal", kind)


# --------------------------------------------------------------------------- #
# Retry behaviour
# --------------------------------------------------------------------------- #

class _RetryHarnessBase(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        self.repo = PartnerProfileRepository(table_name="ris-fix02")
        self.repo._table = self.dynamo
        self.repo._client = self.dynamo
        self.repo.create(_cv(), **IDENTITY)
        self.repo.create(_sp(), **IDENTITY)
        self.client = SequenceClient(self.dynamo, [])
        self.repo._client = self.client

    def counter(self, rt, parent):
        return self.dynamo.resources[f"capacity#{rt}#{parent}"]["count"]

    def ats_ids(self):
        return [k for k, v in self.dynamo.resources.items()
                if v.get("resourceType") == "ATSSearchProfile"]

    def _run(self, fn):
        with patch("jobsearch.partner_profile_repository.time.sleep") as sleep, \
                patch("jobsearch.partner_profile_repository.random.uniform",
                      return_value=0.01):
            result = fn()
        return result, sleep


class TestRetry(_RetryHarnessBase):
    def test_one_conflict_then_success(self):
        self.client.errors = [TxError(_reasons("TransactionConflict", "None"))]
        rid, sleep = self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual("ats-1", rid)
        self.assertEqual(2, self.client.calls)
        self.assertEqual(1, sleep.call_count)
        self.assertEqual(1, self.counter("ATS", "sp-1"))
        self.assertEqual(["ats-1"], self.ats_ids())

    def test_two_conflicts_then_success(self):
        self.client.errors = [
            TxError(_reasons("None", "TransactionConflict")),
            TxError(_reasons("None", "TransactionConflict")),
        ]
        _, sleep = self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual(3, self.client.calls)
        self.assertEqual(2, sleep.call_count)
        self.assertEqual(1, self.counter("ATS", "sp-1"))

    def test_retry_limit_and_no_partial_state(self):
        self.client.errors = [
            TxError(_reasons("None", "TransactionConflict"))
            for _ in range(TRANSACTION_MAX_ATTEMPTS)
        ]
        with self.assertRaises(PartnerProfileTransientError):
            self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual(TRANSACTION_MAX_ATTEMPTS, self.client.calls)
        self.assertEqual([], self.ats_ids())
        self.assertEqual(0, self.counter("ATS", "sp-1"))

    def test_capacity_business_is_not_retried(self):
        self.client.errors = [TxError(
            _reasons("ConditionalCheckFailed", "None", "None", "None"))]
        with self.assertRaises(PartnerProfileConflictError):
            self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual(1, self.client.calls)
        self.assertEqual([], self.ats_ids())

    def test_parent_guard_is_rechecked_on_retry(self):
        self.repo.reserve_parent_delete(
            "sp-1", **IDENTITY, child_type="ATSSearchProfile")
        self.client.calls = 0
        self.client.errors = [TxError(_reasons("None", "None",
                                               "TransactionConflict", "None"))]
        with self.assertRaises(PartnerProfileConflictError):
            self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual(2, self.client.calls)
        self.assertEqual([], self.ats_ids())

    def test_update_stale_version_is_not_retried(self):
        self.repo.update(_cv(), **IDENTITY, expected_version=1)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.update(_cv(), **IDENTITY, expected_version=1)
        self.assertEqual(0, self.client.calls)

    def test_idempotency_payload_conflict_is_not_retried(self):
        self.repo.create(_ats(), **IDENTITY, idempotency_key="k")
        self.client.calls = 0
        other = _ats(ats_id="ats-2")
        other.name = "different"
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.create(other, **IDENTITY, idempotency_key="k")
        self.assertEqual(1, self.client.calls)

    def test_unknown_outcome_without_idempotency_is_not_retried(self):
        self.client.errors = [EndpointConnectionError()]
        with self.assertRaises(PartnerProfileIndeterminateError):
            self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual(1, self.client.calls)
        self.assertEqual([], self.ats_ids())

    def test_unknown_outcome_with_idempotency_recovers_original(self):
        first = self.repo.create(_ats(), **IDENTITY, idempotency_key="k")
        self.client.errors = [EndpointConnectionError()]
        self.client.calls = 0
        again = self.repo.create(_ats(ats_id="ats-2"), **IDENTITY,
                                 idempotency_key="k")
        self.assertEqual(first, again)
        self.assertEqual(1, self.client.calls)
        self.assertEqual(["ats-1"], self.ats_ids())

    def test_transaction_in_progress_is_not_retried(self):
        self.client.errors = [TransactionInProgressException()]
        with self.assertRaises(PartnerProfileIndeterminateError):
            self._run(lambda: self.repo.create(_ats(), **IDENTITY))
        self.assertEqual(1, self.client.calls)

    def test_delete_retries_without_duplicate_effect(self):
        self.repo.create(_ats(), **IDENTITY)
        self.client.calls = 0
        self.client.errors = [TxError(_reasons("None", "TransactionConflict"))]
        result, sleep = self._run(
            lambda: self.repo.delete("ats-1", **IDENTITY))
        self.assertTrue(result)
        self.assertEqual(2, self.client.calls)
        self.assertEqual(1, sleep.call_count)
        self.assertNotIn("ats-1", self.dynamo.resources)
        self.assertEqual(0, self.counter("ATS", "sp-1"))

    def test_delete_unknown_outcome_is_not_retried(self):
        self.repo.create(_ats(), **IDENTITY)
        self.client.calls = 0
        self.client.errors = [EndpointConnectionError()]
        with self.assertRaises(PartnerProfileIndeterminateError):
            self.repo.delete("ats-1", **IDENTITY)
        self.assertEqual(1, self.client.calls)
        self.assertIn("ats-1", self.dynamo.resources)


# --------------------------------------------------------------------------- #
# Concurrency invariants
# --------------------------------------------------------------------------- #

class TestConcurrencyInvariants(_RetryHarnessBase):
    def test_two_updates_same_version_only_one_wins(self):
        first = _cv()
        second = _cv()
        self.repo.update(first, **IDENTITY, expected_version=1)
        with self.assertRaises(PartnerProfileConflictError):
            self.repo.update(second, **IDENTITY, expected_version=1)

    def test_two_creates_for_last_slot_only_one_wins(self):
        for i in range(4):
            self.repo.create(_ats(ats_id=f"a{i}"), **IDENTITY)
        outcome = []
        barrier = threading.Barrier(2)

        def attempt(i):
            barrier.wait()
            try:
                self.repo.create(_ats(ats_id=f"race{i}"), **IDENTITY)
                outcome.append("ok")
            except PartnerProfileConflictError:
                outcome.append("conflict")

        threads = [threading.Thread(target=attempt, args=(i,))
                   for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(1, outcome.count("ok"), outcome)
        self.assertEqual(1, outcome.count("conflict"), outcome)
        self.assertEqual(5, self.counter("ATS", "sp-1"))


# --------------------------------------------------------------------------- #
# HTTP mapping
# --------------------------------------------------------------------------- #

class TestHttpMapping(AtsHarness):
    def test_exhausted_transient_conflict_is_503(self):
        _, sp_id = self.parent()
        self.repo._client = SequenceClient(self.dynamo, [
            TxError(_reasons("None", "TransactionConflict"))
            for _ in range(TRANSACTION_MAX_ATTEMPTS)
        ])
        with patch("jobsearch.partner_profile_repository.time.sleep"):
            resp = self.create_ats(sp_id)
        self.assertEqual(503, resp["statusCode"])
        self.assertEqual("Service unavailable", self.body(resp)["error"])

    def test_capacity_conflict_remains_409(self):
        _, sp_id = self.parent()
        for i in range(5):
            self.assertEqual(201, self.create_ats(sp_id, name=f"A{i}")["statusCode"])
        self.assertEqual(409, self.create_ats(sp_id, name="A6")["statusCode"])

    def test_stale_update_remains_409(self):
        _, sp_id = self.parent()
        ats_id = self.body(self.create_ats(sp_id))["atsSearchProfileId"]
        resp = self.call("PUT", self.ats_url(sp_id, ats_id),
                         body={"name": "x", "version": 99})
        self.assertEqual(409, resp["statusCode"])

    def test_unknown_outcome_is_503(self):
        _, sp_id = self.parent()
        self.repo._client = SequenceClient(
            self.dynamo, [EndpointConnectionError()])
        resp = self.create_ats(sp_id)
        self.assertEqual(503, resp["statusCode"])


if __name__ == "__main__":
    unittest.main()
