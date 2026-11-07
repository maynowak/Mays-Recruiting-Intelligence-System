"""Synthetic active-notice pilot E2E (local only, no AWS, no deployment).

Complements ``test_consent_e2e_joint.py`` for the *fully enabled* pilot state:

    APPLICATION_CONSENT_ENFORCED=true
    CONSENT_NOTICE_STATE_ENFORCED=true
    NOTICE_REGISTRY["application-storage"]["1.0"] = ACTIVE + legal ref

It proves the intended end state before any real activation: writes need a
grant, grants need a grantable notice, withdrawal blocks new writes, and
read/export/delete remain available. No live persistence is involved.
"""

import json
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

try:
    import boto3
    from moto import mock_aws
except ImportError:  # pragma: no cover - moto/boto3 unavailable
    boto3 = None
    mock_aws = None

from jobsearch import consent_contract
from jobsearch.consent_contract import (
    NOTICE_ACTIVE, NOTICE_APPROVED, NOTICE_DRAFT, NOTICE_SUPERSEDED,
    STATUS_GRANTED, STATUS_WITHDRAWN, ConsentContext,
    ConsentContractError, notice_version,
)
from jobsearch.consent_repository import ConsentRepository

from tests.application_e2e_harness import synthetic_create
from tests.consent_e2e_harness import (
    PRIMARY, SECONDARY_USER, ConsentGateDenied, JointConsentE2EHarness,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lambda") not in sys.path:
    sys.path.insert(0, str(ROOT / "lambda"))

PURPOSE = "application-storage"
VERSION = "1.0"
LEGAL_REF = "SYNTHETIC-LEGAL-APPROVAL-NOT-REAL"


def _entry(**changes):
    return replace(notice_version(PURPOSE, VERSION), **changes)


def _active_notice():
    return _entry(state=NOTICE_ACTIVE, legal_approval_ref=LEGAL_REF)


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class ActiveNoticePilotE2ETests(unittest.TestCase):
    APPS = "synthetic-active-notice-applications"
    CONSENTS = "synthetic-active-notice-consents"

    def setUp(self):
        self.env = self._environment()
        self.env.__enter__()
        self.aws = mock_aws()
        self.aws.start()
        self.db = boto3.resource("dynamodb", region_name="eu-central-1")
        self._create_tables(self.db)
        self.harness = JointConsentE2EHarness(
            self.db, self.APPS, self.CONSENTS, enforced=True)

    def tearDown(self):
        self.aws.stop()
        self.env.__exit__(None, None, None)

    @staticmethod
    def _environment():
        class Environment:
            KEYS = (
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION",
                "AWS_EC2_METADATA_DISABLED", "RIS_CURSOR_SECRET",
                "APPLICATION_CONSENT_ENFORCED",
                "CONSENT_NOTICE_STATE_ENFORCED",
            )

            def __enter__(self):
                self.old = {k: os.environ.get(k) for k in self.KEYS}
                os.environ.update({
                    "AWS_ACCESS_KEY_ID": "testing",
                    "AWS_SECRET_ACCESS_KEY": "testing",
                    "AWS_SESSION_TOKEN": "testing",
                    "AWS_DEFAULT_REGION": "eu-central-1",
                    "AWS_EC2_METADATA_DISABLED": "true",
                    "RIS_CURSOR_SECRET": "local-only-active-notice-pilot-secret",
                    # Fully enabled pilot state. The notice itself is patched
                    # to ACTIVE only inside these tests; the real registry is
                    # unchanged (still DRAFT).
                    "APPLICATION_CONSENT_ENFORCED": "true",
                    "CONSENT_NOTICE_STATE_ENFORCED": "true",
                })
                return self

            def __exit__(self, *_):
                for key, value in self.old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        return Environment()

    @staticmethod
    def _create_tables(db):
        db.create_table(
            TableName=ActiveNoticePilotE2ETests.APPS,
            KeySchema=[
                {"AttributeName": "applicationId", "KeyType": "HASH"},
                {"AttributeName": "entityKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "applicationId", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
                {"AttributeName": "ownerKey", "AttributeType": "S"},
                {"AttributeName": "updatedAt", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "gsi-owner",
                "KeySchema": [
                    {"AttributeName": "ownerKey", "KeyType": "HASH"},
                    {"AttributeName": "updatedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 1,
                                          "WriteCapacityUnits": 1},
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        db.create_table(
            TableName=ActiveNoticePilotE2ETests.CONSENTS,
            KeySchema=[
                {"AttributeName": "scopeKey", "KeyType": "HASH"},
                {"AttributeName": "entityKey", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "scopeKey", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

    def _handler_gate(self):
        import handler

        with patch.object(handler, "_consent_repo",
                          lambda: self.harness.consent):
            return handler._application_consent_error(
                PRIMARY.consent_context())

    def test_full_pilot_flow_with_active_notice(self):
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: _active_notice()}):
            harness = self.harness

            # 1) No consent -> no write at repository or handler seam.
            self.assertFalse(harness.write_allowed())
            with self.assertRaises(ConsentGateDenied):
                harness.create(synthetic_create(1))
            denied = self._handler_gate()
            self.assertEqual(403, denied["statusCode"])
            self.assertEqual("CONSENT_REQUIRED",
                             json.loads(denied["body"])["code"])

            # 2) Grant succeeds only because the patched notice is ACTIVE.
            granted = harness.grant()
            self.assertEqual(STATUS_GRANTED, granted["status"])
            self.assertEqual(NOTICE_ACTIVE, granted["noticeState"])
            self.assertTrue(granted["noticeApproved"])
            self.assertTrue(granted["acceptedForNewGrant"])
            self.assertIsNone(self._handler_gate())

            # 3) Create and update are allowed with a grant.
            created = harness.create(synthetic_create(1))
            app_id = created["applicationId"]
            self.assertEqual(1, created["version"])
            updated = harness.patch(app_id, {
                "job": {"jobId": "synthetic-job-updated"},
                "expectedVersion": 1,
            })
            self.assertEqual(2, updated["version"])

            # 4) Withdraw -> new writes denied again.
            withdrawn = harness.withdraw()
            self.assertEqual(STATUS_WITHDRAWN, withdrawn["status"])
            self.assertFalse(harness.write_allowed())
            with self.assertRaises(ConsentGateDenied):
                harness.patch(app_id, {
                    "job": {"jobId": "synthetic-job-after-withdrawal"},
                    "expectedVersion": 2,
                })
            with self.assertRaises(ConsentGateDenied):
                harness.create(synthetic_create(2))
            denied = self._handler_gate()
            self.assertEqual(403, denied["statusCode"])

            # 5) Read, export and delete remain available after withdrawal.
            current = harness.get(app_id)
            self.assertEqual(app_id, current["applicationId"])
            self.assertEqual(2, current["version"])
            exported = harness.export(app_id)
            self.assertEqual(app_id,
                             exported["application"]["applicationId"])
            harness.delete(app_id, current["version"])
            with self.assertRaises(Exception):
                harness.get(app_id)

            # 6) Regrant under the still-ACTIVE notice works again.
            regranted = harness.grant()
            self.assertEqual(STATUS_GRANTED, regranted["status"])
            self.assertIsNone(self._handler_gate())
            recreated = harness.create(synthetic_create(3))
            self.assertNotEqual(app_id, recreated["applicationId"])
            self.assertEqual(1, recreated["version"])

    def test_consent_never_leaks_across_user_or_tenant_with_active_notice(self):
        with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                        {VERSION: _active_notice()}):
            self.harness.grant()
            self.assertTrue(self.harness.write_allowed(PRIMARY))
            self.assertFalse(self.harness.write_allowed(SECONDARY_USER))
            with self.assertRaises(ConsentGateDenied):
                self.harness.create(synthetic_create(7),
                                    identity=SECONDARY_USER)


@unittest.skipUnless(boto3 and mock_aws, "boto3/moto unavailable")
class ActiveNoticeGrantMatrixTests(unittest.TestCase):
    """Grantability under CONSENT_NOTICE_STATE_ENFORCED=true."""

    def _repo(self, name):
        db = boto3.resource("dynamodb", region_name="eu-central-1")
        db.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": "scopeKey", "KeyType": "HASH"},
                       {"AttributeName": "entityKey", "KeyType": "RANGE"}],
            AttributeDefinitions=[
                {"AttributeName": "scopeKey", "AttributeType": "S"},
                {"AttributeName": "entityKey", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        return ConsentRepository(name, db)

    @mock_aws
    def test_draft_and_superseded_cannot_be_granted(self):
        ctx = ConsentContext("u1", "t1", "p1", "https://issuer")
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            for state, name in ((NOTICE_DRAFT, "consents-draft"),
                                (NOTICE_SUPERSEDED, "consents-superseded")):
                entry = _entry(state=state, legal_approval_ref=LEGAL_REF)
                with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                                {VERSION: entry}):
                    repo = self._repo(name)
                    with self.assertRaises(ConsentContractError) as caught:
                        repo.grant(ctx, PURPOSE, VERSION)
                self.assertEqual("NOTICE_NOT_ACTIVE",
                                 caught.exception.code, state)
                self.assertEqual("NOT_GRANTED",
                                 repo.get(ctx, PURPOSE)["status"], state)

    @mock_aws
    def test_approved_and_active_can_be_granted_when_flags_are_true(self):
        ctx = ConsentContext("u1", "t1", "p1", "https://issuer")
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            for state, name in ((NOTICE_APPROVED, "consents-approved"),
                                (NOTICE_ACTIVE, "consents-active")):
                entry = _entry(state=state, legal_approval_ref=LEGAL_REF)
                with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                                {VERSION: entry}):
                    granted = self._repo(name).grant(ctx, PURPOSE, VERSION)
                self.assertEqual(STATUS_GRANTED, granted["status"], state)
                self.assertEqual(state, granted["noticeState"], state)
                self.assertTrue(granted["noticeApproved"], state)
                self.assertTrue(granted["acceptedForNewGrant"], state)

    @mock_aws
    def test_unknown_subject_still_cannot_use_active_notice(self):
        """An ACTIVE notice does not bypass user/tenant isolation."""
        ctx = ConsentContext("u1", "t1", "p1", "https://issuer")
        other = ConsentContext("u2", "t1", "p1", "https://issuer")
        with patch.dict(os.environ,
                        {"CONSENT_NOTICE_STATE_ENFORCED": "true"}):
            entry = _active_notice()
            with patch.dict(consent_contract.NOTICE_REGISTRY[PURPOSE],
                            {VERSION: entry}):
                repo = self._repo("consents-isolation")
                repo.grant(ctx, PURPOSE, VERSION)
        self.assertTrue(repo.has_consent(ctx, PURPOSE))
        self.assertFalse(repo.has_consent(other, PURPOSE))


if __name__ == "__main__":
    unittest.main()
