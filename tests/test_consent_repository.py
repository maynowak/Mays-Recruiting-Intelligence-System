import os
import unittest

try:
    import boto3
    from moto import mock_aws
    from jobsearch.consent_contract import (
        ConsentContext, ConsentContractError, STATUS_GRANTED,
        STATUS_NOT_GRANTED, STATUS_WITHDRAWN)
    from jobsearch.consent_repository import ConsentConflict, ConsentRepository
except ImportError:  # pragma: no cover
    boto3 = None
    mock_aws = lambda fn: fn


CTX = ConsentContext("u1", "t1", "p1", "https://issuer")


def _table():
    db = boto3.resource("dynamodb", region_name="eu-central-1")
    db.create_table(
        TableName="consents",
        KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                   {"AttributeName": "entityKey", "KeyType": "RANGE"}],
        AttributeDefinitions=[{"AttributeName": "scopeKey", "AttributeType": "S"},
                              {"AttributeName": "entityKey", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return ConsentRepository("consents", db)


@unittest.skipUnless(boto3, "boto3/moto unavailable")
class ConsentRepositoryTests(unittest.TestCase):
    @mock_aws
    def test_not_granted_initially(self):
        repo = _table()
        result = repo.get(CTX, "application-storage")
        self.assertEqual(STATUS_NOT_GRANTED, result["status"])
        self.assertEqual(0, result["version"])
        self.assertIsNone(result["grantedAt"])

    @mock_aws
    def test_grant_withdraw_regrant_with_history(self):
        repo = _table()
        granted = repo.grant(CTX, "application-storage", "1.0")
        self.assertEqual(STATUS_GRANTED, granted["status"])
        self.assertEqual(1, granted["version"])

        withdrawn = repo.withdraw(CTX, "application-storage")
        self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"])
        self.assertIsNotNone(withdrawn["withdrawnAt"])
        self.assertEqual(2, withdrawn["version"])

        regranted = repo.grant(CTX, "application-storage", "1.0")
        self.assertEqual(STATUS_GRANTED, regranted["status"])
        self.assertIsNone(regranted["withdrawnAt"])
        self.assertEqual(3, regranted["version"])

        events, _ = repo.history(CTX, "application-storage")
        self.assertEqual(["REGRANTED", "WITHDRAWN", "GRANTED"],
                         [e["event"] for e in events])

    @mock_aws
    def test_repeat_grant_is_idempotent(self):
        repo = _table()
        repo.grant(CTX, "application-storage", "1.0")
        again = repo.grant(CTX, "application-storage", "1.0")
        self.assertEqual(1, again["version"])
        events, _ = repo.history(CTX, "application-storage")
        self.assertEqual(1, len(events))

    @mock_aws
    def test_withdraw_without_consent_fails(self):
        repo = _table()
        with self.assertRaises(ConsentContractError):
            repo.withdraw(CTX, "application-storage")

    @mock_aws
    def test_unknown_purpose_and_notice_version_are_rejected(self):
        repo = _table()
        with self.assertRaises(ConsentContractError):
            repo.grant(CTX, "marketing", "1.0")
        with self.assertRaises(ConsentContractError):
            repo.grant(CTX, "application-storage", "9.9")

    @mock_aws
    def test_tenant_and_user_isolation(self):
        repo = _table()
        repo.grant(CTX, "application-storage", "1.0")
        other_tenant = ConsentContext("u1", "t2", "p1", "https://issuer")
        other_user = ConsentContext("u2", "t1", "p1", "https://issuer")
        self.assertFalse(repo.has_consent(other_tenant, "application-storage"))
        self.assertFalse(repo.has_consent(other_user, "application-storage"))
        self.assertTrue(repo.has_consent(CTX, "application-storage"))

    @mock_aws
    def test_conditional_write_conflict_is_reported(self):
        repo = _table()
        repo.grant(CTX, "application-storage", "1.0")

        def conflict(items):
            raise RuntimeError("ConditionalCheckFailedException")

        repo._transact = conflict
        with self.assertRaises(ConsentConflict):
            repo.withdraw(CTX, "application-storage")
